import os

from dotenv import load_dotenv

load_dotenv()


def env_value(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if value.startswith("your_"):
        return ""
    return value


def default_data_dir() -> str:
    return "/tmp/lead-validation-data" if os.getenv("VERCEL") else "data"


class Settings:
    PROJECT_NAME: str = "Real Estate Lead Automation API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    LOG_LEVEL: str = env_value("LOG_LEVEL", "INFO").upper()

    CALL_PROVIDER: str = env_value("CALL_PROVIDER", "twilio").lower()
    TWILIO_ACCOUNT_SID: str = env_value("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str = env_value("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: str = env_value("TWILIO_PHONE_NUMBER")
    TELNYX_API_KEY: str = env_value("TELNYX_API_KEY")
    TELNYX_PHONE_NUMBER: str = env_value("TELNYX_PHONE_NUMBER") or env_value("TELNYX_FROM_NUMBER")
    TELNYX_CONNECTION_ID: str = env_value("TELNYX_CONNECTION_ID")
    TELNYX_API_BASE_URL: str = env_value("TELNYX_API_BASE_URL", "https://api.telnyx.com/v2")
    PUBLIC_BASE_URL: str = env_value("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    CALL_MIN_SCORE: int = int(env_value("CALL_MIN_SCORE", "50") or "50")
    CALL_COOLDOWN_HOURS: int = int(env_value("CALL_COOLDOWN_HOURS", "24") or "24")
    EMAIL_VALIDATOR_API_KEY: str = env_value("EMAIL_VALIDATOR_API_KEY") or env_value("email_validator_api_key")
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    MONGODB_URI: str = env_value("MONGODB_URI")
    MONGODB_DB_NAME: str = env_value("MONGODB_DB_NAME", "lead_validation_automation")
    OPENROUTER_API_KEY: str = env_value("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = env_value("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL: str = env_value("OPENROUTER_MODEL", "~openai/gpt-latest")
    OPENROUTER_SITE_URL: str = env_value("OPENROUTER_SITE_URL", "http://127.0.0.1:3000")
    OPENROUTER_APP_NAME: str = env_value("OPENROUTER_APP_NAME", "Real Estate Lead Automation")

    SMTP_HOST: str = env_value("SMTP_HOST")
    SMTP_PORT: int = int(env_value("SMTP_PORT", "587") or "587")
    SMTP_USERNAME: str = env_value("SMTP_USERNAME")
    SMTP_PASSWORD: str = env_value("SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = env_value("SMTP_FROM_EMAIL")
    SMTP_FROM_NAME: str = env_value("SMTP_FROM_NAME", "Real Estate Sales Team")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    WHATSAPP_PROVIDER: str = env_value("WHATSAPP_PROVIDER", "meta")
    WHATSAPP_VERIFY_TOKEN: str = env_value("WHATSAPP_VERIFY_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID: str = env_value("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_WABA_ID: str = env_value("WHATSAPP_WABA_ID")
    WHATSAPP_ACCESS_TOKEN: str = env_value("WHATSAPP_ACCESS_TOKEN")
    WHATSAPP_GRAPH_BASE_URL: str = env_value("WHATSAPP_GRAPH_BASE_URL", "https://graph.facebook.com/v20.0")
    WHATSAPP_DEFAULT_COUNTRY_CODE: str = env_value("WHATSAPP_DEFAULT_COUNTRY_CODE", "91")

    DATA_DIR: str = os.getenv("DATA_DIR", default_data_dir())
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", os.path.join(DATA_DIR, "lead_automation.sqlite3"))
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", os.path.join(DATA_DIR, "uploads"))
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", os.path.join(DATA_DIR, "outputs"))

    CSV_COLUMNS = {
        "email": ["Email", "email", "email_address", "business_email", "business_email_address"],
        "phone": ["Phone", "phone", "phone_number", "mobile_number", "mobile_phone"],
    }


settings = Settings()
