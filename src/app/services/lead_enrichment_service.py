import json
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

import httpx
from fastapi import HTTPException

from src.app.core.config import settings
from src.app.db.database import execute
from src.app.services.lead_service import LeadService


class LeadEnrichmentService:
    PROVIDER = "people_data_labs"

    @staticmethod
    def enrich_lead(lead_id: int) -> dict:
        lead = LeadService.get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found.")
        if lead.get("validation_status") != "Valid":
            raise HTTPException(status_code=400, detail="Only valid leads can be enriched.")

        params = LeadEnrichmentService.build_pdl_params(lead)
        if not params:
            result = LeadEnrichmentService.skipped_result("Lead needs email, phone, or name plus location for enrichment.")
            LeadEnrichmentService.save_result(lead, result)
            return {"success": False, "message": result["summary"], "lead": LeadService.get_lead(lead_id)}

        if not settings.PDL_API_KEY:
            raise HTTPException(status_code=400, detail="PDL_API_KEY is not configured.")

        try:
            response = httpx.get(
                settings.PDL_PERSON_ENRICH_URL,
                headers={"X-Api-Key": settings.PDL_API_KEY, "Accept": "application/json"},
                params=params,
                timeout=30.0,
            )
        except Exception as exc:
            result = LeadEnrichmentService.failed_result(f"People Data Labs request failed: {exc}")
            LeadEnrichmentService.save_result(lead, result)
            raise HTTPException(status_code=400, detail=result["summary"]) from exc

        if response.status_code == 404:
            result = LeadEnrichmentService.not_found_result("No matching People Data Labs profile found.")
            LeadEnrichmentService.save_result(lead, result)
            return {"success": True, "message": result["summary"], "lead": LeadService.get_lead(lead_id)}

        try:
            payload = response.json()
        except ValueError as exc:
            result = LeadEnrichmentService.failed_result("People Data Labs returned a non-JSON response.")
            LeadEnrichmentService.save_result(lead, result)
            raise HTTPException(status_code=400, detail=result["summary"]) from exc

        if response.status_code >= 400:
            message = payload.get("error", {}).get("message") if isinstance(payload.get("error"), dict) else response.text
            result = LeadEnrichmentService.failed_result(f"People Data Labs error: {message}")
            LeadEnrichmentService.save_result(lead, result)
            raise HTTPException(status_code=400, detail=result["summary"])

        result = LeadEnrichmentService.matched_result(lead, payload)
        LeadEnrichmentService.save_result(lead, result)
        return {"success": True, "message": result["summary"], "lead": LeadService.get_lead(lead_id)}

    @staticmethod
    def build_pdl_params(lead: dict) -> dict:
        params: dict[str, Any] = {"min_likelihood": 5}
        email = str(lead.get("email") or "").strip()
        phone = LeadService._normalize_phone(str(lead.get("phone") or "").strip())
        name = str(lead.get("name") or "").replace("_", " ").strip()
        location = str(lead.get("location_preference") or "").strip()
        if email:
            params["email"] = email
        if phone and phone.startswith("+"):
            params["phone"] = phone
        if name and " " in name:
            params["name"] = name
        if location:
            params["location"] = location
        if params.keys() == {"min_likelihood"}:
            return {}
        return params

    @staticmethod
    def matched_result(lead: dict, payload: dict) -> dict:
        data = payload.get("data") or {}
        confidence = int(payload.get("likelihood") or 0)
        email_match = LeadEnrichmentService.email_matches(lead, data)
        phone_match = LeadEnrichmentService.phone_matches(lead, data)
        name_match = LeadEnrichmentService.name_similarity(str(lead.get("name") or ""), str(data.get("full_name") or "")) >= 0.72
        profiles = LeadEnrichmentService.extract_profiles(data)
        company = LeadEnrichmentService.extract_company(data)
        title = LeadEnrichmentService.extract_title(data)
        location = LeadEnrichmentService.extract_location(data)
        summary_parts = [f"PDL matched profile with confidence {confidence}/10"]
        if data.get("full_name"):
            summary_parts.append(f"name: {data.get('full_name')}")
        if company:
            summary_parts.append(f"company: {company}")
        if title:
            summary_parts.append(f"title: {title}")
        if profiles:
            summary_parts.append("social profile found")
        match_notes = []
        if email_match:
            match_notes.append("email matched")
        if phone_match:
            match_notes.append("phone matched")
        if name_match:
            match_notes.append("name matched")
        if match_notes:
            summary_parts.append(", ".join(match_notes))
        return {
            "status": "matched",
            "confidence": confidence,
            "score_delta": 0,
            "summary": "; ".join(summary_parts),
            "data": payload,
            "full_name": str(data.get("full_name") or ""),
            "company": company,
            "title": title,
            "location": location,
            "profiles": profiles,
        }

    @staticmethod
    def save_result(lead: dict, result: dict) -> None:
        score_delta = 0
        validation_remarks = LeadEnrichmentService.merge_remarks(lead.get("validation_remarks"), result.get("summary"))
        execute(
            """
            UPDATE leads
            SET enrichment_status = ?,
                enrichment_provider = ?,
                enrichment_confidence = ?,
                enrichment_score_delta = ?,
                enrichment_summary = ?,
                enrichment_data = ?,
                enrichment_full_name = ?,
                enrichment_company = ?,
                enrichment_title = ?,
                enrichment_location = ?,
                enrichment_profiles = ?,
                enriched_at = ?,
                validation_remarks = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                result.get("status", ""),
                LeadEnrichmentService.PROVIDER,
                int(result.get("confidence") or 0),
                score_delta,
                result.get("summary", ""),
                json.dumps(result.get("data") or {}),
                result.get("full_name", ""),
                result.get("company", ""),
                result.get("title", ""),
                result.get("location", ""),
                json.dumps(result.get("profiles") or []),
                datetime.utcnow().isoformat(timespec="seconds"),
                validation_remarks,
                lead["id"],
            ),
        )

    @staticmethod
    def email_matches(lead: dict, data: dict) -> bool:
        lead_email = str(lead.get("email") or "").strip().lower()
        if not lead_email:
            return False
        return lead_email in {email.lower() for email in LeadEnrichmentService.extract_emails(data)}

    @staticmethod
    def phone_matches(lead: dict, data: dict) -> bool:
        lead_phone = LeadEnrichmentService.digits(lead.get("phone"))
        if not lead_phone:
            return False
        return any(LeadEnrichmentService.digits(phone).endswith(lead_phone[-10:]) for phone in LeadEnrichmentService.extract_phones(data))

    @staticmethod
    def extract_emails(data: dict) -> list[str]:
        values = data.get("emails") or []
        emails = []
        for item in values if isinstance(values, list) else []:
            emails.append(str(item.get("address") if isinstance(item, dict) else item or "").strip())
        return [email for email in emails if email]

    @staticmethod
    def extract_phones(data: dict) -> list[str]:
        values = data.get("phone_numbers") or data.get("phones") or []
        phones = []
        for item in values if isinstance(values, list) else []:
            phones.append(str(item.get("number") if isinstance(item, dict) else item or "").strip())
        return [phone for phone in phones if phone]

    @staticmethod
    def extract_profiles(data: dict) -> list[str]:
        profiles = data.get("profiles") or []
        urls = []
        for item in profiles if isinstance(profiles, list) else []:
            value = item.get("url") if isinstance(item, dict) else item
            if value:
                urls.append(LeadEnrichmentService.normalize_profile_url(str(value)))
        linkedin = data.get("linkedin_url") or data.get("linkedin_username")
        if linkedin:
            urls.insert(0, LeadEnrichmentService.normalize_linkedin_url(str(linkedin)))
        return list(dict.fromkeys(url for url in urls if url))

    @staticmethod
    def normalize_linkedin_url(value: str) -> str:
        profile = value.strip()
        if not profile:
            return ""
        if profile.startswith("http://") or profile.startswith("https://"):
            return profile
        if "linkedin.com/" in profile:
            return f"https://{profile.lstrip('/')}"
        return f"https://linkedin.com/in/{profile.strip('/')}"

    @staticmethod
    def normalize_profile_url(value: str) -> str:
        profile = value.strip()
        if not profile:
            return ""
        if profile.startswith("http://") or profile.startswith("https://"):
            return profile
        return f"https://{profile.lstrip('/')}"

    @staticmethod
    def extract_company(data: dict) -> str:
        job_company = data.get("job_company_name") or data.get("job_company_website")
        if job_company:
            return str(job_company)
        experience = data.get("experience") or []
        if isinstance(experience, list) and experience:
            company = experience[0].get("company", {}) if isinstance(experience[0], dict) else {}
            return str(company.get("name") or "")
        return ""

    @staticmethod
    def extract_title(data: dict) -> str:
        return str(data.get("job_title") or data.get("job_title_role") or "")

    @staticmethod
    def extract_location(data: dict) -> str:
        return str(data.get("location_name") or data.get("location_locality") or data.get("location_region") or "")

    @staticmethod
    def name_similarity(left: str, right: str) -> float:
        return SequenceMatcher(None, left.lower().replace("_", " "), right.lower()).ratio() if left and right else 0

    @staticmethod
    def digits(value: object) -> str:
        return "".join(filter(str.isdigit, str(value or "")))

    @staticmethod
    def merge_remarks(existing: object, summary: object) -> str:
        base = str(existing or "").strip()
        enrichment = f"Enrichment: {summary}" if summary else "Enrichment checked."
        if not base:
            return enrichment
        if "Enrichment:" in base:
            base = base.split("Enrichment:", 1)[0].strip()
        return f"{base} {enrichment}".strip()[:1200]

    @staticmethod
    def skipped_result(summary: str) -> dict:
        return {"status": "skipped", "confidence": 0, "score_delta": 0, "summary": summary, "data": {}}

    @staticmethod
    def not_found_result(summary: str) -> dict:
        return {"status": "not_found", "confidence": 0, "score_delta": 0, "summary": summary, "data": {}}

    @staticmethod
    def failed_result(summary: str) -> dict:
        return {"status": "failed", "confidence": 0, "score_delta": 0, "summary": summary, "data": {}}

    @staticmethod
    def demo_result(lead: dict) -> dict:
        payload = {
            "status": 200,
            "likelihood": 8,
            "data": {
                "full_name": str(lead.get("name") or "").replace("_", " ").title(),
                "job_title": "Property Buyer",
                "job_company_name": "Demo Verified Profile",
                "location_name": lead.get("location_preference") or "",
                "emails": [{"address": lead.get("email", "")}],
                "phone_numbers": [{"number": lead.get("phone", "")}],
                "profiles": [{"url": "https://linkedin.com/in/demo-lead"}],
            },
        }
        return LeadEnrichmentService.matched_result(lead, payload)
