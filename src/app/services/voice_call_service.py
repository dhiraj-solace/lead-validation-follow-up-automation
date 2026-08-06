from datetime import datetime, timedelta
import base64
import json
from pathlib import PurePosixPath

from fastapi import HTTPException
from fastapi.responses import Response
import httpx
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from src.app.core.config import settings
from src.app.db.database import execute, fetch_all, fetch_one
from src.app.services.lead_service import LeadService


CALLABLE_STATUSES = {"Hot", "Warm"}
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

        call_id = execute(
            """
            INSERT INTO call_logs (lead_id, agent_id, script, call_mode, status)
            VALUES (?, ?, ?, ?, 'queued')
            """,
            (lead_id, lead.get("assigned_agent_id"), clean_script, normalized_mode),
        )

        missing = VoiceCallService.missing_credentials()
        if missing:
            if settings.DEMO_MODE:
                return VoiceCallService._complete_demo_call(call_id, lead, f"Missing Twilio credentials: {', '.join(missing)}")
            execute(
                "UPDATE call_logs SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (f"Twilio voice credentials are not configured: {', '.join(missing)}", call_id),
            )
            raise HTTPException(status_code=400, detail=f"Twilio voice credentials are not configured: {', '.join(missing)}")

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
    def missing_credentials() -> list[str]:
        required = {
            "TWILIO_ACCOUNT_SID": settings.TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": settings.TWILIO_AUTH_TOKEN,
            "TWILIO_PHONE_NUMBER": settings.TWILIO_PHONE_NUMBER,
        }
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
    def transcribe_recording(call_id: int) -> dict:
        call = VoiceCallService.get_call(call_id)
        if not call:
            raise HTTPException(status_code=404, detail="Call log not found.")
        recording_url = str(call.get("recording_url") or "").strip()
        if not recording_url:
            raise HTTPException(status_code=400, detail="Recording URL is not available yet.")

        if "recording-demo" in recording_url or str(call.get("call_sid") or "").startswith("DEMO-CALL"):
            transcript = "Demo transcript: the lead confirmed interest, shared a preferred location, and asked for property details on WhatsApp."
            analysis = VoiceCallService.fallback_transcript_analysis(transcript, call)
            VoiceCallService.save_transcript(call_id, transcript, analysis, "demo_transcript", 0)
            VoiceCallService.apply_transcript_analysis_to_lead(call, analysis)
            return VoiceCallService.get_call(call_id) or {}

        if not settings.OPENROUTER_API_KEY:
            VoiceCallService.mark_transcript_failed(call_id, "OPENROUTER_API_KEY is not configured.")
            raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY is not configured.")

        VoiceCallService.mark_transcript_processing(call_id)
        try:
            audio_bytes = VoiceCallService.download_recording(recording_url)
            audio_format = VoiceCallService.audio_format(recording_url)
            transcription = VoiceCallService.openrouter_transcribe(audio_bytes, audio_format)
            transcript = str(transcription.get("text") or "").strip()
            if not transcript:
                raise ValueError("OpenRouter returned an empty transcript.")
            usage = transcription.get("usage") or {}
            analysis = VoiceCallService.analyze_transcript(transcript, call)
            VoiceCallService.save_transcript(
                call_id=call_id,
                transcript=transcript,
                analysis=analysis,
                model=str(transcription.get("model") or settings.OPENROUTER_STT_MODEL),
                cost=float(usage.get("cost") or 0),
            )
            VoiceCallService.apply_transcript_analysis_to_lead(call, analysis)
        except HTTPException:
            raise
        except Exception as exc:
            VoiceCallService.mark_transcript_failed(call_id, str(exc))
            raise HTTPException(status_code=400, detail=f"Recording transcription failed: {exc}") from exc

        return VoiceCallService.get_call(call_id) or {}

    @staticmethod
    def download_recording(recording_url: str) -> bytes:
        auth = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
            response = client.get(recording_url, auth=auth)
            response.raise_for_status()
            return response.content

    @staticmethod
    def openrouter_transcribe(audio_bytes: bytes, audio_format: str) -> dict:
        payload = {
            "model": settings.OPENROUTER_STT_MODEL,
            "input_audio": {
                "data": base64.b64encode(audio_bytes).decode("ascii"),
                "format": audio_format,
            },
            "language": "en",
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-OpenRouter-Title": settings.OPENROUTER_APP_NAME,
        }
        with httpx.Client(timeout=90.0) as client:
            response = client.post(
                f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/audio/transcriptions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def analyze_transcript(transcript: str, call: dict) -> dict:
        lead = LeadService.get_lead(int(call.get("lead_id") or 0)) or {}
        prompt = {
            "task": "Analyze this real estate sales call transcript and return structured JSON only.",
            "lead_context": {
                "name": lead.get("name", ""),
                "property_type": lead.get("property_type", ""),
                "configuration": lead.get("configuration", ""),
                "location_preference": lead.get("location_preference", ""),
                "budget": lead.get("budget", ""),
                "timeline": lead.get("timeline", ""),
                "current_score": lead.get("score", 0),
                "current_score_band": lead.get("score_band", "Cold"),
            },
            "transcript": transcript,
            "json_schema": {
                "interest": "high | medium | low | not_interested | unknown",
                "budget": "budget mentioned by lead, or empty string",
                "location": "preferred location mentioned by lead, or empty string",
                "timeline": "purchase timeline mentioned by lead, or empty string",
                "objections": ["list of objections or concerns"],
                "visit_intent": "yes | maybe | no | unknown",
                "do_not_call": False,
                "score": "integer 0-100",
                "score_band": "Hot | Warm | Cold",
                "summary": "2-3 sentence concise call summary",
                "suggested_next_action": "one clear action for sales team",
            },
            "rules": [
                "Hot means strong interest, budget/timeline clarity, or visit intent.",
                "Warm means some interest but missing budget/timeline or needs nurture.",
                "Cold means no interest, wrong requirement, unreachable intent, or do-not-call.",
                "Set do_not_call true only if the lead explicitly asks not to be called again.",
                "Do not invent budget, location, or timeline if not present.",
            ],
        }
        payload = {
            "model": settings.OPENROUTER_MODEL,
            "temperature": 0.1,
            "max_tokens": 700,
            "messages": [
                {
                    "role": "system",
                    "content": "You extract structured CRM facts from real estate call transcripts. Return only valid JSON.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=True)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-OpenRouter-Title": settings.OPENROUTER_APP_NAME,
        }
        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(
                    f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            return VoiceCallService.normalize_transcript_analysis(VoiceCallService.parse_ai_json(content), transcript)
        except Exception:
            return VoiceCallService.fallback_transcript_analysis(transcript, call)

    @staticmethod
    def save_transcript(call_id: int, transcript: str, analysis: dict, model: str, cost: float) -> None:
        summary = str(analysis.get("summary") or VoiceCallService.summarize_transcript(transcript))
        next_action = str(analysis.get("suggested_next_action") or "")
        execute(
            """
            UPDATE call_logs
            SET transcript_text = ?,
                transcript_status = ?,
                transcript_summary = ?,
                transcript_analysis = ?,
                transcript_next_action = ?,
                transcript_error = ?,
                transcript_model = ?,
                transcript_cost = ?,
                transcribed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (transcript, "completed", summary, json.dumps(analysis), next_action, "", model, cost, call_id),
        )

    @staticmethod
    def apply_transcript_analysis_to_lead(call: dict, analysis: dict) -> None:
        lead_id = int(call.get("lead_id") or 0)
        if not lead_id:
            return
        score = VoiceCallService.safe_int(str(analysis.get("score") or 0))
        score = max(0, min(score, 100))
        score_band = VoiceCallService.normalize_score_band(analysis.get("score_band"), score)
        status = score_band
        do_not_call = 1 if analysis.get("do_not_call") else 0
        automation_status = "stopped" if do_not_call or score_band == "Cold" else "active"
        next_followup_at = None if automation_status != "active" else datetime.utcnow().isoformat(timespec="seconds")
        remarks = VoiceCallService.analysis_remarks(analysis)
        execute(
            """
            UPDATE leads
            SET score = ?,
                score_band = ?,
                validation_remarks = ?,
                status = ?,
                automation_status = ?,
                next_followup_at = ?,
                do_not_call = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (score, score_band, remarks, status, automation_status, next_followup_at, do_not_call, lead_id),
        )

    @staticmethod
    def normalize_transcript_analysis(value: dict, transcript: str) -> dict:
        score = VoiceCallService.safe_int(str(value.get("score") or 0))
        if score <= 0:
            score = VoiceCallService.fallback_score_from_text(transcript)
        score = max(0, min(score, 100))
        score_band = VoiceCallService.normalize_score_band(value.get("score_band"), score)
        objections = value.get("objections") if isinstance(value.get("objections"), list) else []
        return {
            "interest": VoiceCallService.pick(value.get("interest"), {"high", "medium", "low", "not_interested", "unknown"}, "unknown"),
            "budget": str(value.get("budget") or "")[:160],
            "location": str(value.get("location") or "")[:160],
            "timeline": str(value.get("timeline") or "")[:160],
            "objections": [str(item)[:180] for item in objections[:5]],
            "visit_intent": VoiceCallService.pick(value.get("visit_intent"), {"yes", "maybe", "no", "unknown"}, "unknown"),
            "do_not_call": bool(value.get("do_not_call")),
            "score": score,
            "score_band": score_band,
            "summary": str(value.get("summary") or VoiceCallService.summarize_transcript(transcript))[:900],
            "suggested_next_action": str(value.get("suggested_next_action") or VoiceCallService.default_next_action(score_band))[:300],
        }

    @staticmethod
    def fallback_transcript_analysis(transcript: str, call: dict) -> dict:
        score = VoiceCallService.fallback_score_from_text(transcript)
        score_band = VoiceCallService.normalize_score_band("", score)
        lower = transcript.lower()
        do_not_call = any(term in lower for term in ["do not call", "don't call", "dont call", "stop calling"])
        interest = "high" if score >= 80 else "medium" if score >= 50 else "not_interested" if do_not_call else "low"
        visit_intent = "yes" if any(term in lower for term in ["visit", "site visit", "schedule"]) else "unknown"
        return {
            "interest": interest,
            "budget": "",
            "location": "",
            "timeline": "",
            "objections": ["Do not call requested"] if do_not_call else [],
            "visit_intent": visit_intent,
            "do_not_call": do_not_call,
            "score": score,
            "score_band": score_band,
            "summary": VoiceCallService.summarize_transcript(transcript),
            "suggested_next_action": VoiceCallService.default_next_action(score_band),
        }

    @staticmethod
    def fallback_score_from_text(transcript: str) -> int:
        lower = transcript.lower()
        score = 45
        if any(term in lower for term in ["yes", "interested", "looking", "send", "share"]):
            score += 20
        if any(term in lower for term in ["visit", "schedule", "appointment"]):
            score += 20
        if any(term in lower for term in ["budget", "lakh", "crore", "price"]):
            score += 10
        if any(term in lower for term in ["today", "tomorrow", "this week", "immediate", "soon"]):
            score += 10
        if any(term in lower for term in ["not interested", "do not call", "don't call", "no longer"]):
            score -= 40
        return max(0, min(score, 100))

    @staticmethod
    def normalize_score_band(value: object, score: int) -> str:
        band = str(value or "").strip().title()
        if band in {"Hot", "Warm", "Cold"}:
            return band
        return "Hot" if score >= 80 else "Warm" if score >= 50 else "Cold"

    @staticmethod
    def analysis_remarks(analysis: dict) -> str:
        parts = [
            f"Call AI analysis: interest={analysis.get('interest', 'unknown')}",
            f"visit_intent={analysis.get('visit_intent', 'unknown')}",
        ]
        for label in ["budget", "location", "timeline"]:
            if analysis.get(label):
                parts.append(f"{label}={analysis[label]}")
        objections = analysis.get("objections") or []
        if objections:
            parts.append(f"objections={'; '.join(str(item) for item in objections)}")
        if analysis.get("suggested_next_action"):
            parts.append(f"next_action={analysis['suggested_next_action']}")
        return " | ".join(parts)[:900]

    @staticmethod
    def default_next_action(score_band: str) -> str:
        if score_band == "Hot":
            return "Call back today and schedule a site visit or share the strongest shortlist."
        if score_band == "Warm":
            return "Send a tailored shortlist and follow up within 24-48 hours."
        return "Pause aggressive outreach and add to low-priority nurture unless the lead re-engages."

    @staticmethod
    def pick(value: object, allowed: set[str], default: str) -> str:
        normalized = str(value or "").strip().lower()
        return normalized if normalized in allowed else default

    @staticmethod
    def parse_ai_json(content: str) -> dict:
        value = str(content or "").strip()
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
    def mark_transcript_processing(call_id: int) -> None:
        execute(
            """
            UPDATE call_logs
            SET transcript_status = ?,
                transcript_error = '',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            ("processing", call_id),
        )

    @staticmethod
    def mark_transcript_failed(call_id: int, error: str) -> None:
        execute(
            """
            UPDATE call_logs
            SET transcript_status = ?,
                transcript_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            ("failed", str(error)[:900], call_id),
        )

    @staticmethod
    def summarize_transcript(transcript: str) -> str:
        clean = " ".join(str(transcript or "").split())
        if not clean:
            return ""
        lower = clean.lower()
        signals = []
        if any(word in lower for word in ["yes", "interested", "looking", "visit", "schedule"]):
            signals.append("interest detected")
        if any(word in lower for word in ["budget", "lakh", "crore", "price"]):
            signals.append("budget discussed")
        if any(word in lower for word in ["today", "tomorrow", "week", "month", "immediate"]):
            signals.append("timeline discussed")
        if any(word in lower for word in ["not interested", "don't call", "do not call", "no longer"]):
            signals.append("possible low intent or do-not-call signal")
        prefix = f"AI call summary ({', '.join(signals)}): " if signals else "AI call summary: "
        return prefix + (clean[:700] + ("..." if len(clean) > 700 else ""))

    @staticmethod
    def audio_format(recording_url: str) -> str:
        suffix = PurePosixPath(recording_url.split("?", 1)[0]).suffix.lower().lstrip(".")
        return suffix if suffix in {"wav", "mp3", "flac", "m4a", "ogg", "webm", "aac"} else "mp3"

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
