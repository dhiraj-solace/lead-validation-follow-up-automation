import csv
import io
import logging
import os
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from src.app.core.config import settings
from src.app.db.database import execute
from src.app.models.schemas import (
    AgentCreateRequest,
    AppSettingsRequest,
    AutomationRunResponse,
    BatchEmailValidationResponse,
    BatchPhoneValidationResponse,
    CallPreferencesRequest,
    EmailGenerateRequest,
    CallScriptRequest,
    EmailDraftRequest,
    EmailDraftResponse,
    EmailFeedbackRequest,
    EmailValidationResult,
    LearningActiveRequest,
    LearningReviewRequest,
    MarkRepliedRequest,
    PhoneValidationResult,
    SendEmailResponse,
    SendTestEmailRequest,
    TemplateCreateRequest,
    UploadLeadsResponse,
)
from src.app.services.agent_service import AgentService
from src.app.services.app_settings_service import AppSettingsService
from src.app.services.ai_email_service import AIEmailService
from src.app.services.demo_data_service import DemoDataService
from src.app.services.email_sender_service import EmailSenderService
from src.app.services.email_learning_service import EmailLearningService
from src.app.services.email_service import EmailService
from src.app.services.file_parser_service import FileParserService
from src.app.services.followup_service import FollowupService
from src.app.services.lead_enrichment_service import LeadEnrichmentService
from src.app.services.lead_service import LeadService
from src.app.services.phone_service import TwilioLookupClient
from src.app.services.scoring_service import LeadScoringService
from src.app.services.template_service import TemplateService
from src.app.services.voice_call_service import VoiceCallService
from src.app.services.whatsapp_sender_service import WhatsAppSenderService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/dashboard")
async def dashboard():
    return LeadService.dashboard()


@router.get("/settings")
async def app_settings():
    return AppSettingsService.get_settings()


@router.patch("/settings")
async def update_app_settings(payload: AppSettingsRequest):
    return AppSettingsService.update_settings(auto_email_send_enabled=payload.auto_email_send_enabled)


@router.post("/upload-leads", response_model=UploadLeadsResponse)
async def upload_leads(
    file: UploadFile = File(...),
    validate_contacts: bool = Query(default=True),
):
    logger.info(
        "upload_leads.start filename=%s validate_contacts=%s",
        file.filename,
        validate_contacts,
    )
    rows = await FileParserService.parse_lead_upload(file)
    logger.info("upload_leads.parsed filename=%s rows=%s", file.filename, len(rows))
    leads = []
    created = 0
    merged = 0

    for row in rows:
        lead, was_duplicate = await LeadService.create_or_update_from_upload(row, validate_contacts=validate_contacts)
        leads.append(lead)
        if was_duplicate:
            merged += 1
        else:
            created += 1

    auto_drafted = 0
    auto_sent = 0
    auto_email_send_enabled = AppSettingsService.auto_email_send_enabled()
    refreshed_leads = []
    for lead in leads:
        if _should_auto_generate_draft(lead):
            try:
                draft_result = AIEmailService.generate_draft(lead["id"])
                if draft_result.get("success"):
                    auto_drafted += 1
                    lead = LeadService.get_lead(lead["id"]) or lead
                    if auto_email_send_enabled and _should_auto_send_email(lead):
                        send_result = await AIEmailService.send_draft(
                            lead["id"],
                            lead.get("email_draft_subject"),
                            lead.get("email_draft_body"),
                        )
                        if send_result.get("success"):
                            auto_sent += 1
                            lead = LeadService.get_lead(lead["id"]) or lead
            except Exception:
                logger.exception("upload_leads.auto_email_failed lead_id=%s", lead.get("id"))
        refreshed_leads.append(lead)

    response = UploadLeadsResponse(
        total_rows=len(rows),
        created=created,
        merged_duplicates=merged,
        auto_drafted=auto_drafted,
        auto_sent=auto_sent,
        valid=sum(1 for lead in refreshed_leads if lead.get("validation_status") == "Valid"),
        invalid=sum(1 for lead in refreshed_leads if lead.get("validation_status") == "Invalid"),
        duplicate=sum(1 for lead in refreshed_leads if lead.get("validation_status") == "Duplicate"),
        hot=sum(1 for lead in refreshed_leads if lead.get("score_band") == "Hot"),
        warm=sum(1 for lead in refreshed_leads if lead.get("score_band") == "Warm"),
        cold=sum(1 for lead in refreshed_leads if lead.get("score_band") == "Cold"),
        leads=refreshed_leads,
    )
    logger.info(
        "upload_leads.complete filename=%s total_rows=%s created=%s merged=%s auto_drafted=%s auto_sent=%s",
        file.filename,
        response.total_rows,
        response.created,
        response.merged_duplicates,
        response.auto_drafted,
        response.auto_sent,
    )
    return response


