from datetime import datetime, timedelta

from fastapi import HTTPException
from fastapi.responses import Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from src.app.core.config import settings
from src.app.db.database import execute, fetch_all, fetch_one
from src.app.services.lead_service import LeadService


CALLABLE_STATUSES = {"Hot", "Warm"}
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
    def start_call(lead_id: int, script: str) -> dict:
        lead = LeadService.get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found.")
        eligibility = VoiceCallService.eligibility(lead)
        if not eligibility["eligible"]:
            raise HTTPException(status_code=400, detail=" ".join(eligibility["reasons"]))

        clean_script = VoiceCallService.clean_script(script)
        if not clean_script:
            raise HTTPException(status_code=400, detail="Call script is required.")

        call_id = execute(
            """
            INSERT INTO call_logs (lead_id, agent_id, script, status)
            VALUES (?, ?, ?, 'queued')
            """,
            (lead_id, lead.get("assigned_agent_id"), clean_script),
        )

        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_PHONE_NUMBER:
            if settings.DEMO_MODE:
                return VoiceCallService._complete_demo_call(call_id, lead)
            execute(
                "UPDATE call_logs SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                ("Twilio voice credentials are not configured.", call_id),
            )
            raise HTTPException(status_code=400, detail="Twilio voice credentials are not configured.")

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
        }

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
        response = VoiceResponse()
        response.say(call.get("script") or "Hello. A sales advisor is calling about your property enquiry.", voice="alice")
        return Response(content=str(response), media_type="application/xml")

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
