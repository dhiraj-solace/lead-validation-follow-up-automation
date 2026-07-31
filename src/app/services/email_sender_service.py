import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from src.app.core.config import settings

class EmailSenderService:
    @staticmethod
    async def send_email(to_email: str, subject: str, body: str, sender_config: dict | None = None) -> dict:
        return await asyncio.to_thread(EmailSenderService._send_email_sync, to_email, subject, body, sender_config)

    @staticmethod
    def build_property_followup_body(data: dict) -> str:
        name = data.get("lead_name") or "there"
        property_type = data.get("property_type") or "property"
        configuration = data.get("configuration") or "suitable"
        location = data.get("location_preference") or "your preferred location"
        budget = data.get("budget") or "your budget"
        agent_name = data.get("agent_name") or settings.SMTP_FROM_NAME

        return (
            f"Hi {name},\n\n"
            f"Thanks for your interest in {property_type} options around {location}.\n\n"
            f"We have a few {configuration} matches that may fit {budget}. "
            "Would you like me to share the best available options?\n\n"
            f"Regards,\n{agent_name}"
        )
    
    @staticmethod
    def _send_email_sync(to_email: str, subject: str, body: str, sender_config: dict | None = None) -> dict:
        config = EmailSenderService._resolve_sender_config(sender_config)
        missing = EmailSenderService._missing_settings(config)
        if missing:
            if settings.DEMO_MODE:
                return {
                    "success": True,
                    "message": (
                        f"Demo mode: email captured from {config['from_email'] or 'configured sender'} "
                        "and marked sent. Configure SMTP password to send real email."
                    ),
                }
            return {
                "success": False,
                "message": f"Missing SMTP settings for sender {config['from_email'] or 'account'}: {', '.join(missing)}",
            }

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((config["from_name"], config["from_email"]))
        message["To"] = to_email
        message.set_content(body)

        try:
            with smtplib.SMTP(config["smtp_host"], config["smtp_port"], timeout=20) as smtp:
                if config["smtp_use_tls"]:
                    smtp.starttls()
                smtp.login(config["smtp_username"], config["smtp_password"])
                smtp.send_message(message)

            return {"success": True, "message": f"Email sent successfully from {config['from_email']}."}
        except Exception as exc:
            return {"success": False, "message": f"Email send failed: {exc}"}

    @staticmethod
    def _resolve_sender_config(sender_config: dict | None = None) -> dict:
        if sender_config:
            return {
                "smtp_host": sender_config.get("smtp_host", ""),
                "smtp_port": int(sender_config.get("smtp_port") or 587),
                "smtp_use_tls": bool(sender_config.get("smtp_use_tls", True)),
                "smtp_username": sender_config.get("smtp_username", ""),
                "smtp_password": sender_config.get("smtp_password", ""),
                "from_email": sender_config.get("from_email") or sender_config.get("smtp_username", ""),
                "from_name": sender_config.get("from_name") or settings.SMTP_FROM_NAME,
            }

        return {
            "smtp_host": settings.SMTP_HOST,
            "smtp_port": settings.SMTP_PORT,
            "smtp_use_tls": settings.SMTP_USE_TLS,
            "smtp_username": settings.SMTP_USERNAME,
            "smtp_password": settings.SMTP_PASSWORD,
            "from_email": settings.SMTP_FROM_EMAIL,
            "from_name": settings.SMTP_FROM_NAME,
        }

    @staticmethod
    def _missing_settings(config: dict) -> list[str]:
        required = {
            "SMTP_HOST": config["smtp_host"],
            "SMTP_USERNAME": config["smtp_username"],
            "SMTP_PASSWORD": config["smtp_password"],
            "SMTP_FROM_EMAIL": config["from_email"],
        }
        return [name for name, value in required.items() if not value]
