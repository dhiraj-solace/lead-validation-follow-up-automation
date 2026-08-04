from datetime import datetime, timedelta

from src.app.db.database import execute, fetch_one
from src.app.services.lead_service import LeadService


DEMO_LEADS = [
    {
        "name": "Ananya Iyer",
        "email": "ananya.iyer@example.com",
        "phone": "+919876543210",
        "source": "Referral",
        "property_type": "Apartment",
        "configuration": "2-BHK",
        "location_preference": "Wakad",
        "budget": "85 lakh",
        "timeline": "immediate",
        "message": "Looking for a ready or near-ready 2 BHK in Wakad with good connectivity.",
        "call_consent": "yes",
        "do_not_call": "no",
    },
    {
        "name": "Manav Joshi",
        "email": "manav.joshi@example.com",
        "phone": "+919812345678",
        "source": "MagicBricks Portal",
        "property_type": "Villa",
        "configuration": "3-BHK",
        "location_preference": "Baner",
        "budget": "1.6 crore",
        "timeline": "within 60 days",
        "message": "Interested in ready possession villa options near Baner for family use.",
        "call_consent": "yes",
        "do_not_call": "no",
    },
    {
        "name": "Kavita Rao",
        "email": "kavita.rao@example.com",
        "phone": "+919822334455",
        "source": "Website",
        "property_type": "Apartment",
        "configuration": "3-BHK",
        "location_preference": "Hinjewadi",
        "budget": "1.1 crore",
        "timeline": "3 months",
        "message": "Need a spacious 3 BHK near IT park with parking and good school access.",
        "call_consent": "yes",
        "do_not_call": "no",
    },
    {
        "name": "Dev Patel",
        "email": "dev.patel@example.com",
        "phone": "+919900112233",
        "source": "Instagram Ad",
        "property_type": "Plot",
        "configuration": "Residential plot",
        "location_preference": "Kharadi",
        "budget": "70 lakh",
        "timeline": "6 months",
        "message": "Exploring residential plot investment options, not urgent but open to strong deals.",
        "call_consent": "no",
        "do_not_call": "no",
    },
    {
        "name": "Ananya Iyer Duplicate",
        "email": "ananya.iyer@example.com",
        "phone": "+919876543210",
        "source": "99acres Portal",
        "property_type": "Apartment",
        "configuration": "2-BHK",
        "location_preference": "Wakad",
        "budget": "85 lakh",
        "timeline": "immediate",
        "message": "Duplicate portal inquiry for same buyer and same phone number.",
        "call_consent": "yes",
        "do_not_call": "no",
    },
    {
        "name": "Ritu Malhotra",
        "email": "ritu.malhotra",
        "phone": "+919833221100",
        "source": "Facebook Lead Ad",
        "property_type": "Apartment",
        "configuration": "1-BHK",
        "location_preference": "Pimple Saudagar",
        "budget": "45 lakh",
        "timeline": "soon",
        "message": "Invalid email example to test validation remarks.",
        "call_consent": "yes",
        "do_not_call": "no",
    },
    {
        "name": "Sameer Khan",
        "email": "sameer.khan@example.com",
        "phone": "12345",
        "source": "Cold Ad",
        "property_type": "Apartment",
        "configuration": "2-BHK",
        "location_preference": "Undri",
        "budget": "55 lakh",
        "timeline": "later",
        "message": "Invalid phone example to test phone validation and cold scoring.",
        "call_consent": "no",
        "do_not_call": "yes",
    },
]

DEMO_CALL_STATUSES = ["completed", "answered", "busy", "no-answer", "failed"]
DEMO_WHATSAPP_STATUSES = ["sent", "delivered", "read", "failed"]


