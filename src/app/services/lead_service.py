from datetime import datetime, timedelta
import re

from src.app.core.config import settings
from src.app.db.database import execute, fetch_all, fetch_one
from src.app.services.agent_service import AgentService
from src.app.services.email_service import EmailService
from src.app.services.phone_service import TwilioLookupClient
from src.app.services.scoring_service import LeadScoringService


class LeadService:
    @staticmethod
    def list_leads(status: str | None = None, score_band: str | None = None) -> list[dict]:
        filters = []
        params = []
        if status:
            filters.append("l.status = ?")
            params.append(status)
        if score_band:
            filters.append("l.score_band = ?")
            params.append(score_band)

        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        return fetch_all(
            f"""
            SELECT
                l.*,
                a.name AS assigned_agent_name,
                a.email AS assigned_agent_email,
                a.email_provider AS assigned_agent_email_provider,
                a.email_account_active AS assigned_agent_email_account_active
            FROM leads l
            LEFT JOIN agents a ON a.id = l.assigned_agent_id
            {where}
            ORDER BY l.updated_at DESC, l.id DESC
            """,
            params,
        )

    @staticmethod
    def list_high_priority() -> list[dict]:
        return fetch_all(
            """
            SELECT
                l.*,
                a.name AS assigned_agent_name,
                a.email AS assigned_agent_email,
                a.email_provider AS assigned_agent_email_provider,
                a.email_account_active AS assigned_agent_email_account_active
            FROM leads l
            LEFT JOIN agents a ON a.id = l.assigned_agent_id
            WHERE l.score_band = 'Hot'
              AND l.validation_status = 'Valid'
              AND l.status != 'Duplicate'
            ORDER BY l.score DESC, l.updated_at DESC
            """
        )

    @staticmethod
    def get_lead(lead_id: int) -> dict | None:
        return fetch_one(
            """
            SELECT
                l.*,
                a.name AS assigned_agent_name,
                a.email AS assigned_agent_email,
                a.email_provider AS assigned_agent_email_provider,
                a.email_account_active AS assigned_agent_email_account_active
            FROM leads l
            LEFT JOIN agents a ON a.id = l.assigned_agent_id
            WHERE l.id = ?
            """,
            (lead_id,),
        )

    @staticmethod
    def get_messages(lead_id: int) -> list[dict]:
        return fetch_all(
            "SELECT * FROM message_logs WHERE lead_id = ? ORDER BY sent_at DESC, id DESC",
            (lead_id,),
        )

    @staticmethod
    async def create_or_update_from_upload(row: dict, validate_contacts: bool = True) -> tuple[dict, bool]:
        basic_validation = LeadService._validate_row_fields(row)
        existing = LeadService.find_duplicate(row.get("email", ""), row.get("phone", ""))
        if existing:
            return LeadService._insert_duplicate(row, existing, basic_validation), True

        enriched, assigned_agent_id, automation_status, next_followup_at = await LeadService._prepare_new_lead(
            row,
            validate_contacts,
        )

        lead_id = execute(
            """
            INSERT INTO leads (
                name, email, phone, source, property_type, configuration, location_preference,
                budget, timeline, message, email_status, phone_status, sms_capable, carrier,
                line_type, score, score_band, score_breakdown, validation_status, validation_remarks,
                status, assigned_agent_id,
                automation_status, next_followup_at, call_consent, do_not_call
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                enriched.get("name", ""),
                enriched.get("email", ""),
                enriched.get("phone", ""),
                enriched.get("source", ""),
                enriched.get("property_type", ""),
                enriched.get("configuration", ""),
                enriched.get("location_preference", ""),
                enriched.get("budget", ""),
                enriched.get("timeline", ""),
                enriched.get("message", ""),
                enriched.get("email_status", "pending"),
                enriched.get("phone_status", "pending"),
                enriched.get("sms_capable", ""),
                enriched.get("carrier", ""),
                enriched.get("line_type", ""),
                enriched["score"],
                enriched["score_band"],
                enriched["score_breakdown"],
                enriched["validation_status"],
                enriched["validation_remarks"],
                enriched["status"],
                assigned_agent_id,
                automation_status,
                next_followup_at,
                1 if LeadService._truthy(enriched.get("call_consent")) else 0,
                1 if LeadService._truthy(enriched.get("do_not_call")) else 0,
            ),
        )
        return LeadService.get_lead(lead_id), False

    @staticmethod
    async def replace_duplicate(duplicate_id: int, validate_contacts: bool = True) -> dict:
        duplicate = LeadService.get_lead(duplicate_id)
        if not duplicate:
            return {"success": False, "message": "Duplicate lead not found."}
        if duplicate.get("validation_status") != "Duplicate" or not duplicate.get("duplicate_of"):
            return {"success": False, "message": "This lead is not pending duplicate resolution."}

        original_id = duplicate["duplicate_of"]
        row = LeadService._row_from_lead(duplicate)
        enriched, assigned_agent_id, automation_status, next_followup_at = await LeadService._prepare_new_lead(
            row,
            validate_contacts,
        )
        execute(
            """
            UPDATE leads
            SET name = ?,
                email = ?,
                phone = ?,
                source = ?,
                property_type = ?,
                configuration = ?,
                location_preference = ?,
                budget = ?,
                timeline = ?,
                message = ?,
                email_status = ?,
                phone_status = ?,
                sms_capable = ?,
                carrier = ?,
                line_type = ?,
                score = ?,
                score_band = ?,
                score_breakdown = ?,
                validation_status = ?,
                validation_remarks = ?,
                status = ?,
                assigned_agent_id = ?,
                automation_status = ?,
                next_followup_at = ?,
                call_consent = ?,
                do_not_call = ?,
                duplicate_of = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                enriched.get("name", ""),
                enriched.get("email", ""),
                enriched.get("phone", ""),
                enriched.get("source", ""),
                enriched.get("property_type", ""),
                enriched.get("configuration", ""),
                enriched.get("location_preference", ""),
                enriched.get("budget", ""),
                enriched.get("timeline", ""),
                enriched.get("message", ""),
                enriched.get("email_status", "pending"),
                enriched.get("phone_status", "pending"),
                enriched.get("sms_capable", ""),
                enriched.get("carrier", ""),
                enriched.get("line_type", ""),
                enriched["score"],
                enriched["score_band"],
                enriched["score_breakdown"],
                enriched["validation_status"],
                f"Replaced by uploaded duplicate #{duplicate_id}. {enriched['validation_remarks']}",
                enriched["status"],
                assigned_agent_id,
                automation_status,
                next_followup_at,
                1 if LeadService._truthy(enriched.get("call_consent")) else 0,
                1 if LeadService._truthy(enriched.get("do_not_call")) else 0,
                original_id,
            ),
        )
        execute("DELETE FROM leads WHERE id = ?", (duplicate_id,))
        return {
            "success": True,
            "message": f"Replaced old lead #{original_id} with uploaded duplicate #{duplicate_id}.",
            "lead": LeadService.get_lead(original_id),
            "removed_duplicate_id": duplicate_id,
        }

    @staticmethod
    def skip_duplicate(duplicate_id: int) -> dict:
        duplicate = LeadService.get_lead(duplicate_id)
        if not duplicate:
            return {"success": False, "message": "Duplicate lead not found."}
        if duplicate.get("validation_status") != "Duplicate":
            return {"success": False, "message": "This lead is not pending duplicate resolution."}

        execute("DELETE FROM leads WHERE id = ?", (duplicate_id,))
        return {"success": True, "message": f"Skipped duplicate lead #{duplicate_id}.", "lead_id": duplicate_id}

    @staticmethod
    def delete_lead(lead_id: int) -> dict:
        lead = LeadService.get_lead(lead_id)
        if not lead:
            return {"success": False, "message": "Lead not found."}

        execute("DELETE FROM message_logs WHERE lead_id = ?", (lead_id,))
        execute("DELETE FROM call_logs WHERE lead_id = ?", (lead_id,))
        execute("DELETE FROM email_generation_history WHERE lead_id = ?", (lead_id,))
        execute("DELETE FROM leads WHERE duplicate_of = ?", (lead_id,))
        execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        return {"success": True, "message": f"Deleted lead #{lead_id}.", "lead_id": lead_id}

    @staticmethod
    def update_call_preferences(lead_id: int, call_consent: bool, do_not_call: bool = False) -> dict:
        lead = LeadService.get_lead(lead_id)
        if not lead:
            return {"success": False, "message": "Lead not found."}

        execute(
            """
            UPDATE leads
            SET call_consent = ?,
                do_not_call = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if call_consent else 0, 1 if do_not_call else 0, lead_id),
        )
        return {
            "success": True,
            "message": "Call preferences updated.",
            "lead": LeadService.get_lead(lead_id),
        }

    @staticmethod
    def find_duplicate(email: str, phone: str) -> dict | None:
        if email:
            lead = fetch_one(
                """
                SELECT *
                FROM leads
                WHERE lower(email) = lower(?)
                ORDER BY CASE WHEN status = 'Duplicate' THEN 1 ELSE 0 END, id ASC
                LIMIT 1
                """,
                (email,),
            )
            if lead:
                return lead
        if phone:
            return fetch_one(
                """
                SELECT *
                FROM leads
                WHERE phone = ?
                ORDER BY CASE WHEN status = 'Duplicate' THEN 1 ELSE 0 END, id ASC
                LIMIT 1
                """,
                (phone,),
            )
        return None

    @staticmethod
    def mark_replied(lead_id: int, reply_text: str = "") -> dict | None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        execute(
            """
            UPDATE leads
            SET status = 'Responded',
                automation_status = 'stopped',
                replied_at = ?,
                next_followup_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (now, lead_id),
        )
        if reply_text:
            execute(
                """
                INSERT INTO message_logs (lead_id, channel, direction, body, status)
                VALUES (?, 'email', 'inbound', ?, 'received')
                """,
                (lead_id, reply_text),
            )
        return LeadService.get_lead(lead_id)

    @staticmethod
    def update_followup_state(lead_id: int, step: int, status: str, interval_days: int = 2) -> dict | None:
        now = datetime.utcnow()
        next_at = None if status != "active" else (now + timedelta(days=interval_days)).isoformat(timespec="seconds")
        execute(
            """
            UPDATE leads
            SET followup_step = ?,
                automation_status = ?,
                last_contacted_at = ?,
                next_followup_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (step, status, now.isoformat(timespec="seconds"), next_at, lead_id),
        )
        return LeadService.get_lead(lead_id)

    @staticmethod
    def dashboard() -> dict:
        rows = fetch_all(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN score_band = 'Hot' THEN 1 ELSE 0 END), 0) AS hot,
                COALESCE(SUM(CASE WHEN score_band = 'Warm' THEN 1 ELSE 0 END), 0) AS warm,
                COALESCE(SUM(CASE WHEN score_band = 'Cold' THEN 1 ELSE 0 END), 0) AS cold,
                COALESCE(SUM(CASE WHEN validation_status = 'Invalid' THEN 1 ELSE 0 END), 0) AS invalid,
                COALESCE(SUM(CASE WHEN validation_status = 'Duplicate' THEN 1 ELSE 0 END), 0) AS duplicate,
                COALESCE(SUM(CASE WHEN email_status = 'valid' THEN 1 ELSE 0 END), 0) AS valid_emails,
                COALESCE(SUM(CASE WHEN phone_status = 'valid' THEN 1 ELSE 0 END), 0) AS valid_phones,
                COALESCE(SUM(CASE WHEN automation_status = 'active' THEN 1 ELSE 0 END), 0) AS active_followups,
                COALESCE(SUM(CASE WHEN email_sent_status = 'sent' THEN 1 ELSE 0 END), 0) AS emails_sent,
                COALESCE(SUM(CASE WHEN status = 'Responded' THEN 1 ELSE 0 END), 0) AS responded
            FROM leads
            """
        )
        return rows[0] if rows else {}

    @staticmethod
    async def _prepare_new_lead(row: dict, validate_contacts: bool = True) -> tuple[dict, int | None, str, str | None]:
        basic_validation = LeadService._validate_row_fields(row)
        enriched = dict(row)
        remarks = list(basic_validation["remarks"])
        notes = []
        if validate_contacts:
            enriched.update(await LeadService._validate_contacts(row))
        else:
            enriched.update({"email_status": "skipped", "phone_status": "skipped"})

        if enriched.get("email_status") in {"invalid", "error", "missing"}:
            remarks.append(f"Email status is {enriched.get('email_status')}.")
        if enriched.get("phone_status") in {"invalid", "error", "missing"}:
            remarks.append(f"Phone status is {enriched.get('phone_status')}.")
        if str(enriched.get("email_reason", "")).startswith("demo_"):
            notes.append("Email API not configured or unavailable; used demo simple email validation.")
        if str(enriched.get("phone_reason", "")).startswith("demo_"):
            notes.append("Phone API not configured or unavailable; used demo simple phone validation.")

        validation_status = "Invalid" if remarks else "Valid"
        scoring = LeadScoringService.calculate_score(enriched)
        if validation_status == "Invalid":
            scoring = LeadScoringService.apply_invalid_validation_cap(scoring)
        enriched.update(
            {
                "score": scoring["lead_score"],
                "score_band": scoring["score_band"],
                "score_breakdown": scoring["score_breakdown"],
                "validation_status": validation_status,
                "validation_remarks": " ".join(remarks + notes) if remarks or notes else "Lead passed required field and duplicate checks.",
                "status": validation_status if validation_status == "Invalid" else scoring["score_band"],
            }
        )

        agent = AgentService.choose_agent(enriched) if validation_status == "Valid" and enriched["score_band"] == "Hot" else None
        assigned_agent_id = agent["id"] if agent else None
        automation_status = "active" if validation_status == "Valid" and enriched["score_band"] in {"Hot", "Warm"} else "not_started"
        next_followup_at = datetime.utcnow().isoformat(timespec="seconds") if automation_status == "active" else None
        return enriched, assigned_agent_id, automation_status, next_followup_at

    @staticmethod
    def _row_from_lead(lead: dict) -> dict:
        return {
            "name": lead.get("name", ""),
            "email": lead.get("email", ""),
            "phone": lead.get("phone", ""),
            "source": lead.get("source", ""),
            "property_type": lead.get("property_type", ""),
            "configuration": lead.get("configuration", ""),
            "location_preference": lead.get("location_preference", ""),
            "budget": lead.get("budget", ""),
            "timeline": lead.get("timeline", ""),
            "message": lead.get("message", ""),
            "call_consent": lead.get("call_consent", 0),
            "do_not_call": lead.get("do_not_call", 0),
        }

    @staticmethod
    async def _validate_contacts(row: dict) -> dict:
        email_status = "missing"
        phone_status = "missing"
        email = row.get("email", "")
        phone = row.get("phone", "")
        email_reason = ""
        phone_reason = ""

        if email:
            email_result = await EmailService.validate_email(email)
            email_status = email_result.get("status", "error")
            email_reason = email_result.get("reason", "")

        phone_result = None
        if phone:
            twilio_client = TwilioLookupClient()
            phone_result = await twilio_client.lookup_number(LeadService._normalize_phone(phone))
            phone_status = "valid" if phone_result and phone_result.get("Valid") and phone_result.get("Active") else "invalid"
            phone_reason = phone_result.get("Reason", "") if phone_result else ""

        return {
            "email_status": email_status,
            "phone_status": phone_status,
            "email_reason": email_reason,
            "phone_reason": phone_reason,
            "sms_capable": str(phone_result.get("SMS_Capable", "")) if phone_result else "",
            "carrier": phone_result.get("Carrier", "") if phone_result else "",
            "line_type": phone_result.get("Line_Type", "") if phone_result else "",
        }

    @staticmethod
    def _insert_duplicate(row: dict, existing: dict, basic_validation: dict) -> dict:
        scoring = LeadScoringService.calculate_score(row)
        scoring = LeadScoringService.apply_invalid_validation_cap(scoring, reason="Duplicate lead")
        remarks = list(basic_validation["remarks"])
        remarks.append(f"Duplicate lead matched existing lead #{existing['id']} by email or phone.")
        lead_id = execute(
            """
            INSERT INTO leads (
                name, email, phone, source, property_type, configuration, location_preference,
                budget, timeline, message, email_status, phone_status, score, score_band,
                score_breakdown, validation_status, validation_remarks, status, automation_status, call_consent,
                do_not_call, duplicate_of
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'skipped', 'skipped', ?, ?, ?, 'Duplicate', ?, 'Duplicate', 'stopped', ?, ?, ?)
            """,
            (
                row.get("name", ""),
                row.get("email", ""),
                row.get("phone", ""),
                row.get("source", ""),
                row.get("property_type", ""),
                row.get("configuration", ""),
                row.get("location_preference", ""),
                row.get("budget", ""),
                row.get("timeline", ""),
                row.get("message", ""),
                scoring["lead_score"],
                scoring["score_band"],
                scoring["score_breakdown"],
                " ".join(remarks),
                1 if LeadService._truthy(row.get("call_consent")) else 0,
                1 if LeadService._truthy(row.get("do_not_call")) else 0,
                existing["id"],
            ),
        )
        return LeadService.get_lead(lead_id)

    @staticmethod
    def _validate_row_fields(row: dict) -> dict:
        remarks = []
        required = [
            "name",
            "email",
            "phone",
            "source",
            "property_type",
            "configuration",
            "location_preference",
            "budget",
            "timeline",
            "message",
        ]
        missing = [field for field in required if not str(row.get(field, "")).strip()]
        if missing:
            remarks.append(f"Missing required fields: {', '.join(missing)}.")

        email = str(row.get("email", "")).strip()
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            remarks.append("Email format is invalid.")

        phone_digits = "".join(filter(str.isdigit, str(row.get("phone", ""))))
        if phone_digits and len(phone_digits) < 10:
            remarks.append("Phone number is too short.")
        if phone_digits and len(phone_digits) > 13:
            remarks.append("Phone number is too long.")

        return {"valid": not remarks, "remarks": remarks}

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        digits = "".join(filter(str.isdigit, phone))
        default_country_code = "".join(filter(str.isdigit, settings.PHONE_DEFAULT_COUNTRY_CODE or "91")) or "91"
        if len(digits) == 10:
            return f"+{default_country_code}{digits}"
        if len(digits) == 11 and digits.startswith("0"):
            return f"+{default_country_code}{digits[1:]}"
        if len(digits) == 10 + len(default_country_code) and digits.startswith(default_country_code):
            return f"+{digits}"
        return phone

    @staticmethod
    def _truthy(value: object) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "consented", "opted_in", "opted-in"}
