from src.app.db.database import execute, fetch_all, fetch_one
from src.app.core.config import settings


DEFAULT_SETTINGS = {
    "auto_email_send_enabled": "false",
}


class AppSettingsService:
    @staticmethod
    def get_settings() -> dict:
        rows = fetch_all("SELECT key, value FROM app_settings", ())
        saved_settings = dict(DEFAULT_SETTINGS)
        saved_settings.update({row["key"]: row["value"] for row in rows})
        return {
            "auto_email_send_enabled": AppSettingsService.as_bool(saved_settings.get("auto_email_send_enabled")),
            "twilio_credentials": AppSettingsService.twilio_credentials(),
        }

    @staticmethod
    def update_settings(auto_email_send_enabled: bool | None = None) -> dict:
        if auto_email_send_enabled is not None:
            AppSettingsService.upsert_setting("auto_email_send_enabled", "true" if auto_email_send_enabled else "false")
        return AppSettingsService.get_settings()

    @staticmethod
    def auto_email_send_enabled() -> bool:
        row = fetch_one("SELECT value FROM app_settings WHERE key = 'auto_email_send_enabled'", ())
        return AppSettingsService.as_bool((row or {}).get("value"))

    @staticmethod
    def twilio_credentials() -> dict:
        required = {
            "TWILIO_ACCOUNT_SID": settings.TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": settings.TWILIO_AUTH_TOKEN,
            "TWILIO_PHONE_NUMBER": settings.TWILIO_PHONE_NUMBER,
            "PUBLIC_BASE_URL": settings.PUBLIC_BASE_URL,
        }
        missing = [name for name, value in required.items() if not value]
        return {
            "configured": not missing,
            "missing": missing,
            "message": (
                "Twilio credentials are configured."
                if not missing
                else f"Twilio is missing server env: {', '.join(missing)}"
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
    def as_bool(value: object) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}
