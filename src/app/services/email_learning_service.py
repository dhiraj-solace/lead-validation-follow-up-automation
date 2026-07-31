import json
import re
from difflib import SequenceMatcher

from src.app.db.database import execute, fetch_all, fetch_one


SPAM_WORDS = {
    "act now",
    "limited time",
    "guaranteed",
    "free",
    "risk-free",
    "urgent",
    "winner",
    "click here",
    "lowest price",
    "100%",
}

CTA_WORDS = {
    "call",
    "reply",
    "shortlist",
    "visit",
    "schedule",
    "share",
    "discuss",
    "book",
    "connect",
    "available",
}

REAL_ESTATE_TERMS = {
    "property",
    "apartment",
    "villa",
    "plot",
    "flat",
    "home",
    "bhk",
    "location",
    "budget",
    "shortlist",
    "visit",
    "availability",
    "options",
}


class EmailLearningService:
    @staticmethod
    def run_guardrails(subject: str, body: str, lead: dict | None = None, tone: str = "") -> dict:
        text = f"{subject}\n{body}".strip()
        lowered = text.lower()
        issues: list[str] = []

        found_spam = sorted(word for word in SPAM_WORDS if word in lowered)
        if found_spam:
            issues.append(f"Spam-risk words found: {', '.join(found_spam)}.")

        if not any(word in lowered for word in CTA_WORDS):
            issues.append("Missing clear CTA.")

        if "{" in text or "}" in text:
            issues.append("Unresolved personalization placeholder found.")

        if lead:
            lead_name = str(lead.get("name") or "").strip().lower()
            if lead_name and lead_name.split()[0] not in lowered:
                issues.append("Lead name personalization is missing.")

            preferred_location = str(lead.get("location_preference") or "").strip().lower()
            if preferred_location and preferred_location not in lowered:
                issues.append("Lead location preference is missing.")

            lead_property = str(lead.get("property_type") or "").strip().lower()
            if lead_property and lead_property not in lowered:
                issues.append("Lead property type is missing.")

        sentences = [part.strip().lower() for part in re.split(r"[.!?\n]+", body) if part.strip()]
        for index, sentence in enumerate(sentences):
            for other in sentences[index + 1 :]:
                if len(sentence) > 24 and SequenceMatcher(None, sentence, other).ratio() > 0.88:
                    issues.append("Duplicate or repetitive content found.")
                    break
            if any("Duplicate or repetitive" in issue for issue in issues):
                break

        if tone and tone.lower() in {"aggressive", "pushy"}:
            issues.append("Tone is too pushy for real estate follow-up.")

        if not any(term in lowered for term in REAL_ESTATE_TERMS):
            issues.append("Content does not look relevant to real estate lead follow-up.")

        unsafe_terms = ["password", "otp", "bank account", "credit card", "payment link"]
        found_unsafe = sorted(term for term in unsafe_terms if term in lowered)
        if found_unsafe:
            issues.append(f"Unsafe or irrelevant sensitive terms found: {', '.join(found_unsafe)}.")

        return {"passed": not issues, "issues": issues}

    @staticmethod
    def judge_email(subject: str, body: str, lead: dict | None, guardrail: dict, campaign_type: str = "") -> dict:
        score = 100
        reasons: list[str] = []

        for issue in guardrail.get("issues", []):
            score -= 15
            reasons.append(issue)

        word_count = len(body.split())
        if word_count < 60:
            score -= 10
            reasons.append("Body is too short for a useful personalized follow-up.")
        elif word_count > 180:
            score -= 8
            reasons.append("Body is longer than the preferred 90-150 word range.")

        if len(subject.strip()) < 8:
            score -= 10
            reasons.append("Subject is too short.")
        if len(subject.strip()) > 180:
            score -= 5
            reasons.append("Subject is too long.")

        if lead:
            score_band = str(lead.get("score_band") or "").lower()
            if score_band == "hot" and not any(word in body.lower() for word in ["today", "visit", "call", "shortlist"]):
                score -= 8
                reasons.append("Hot lead email should have a stronger immediate next step.")
            if score_band == "cold" and any(word in body.lower() for word in ["urgent", "today only"]):
                score -= 8
                reasons.append("Cold lead email should avoid urgent language.")

        score = max(0, min(100, score))
        status = "ready" if score >= 80 and guardrail.get("passed") else "needs_review"
        if score < 60:
            status = "blocked"

        return {
            "score": score,
            "status": status,
            "reason": " ".join(reasons) if reasons else "Email is professional, relevant, personalized, and ready to review.",
            "campaign_type": campaign_type or (lead or {}).get("score_band", "General"),
        }

    @staticmethod
    def record_generation(
        lead: dict,
        template: dict | None,
        provider: str,
        subject: str,
        body: str,
        guardrail: dict,
        judge: dict,
        tone: str = "helpful",
        campaign_type: str = "",
        user_action: str = "generated",
        user_feedback: str = "",
        final_subject: str = "",
        final_body: str = "",
        selected_version: str = "generated",
        llm_provider: str = "",
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: float = 0,
        latency_ms: int = 0,
        error_message: str = "",
    ) -> int:
        review_status = user_action
        return execute(
            """
            INSERT INTO email_generation_history
            (
                lead_id, template_id, provider, campaign_type, tone, subject, body,
                final_subject, final_body, selected_version, user_action, user_feedback,
                guardrail_passed, guardrail_issues, judge_score, judge_status, judge_reason,
                is_active, review_status, llm_provider, model, prompt_tokens, completion_tokens,
                total_tokens, estimated_cost, latency_ms, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead["id"],
                (template or {}).get("id"),
                provider,
                campaign_type or lead.get("score_band", "General"),
                tone,
                subject,
                body,
                final_subject or subject,
                final_body or body,
                selected_version,
                user_action,
                user_feedback,
                1 if guardrail.get("passed") else 0,
                json.dumps(guardrail.get("issues", []), ensure_ascii=True),
                judge.get("score", 0),
                judge.get("status", "pending"),
                judge.get("reason", ""),
                1,
                review_status,
                llm_provider or provider,
                model,
                int(prompt_tokens or 0),
                int(completion_tokens or 0),
                int(total_tokens or 0),
                float(estimated_cost or 0),
                int(latency_ms or 0),
                error_message,
            ),
        )

    @staticmethod
    def record_feedback(
        lead: dict,
        action: str,
        subject: str,
        body: str,
        feedback: str = "",
        tone: str = "",
        campaign_type: str = "",
    ) -> dict:
        normalized_action = action.lower().strip()
        if normalized_action not in {"approved", "rejected", "modified", "sent"}:
            normalized_action = "modified"

        guardrail = EmailLearningService.run_guardrails(subject, body, lead, tone)
        judge = EmailLearningService.judge_email(subject, body, lead, guardrail, campaign_type)
        history_id = EmailLearningService.record_generation(
            lead=lead,
            template=None,
            provider="user_feedback",
            subject=subject,
            body=body,
            guardrail=guardrail,
            judge=judge,
            tone=tone or "user_selected",
            campaign_type=campaign_type or lead.get("score_band", "General"),
            user_action=normalized_action,
            user_feedback=feedback,
            final_subject=subject,
            final_body=body,
            selected_version="final" if normalized_action in {"approved", "sent"} else normalized_action,
        )
        return EmailLearningService.format_result(history_id, guardrail, judge)

    @staticmethod
    def approved_patterns_for_lead(lead: dict, limit: int = 3) -> list[dict]:
        rows = fetch_all(
            """
            SELECT campaign_type, tone, final_subject, final_body, judge_score, user_action, user_feedback
            FROM email_generation_history
            WHERE user_action IN ('approved', 'sent')
              AND COALESCE(is_active, 1) = 1
              AND final_body <> ''
            ORDER BY judge_score DESC, updated_at DESC, id DESC
            LIMIT 40
            """,
            (),
        )
        return EmailLearningService._rank_examples_for_lead(lead, rows, limit)

    @staticmethod
    def error_examples_for_lead(lead: dict, limit: int = 3) -> list[dict]:
        rows = fetch_all(
            """
            SELECT
                campaign_type, tone, subject, body, final_subject, final_body,
                judge_score, judge_status, judge_reason, guardrail_issues,
                user_action, user_feedback
            FROM email_generation_history
            WHERE (
                    guardrail_passed = 0
                    OR judge_status IN ('needs_review', 'blocked')
                    OR user_action = 'rejected'
                  )
              AND COALESCE(is_active, 1) = 1
              AND body <> ''
            ORDER BY updated_at DESC, id DESC
            LIMIT 40
            """,
            (),
        )
        return EmailLearningService._rank_examples_for_lead(lead, rows, limit)

    @staticmethod
    def _rank_examples_for_lead(lead: dict, rows: list[dict], limit: int) -> list[dict]:
        def normalized(value: object) -> str:
            return str(value or "").strip().lower()

        lead_terms = {
            "campaign": normalized(lead.get("score_band")),
            "property": normalized(lead.get("property_type")),
            "location": normalized(lead.get("location_preference")),
            "configuration": normalized(lead.get("configuration")),
            "budget": normalized(lead.get("budget")),
            "source": normalized(lead.get("source")),
        }

        ranked: list[tuple[int, dict]] = []
        for row in rows:
            haystack = " ".join(
                normalized(row.get(key))
                for key in [
                    "campaign_type",
                    "tone",
                    "subject",
                    "body",
                    "final_subject",
                    "final_body",
                    "user_feedback",
                    "judge_reason",
                ]
            )
            score = 0
            if normalized(row.get("campaign_type")) == lead_terms["campaign"]:
                score += 5
            for term_name in ["property", "location", "configuration", "budget", "source"]:
                term = lead_terms[term_name]
                if term and term in haystack:
                    score += 3
            score += int(row.get("judge_score") or 0) // 25
            ranked.append((score, row))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in ranked[:limit]]

    @staticmethod
    def history_for_lead(lead_id: int) -> list[dict]:
        return fetch_all(
            """
            SELECT *
            FROM email_generation_history
            WHERE lead_id = ?
            ORDER BY id DESC
            """,
            (lead_id,),
        )

    @staticmethod
    def latest_history_for_lead(lead_id: int) -> dict | None:
        return fetch_one(
            """
            SELECT *
            FROM email_generation_history
            WHERE lead_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (lead_id,),
        )

    @staticmethod
    def admin_history(status: str = "all", active: str = "true", campaign_type: str = "") -> list[dict]:
        filters: list[str] = []
        params: list[object] = []

        normalized_status = status.lower().strip()
        if normalized_status == "gold":
            filters.append("h.user_action IN ('approved', 'sent')")
        elif normalized_status == "error":
            filters.append(
                """
                (
                    h.user_action = 'rejected'
                    OR h.guardrail_passed = 0
                    OR h.judge_status IN ('needs_review', 'blocked')
                )
                """
            )
        elif normalized_status not in {"all", ""}:
            filters.append("h.user_action = ?")
            params.append(normalized_status)

        if active.lower().strip() in {"true", "1", "active"}:
            filters.append("COALESCE(h.is_active, 1) = 1")
        elif active.lower().strip() in {"false", "0", "inactive"}:
            filters.append("COALESCE(h.is_active, 1) = 0")

        if campaign_type:
            filters.append("LOWER(h.campaign_type) = LOWER(?)")
            params.append(campaign_type)

        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        return fetch_all(
            f"""
            SELECT
                h.*,
                l.name AS lead_name,
                l.email AS lead_email,
                l.score_band AS lead_score_band,
                l.property_type AS lead_property_type,
                l.location_preference AS lead_location_preference
            FROM email_generation_history h
            LEFT JOIN leads l ON l.id = h.lead_id
            {where}
            ORDER BY h.updated_at DESC, h.id DESC
            LIMIT 250
            """,
            params,
        )

    @staticmethod
    def admin_stats() -> dict:
        row = fetch_one(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN user_action IN ('approved', 'sent') AND COALESCE(is_active, 1) = 1 THEN 1 ELSE 0 END), 0) AS gold,
                COALESCE(SUM(CASE WHEN (user_action = 'rejected' OR guardrail_passed = 0 OR judge_status IN ('needs_review', 'blocked')) AND COALESCE(is_active, 1) = 1 THEN 1 ELSE 0 END), 0) AS error,
                COALESCE(SUM(CASE WHEN COALESCE(is_active, 1) = 0 THEN 1 ELSE 0 END), 0) AS inactive,
                COALESCE(ROUND(AVG(judge_score), 1), 0) AS avg_judge_score,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(ROUND(SUM(estimated_cost), 4), 0) AS estimated_cost,
                COALESCE(ROUND(AVG(NULLIF(latency_ms, 0)), 0), 0) AS avg_latency_ms
            FROM email_generation_history
            """,
            (),
        )
        attempts = fetch_one(
            """
            SELECT COALESCE(ROUND(AVG(attempt_count), 1), 0) AS avg_attempts
            FROM (
                SELECT lead_id, COUNT(*) AS attempt_count
                FROM email_generation_history
                WHERE provider LIKE 'openrouter_attempt_%'
                GROUP BY lead_id, strftime('%Y-%m-%d %H:%M', created_at)
            )
            """,
            (),
        )
        return {**(row or {}), "avg_attempts": (attempts or {}).get("avg_attempts", 0)}

    @staticmethod
    def update_admin_review(history_id: int, action: str, admin_note: str = "") -> dict | None:
        normalized = action.lower().strip()
        if normalized not in {"approved", "rejected", "modified", "generated", "sent"}:
            normalized = "modified"
        execute(
            """
            UPDATE email_generation_history
            SET user_action = ?,
                review_status = ?,
                selected_version = CASE WHEN ? IN ('approved', 'sent') THEN 'final' ELSE selected_version END,
                admin_note = ?,
                is_active = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (normalized, normalized, normalized, admin_note, history_id),
        )
        return EmailLearningService.get_history_record(history_id)

    @staticmethod
    def set_learning_active(history_id: int, is_active: bool, admin_note: str = "") -> dict | None:
        execute(
            """
            UPDATE email_generation_history
            SET is_active = ?,
                admin_note = COALESCE(NULLIF(?, ''), admin_note),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if is_active else 0, admin_note, history_id),
        )
        return EmailLearningService.get_history_record(history_id)

    @staticmethod
    def get_history_record(history_id: int) -> dict | None:
        return fetch_one(
            """
            SELECT
                h.*,
                l.name AS lead_name,
                l.email AS lead_email,
                l.score_band AS lead_score_band,
                l.property_type AS lead_property_type,
                l.location_preference AS lead_location_preference
            FROM email_generation_history h
            LEFT JOIN leads l ON l.id = h.lead_id
            WHERE h.id = ?
            """,
            (history_id,),
        )

    @staticmethod
    def format_result(history_id: int, guardrail: dict, judge: dict) -> dict:
        return {
            "history_id": history_id,
            "guardrail_passed": bool(guardrail.get("passed")),
            "guardrail_issues": guardrail.get("issues", []),
            "judge_score": judge.get("score", 0),
            "judge_status": judge.get("status", "pending"),
            "judge_reason": judge.get("reason", ""),
        }