class DemoDataService:
    @staticmethod
    async def load_demo_leads(validate_contacts: bool = True) -> dict:
        leads = []
        created = 0
        duplicates = 0
        skipped_existing = 0

        for index, row in enumerate(DEMO_LEADS):
            existing_same_row = DemoDataService._same_row_exists(row)
            if existing_same_row:
                DemoDataService._refresh_demo_flags(existing_same_row["id"], row)
                lead = DemoDataService._apply_demo_profile(existing_same_row["id"], row, index)
                leads.append(lead)
                skipped_existing += 1
                continue

            lead, was_duplicate = await LeadService.create_or_update_from_upload(
                row,
                validate_contacts=validate_contacts,
            )
            if lead and lead.get("validation_status") != "Duplicate":
                lead = DemoDataService._apply_demo_profile(lead["id"], row, index)
            leads.append(lead)
            if was_duplicate:
                duplicates += 1
            else:
                created += 1

        seeded_calls = 0
        seeded_whatsapp = 0
        for index, lead in enumerate(leads):
            seeded_calls += DemoDataService._seed_call_history(lead, index)
            seeded_whatsapp += DemoDataService._seed_whatsapp_history(lead, index)

        return {
            "total_rows": len(DEMO_LEADS),
            "created": created,
            "merged_duplicates": duplicates,
            "skipped_existing": skipped_existing,
            "seeded_calls": seeded_calls,
            "seeded_whatsapp": seeded_whatsapp,
            "valid": sum(1 for lead in leads if lead["validation_status"] == "Valid"),
            "invalid": sum(1 for lead in leads if lead["validation_status"] == "Invalid"),
            "duplicate": sum(1 for lead in leads if lead["validation_status"] == "Duplicate"),
            "hot": sum(1 for lead in leads if lead["score_band"] == "Hot"),
            "warm": sum(1 for lead in leads if lead["score_band"] == "Warm"),
            "cold": sum(1 for lead in leads if lead["score_band"] == "Cold"),
            "leads": leads,
        }

    @staticmethod
    def _same_row_exists(row: dict) -> dict | None:
        return fetch_one(
            """
            SELECT *
            FROM leads
            WHERE lower(email) = lower(?)
              AND phone = ?
              AND lower(name) = lower(?)
            LIMIT 1
            """,
            (row.get("email", ""), row.get("phone", ""), row.get("name", "")),
        )

    @staticmethod
    def _refresh_demo_flags(lead_id: int, row: dict) -> None:
        execute(
            """
            UPDATE leads
            SET call_consent = ?,
                do_not_call = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                1 if LeadService._truthy(row.get("call_consent")) else 0,
                1 if LeadService._truthy(row.get("do_not_call")) else 0,
                lead_id,
            ),
        )

    @staticmethod
    def _apply_demo_profile(lead_id: int, row: dict, index: int) -> dict:
        if index == 4:
            return LeadService.get_lead(lead_id) or {}

        demo_scores = [
            (100, "Hot", "Valid", "Hot"),
            (92, "Hot", "Valid", "Hot"),
            (88, "Hot", "Valid", "Hot"),
            (64, "Warm", "Valid", "Warm"),
            (49, "Cold", "Invalid", "Invalid"),
            (35, "Cold", "Invalid", "Invalid"),
        ]
        score, band, validation, status = demo_scores[index if index < 4 else index - 1]
        agent = fetch_one(
            """
            SELECT id
            FROM agents
            WHERE active = 1
              AND (lower(territory) = lower(?) OR lower(property_type) = lower(?))
            ORDER BY
              CASE WHEN lower(territory) = lower(?) THEN 0 ELSE 1 END,
              id ASC
            LIMIT 1
            """,
            (
                row.get("location_preference", ""),
                row.get("property_type", ""),
                row.get("location_preference", ""),
            ),
        )
        remarks = (
            "Lead passed demo validation and is ready for outreach."
            if validation == "Valid"
            else "Demo invalid lead retained to show blocked outreach and validation remarks."
        )
        execute(
            """
            UPDATE leads
            SET email_status = ?,
                phone_status = ?,
                score = ?,
                score_band = ?,
                score_breakdown = ?,
                validation_status = ?,
                validation_remarks = ?,
                status = ?,
                assigned_agent_id = ?,
                automation_status = ?,
                call_consent = ?,
                do_not_call = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                "valid" if validation == "Valid" else "invalid",
                "valid" if validation == "Valid" else "invalid",
                score,
                band,
                DemoDataService._score_breakdown(score, band),
                validation,
                remarks,
                status,
                agent["id"] if agent and validation == "Valid" and band in {"Hot", "Warm"} else None,
                "active" if validation == "Valid" and band in {"Hot", "Warm"} else "not_started",
                1 if LeadService._truthy(row.get("call_consent")) else 0,
                1 if LeadService._truthy(row.get("do_not_call")) else 0,
                lead_id,
            ),
        )
        return LeadService.get_lead(lead_id) or {}

    @staticmethod
    def _score_breakdown(score: int, band: str) -> str:
        if band == "Hot":
            return "Email Valid (+20), Phone Valid (+20), High Intent Source (+15), Budget Fit (+15), Location Match (+10), Immediate Timeline (+15), Detailed Inquiry (+5)"
        if band == "Warm":
            return "Email Valid (+20), Phone Valid (+20), Moderate Source (+8), Budget Fit (+10), Location Match (+6)"
        return f"Validation Cap ({score})"

    @staticmethod
    def _seed_call_history(lead: dict, index: int) -> int:
        if not lead or lead.get("validation_status") == "Duplicate":
            return 0
        exists = fetch_one("SELECT id FROM call_logs WHERE lead_id = ? AND call_sid LIKE 'DEMO-CALL-%' LIMIT 1", (lead["id"],))
        if exists:
            return 0

        status = DEMO_CALL_STATUSES[index % len(DEMO_CALL_STATUSES)]
        called_at = (datetime.utcnow() - timedelta(days=2 + index, hours=index)).isoformat(timespec="seconds")
        duration = 92 if status in {"completed", "answered"} else 0
        recording_ready = status in {"completed", "answered"}
        recording_status = "completed" if recording_ready else "failed" if status == "failed" else "not_available"
        script = (
            f"Hello {lead.get('name')}, this is {lead.get('assigned_agent_name') or 'your property advisor'} "
            f"following up on your {lead.get('configuration')} {lead.get('property_type')} requirement in "
            f"{lead.get('location_preference')}. We have a shortlist matching your budget of {lead.get('budget')}."
        )
        execute(
            """
            INSERT INTO call_logs (
                lead_id, agent_id, call_sid, script, status, duration,
                recording_sid, recording_url, recording_status, recording_duration, recording_available_at,
                error_message, called_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead["id"],
                lead.get("assigned_agent_id"),
                f"DEMO-CALL-{lead['id']}-{index + 1:03d}",
                script,
                status,
                duration,
                f"DEMO-REC-{lead['id']}-{index + 1:03d}" if recording_ready else "",
                f"https://api.twilio.com/demo/recordings/DEMO-REC-{lead['id']}-{index + 1:03d}.mp3" if recording_ready else "",
                recording_status,
                duration if recording_ready else 0,
                called_at if recording_ready else None,
                "Demo provider outage example." if status == "failed" else "",
                called_at,
                called_at,
            ),
        )
        return 1

    @staticmethod
    def _seed_whatsapp_history(lead: dict, index: int) -> int:
        if not lead or lead.get("validation_status") == "Duplicate":
            return 0
        exists = fetch_one(
            "SELECT id FROM message_logs WHERE lead_id = ? AND channel = 'whatsapp' AND subject LIKE 'Demo WhatsApp%' LIMIT 1",
            (lead["id"],),
        )
        if exists:
            return 0

        status = DEMO_WHATSAPP_STATUSES[index % len(DEMO_WHATSAPP_STATUSES)]
        sent_at = (datetime.utcnow() - timedelta(days=1 + index, minutes=15 * index)).isoformat(timespec="seconds")
        body = (
            f"Hi {lead.get('name')}, we found {lead.get('configuration')} {lead.get('property_type')} options in "
            f"{lead.get('location_preference')} around {lead.get('budget')}. Reply YES and our advisor will share details."
        )
        execute(
            """
            INSERT INTO message_logs (lead_id, channel, direction, subject, body, status, error, sent_at)
            VALUES (?, 'whatsapp', 'outbound', ?, ?, ?, ?, ?)
            """,
            (
                lead["id"],
                f"Demo WhatsApp {status}",
                body,
                status,
                "Demo failed delivery example." if status == "failed" else "",
                sent_at,
            ),
        )
        return 1
