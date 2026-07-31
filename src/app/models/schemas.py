from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EmailValidationResult(BaseModel):
    email: str
    status: str
    score: float = 0.0
    reason: Optional[str] = None


class BatchEmailValidationResponse(BaseModel):
    total_processed: int
    valid_count: int
    invalid_count: int
    risky_count: int
    results: List[EmailValidationResult]
    csv_file: Optional[str] = None


class PhoneValidationResult(BaseModel):
    phone: str
    status: str
    sms_capable: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class BatchPhoneValidationResponse(BaseModel):
    total_processed: int
    valid_count: int
    invalid_count: int
    results: List[PhoneValidationResult]
    csv_file: Optional[str] = None


class LeadResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    source: Optional[str] = ""
    property_type: Optional[str] = ""
    configuration: Optional[str] = ""
    location_preference: Optional[str] = ""
    budget: Optional[str] = ""
    timeline: Optional[str] = ""
    message: Optional[str] = ""
    email_status: Optional[str] = ""
    phone_status: Optional[str] = ""
    sms_capable: Optional[str] = ""
    carrier: Optional[str] = ""
    line_type: Optional[str] = ""
    score: int = 0
    score_band: str = "Cold"
    score_breakdown: Optional[str] = ""
    status: str = "New"
    assigned_agent_id: Optional[int] = None
    assigned_agent_name: Optional[str] = None
    assigned_agent_email: Optional[str] = None
    assigned_agent_email_provider: Optional[str] = ""
    assigned_agent_email_account_active: Optional[int] = 0
    followup_step: int = 0
    automation_status: str = "not_started"
    next_followup_at: Optional[str] = None
    last_contacted_at: Optional[str] = None
    replied_at: Optional[str] = None
    validation_status: Optional[str] = "Pending"
    validation_remarks: Optional[str] = ""
    email_draft_subject: Optional[str] = ""
    email_draft_body: Optional[str] = ""
    email_sent_status: Optional[str] = "not_sent"
    email_sent_at: Optional[str] = None
    duplicate_of: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UploadLeadsResponse(BaseModel):
    total_rows: int
    created: int
    merged_duplicates: int
    auto_drafted: int = 0
    valid: int
    invalid: int
    duplicate: int
    hot: int
    warm: int
    cold: int
    leads: List[LeadResponse]


class AgentCreateRequest(BaseModel):
    name: str
    email: str
    territory: Optional[str] = ""
    property_type: Optional[str] = ""
    email_provider: Optional[str] = "gmail"
    email_username: Optional[str] = ""
    email_password: Optional[str] = ""
    smtp_host: Optional[str] = ""
    smtp_port: int = 587
    smtp_use_tls: bool = True
    email_account_active: bool = True
    active: bool = True


class TemplateCreateRequest(BaseModel):
    name: str
    category: str
    subject: str
    body: str
    property_type: Optional[str] = ""
    reply_rate: float = 0
    conversion_rate: float = 0
    active: bool = True


class SendTestEmailRequest(BaseModel):
    to_email: str
    lead_name: str
    property_type: str = "property"
    configuration: Optional[str] = None
    location_preference: Optional[str] = None
    budget: Optional[str] = None
    agent_name: str = "Sales Team"


class SendEmailResponse(BaseModel):
    success: bool
    message: str
    to_email: str
    subject: str


class MarkRepliedRequest(BaseModel):
    reply_text: Optional[str] = ""


class EmailDraftRequest(BaseModel):
    subject: str
    body: str


class EmailFeedbackRequest(BaseModel):
    action: str
    subject: Optional[str] = None
    body: Optional[str] = None
    feedback: Optional[str] = ""
    tone: Optional[str] = ""
    campaign_type: Optional[str] = ""


class LearningReviewRequest(BaseModel):
    action: str
    admin_note: Optional[str] = ""


class LearningActiveRequest(BaseModel):
    is_active: bool
    admin_note: Optional[str] = ""


class EmailDraftResponse(BaseModel):
    success: bool
    message: str
    lead_id: Optional[int] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    attempt_count: Optional[int] = None
    retry_reasons: Optional[List[str]] = None
    history_id: Optional[int] = None
    guardrail_passed: Optional[bool] = None
    guardrail_issues: Optional[List[str]] = None
    judge_score: Optional[int] = None
    judge_status: Optional[str] = None
    judge_reason: Optional[str] = None
