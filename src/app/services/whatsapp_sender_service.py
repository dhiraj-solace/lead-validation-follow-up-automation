import httpx

from src.app.core.config import settings


class WhatsAppSenderService:
    @staticmethod
    async def send_text(to_phone: str, body: str) -> dict:
        phone = WhatsAppSenderService.normalize_phone(to_phone)
        if not phone:
            return {"success": False, "message": "Lead has no valid WhatsApp phone number."}
        if not body.strip():
            return {"success": False, "message": "WhatsApp message body is empty."}

        missing = WhatsAppSenderService._missing_settings()
        if missing:
            if settings.DEMO_MODE:
                return {
                    "success": True,
                    "message": "Demo mode: WhatsApp message captured and marked sent. Configure Meta credentials to send real WhatsApp.",
                    "to_phone": phone,
                }
            return {"success": False, "message": f"Missing WhatsApp settings: {', '.join(missing)}", "to_phone": phone}

        url = f"{settings.WHATSAPP_GRAPH_BASE_URL.rstrip('/')}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": body[:4096]},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            message_id = ((data.get("messages") or [{}])[0] or {}).get("id", "")
            return {
                "success": True,
                "message": "WhatsApp message sent successfully.",
                "to_phone": phone,
                "provider_message_id": message_id,
            }
        except httpx.HTTPStatusError as exc:
            return {
                "success": False,
                "message": f"WhatsApp send failed: {exc.response.status_code} {exc.response.text}",
                "to_phone": phone,
            }
        except Exception as exc:
            return {"success": False, "message": f"WhatsApp send failed: {exc}", "to_phone": phone}

    @staticmethod
    def normalize_phone(phone: str) -> str:
        raw = str(phone or "").strip()
        digits = "".join(filter(str.isdigit, raw))
        if not digits:
            return ""
        if raw.startswith("+"):
            return digits
        if len(digits) == 10:
            return f"{settings.WHATSAPP_DEFAULT_COUNTRY_CODE}{digits}"
        return digits

    @staticmethod
    def _missing_settings() -> list[str]:
        required = {
            "WHATSAPP_PHONE_NUMBER_ID": settings.WHATSAPP_PHONE_NUMBER_ID,
            "WHATSAPP_ACCESS_TOKEN": settings.WHATSAPP_ACCESS_TOKEN,
        }
        return [name for name, value in required.items() if not value]
