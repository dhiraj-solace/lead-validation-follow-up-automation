from src.app.db.database import execute, fetch_all, fetch_one


DEFAULT_SETTINGS = {
    "auto_email_send_enabled": "false",
}


class AppSettingsService:
    @staticmethod
    def get_settings() -> dict:
        rows = fetch_all("SELECT key, value FROM app_settings", ())
        settings = dict(DEFAULT_SETTINGS)
        settings.update({row["key"]: row["value"] for row in rows})
        return {
            "auto_email_send_enabled": AppSettingsService.as_bool(settings.get("auto_email_send_enabled")),
        }

    @staticmethod
    def update_settings(auto_email_send_enabled: bool) -> dict:
        execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES ('auto_email_send_enabled', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            ("true" if auto_email_send_enabled else "false",),
        )
        return AppSettingsService.get_settings()

    @staticmethod
    def auto_email_send_enabled() -> bool:
        row = fetch_one("SELECT value FROM app_settings WHERE key = 'auto_email_send_enabled'", ())
        return AppSettingsService.as_bool((row or {}).get("value"))

    @staticmethod
    def as_bool(value: object) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}
