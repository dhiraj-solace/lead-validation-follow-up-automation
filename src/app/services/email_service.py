import logging
import httpx
import re
from typing import Dict, Any
from src.app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    BASE_URL = "https://emailreputation.abstractapi.com/v1/"
    _client = None
    
    @classmethod
    async def get_client(cls):
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(timeout=10.0)
        return cls._client

    @classmethod
    async def validate_email(cls, email: str) -> Dict[str, Any]:
        if not settings.EMAIL_VALIDATOR_API_KEY:
            if settings.DEMO_MODE:
                return cls._simple_validate_email(email, "demo_missing_api_key")
            logger.error("API key for email validator not found.")
            return {"status": "error", "reason": "missing_api_key"}
            
        params = {
            "api_key": settings.EMAIL_VALIDATOR_API_KEY,
            "email": email
        }
        
        try:
            client = await cls.get_client()
            response = await client.get(cls.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            deliverability_status = data.get("deliverability")
            if not deliverability_status:
                deliverability_status = data.get("email_deliverability", {}).get("status")

            is_active = False
            if deliverability_status:
                is_active = deliverability_status.upper() == "DELIVERABLE"

            def get_nested(data, key_path, default=None):
                val = data
                for key in key_path:
                    if isinstance(val, dict):
                        val = val.get(key)
                    else:
                        return default
                return val if val is not None else default

            quality_score = data.get("quality_score")
            if quality_score is None:
                quality_score = get_nested(data, ["email_quality", "score"], 0)
            quality_score = float(quality_score)

            is_disposable = get_nested(data, ["is_disposable_email", "value"])
            if is_disposable is None:
                is_disposable = get_nested(data, ["email_quality", "is_disposable"], False)

            is_catchall = get_nested(data, ["is_catchall_email", "value"])
            if is_catchall is None:
                is_catchall = get_nested(data, ["email_quality", "is_catchall"], False)
            
            if not is_active:
                return {"status": "invalid", "reason": "non_deliverable", "details": data}

            if is_disposable:
                return {"status": "risky", "reason": "disposable", "score": quality_score}
                
            if is_catchall:
                return {"status": "risky", "reason": "catch_all", "score": quality_score}

            if quality_score < 0.7:
                return {"status": "risky", "reason": "low_score", "score": quality_score}

            return {"status": "valid", "score": quality_score, "details": data}

        except httpx.TimeoutException:
            logger.error(f"Timeout connecting to Abstract API for email: {email}")
            if settings.DEMO_MODE:
                return cls._simple_validate_email(email, "demo_api_timeout_fallback")
            return {"status": "error", "reason": "timeout"}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for email {email}: {e}")
            if settings.DEMO_MODE:
                return cls._simple_validate_email(email, "demo_api_connection_fallback")
            return {"status": "error", "reason": "api_connection_failed", "details": str(e)}
        except Exception as e:
            logger.exception(f"Unexpected error validating email {email}")
            if settings.DEMO_MODE:
                return cls._simple_validate_email(email, "demo_unexpected_error_fallback")
            return {"status": "error", "reason": "unexpected_error", "details": str(e)}

    @staticmethod
    def _simple_validate_email(email: str, reason: str = "simple_validation") -> Dict[str, Any]:
        value = str(email or "").strip().lower()
        if not value:
            return {"status": "missing", "reason": "missing_email", "score": 0.0}

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            return {"status": "invalid", "reason": "invalid_format", "score": 0.0}

        domain = value.rsplit("@", 1)[-1]
        disposable_domains = {"mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com"}
        if domain in disposable_domains:
            return {"status": "risky", "reason": "disposable_domain_simple_check", "score": 0.45}

        return {
            "status": "valid",
            "reason": reason,
            "score": 0.88,
            "details": {"mode": "demo_simple_validation", "api_validation": "not_used"},
        }
