from src.app.db.database import execute, fetch_all, fetch_one
from src.app.core.config import settings


DEFAULT_SETTINGS = {
    "auto_email_send_enabled": "false",
    "call_provider": settings.CALL_PROVIDER if settings.CALL_PROVIDER in {"twilio", "telnyx"} else "twilio",
}
CALL_PROVIDERS = {"twilio", "telnyx"}


class AppSettingsService:
    @staticmethod
    def get_settings() -> dict:
        rows = fetch_all("SELECT key, value FROM app_settings", ())
        settings = dict(DEFAULT_SETTINGS)
        settings.update({row["key"]: row["value"] for row in rows})
        call_provider = AppSettingsService.normalize_call_provider(settings.get("call_provider"))
        return {
            "auto_email_send_enabled": AppSettingsService.as_bool(settings.get("auto_email_send_enabled")),
            "call_provider": call_provider,
            "call_provider_credentials": AppSettingsService.call_provider_credentials(call_provider),
        }

    @staticmethod
    def update_settings(auto_email_send_enabled: bool | None = None, call_provider: str | None = None) -> dict:
        if auto_email_send_enabled is not None:
            AppSettingsService.upsert_setting("auto_email_send_enabled", "true" if auto_email_send_enabled else "false")
        if call_provider is not None:
            AppSettingsService.upsert_setting("call_provider", AppSettingsService.normalize_call_provider(call_provider))
        return AppSettingsService.get_settings()

    @staticmethod
    def auto_email_send_enabled() -> bool:
        row = fetch_one("SELECT value FROM app_settings WHERE key = 'auto_email_send_enabled'", ())
        return AppSettingsService.as_bool((row or {}).get("value"))

    @staticmethod
    def call_provider() -> str:
        row = fetch_one("SELECT value FROM app_settings WHERE key = 'call_provider'", ())
        return AppSettingsService.normalize_call_provider((row or {}).get("value") or DEFAULT_SETTINGS["call_provider"])

    @staticmethod
    def call_provider_credentials(provider: str | None = None) -> dict:
        selected = AppSettingsService.normalize_call_provider(provider)
        required = {
            "twilio": {
                "TWILIO_ACCOUNT_SID": settings.TWILIO_ACCOUNT_SID,
                "TWILIO_AUTH_TOKEN": settings.TWILIO_AUTH_TOKEN,
                "TWILIO_PHONE_NUMBER": settings.TWILIO_PHONE_NUMBER,
                "PUBLIC_BASE_URL": settings.PUBLIC_BASE_URL,
            },
            "telnyx": {
                "TELNYX_API_KEY": settings.TELNYX_API_KEY,
                "TELNYX_PHONE_NUMBER": settings.TELNYX_PHONE_NUMBER,
                "TELNYX_CONNECTION_ID": settings.TELNYX_CONNECTION_ID,
                "PUBLIC_BASE_URL": settings.PUBLIC_BASE_URL,
            },
        }[selected]
        missing = [name for name, value in required.items() if not value]
        return {
            "provider": selected,
            "configured": not missing,
            "missing": missing,
            "message": (
                f"{selected.title()} credentials are configured."
                if not missing
                else f"{selected.title()} is missing server env: {', '.join(missing)}"
            ),
        }

    @staticmethod
    def upsert_setting(key: str, value: str) -> None:
        execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )

    @staticmethod
    def normalize_call_provider(value: object) -> str:
        provider = str(value or "").strip().lower()
        return provider if provider in CALL_PROVIDERS else "twilio"

    @staticmethod
    def as_bool(value: object) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}
