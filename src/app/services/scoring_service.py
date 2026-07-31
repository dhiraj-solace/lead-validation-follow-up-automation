class LeadScoringService:
    INVALID_SCORE_CAP = 49

    @staticmethod
    def calculate_score(data: dict) -> dict:
        score = 0
        breakdown = []

        email_status = str(data.get("email_status", "")).lower()
        phone_status = str(data.get("phone_status", "")).lower()
        source = str(data.get("source", "")).lower()
        budget = str(data.get("budget", "")).strip()
        timeline = str(data.get("timeline", "")).lower()
        location = str(data.get("location_preference", "")).strip()
        property_type = str(data.get("property_type", "")).strip()
        configuration = str(data.get("configuration", "")).strip()
        message = str(data.get("message", "")).strip()

        if email_status == "valid":
            score += 20
            breakdown.append("Email Valid (+20)")
        elif email_status == "risky":
            score += 10
            breakdown.append("Email Risky (+10)")
        elif email_status in {"invalid", "error", "missing"}:
            breakdown.append("Email Invalid (+0)")
        elif email_status:
            breakdown.append("Email Not Verified (+0)")

        if phone_status == "valid":
            score += 20
            breakdown.append("Phone Valid (+20)")
        elif phone_status in {"invalid", "error", "missing"}:
            breakdown.append("Phone Invalid (+0)")
        elif phone_status:
            breakdown.append("Phone Not Verified (+0)")

        if "referral" in source:
            score += 15
            breakdown.append("Referral Source (+15)")
        elif any(term in source for term in ["website", "portal", "organic"]):
            score += 10
            breakdown.append("Strong Source (+10)")
        elif source:
            score += 5
            breakdown.append("Basic Source (+5)")

        if budget:
            score += 15
            breakdown.append("Budget Provided (+15)")

        if location:
            score += 10
            breakdown.append("Location Preference (+10)")

        if property_type and configuration:
            score += 10
            breakdown.append("Clear Requirement (+10)")
        elif property_type or configuration:
            score += 5
            breakdown.append("Partial Requirement (+5)")

        if any(term in timeline for term in ["immediate", "now", "week", "month", "30", "60", "soon"]):
            score += 15
            breakdown.append("Near Timeline (+15)")
        elif timeline:
            score += 8
            breakdown.append("Timeline Provided (+8)")

        if len(message) >= 20:
            score += 10
            breakdown.append("Detailed Inquiry (+10)")

        raw_score = score
        score = min(raw_score, 100)
        if raw_score > 100:
            breakdown.append(f"Score Cap (-{raw_score - score})")

        if score >= 80:
            score_band = "Hot"
        elif score >= 50:
            score_band = "Warm"
        else:
            score_band = "Cold"

        return {
            "lead_score": score,
            "score_band": score_band,
            "score_breakdown": ", ".join(breakdown),
        }

    @staticmethod
    def apply_invalid_validation_cap(scoring: dict, reason: str = "Validation failed") -> dict:
        breakdown = scoring.get("score_breakdown", "")
        current_score = min(int(scoring.get("lead_score", 0)), 100)
        capped_score = min(current_score, LeadScoringService.INVALID_SCORE_CAP)
        cap_points = current_score - capped_score
        cap_note = (
            f"{reason} (-{cap_points})"
            if cap_points > 0
            else f"{reason} (+0)"
        )
        return {
            "lead_score": capped_score,
            "score_band": "Cold",
            "score_breakdown": f"{breakdown}, {cap_note}" if breakdown else cap_note,
        }
