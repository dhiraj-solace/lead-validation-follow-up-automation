import logging
import asyncio
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from src.app.core.config import settings

logger = logging.getLogger(__name__)

class TwilioLookupClient:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.client = Client(self.account_sid, self.auth_token) if self.account_sid and self.auth_token else None
    
    async def lookup_number(self, phone_number):
        return await asyncio.to_thread(self._lookup_number_sync, phone_number)

    def _lookup_number_sync(self, phone_number):
        if not self.client:
            if settings.DEMO_MODE:
                return self._simple_lookup_number(phone_number, "demo_missing_twilio_credentials")
            return {
                "Valid": False,
                "Active": False,
                "SMS_Capable": False,
                "Line_Type": "Missing Credentials",
                "Carrier": "Missing Credentials",
            }

        try:
            phone_info = self.client.lookups.v2.phone_numbers(phone_number).fetch(
                fields='line_type_intelligence'
            )
            
            valid = phone_info.valid if hasattr(phone_info, 'valid') else False
            active = False
            sms_capable = False
            line_type = "Unknown"
            carrier = "Unknown"
            
            if hasattr(phone_info, 'line_type_intelligence') and phone_info.line_type_intelligence:
                line_type_data = phone_info.line_type_intelligence
                line_type = line_type_data.get('type', 'Unknown')
                carrier = line_type_data.get('carrier_name', 'Unknown')
                
                if line_type in ['mobile', 'voip']:
                    sms_capable = True
                
                if valid and carrier != "Unknown":
                    active = True
            
            return {
                "Valid": valid,
                "Active": active,
                "SMS_Capable": sms_capable,
                "Line_Type": line_type,
                "Carrier": carrier,
                "phone_number": phone_info.phone_number,
                "country_code": phone_info.country_code
            }
        except TwilioRestException as err:
            logger.error(f"Twilio API Error: {err.msg}")
            if settings.DEMO_MODE:
                return self._simple_lookup_number(phone_number, "demo_twilio_error_fallback")
            return {"Valid": False, "Active": False, "SMS_Capable": False, "Line_Type": "Error", "Carrier": "Error"}
        except Exception as e:
            logger.error(f"Unexpected Error: {e}")
            if settings.DEMO_MODE:
                return self._simple_lookup_number(phone_number, "demo_unexpected_error_fallback")
            return {"Valid": False, "Active": False, "SMS_Capable": False, "Line_Type": "Error", "Carrier": "Error"}

    def _simple_lookup_number(self, phone_number, reason):
        digits = "".join(filter(str.isdigit, str(phone_number or "")))
        valid = 10 <= len(digits) <= 13
        return {
            "Valid": valid,
            "Active": valid,
            "SMS_Capable": valid,
            "Line_Type": "mobile_demo" if valid else "invalid_demo",
            "Carrier": "Demo Carrier" if valid else "Demo Invalid",
            "Reason": reason if valid else "invalid_phone_format",
            "phone_number": phone_number,
            "country_code": "DEMO",
        }
    
    async def check_balance(self):
        return await asyncio.to_thread(self._check_balance_sync)

    def _check_balance_sync(self):
        try:
            balance = self.client.api.v2010.balance.fetch()
            return {"success": True, "balance": balance.balance, "currency": balance.currency}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def validate_number(self, phone_number):
        return await asyncio.to_thread(self._validate_number_sync, phone_number)

    def _validate_number_sync(self, phone_number):
        try:
            phone_info = self.client.lookups.v2.phone_numbers(phone_number).fetch()
            return {"success": True, "valid": phone_info.valid, "phone_number": phone_info.phone_number}
        except Exception as e:
            return {"success": False, "error": str(e)}