@router.get("")
async def list_leads(
    status: str | None = None,
    score_band: str | None = None,
):
    return LeadService.list_leads(status=status, score_band=score_band)


@router.get("/high-priority")
async def high_priority_leads():
    return LeadService.list_high_priority()


@router.get("/followups/queue")
async def followup_queue():
    return FollowupService.list_queue()


@router.post("/followups/process-due")
async def process_due_followups():
    return await FollowupService.process_due()


@router.get("/agents/list")
async def list_agents():
    return AgentService.list_agents()


@router.post("/agents")
async def create_agent(payload: AgentCreateRequest):
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return AgentService.create_agent(data)


@router.get("/templates/list")
async def list_templates():
    return TemplateService.list_templates()


@router.post("/templates")
async def create_template(payload: TemplateCreateRequest):
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return TemplateService.create_template(data)


@router.post("/demo/load")
async def load_demo_data(validate_contacts: bool = Query(default=True)):
    return await DemoDataService.load_demo_leads(validate_contacts=validate_contacts)


@router.post("/{lead_id:int}/duplicates/replace")
async def replace_duplicate(lead_id: int, validate_contacts: bool = Query(default=True)):
    result = await LeadService.replace_duplicate(lead_id, validate_contacts=validate_contacts)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/{lead_id:int}/duplicates/skip")
