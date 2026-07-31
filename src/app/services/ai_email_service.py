from datetime import datetime
import json
import logging
from time import perf_counter

import httpx

from src.app.core.config import settings
from src.app.db.database import execute
from src.app.services.agent_service import AgentService
from src.app.services.email_learning_service import EmailLearningService
from src.app.services.email_sender_service import EmailSenderService
from src.app.services.lead_service import LeadService
from src.app.services.template_service import TemplateService


logger = logging.getLogger(__name__)

MAIL_WRITING_PROMPT = (
    "Write a concise real estate follow-up email using the lead requirement, score category, "
    "best historical template, and matching inventory context. Keep the tone helpful, specific, "
    "and action-oriented. Do not overpromise availability. Return only JSON with subject and body."
)

MAX_GUARDRAIL_RETRIES = 5

DEMO_PROPERTY_INVENTORY = [
    {
        "name": "Skyline Wakad Central",
        "property_type": "Apartment",
        "configuration": "2-BHK",
        "location": "Wakad",
        "budget_band": "78-88 lakh",
        "highlight": "ready possession options near Bhumkar Chowk",
    },
    {
        "name": "Baner Grove Villas",
        "property_type": "Villa",
        "configuration": "3-BHK",
        "location": "Baner",
        "budget_band": "1.45-1.75 crore",
        "highlight": "limited ready villas with private garden layouts",
    },
    {
        "name": "Hinjewadi Heights",
        "property_type": "Apartment",
        "configuration": "3-BHK",
        "location": "Hinjewadi",
        "budget_band": "98 lakh-1.2 crore",
        "highlight": "IT park connectivity with parking and clubhouse access",
    },
    {
        "name": "Kharadi Park Plots",
        "property_type": "Plot",
        "configuration": "Residential plot",
        "location": "Kharadi",
        "budget_band": "65-80 lakh",
        "highlight": "clear-title residential plots near upcoming infrastructure",
    },
]


