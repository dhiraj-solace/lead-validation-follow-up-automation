from datetime import datetime, timedelta
import base64
import json
import logging

from fastapi import HTTPException
from fastapi.responses import Response
import httpx
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from src.app.core.config import settings
from src.app.db.database import execute, fetch_all, fetch_one
from src.app.services.app_settings_service import AppSettingsService
from src.app.services.lead_service import LeadService


CALLABLE_STATUSES = {"Hot", "Warm"}
logger = logging.getLogger(__name__)
QUESTIONNAIRE_MODE = "questionnaire"
QUESTIONNAIRE_QUESTIONS = [
    {
        "key": "still_looking",
        "question": "Are you still looking for a property?",
    },
    {
        "key": "location",
        "question": "Which location are you mainly interested in?",
    },
    {
        "key": "budget",
        "question": "What budget range are you comfortable with?",
    },
    {
        "key": "timeline",
        "question": "How soon are you planning to buy?",
    },
    {
        "key": "site_visit",
        "question": "Would you like our advisor to schedule a site visit?",
    },
]
TWILIO_STATUS_MAP = {
    "queued": "queued",
    "initiated": "queued",
    "ringing": "ringing",
    "in-progress": "answered",
    "completed": "completed",
    "busy": "busy",
    "failed": "failed",
    "no-answer": "no-answer",
    "canceled": "failed",
}
TELNYX_STATUS_MAP = {
    "call.initiated": "queued",
    "call.answered": "answered",
    "call.bridged": "answered",
    "call.hangup": "completed",
    "call.recording.saved": "completed",
    "call.recording.error": "failed",
}


