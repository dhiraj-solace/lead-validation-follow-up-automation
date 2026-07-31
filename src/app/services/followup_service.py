from datetime import datetime

from src.app.db.database import execute, fetch_all
from src.app.services.agent_service import AgentService
from src.app.services.email_sender_service import EmailSenderService
from src.app.services.lead_service import LeadService
from src.app.services.template_service import TemplateService


class FollowupService:
    @staticmethod
    def list_queue() -> list[dict]:
        return fetch_all(
            """
            SELECT l.*, a.name AS assigned_agent_name, a.email AS assigned_agent_email
            FROM leads l
            LEFT JOIN agents a ON a.id = l.assigned_agent_id
            WHERE l.automation_status = 'active'
            ORDER BY l.next_followup_at ASC, l.score DESC
            """
        )
    
    @staticmethod
    async def send_followup(lead_id: int) -> dict:
        lead = LeadService.get_lead(lead_id)
        if not lead:
            return {"success": False, "message": "Lead not found."}
        if lead.get("automation_status") == "stopped":
            return {"success": False, "message": "Automation is stopped for this lead."}
        if not lead.get("email"):
            return {"success": False, "message": "Lead has no email address."}

        agent = AgentService.get_agent(lead["assigned_agent_id"]) if lead.get("assigned_agent_id") else None
        sender_config = AgentService.get_sender_config(agent)
        if agent and not sender_config:
            return {"success": False, "message": "Assigned agent email account is not configured or inactive.", "lead": lead}
        template = TemplateService.select_template(lead)
        if not template:
            return {"success": False, "message": "No active email template available."}

        subject = TemplateService.render(template["subject"], lead, agent)
        body = TemplateService.render(template["body"], lead, agent)
        result = await EmailSenderService.send_email(lead["email"], subject, body, sender_config=sender_config)

        execute(
            """
            INSERT INTO message_logs (lead_id, template_id, channel, direction, subject, body, status, error)
            VALUES (?, ?, 'email', 'outbound', ?, ?, ?, ?)
            """,
            (
                lead_id,
                template["id"],
                subject,
                body,
                "sent" if result["success"] else "failed",
                "" if result["success"] else result["message"],
            ),
        )

        if result["success"]:
            execute(
                """
                UPDATE leads
                SET email_sent_status = 'sent',
                    email_sent_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (lead_id,),
            )
            next_step = int(lead.get("followup_step") or 0) + 1
            if next_step >= 3:
                LeadService.update_followup_state(lead_id, next_step, "completed", interval_days=30)
                execute("UPDATE leads SET status = 'Cold', score_band = 'Cold' WHERE id = ?", (lead_id,))
                updated = LeadService.get_lead(lead_id)
            else:
                updated = LeadService.update_followup_state(lead_id, next_step, "active", interval_days=2)
            return {"success": True, "message": "Follow-up sent.", "lead": updated}

        return {"success": False, "message": result["message"], "lead": lead}

    @staticmethod
    async def process_due() -> dict:
        now = datetime.utcnow().isoformat(timespec="seconds")
        due = fetch_all(
            """
            SELECT id
            FROM leads
            WHERE automation_status = 'active'
              AND next_followup_at IS NOT NULL
              AND next_followup_at <= ?
            ORDER BY next_followup_at ASC
            """,
            (now,),
        )

        sent = 0
        failed = 0
        for lead in due:
            result = await FollowupService.send_followup(lead["id"])
            if result["success"]:
                sent += 1
            else:
                failed += 1

        return {"total_due": len(due), "sent": sent, "failed": failed}