class AIEmailService:
    @staticmethod
    def generate_draft(lead_id: int) -> dict:
        lead = LeadService.get_lead(lead_id)
        if not lead:
            return {"success": False, "message": "Lead not found."}

        agent = AgentService.get_agent(lead["assigned_agent_id"]) if lead.get("assigned_agent_id") else None
        template = TemplateService.select_template(lead)
        if not template:
            return {"success": False, "message": "No template available for this lead."}

        subject = TemplateService.render(template["subject"], lead, agent)
        base_body = TemplateService.render(template["body"], lead, agent)
        match = AIEmailService._find_inventory_match(lead)
        gold_examples = EmailLearningService.approved_patterns_for_lead(lead, limit=3)
        error_examples = EmailLearningService.error_examples_for_lead(lead, limit=3)
        retry_feedback: list[dict] = []
        attempts: list[dict] = []

        if settings.OPENROUTER_API_KEY:
            for attempt_number in range(1, MAX_GUARDRAIL_RETRIES + 1):
                ai_result = AIEmailService._generate_with_openrouter(
                    lead=lead,
                    agent=agent,
                    template=template,
                    rendered_subject=subject,
                    rendered_body=base_body,
                    inventory_match=match,
                    approved_patterns=gold_examples,
                    error_examples=error_examples,
                    retry_feedback=retry_feedback,
                )
                if not ai_result:
                    break

                candidate_subject = ai_result["subject"]
                candidate_body = ai_result["body"]
                guardrail = EmailLearningService.run_guardrails(candidate_subject, candidate_body, lead)
                judge = EmailLearningService.judge_email(
                    candidate_subject,
                    candidate_body,
                    lead,
                    guardrail,
                    lead.get("score_band", "General"),
                )
                ready = AIEmailService._is_ready_for_review(guardrail, judge)
                history_id = EmailLearningService.record_generation(
                    lead=lead,
                    template=template,
                    provider=f"openrouter_attempt_{attempt_number}",
                    subject=candidate_subject,
                    body=candidate_body,
                    guardrail=guardrail,
                    judge=judge,
                    tone="helpful",
                    campaign_type=lead.get("score_band", "General"),
                    user_action="generated" if ready else "guardrail_retry",
                    user_feedback="" if ready else f"Retry needed: {judge.get('reason', '')}",
                    selected_version="generated" if ready else "retry_failed",
                    llm_provider="openrouter",
                    model=str(ai_result.get("model") or settings.OPENROUTER_MODEL),
                    prompt_tokens=int(ai_result.get("prompt_tokens") or 0),
                    completion_tokens=int(ai_result.get("completion_tokens") or 0),
                    total_tokens=int(ai_result.get("total_tokens") or 0),
                    estimated_cost=float(ai_result.get("estimated_cost") or 0),
                    latency_ms=int(ai_result.get("latency_ms") or 0),
                )
                attempt = {
                    "attempt": attempt_number,
                    "history_id": history_id,
                    "subject": candidate_subject,
                    "body": candidate_body,
                    "guardrail": guardrail,
                    "judge": judge,
                    "ready": ready,
                }
                attempts.append(attempt)

                if ready:
                    break

                retry_feedback.append(
                    {
                        "attempt": attempt_number,
                        "failed_subject": candidate_subject,
                        "failed_body": candidate_body,
                        "guardrail_issues": guardrail.get("issues", []),
                        "judge_status": judge.get("status", ""),
                        "judge_score": judge.get("score", 0),
                        "judge_reason": judge.get("reason", ""),
                        "retry_instruction": "Do not repeat these issues in the next draft.",
                    }
                )

        if attempts:
            final_attempt = AIEmailService._select_best_attempt(attempts)
            subject = final_attempt["subject"]
            body = final_attempt["body"]
            guardrail = final_attempt["guardrail"]
            judge = final_attempt["judge"]
            history_id = final_attempt["history_id"]
            attempt_count = len(attempts)
            retry_reasons = AIEmailService._format_retry_reasons(retry_feedback)
            if final_attempt["ready"]:
                message = f"Email draft passed guardrails after {attempt_count} attempt(s)."
            else:
                message = (
                    f"Email draft needs review after {attempt_count} OpenRouter attempt(s). "
                    "It was saved as the best available draft, but should not be sent until fixed."
                )
        else:
            body = AIEmailService._rewrite_with_category_angle(base_body, lead, agent)
            message = "Email draft generated with local demo writer."
            guardrail = EmailLearningService.run_guardrails(subject, body, lead)
            judge = EmailLearningService.judge_email(subject, body, lead, guardrail, lead.get("score_band", "General"))
            history_id = EmailLearningService.record_generation(
                lead=lead,
                template=template,
                provider="local_demo_writer",
                subject=subject,
                body=body,
                guardrail=guardrail,
                judge=judge,
                tone="helpful",
                campaign_type=lead.get("score_band", "General"),
            )
            attempt_count = 1
            retry_reasons = []

        AIEmailService.save_draft(lead_id, subject, body, record_learning=False)

        return {
            "success": True,
            "message": message,
            "lead_id": lead_id,
            "subject": subject,
            "body": body,
            "attempt_count": attempt_count,
            "retry_reasons": retry_reasons,
            **EmailLearningService.format_result(history_id, guardrail, judge),
        }

    @staticmethod
    def save_draft(lead_id: int, subject: str, body: str, record_learning: bool = True) -> dict:
        execute(
            """
            UPDATE leads
            SET email_draft_subject = ?,
                email_draft_body = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (subject, body, lead_id),
        )
        lead = LeadService.get_lead(lead_id) if record_learning else None
        learning = {}
        if lead:
            guardrail = EmailLearningService.run_guardrails(subject, body, lead)
            judge = EmailLearningService.judge_email(subject, body, lead, guardrail, lead.get("score_band", "General"))
            history_id = EmailLearningService.record_generation(
                lead=lead,
                template=None,
                provider="manual_edit",
                subject=subject,
                body=body,
                guardrail=guardrail,
                judge=judge,
                tone="user_edited",
                campaign_type=lead.get("score_band", "General"),
                user_action="modified",
                final_subject=subject,
                final_body=body,
                selected_version="modified",
            )
            learning = EmailLearningService.format_result(history_id, guardrail, judge)
        return {"success": True, "message": "Email draft saved.", "subject": subject, "body": body, **learning}

    @staticmethod
    async def send_draft(lead_id: int, subject: str | None = None, body: str | None = None) -> dict:
        lead = LeadService.get_lead(lead_id)
        if not lead:
            return {"success": False, "message": "Lead not found."}
        if lead.get("validation_status") != "Valid":
            return {"success": False, "message": "Only valid leads can receive emails."}
        if not lead.get("email"):
            return {"success": False, "message": "Lead has no email address."}

        final_subject = subject or lead.get("email_draft_subject") or f"Property options for {lead.get('location_preference') or 'your requirement'}"
        final_body = body or lead.get("email_draft_body")
        if not final_body:
            generated = AIEmailService.generate_draft(lead_id)
            if not generated["success"]:
                return generated
            final_subject = generated["subject"]
            final_body = generated["body"]

        guardrail = EmailLearningService.run_guardrails(final_subject, final_body, lead)
        judge = EmailLearningService.judge_email(final_subject, final_body, lead, guardrail, lead.get("score_band", "General"))
        if not guardrail["passed"] or judge["status"] == "blocked":
            history_id = EmailLearningService.record_generation(
                lead=lead,
                template=None,
                provider="send_guardrail",
                subject=final_subject,
                body=final_body,
                guardrail=guardrail,
                judge=judge,
                tone="send_review",
                campaign_type=lead.get("score_band", "General"),
                user_action="rejected",
                user_feedback="Blocked by guardrails before sending.",
                final_subject=final_subject,
                final_body=final_body,
                selected_version="blocked",
            )
            return {
                "success": False,
                "message": f"Email needs review before sending: {judge['reason']}",
                "lead_id": lead_id,
                "subject": final_subject,
                "body": final_body,
                **EmailLearningService.format_result(history_id, guardrail, judge),
            }

        agent = AgentService.get_agent(lead["assigned_agent_id"]) if lead.get("assigned_agent_id") else None
        sender_config = AgentService.get_sender_config(agent)
        if agent and not sender_config:
            history_id = EmailLearningService.record_generation(
                lead=lead,
                template=None,
                provider="send_agent_sender_config",
                subject=final_subject,
                body=final_body,
                guardrail=guardrail,
                judge=judge,
                tone="send_review",
                campaign_type=lead.get("score_band", "General"),
                user_action="rejected",
                user_feedback="Assigned agent email account is not configured or inactive.",
                final_subject=final_subject,
                final_body=final_body,
                selected_version="blocked",
            )
            return {
                "success": False,
                "message": "Assigned agent email account is not configured or inactive.",
                "lead_id": lead_id,
                "subject": final_subject,
                "body": final_body,
                **EmailLearningService.format_result(history_id, guardrail, judge),
            }

        result = await EmailSenderService.send_email(lead["email"], final_subject, final_body, sender_config=sender_config)
        now = datetime.utcnow().isoformat(timespec="seconds")
        history_id = EmailLearningService.record_generation(
            lead=lead,
            template=None,
            provider="send_final",
            subject=final_subject,
            body=final_body,
            guardrail=guardrail,
            judge=judge,
            tone="approved_for_send",
            campaign_type=lead.get("score_band", "General"),
            user_action="sent" if result["success"] else "rejected",
            user_feedback="" if result["success"] else result["message"],
            final_subject=final_subject,
            final_body=final_body,
            selected_version="final",
        )

        execute(
            """
            INSERT INTO message_logs (lead_id, channel, direction, subject, body, status, error)
            VALUES (?, 'email', 'outbound', ?, ?, ?, ?)
            """,
            (
                lead_id,
                final_subject,
                final_body,
                "sent" if result["success"] else "failed",
                "" if result["success"] else result["message"],
            ),
        )

        execute(
            """
            UPDATE leads
            SET email_draft_subject = ?,
                email_draft_body = ?,
                email_sent_status = ?,
                email_sent_at = ?,
                last_contacted_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                final_subject,
                final_body,
                "sent" if result["success"] else "failed",
                now if result["success"] else None,
                now if result["success"] else lead.get("last_contacted_at"),
                lead_id,
            ),
        )

        return {
            "success": result["success"],
            "message": result["message"],
            "lead_id": lead_id,
            "subject": final_subject,
            "body": final_body,
            **EmailLearningService.format_result(history_id, guardrail, judge),
        }

    @staticmethod
    def _rewrite_with_category_angle(base_body: str, lead: dict, agent: dict | None) -> str:
        category = lead.get("score_band", "Cold")
        location = lead.get("location_preference") or "your preferred location"
        requirement = " ".join(
            value for value in [lead.get("configuration"), lead.get("property_type")] if value
        ) or "property"
        budget = lead.get("budget") or "your budget"
        timeline = lead.get("timeline") or "your timeline"
        agent_name = (agent or {}).get("name", "Sales Team")
        match = AIEmailService._find_inventory_match(lead)
        inventory_line = ""
        if match:
            inventory_line = (
                f"\n\nOne matching option to start with is {match['name']}: "
                f"{match['configuration']} {match['property_type']} in {match['location']} "
                f"around {match['budget_band']}, with {match['highlight']}."
            )

        if category == "Hot":
            angle = (
                f"\n\nSince your requirement is specific and timeline is {timeline}, "
                f"I can prioritize the best {requirement} matches in {location} and share availability today."
            )
        elif category == "Warm":
            angle = (
                f"\n\nI can also send a short comparison of {requirement} options in {location}, "
                f"including choices close to {budget}, so you can decide comfortably."
            )
        else:
            angle = (
                f"\n\nNo pressure at all. I can keep you updated when better {requirement} options "
                f"come up around {location}."
            )

        return f"{base_body.rstrip()}{inventory_line}{angle}\n\n{agent_name}"

    @staticmethod
    def _generate_with_openrouter(
        lead: dict,
        agent: dict | None,
        template: dict,
        rendered_subject: str,
        rendered_body: str,
        inventory_match: dict | None,
        approved_patterns: list[dict] | None = None,
        error_examples: list[dict] | None = None,
        retry_feedback: list[dict] | None = None,
    ) -> dict | None:
        if not settings.OPENROUTER_API_KEY:
            return None

        payload = {
            "model": settings.OPENROUTER_MODEL,
            "temperature": 0.55,
            "max_tokens": 700,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You write practical real estate sales emails. "
                        "Never claim exact availability unless provided. "
                        "Use a warm, concise, human tone. "
                        "Return only valid JSON with keys subject and body."
                    ),
                },
                {
                    "role": "user",
                    "content": AIEmailService._build_openrouter_prompt(
                        lead,
                        agent,
                        template,
                        rendered_subject,
                        rendered_body,
                        inventory_match,
                        approved_patterns or [],
                        error_examples or [],
                        retry_feedback or [],
                    ),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-OpenRouter-Title": settings.OPENROUTER_APP_NAME,
        }

        started_at = perf_counter()
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            parsed = AIEmailService._parse_ai_json(content)
            subject = str(parsed.get("subject") or rendered_subject).strip()
            body = str(parsed.get("body") or "").strip()
            if not body:
                return None
            latency_ms = int((perf_counter() - started_at) * 1000)
            return {
                "subject": subject[:180],
                "body": body,
                "model": data.get("model") or settings.OPENROUTER_MODEL,
                "prompt_tokens": usage.get("prompt_tokens") or 0,
                "completion_tokens": usage.get("completion_tokens") or 0,
                "total_tokens": usage.get("total_tokens") or usage.get("total") or 0,
                "estimated_cost": usage.get("cost") or usage.get("total_cost") or 0,
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            logger.warning("OpenRouter draft generation failed; using local fallback: %s", exc)
            return None

    @staticmethod
    def _build_openrouter_prompt(
        lead: dict,
        agent: dict | None,
        template: dict,
        rendered_subject: str,
        rendered_body: str,
        inventory_match: dict | None,
        approved_patterns: list[dict] | None = None,
        error_examples: list[dict] | None = None,
        retry_feedback: list[dict] | None = None,
    ) -> str:
        context = {
            "mail_writing_prompt": MAIL_WRITING_PROMPT,
            "lead": {
                "name": lead.get("name", ""),
                "email": lead.get("email", ""),
                "source": lead.get("source", ""),
                "property_type": lead.get("property_type", ""),
                "configuration": lead.get("configuration", ""),
                "location_preference": lead.get("location_preference", ""),
                "budget": lead.get("budget", ""),
                "timeline": lead.get("timeline", ""),
                "message": lead.get("message", ""),
                "score": lead.get("score", 0),
                "score_band": lead.get("score_band", "Cold"),
                "score_breakdown": lead.get("score_breakdown", ""),
            },
            "assigned_agent": {
                "name": (agent or {}).get("name", "Sales Team"),
                "email": (agent or {}).get("email", ""),
            },
            "selected_old_template": {
                "name": template.get("name", ""),
                "category": template.get("category", ""),
                "property_type": template.get("property_type", ""),
                "reply_rate": template.get("reply_rate", 0),
                "conversion_rate": template.get("conversion_rate", 0),
                "rendered_subject": rendered_subject,
                "rendered_body": rendered_body,
            },
            "matching_inventory": inventory_match or {},
            "successful_approved_email_patterns": [
                {
                    "campaign_type": item.get("campaign_type", ""),
                    "tone": item.get("tone", ""),
                    "subject": item.get("final_subject", ""),
                    "body": item.get("final_body", ""),
                    "judge_score": item.get("judge_score", 0),
                    "feedback": item.get("user_feedback", ""),
                }
                for item in (approved_patterns or [])
            ],
            "failed_error_examples_to_avoid": [
                {
                    "campaign_type": item.get("campaign_type", ""),
                    "tone": item.get("tone", ""),
                    "subject": item.get("final_subject") or item.get("subject", ""),
                    "body": item.get("final_body") or item.get("body", ""),
                    "guardrail_issues": AIEmailService._safe_json_list(item.get("guardrail_issues", "[]")),
                    "judge_score": item.get("judge_score", 0),
                    "judge_status": item.get("judge_status", ""),
                    "judge_reason": item.get("judge_reason", ""),
                    "feedback": item.get("user_feedback", ""),
                }
                for item in (error_examples or [])
            ],
            "current_retry_feedback": retry_feedback or [],
            "output_rules": [
                "Return only JSON.",
                "JSON shape must be {\"subject\": \"...\", \"body\": \"...\"}.",
                "Body should be 90-150 words.",
                "Include one clear next step: call, shortlist, or visit slot.",
                "Reuse the structure and CTA style of approved patterns when relevant, but do not copy names or exact property details from another lead.",
                "Avoid every issue listed in failed_error_examples_to_avoid and current_retry_feedback.",
                "When retry feedback includes a failed draft, change the wording and fix the exact listed guardrail and judge issues.",
                "Do not include markdown.",
            ],
        }
        return json.dumps(context, ensure_ascii=True, indent=2)

    @staticmethod
    def _is_ready_for_review(guardrail: dict, judge: dict) -> bool:
        return bool(guardrail.get("passed")) and judge.get("status") == "ready"

    @staticmethod
    def _select_best_attempt(attempts: list[dict]) -> dict:
        ready_attempts = [attempt for attempt in attempts if attempt["ready"]]
        if ready_attempts:
            return ready_attempts[-1]
        return max(
            attempts,
            key=lambda attempt: (
                int(attempt["judge"].get("score") or 0),
                1 if attempt["guardrail"].get("passed") else 0,
            ),
        )

    @staticmethod
    def _format_retry_reasons(retry_feedback: list[dict]) -> list[str]:
        reasons: list[str] = []
        for item in retry_feedback:
            reason = item.get("judge_reason") or "Guardrail retry needed."
            issues = "; ".join(item.get("guardrail_issues") or [])
            if issues and issues not in reason:
                reason = f"{reason} Issues: {issues}"
            reasons.append(f"Attempt {item.get('attempt')}: {reason}")
        return reasons

    @staticmethod
    def _safe_json_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        try:
            parsed = json.loads(str(value or "[]"))
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
        return []

    @staticmethod
    def _parse_ai_json(content: str) -> dict:
        value = content.strip()
        if value.startswith("```"):
            value = value.strip("`")
            if value.lower().startswith("json"):
                value = value[4:].strip()
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            start = value.find("{")
            end = value.rfind("}")
            if start >= 0 and end > start:
                return json.loads(value[start : end + 1])
            raise

    @staticmethod
    def _find_inventory_match(lead: dict) -> dict | None:
        property_type = str(lead.get("property_type", "")).lower()
        configuration = str(lead.get("configuration", "")).lower()
        location = str(lead.get("location_preference", "")).lower()

        for item in DEMO_PROPERTY_INVENTORY:
            item_property_type = item["property_type"].lower()
            item_configuration = item["configuration"].lower()
            item_location = item["location"].lower()
            property_match = not property_type or property_type in item_property_type or item_property_type in property_type
            config_match = not configuration or configuration in item_configuration or item_configuration in configuration
            location_match = not location or location in item_location or item_location in location
            if property_match and config_match and location_match:
                return item

        for item in DEMO_PROPERTY_INVENTORY:
            if location and (location in item["location"].lower() or item["location"].lower() in location):
                return item

        return None