class VoiceCallService:
    @staticmethod
    def eligibility(lead: dict) -> dict:
        reasons: list[str] = []
        if lead.get("validation_status") != "Valid":
            reasons.append("Lead is not validated.")
        if lead.get("phone_status") != "valid":
            reasons.append("Phone validation status is not valid.")
        if lead.get("score_band") not in CALLABLE_STATUSES:
            reasons.append("Only Hot or Warm leads can be called.")
        if int(lead.get("score") or 0) < settings.CALL_MIN_SCORE:
            reasons.append(f"Lead score is below the minimum call score of {settings.CALL_MIN_SCORE}.")
        if not lead.get("call_consent"):
            reasons.append("Lead has not consented to receive calls.")
        if lead.get("do_not_call"):
            reasons.append("Lead is marked do-not-call.")
        if lead.get("status") == "Duplicate" or lead.get("validation_status") == "Duplicate":
            reasons.append("Duplicate leads cannot be called.")
        if not lead.get("assigned_agent_id"):
            reasons.append("A sales agent must be assigned before calling.")

        cooldown = VoiceCallService.cooldown_block(lead["id"])
        if cooldown:
            reasons.append(cooldown)

        return {
            "eligible": not reasons,
            "reasons": reasons,
            "minimum_score": settings.CALL_MIN_SCORE,
            "cooldown_hours": settings.CALL_COOLDOWN_HOURS,
        }

    @staticmethod
    def cooldown_block(lead_id: int) -> str:
        row = fetch_one(
            """
            SELECT called_at, status
            FROM call_logs
            WHERE lead_id = ?
              AND status IN ('queued', 'ringing', 'answered', 'completed')
            ORDER BY called_at DESC, id DESC
            LIMIT 1
            """,
            (lead_id,),
        )
        if not row or not row.get("called_at"):
            return ""
        try:
            called_at = datetime.fromisoformat(str(row["called_at"]))
        except ValueError:
            return ""
        available_at = called_at + timedelta(hours=settings.CALL_COOLDOWN_HOURS)
        if datetime.utcnow() < available_at:
            return f"Call cooldown is active until {available_at.isoformat(timespec='minutes')}."
        return ""

    @staticmethod
    def generate_script(lead_id: int) -> dict:
        lead = LeadService.get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found.")
        eligibility = VoiceCallService.eligibility(lead)
        if not eligibility["eligible"]:
            raise HTTPException(status_code=400, detail=" ".join(eligibility["reasons"]))

        agent_name = lead.get("assigned_agent_name") or "your property advisor"
        lead_name = VoiceCallService.display_name(lead.get("name"))
        requirement = " ".join(
            item for item in [lead.get("configuration"), lead.get("property_type")] if item
        ) or "property"
        location = lead.get("location_preference") or "your preferred location"
        budget = lead.get("budget") or "your budget"
        timeline = lead.get("timeline") or "your timeline"
        script = (
            f"Hello {lead_name}, this is {agent_name} calling about your enquiry for a {requirement} "
            f"in {location}. I noted your budget is around {budget} and your timeline is {timeline}. "
            "I have a few relevant options to discuss and can help shortlist the best matches. "
            "Would this be a good time for a quick conversation?"
        )
        return {
            "lead_id": lead_id,
            "script": script,
            "masked_phone": VoiceCallService.mask_phone(lead.get("phone", "")),
            "assigned_agent": agent_name,
            "eligibility": eligibility,
        }

    @staticmethod
    def start_call(lead_id: int, script: str, call_mode: str = "script") -> dict:
        lead = LeadService.get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found.")
        eligibility = VoiceCallService.eligibility(lead)
        if not eligibility["eligible"]:
            raise HTTPException(status_code=400, detail=" ".join(eligibility["reasons"]))

        normalized_mode = VoiceCallService.normalize_call_mode(call_mode)
        clean_script = VoiceCallService.clean_script(script)
        if normalized_mode == QUESTIONNAIRE_MODE and not clean_script:
            clean_script = VoiceCallService.questionnaire_intro(lead)
        if not clean_script:
            raise HTTPException(status_code=400, detail="Call script is required.")

        provider = AppSettingsService.call_provider()
        if normalized_mode == QUESTIONNAIRE_MODE and provider == "telnyx":
            raise HTTPException(
                status_code=400,
                detail="Voice questionnaire is ready for Twilio first. Please switch call provider to Twilio for this mode; Telnyx speech flow needs separate TeXML/transcription setup.",
            )

        call_id = execute(
            """
            INSERT INTO call_logs (lead_id, agent_id, script, call_mode, status)
            VALUES (?, ?, ?, ?, 'queued')
            """,
            (lead_id, lead.get("assigned_agent_id"), clean_script, normalized_mode),
        )

        missing = VoiceCallService.missing_credentials(provider)
        if missing:
            if settings.DEMO_MODE:
                return VoiceCallService._complete_demo_call(call_id, lead, f"Missing {provider} credentials: {', '.join(missing)}")
            execute(
                "UPDATE call_logs SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (f"{provider.title()} voice credentials are not configured: {', '.join(missing)}", call_id),
            )
            raise HTTPException(status_code=400, detail=f"{provider.title()} voice credentials are not configured: {', '.join(missing)}")

        if provider == "telnyx":
            return VoiceCallService._start_telnyx_call(call_id, lead, clean_script)

        base_url = settings.PUBLIC_BASE_URL.rstrip("/")
        twiml_url = f"{base_url}{settings.API_V1_STR}/leads/calls/{call_id}/twiml"
        status_url = f"{base_url}{settings.API_V1_STR}/leads/calls/{call_id}/status"
        recording_url = f"{base_url}{settings.API_V1_STR}/leads/calls/{call_id}/recording"

        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            call = client.calls.create(
                to=LeadService._normalize_phone(lead["phone"]),
                from_=settings.TWILIO_PHONE_NUMBER,
                url=twiml_url,
                record=True,
                recording_status_callback=recording_url,
                recording_status_callback_method="POST",
                status_callback=status_url,
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                status_callback_method="POST",
            )
        except Exception as exc:
            if settings.DEMO_MODE:
                return VoiceCallService._complete_demo_call(call_id, lead, str(exc))
            execute(
                "UPDATE call_logs SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(exc), call_id),
            )
            raise HTTPException(status_code=400, detail=f"Twilio call failed: {exc}") from exc

        execute(
            """
            UPDATE call_logs
            SET call_sid = ?,
                status = 'queued',
                recording_status = 'requested',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (call.sid, call_id),
        )
        return {
            "success": True,
            "message": "Call queued.",
            "call_id": call_id,
            "call_sid": call.sid,
            "status": "queued",
            "masked_phone": VoiceCallService.mask_phone(lead.get("phone", "")),
            "provider": "twilio",
        }

    @staticmethod
    def _start_telnyx_call(call_id: int, lead: dict, script: str) -> dict:
        base_url = settings.PUBLIC_BASE_URL.rstrip("/")
        webhook_url = f"{base_url}{settings.API_V1_STR}/leads/calls/{call_id}/telnyx-events"
        headers = {
            "Authorization": f"Bearer {settings.TELNYX_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "connection_id": settings.TELNYX_CONNECTION_ID,
            "to": LeadService._normalize_phone(lead["phone"]),
            "from": settings.TELNYX_PHONE_NUMBER,
            "webhook_url": webhook_url,
            "client_state": base64.b64encode(str(call_id).encode("utf-8")).decode("ascii"),
        }
        try:
            response = httpx.post(
                f"{settings.TELNYX_API_BASE_URL.rstrip('/')}/calls",
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            call_control_id = data.get("call_control_id") or data.get("id") or ""
        except Exception as exc:
            if settings.DEMO_MODE:
                return VoiceCallService._complete_demo_call(call_id, lead, str(exc))
            execute(
                "UPDATE call_logs SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(exc), call_id),
            )
            raise HTTPException(status_code=400, detail=f"Telnyx call failed: {exc}") from exc

        execute(
            """
            UPDATE call_logs
            SET call_sid = ?,
                status = 'queued',
                recording_status = 'requested',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (call_control_id, call_id),
        )
        return {
            "success": True,
            "message": "Telnyx call queued.",
            "call_id": call_id,
            "call_sid": call_control_id,
            "status": "queued",
            "masked_phone": VoiceCallService.mask_phone(lead.get("phone", "")),
            "provider": "telnyx",
        }

    @staticmethod
    def missing_credentials(provider: str | None = None) -> list[str]:
        selected = AppSettingsService.normalize_call_provider(provider or AppSettingsService.call_provider())
        required = {
            "twilio": {
                "TWILIO_ACCOUNT_SID": settings.TWILIO_ACCOUNT_SID,
                "TWILIO_AUTH_TOKEN": settings.TWILIO_AUTH_TOKEN,
                "TWILIO_PHONE_NUMBER": settings.TWILIO_PHONE_NUMBER,
            },
            "telnyx": {
                "TELNYX_API_KEY": settings.TELNYX_API_KEY,
                "TELNYX_PHONE_NUMBER": settings.TELNYX_PHONE_NUMBER,
                "TELNYX_CONNECTION_ID": settings.TELNYX_CONNECTION_ID,
            },
        }[selected]
        return [name for name, value in required.items() if not value]

    @staticmethod
    def _complete_demo_call(call_id: int, lead: dict, provider_error: str = "") -> dict:
        demo_sid = f"DEMO-CALL-{lead['id']}-{call_id}"
        demo_recording_sid = f"DEMO-REC-{lead['id']}-{call_id}"
        demo_recording_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{settings.API_V1_STR}/leads/calls/{call_id}/recording-demo"
        execute(
            """
            UPDATE call_logs
            SET call_sid = ?,
                status = 'queued',
                duration = 0,
                recording_sid = ?,
                recording_url = ?,
                recording_status = 'completed',
                recording_duration = 42,
                recording_available_at = CURRENT_TIMESTAMP,
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                demo_sid,
                demo_recording_sid,
                demo_recording_url,
                f"Demo mode: real Twilio call skipped. Provider error: {provider_error}" if provider_error else "Demo mode: real Twilio call skipped.",
                call_id,
            ),
        )
        return {
            "success": True,
            "message": "Demo mode: call queued and logged without contacting Twilio.",
            "call_id": call_id,
            "call_sid": demo_sid,
            "status": "queued",
            "recording_sid": demo_recording_sid,
            "recording_url": demo_recording_url,
            "recording_status": "completed",
            "masked_phone": VoiceCallService.mask_phone(lead.get("phone", "")),
            "demo": True,
        }

    @staticmethod
    def twiml_response(call_id: int) -> Response:
        call = VoiceCallService.get_call(call_id)
        if not call:
            raise HTTPException(status_code=404, detail="Call log not found.")
        if call.get("call_mode") == QUESTIONNAIRE_MODE:
            return VoiceCallService.questionnaire_twiml(call_id, call)
        response = VoiceResponse()
        response.say(call.get("script") or "Hello. A sales advisor is calling about your property enquiry.", voice="alice")
        return Response(content=str(response), media_type="application/xml")

    @staticmethod
    def questionnaire_twiml(call_id: int, call: dict) -> Response:
        step = VoiceCallService.safe_int(str(call.get("questionnaire_step") or 0))
        lead = LeadService.get_lead(int(call.get("lead_id") or 0)) or {}
        response = VoiceResponse()
        if step == 0:
            response.say(call.get("script") or VoiceCallService.questionnaire_intro(lead), voice="alice")
        VoiceCallService.append_question_gather(response, call_id, step)
        return Response(content=str(response), media_type="application/xml")

    @staticmethod
    def questionnaire_answer_response(call_id: int, speech_result: str = "", confidence: str = "") -> Response:
        call = VoiceCallService.get_call(call_id)
        if not call:
            raise HTTPException(status_code=404, detail="Call log not found.")
        if call.get("call_mode") != QUESTIONNAIRE_MODE:
            raise HTTPException(status_code=400, detail="This call is not a voice questionnaire.")

        step = VoiceCallService.safe_int(str(call.get("questionnaire_step") or 0))
        answers = VoiceCallService.parse_answers(call.get("questionnaire_answers"))
        answer = VoiceCallService.clean_answer(speech_result)
        if answer and step < len(QUESTIONNAIRE_QUESTIONS):
            question = QUESTIONNAIRE_QUESTIONS[step]
            answers.append(
                {
                    "key": question["key"],
                    "question": question["question"],
                    "answer": answer,
                    "confidence": confidence,
                    "answered_at": datetime.utcnow().isoformat(timespec="seconds"),
                }
            )
            step += 1
            VoiceCallService.save_questionnaire_state(call_id, step, answers)

        response = VoiceResponse()
        if not answer:
            response.say("Sorry, I could not hear that clearly. Let me ask once more.", voice="alice")
            VoiceCallService.append_question_gather(response, call_id, step)
            return Response(content=str(response), media_type="application/xml")

        if step >= len(QUESTIONNAIRE_QUESTIONS):
            VoiceCallService.finish_questionnaire(call, answers)
            response.say(
                "Thank you. I have saved your answers. Our property advisor will review this and follow up with the best next step.",
                voice="alice",
            )
            response.hangup()
            return Response(content=str(response), media_type="application/xml")

        response.say("Thank you.", voice="alice")
        VoiceCallService.append_question_gather(response, call_id, step)
        return Response(content=str(response), media_type="application/xml")

    @staticmethod
    def append_question_gather(response: VoiceResponse, call_id: int, step: int) -> None:
        base_url = settings.PUBLIC_BASE_URL.rstrip("/")
        question = QUESTIONNAIRE_QUESTIONS[min(step, len(QUESTIONNAIRE_QUESTIONS) - 1)]["question"]
        gather = response.gather(
            input="speech",
            action=f"{base_url}{settings.API_V1_STR}/leads/calls/{call_id}/question",
            method="POST",
            language="en-IN",
            timeout=6,
            speech_timeout="auto",
        )
        gather.say(question, voice="alice")
        response.say("I did not receive an answer. Goodbye.", voice="alice")
        response.hangup()

    @staticmethod
    def save_questionnaire_state(call_id: int, step: int, answers: list[dict]) -> None:
        execute(
            """
            UPDATE call_logs
            SET questionnaire_step = ?,
                questionnaire_answers = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (step, json.dumps(answers), call_id),
        )

    @staticmethod
    def finish_questionnaire(call: dict, answers: list[dict]) -> None:
        lead_id = int(call.get("lead_id") or 0)
        lead = LeadService.get_lead(lead_id)
        if not lead:
            return
        score = max(int(lead.get("score") or 0), VoiceCallService.questionnaire_score(answers))
        score_band = "Hot" if score >= 80 else "Warm" if score >= 50 else "Cold"
        summary = VoiceCallService.questionnaire_summary(answers)
        execute(
            """
            UPDATE leads
            SET score = ?,
                score_band = ?,
                validation_remarks = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (score, score_band, summary, score_band, lead_id),
        )

    @staticmethod
    def questionnaire_score(answers: list[dict]) -> int:
        joined = " ".join(str(item.get("answer") or "").lower() for item in answers)
        score = 55
        if any(word in joined for word in ["yes", "still", "looking", "interested", "visit", "schedule"]):
            score += 20
        if any(word in joined for word in ["immediate", "soon", "this week", "today", "tomorrow", "month"]):
            score += 15
        if any(word in joined for word in ["no", "not looking", "cancel", "later"]):
            score -= 25
        return max(0, min(score, 100))

    @staticmethod
    def questionnaire_summary(answers: list[dict]) -> str:
        if not answers:
            return "Voice questionnaire completed without captured answers."
        parts = [f"{item.get('question')}: {item.get('answer')}" for item in answers]
        return "Voice questionnaire: " + " | ".join(parts)[:900]

    @staticmethod
    def update_status(call_id: int, call_status: str, duration: str = "", call_sid: str = "") -> dict:
        normalized = TWILIO_STATUS_MAP.get(str(call_status or "").lower(), str(call_status or "queued").lower())
        execute(
            """
            UPDATE call_logs
            SET status = ?,
                duration = ?,
                call_sid = COALESCE(NULLIF(?, ''), call_sid),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (normalized, int(duration or 0), call_sid, call_id),
        )
        return VoiceCallService.get_call(call_id) or {}

    @staticmethod
    def update_recording(
        call_id: int,
        recording_sid: str = "",
        recording_url: str = "",
        recording_status: str = "",
        recording_duration: str = "",
        call_sid: str = "",
    ) -> dict:
        status = str(recording_status or "processing").lower()
        duration = VoiceCallService.safe_int(recording_duration)
        available_at_sql = "CURRENT_TIMESTAMP" if status == "completed" and recording_url else "recording_available_at"
        execute(
            f"""
            UPDATE call_logs
            SET recording_sid = COALESCE(NULLIF(?, ''), recording_sid),
                recording_url = COALESCE(NULLIF(?, ''), recording_url),
                recording_status = ?,
                recording_duration = ?,
                call_sid = COALESCE(NULLIF(?, ''), call_sid),
                recording_available_at = {available_at_sql},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (recording_sid, VoiceCallService.normalize_recording_url(recording_url), status, duration, call_sid, call_id),
        )
        return VoiceCallService.get_call(call_id) or {}

    @staticmethod
    def process_telnyx_event(call_id: int, payload: dict) -> dict:
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        event_type = str(data.get("event_type") or "")
        event_payload = data.get("payload") or {}
        call_control_id = event_payload.get("call_control_id") or event_payload.get("call_leg_id") or ""
        normalized = TELNYX_STATUS_MAP.get(event_type, "")

        if normalized:
            execute(
                """
                UPDATE call_logs
                SET status = ?,
                    call_sid = COALESCE(NULLIF(?, ''), call_sid),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (normalized, call_control_id, call_id),
            )

        if event_type == "call.answered" and call_control_id:
            call = VoiceCallService.get_call(call_id) or {}
            VoiceCallService._telnyx_command(call_control_id, "actions/speak", {
                "payload": call.get("script") or "Hello. A sales advisor is calling about your property enquiry.",
                "voice": "female",
                "language_code": "en-US",
            })
            VoiceCallService._telnyx_command(call_control_id, "actions/record_start", {
                "format": "mp3",
                "channels": "single",
            })

        if event_type == "call.recording.saved":
            recording = event_payload.get("recording_urls") or {}
            recording_url = event_payload.get("recording_url") or recording.get("mp3") or recording.get("wav") or ""
            VoiceCallService.update_recording(
                call_id=call_id,
                recording_sid=event_payload.get("recording_id", ""),
                recording_url=recording_url,
                recording_status="completed",
                recording_duration=str(event_payload.get("duration_millis") or event_payload.get("duration_secs") or 0),
                call_sid=call_control_id,
            )

        return VoiceCallService.get_call(call_id) or {"success": True}

    @staticmethod
    def _telnyx_command(call_control_id: str, action: str, payload: dict) -> None:
        try:
            httpx.post(
                f"{settings.TELNYX_API_BASE_URL.rstrip('/')}/calls/{call_control_id}/{action}",
                headers={
                    "Authorization": f"Bearer {settings.TELNYX_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
                timeout=20.0,
            ).raise_for_status()
        except Exception as exc:
            logger.error("Telnyx command failed for call_control_id=%s action=%s: %s", call_control_id, action, exc)

    @staticmethod
    def normalize_recording_url(value: str) -> str:
        url = str(value or "").strip()
        if not url:
            return ""
        if not url.endswith(".mp3"):
            return f"{url}.mp3"
        return url

    @staticmethod
    def get_call(call_id: int) -> dict | None:
        return fetch_one("SELECT * FROM call_logs WHERE id = ?", (call_id,))

    @staticmethod
    def history_for_lead(lead_id: int) -> list[dict]:
        return fetch_all(
            """
            SELECT c.*, a.name AS agent_name
            FROM call_logs c
            LEFT JOIN agents a ON a.id = c.agent_id
            WHERE c.lead_id = ?
            ORDER BY c.called_at DESC, c.id DESC
            """,
            (lead_id,),
        )

    @staticmethod
    def display_name(value: object) -> str:
        clean = str(value or "there").replace("_", " ").replace("-", " ").strip()
        return " ".join(word.capitalize() for word in clean.split()) or "there"

    @staticmethod
    def normalize_call_mode(value: object) -> str:
        mode = str(value or "script").strip().lower()
        return QUESTIONNAIRE_MODE if mode in {"questionnaire", "questions", "voice_questions"} else "script"

    @staticmethod
    def questionnaire_intro(lead: dict) -> str:
        lead_name = VoiceCallService.display_name(lead.get("name"))
        agent_name = lead.get("assigned_agent_name") or "your property advisor"
        requirement = " ".join(
            item for item in [lead.get("configuration"), lead.get("property_type")] if item
        ) or "property"
        location = lead.get("location_preference") or "your preferred location"
        return (
            f"Hello {lead_name}, this is an automated assistant for {agent_name}. "
            f"I am calling about your enquiry for a {requirement} in {location}. "
            "I will ask a few short questions so our advisor can help you faster."
        )

    @staticmethod
    def parse_answers(value: object) -> list[dict]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        try:
            parsed = json.loads(str(value or "[]"))
        except (TypeError, ValueError):
            return []
        return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []

    @staticmethod
    def clean_answer(value: object) -> str:
        return " ".join(str(value or "").split())[:300]

    @staticmethod
    def mask_phone(value: str) -> str:
        digits = "".join(filter(str.isdigit, value))
        if len(digits) <= 4:
            return "****"
        return f"{'*' * max(len(digits) - 4, 4)}{digits[-4:]}"

    @staticmethod
    def clean_script(value: str) -> str:
        clean = " ".join(str(value or "").split())
        return clean[:1200]

    @staticmethod
    def safe_int(value: str) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