async def skip_duplicate(lead_id: int):
    result = LeadService.skip_duplicate(lead_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.delete("/{lead_id:int}")
async def delete_lead(lead_id: int):
    result = LeadService.delete_lead(lead_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{lead_id:int}/enrich")
async def enrich_lead(lead_id: int):
    return LeadEnrichmentService.enrich_lead(lead_id)


@router.post("/{lead_id:int}/generate-email", response_model=EmailDraftResponse)
async def generate_email(lead_id: int, payload: EmailGenerateRequest | None = None):
    result = AIEmailService.generate_draft(
        lead_id,
        reviewer_feedback=(payload.feedback if payload else "") or "",
        rejected_subject=(payload.subject if payload else "") or "",
        rejected_body=(payload.body if payload else "") or "",
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/{lead_id:int}/email-draft", response_model=EmailDraftResponse)
async def save_email_draft(lead_id: int, payload: EmailDraftRequest):
    lead = LeadService.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    result = AIEmailService.save_draft(lead_id, payload.subject, payload.body)
    return {
        "success": result["success"],
        "message": result["message"],
        "lead_id": lead_id,
        "subject": result["subject"],
        "body": result["body"],
    }


@router.post("/{lead_id:int}/send-email-draft", response_model=EmailDraftResponse)
async def send_email_draft(lead_id: int, payload: EmailDraftRequest):
    result = await AIEmailService.send_draft(lead_id, payload.subject, payload.body)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/{lead_id:int}/run-automation", response_model=AutomationRunResponse)
async def run_lead_automation(lead_id: int):
    lead = LeadService.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    if lead.get("validation_status") != "Valid":
        raise HTTPException(status_code=400, detail="Only valid leads can run automation.")

    steps: list[dict] = []
    started_call_id: int | None = None

    subject = str(lead.get("email_draft_subject") or "").strip()
    body = str(lead.get("email_draft_body") or "").strip()
    if lead.get("email_sent_status") == "sent":
        steps.append({"action": "email", "status": "skipped", "message": "Initial email already sent."})
    else:
        if not subject or not body:
            draft = AIEmailService.generate_draft(lead_id)
            if draft.get("success"):
                subject = str(draft.get("subject") or "")
                body = str(draft.get("body") or "")
                steps.append({"action": "email_draft", "status": "completed", "message": "Email draft generated."})
            else:
                steps.append({"action": "email_draft", "status": "failed", "message": draft.get("message", "Email draft generation failed.")})

        if subject and body:
            try:
                sent = await AIEmailService.send_draft(lead_id, subject, body)
                steps.append({
                    "action": "email",
                    "status": "completed" if sent.get("success") else "failed",
                    "message": sent.get("message", "Email send completed."),
                })
            except Exception as exc:
                steps.append({"action": "email", "status": "failed", "message": str(exc)})
        else:
            steps.append({"action": "email", "status": "skipped", "message": "No email draft available to send."})

    lead = LeadService.get_lead(lead_id) or lead
    eligibility = VoiceCallService.eligibility(lead)
    if not eligibility["eligible"]:
        steps.append({"action": "call", "status": "skipped", "message": " ".join(eligibility["reasons"])})
    else:
        try:
            call_result = VoiceCallService.start_call(
                lead_id,
                VoiceCallService.questionnaire_intro(lead),
                "questionnaire",
            )
            started_call_id = int(call_result.get("call_id") or 0) or None
            steps.append({
                "action": "call",
                "status": "completed",
                "message": call_result.get("message", "Call queued."),
                "call_id": started_call_id,
            })
        except Exception as exc:
            steps.append({"action": "call", "status": "failed", "message": str(exc)})

    transcribe_target = _automation_transcribe_target(lead_id, started_call_id)
    if not transcribe_target:
        steps.append({
            "action": "transcribe",
            "status": "waiting",
            "message": "Recording is not available yet. It will be available after the call ends and Twilio sends the recording callback.",
            "call_id": started_call_id,
        })
    else:
        try:
            call = VoiceCallService.transcribe_recording(int(transcribe_target["id"]))
            steps.append({
                "action": "transcribe",
                "status": "completed",
                "message": "Recording transcribed and analyzed.",
                "call_id": int(call.get("id") or transcribe_target["id"]),
            })
        except Exception as exc:
            steps.append({
                "action": "transcribe",
                "status": "failed",
                "message": str(exc),
                "call_id": int(transcribe_target["id"]),
            })

    failed = [step for step in steps if step["status"] == "failed"]
    waiting = [step for step in steps if step["status"] == "waiting"]
    if failed:
        message = "Automation finished with some failed steps."
    elif waiting:
        message = "Automation started. Transcription is waiting for the call recording."
    else:
        message = "Automation completed."
    return {"success": not failed, "message": message, "lead_id": lead_id, "steps": steps}


@router.post("/{lead_id:int}/send-whatsapp")
async def send_whatsapp_message(lead_id: int):
    lead = LeadService.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    if not lead.get("phone"):
        raise HTTPException(status_code=400, detail="Lead has no phone number.")

    subject = lead.get("email_draft_subject") or "Property follow-up"
    body = lead.get("email_draft_body") or ""
    if not body:
        draft = AIEmailService.generate_draft(lead_id)
        if not draft.get("success"):
            raise HTTPException(status_code=400, detail=draft.get("message", "Could not generate message."))
        subject = draft.get("subject") or subject
        body = draft.get("body") or ""

    result = await WhatsAppSenderService.send_text(lead["phone"], _format_whatsapp_body(body))
    execute(
        """
        INSERT INTO message_logs (lead_id, channel, direction, subject, body, status, error)
        VALUES (?, 'whatsapp', 'outbound', ?, ?, ?, ?)
        """,
        (
            lead_id,
            subject,
            body,
            "sent" if result["success"] else "failed",
            "" if result["success"] else result["message"],
        ),
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/{lead_id:int}/call-script")
async def generate_call_script(lead_id: int):
    return VoiceCallService.generate_script(lead_id)


@router.patch("/{lead_id:int}/call-preferences")
async def update_call_preferences(lead_id: int, payload: CallPreferencesRequest):
    result = LeadService.update_call_preferences(lead_id, payload.call_consent, payload.do_not_call)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/{lead_id:int}/calls")
async def start_voice_call(lead_id: int, payload: CallScriptRequest):
    return VoiceCallService.start_call(lead_id, payload.script, payload.call_mode)


@router.get("/{lead_id:int}/calls")
async def lead_call_history(lead_id: int):
    lead = LeadService.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return VoiceCallService.history_for_lead(lead_id)


@router.get("/calls/{call_id:int}/twiml")
async def call_twiml(call_id: int):
    return VoiceCallService.twiml_response(call_id)


@router.post("/calls/{call_id:int}/question")
async def call_question_answer(
    call_id: int,
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default=""),
):
    return VoiceCallService.questionnaire_answer_response(call_id, SpeechResult, Confidence)


@router.post("/calls/{call_id:int}/status")
async def call_status_callback(
    call_id: int,
    CallStatus: str = Form(default=""),
    CallDuration: str = Form(default="0"),
    CallSid: str = Form(default=""),
):
    return VoiceCallService.update_status(call_id, CallStatus, CallDuration, CallSid)


@router.post("/calls/{call_id:int}/recording")
async def call_recording_callback(
    call_id: int,
    RecordingSid: str = Form(default=""),
    RecordingUrl: str = Form(default=""),
    RecordingStatus: str = Form(default=""),
    RecordingDuration: str = Form(default="0"),
    CallSid: str = Form(default=""),
):
    return VoiceCallService.update_recording(
        call_id=call_id,
        recording_sid=RecordingSid,
        recording_url=RecordingUrl,
        recording_status=RecordingStatus,
        recording_duration=RecordingDuration,
        call_sid=CallSid,
    )


@router.post("/calls/{call_id:int}/transcribe")
async def transcribe_call_recording(call_id: int):
    return VoiceCallService.transcribe_recording(call_id)


@router.post("/{lead_id:int}/email-feedback", response_model=EmailDraftResponse)
async def record_email_feedback(lead_id: int, payload: EmailFeedbackRequest):
    lead = LeadService.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    subject = payload.subject if payload.subject is not None else lead.get("email_draft_subject", "")
    body = payload.body if payload.body is not None else lead.get("email_draft_body", "")
    if not subject or not body:
        raise HTTPException(status_code=400, detail="No email draft available for feedback.")
    if payload.action.lower().strip() == "rejected" and not (payload.feedback or "").strip():
        raise HTTPException(status_code=400, detail="Human rejection reason is required.")

    result = EmailLearningService.record_feedback(
        lead=lead,
        action=payload.action,
        subject=subject,
        body=body,
        feedback=payload.feedback or "",
        tone=payload.tone or "",
        campaign_type=payload.campaign_type or "",
    )
    return {
        "success": True,
        "message": f"Email feedback recorded as {payload.action}.",
        "lead_id": lead_id,
        "subject": subject,
        "body": body,
        **result,
    }


@router.get("/learning/stats")
async def learning_stats():
    return EmailLearningService.admin_stats()


@router.get("/learning/history")
async def learning_history(
    status: str = Query(default="all"),
    active: str = Query(default="true"),
    campaign_type: str = Query(default=""),
):
    return EmailLearningService.admin_history(status=status, active=active, campaign_type=campaign_type)


@router.patch("/learning/history/{history_id:int}")
async def update_learning_review(history_id: int, payload: LearningReviewRequest):
    record = EmailLearningService.update_admin_review(history_id, payload.action, payload.admin_note or "")
    if not record:
        raise HTTPException(status_code=404, detail="Learning record not found.")
    return record


@router.patch("/learning/history/{history_id:int}/active")
async def update_learning_active(history_id: int, payload: LearningActiveRequest):
    record = EmailLearningService.set_learning_active(history_id, payload.is_active, payload.admin_note or "")
    if not record:
        raise HTTPException(status_code=404, detail="Learning record not found.")
    return record


@router.delete("/learning/history/{history_id:int}")
async def remove_learning_record(history_id: int):
    record = EmailLearningService.set_learning_active(history_id, False, "Removed from learning by admin.")
    if not record:
        raise HTTPException(status_code=404, detail="Learning record not found.")
    return record


@router.post("/validate-emails-csv", response_model=BatchEmailValidationResponse)
async def validate_emails_from_csv(file: UploadFile = File(...)):
    rows, email_col = await _process_csv_file(file, "email")
    results, rows_to_save = [], []
    stats = {"valid": 0, "invalid": 0, "risky": 0}

    for row in rows:
        email = row.get(email_col, "").strip()
        if not email:
            continue

        validation = await EmailService.validate_email(email)
        status = validation.get("status", "error")
        if status in stats:
            stats[status] += 1

        score = LeadScoringService.calculate_score(
            {
                "email_status": status,
                "phone_status": row.get("phone_validation_status", ""),
                "source": row.get("source", ""),
                "budget": row.get("budget", ""),
                "timeline": row.get("timeline", ""),
                "message": row.get("message", ""),
            }
        )
        row.update(
            {
                "email_validation_status": status,
                "email_quality_score": validation.get("score", 0.0),
                "email_validation_reason": validation.get("reason", ""),
                "lead_score": score["lead_score"],
                "score_band": score["score_band"],
                "score_breakdown": score["score_breakdown"],
            }
        )
        rows_to_save.append(row)
        results.append(
            EmailValidationResult(
                email=email,
                status=status,
                score=validation.get("score", 0.0),
                reason=validation.get("reason"),
            )
        )

    output_file = _save_results(rows_to_save, file.filename, "email_validation")
    return BatchEmailValidationResponse(
        total_processed=len(results),
        valid_count=stats["valid"],
        invalid_count=stats["invalid"],
        risky_count=stats["risky"],
        results=results,
        csv_file=output_file,
    )


@router.post("/validate-phones-csv", response_model=BatchPhoneValidationResponse)
async def validate_phones_from_csv(file: UploadFile = File(...)):
    rows, phone_col = await _process_csv_file(file, "phone")
    twilio_client = TwilioLookupClient()
    results, rows_to_save = [], []
    stats = {"valid": 0, "invalid": 0}

    for row in rows:
        phone = row.get(phone_col, "").strip()
        if not phone:
            continue

        lookup = _normalize_phone(phone)
        validation = await twilio_client.lookup_number(lookup)
        status = "valid" if validation and validation.get("Valid") and validation.get("Active") else "invalid"
        sms_capable = str(validation.get("SMS_Capable", "")) if validation else ""
        stats[status] += 1

        score = LeadScoringService.calculate_score(
            {
                "email_status": row.get("email_validation_status", ""),
                "phone_status": status,
                "source": row.get("source", ""),
                "budget": row.get("budget", ""),
                "timeline": row.get("timeline", ""),
                "message": row.get("message", ""),
            }
        )
        row.update(
            {
                "phone_validation_status": status,
                "SMS_Capable": sms_capable,
                "lead_score": score["lead_score"],
                "score_band": score["score_band"],
                "score_breakdown": score["score_breakdown"],
            }
        )
        rows_to_save.append(row)
        results.append(
            PhoneValidationResult(
                phone=phone,
                status=status,
                sms_capable=sms_capable,
                details=validation if isinstance(validation, dict) else {"raw": str(validation)},
            )
        )

    output_file = _save_results(rows_to_save, file.filename, "phone_validation")
    return BatchPhoneValidationResponse(
        total_processed=len(results),
        valid_count=stats["valid"],
        invalid_count=stats["invalid"],
        results=results,
        csv_file=output_file,
    )


@router.post("/send-test-email", response_model=SendEmailResponse)
async def send_test_email(payload: SendTestEmailRequest):
    subject = f"Property options for {payload.location_preference or 'your requirement'}"
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    body = EmailSenderService.build_property_followup_body(payload_data)
    result = await EmailSenderService.send_email(payload.to_email, subject, body)

    return SendEmailResponse(
        success=result["success"],
        message=result["message"],
        to_email=payload.to_email,
        subject=subject,
    )


async def _process_csv_file(file: UploadFile, column_name: str):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a CSV file.")

    content = await file.read()
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.") from exc

    reader = csv.DictReader(io.StringIO(decoded))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty.")

    column = next((key for key in rows[0].keys() if key.lower() == column_name.lower()), None)
    if not column:
        raise HTTPException(status_code=400, detail=f"Column '{column_name}' not found in CSV.")

    return rows, column


def _save_results(rows, original_filename, prefix):
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    output_filename = f"{prefix}_{original_filename}"
    output_path = os.path.join(settings.OUTPUT_DIR, output_filename)

    if rows:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    return output_path


def _normalize_phone(phone: str) -> str:
    digits = "".join(filter(str.isdigit, phone))
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    return phone


def _should_auto_generate_draft(lead: dict) -> bool:
    return (
        lead.get("validation_status") == "Valid"
        and lead.get("score_band") == "Hot"
        and not lead.get("email_draft_subject")
        and not lead.get("email_draft_body")
    )


def _should_auto_send_email(lead: dict) -> bool:
    return (
        lead.get("validation_status") == "Valid"
        and lead.get("score_band") == "Hot"
        and lead.get("email")
        and lead.get("email_draft_subject")
        and lead.get("email_draft_body")
        and lead.get("email_sent_status") != "sent"
    )


def _automation_transcribe_target(lead_id: int, started_call_id: int | None = None) -> dict | None:
    calls = VoiceCallService.history_for_lead(lead_id)
    if started_call_id:
        call = next((item for item in calls if int(item.get("id") or 0) == started_call_id), None)
        if call and call.get("recording_url") and call.get("transcript_status") != "completed":
            return call
        return None
    return next(
        (
            call
            for call in calls
            if call.get("recording_url") and call.get("transcript_status") != "completed"
        ),
        None,
    )


def _format_whatsapp_body(body: str) -> str:
    lines = [line.strip() for line in str(body or "").splitlines()]
    compact = "\n".join(line for line in lines if line)
    return compact[:4096]


@router.get("/{lead_id:int}")
async def get_lead(lead_id: int):
    lead = LeadService.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    lead["messages"] = LeadService.get_messages(lead_id)
    lead["calls"] = VoiceCallService.history_for_lead(lead_id)
    lead["call_eligibility"] = VoiceCallService.eligibility(lead)
    return lead


@router.post("/{lead_id:int}/send-followup")
async def send_followup(lead_id: int):
    result = await FollowupService.send_followup(lead_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/{lead_id:int}/mark-replied")
async def mark_replied(lead_id: int, payload: MarkRepliedRequest):
    lead = LeadService.mark_replied(lead_id, payload.reply_text or "")
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return lead
