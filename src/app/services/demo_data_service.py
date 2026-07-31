from src.app.db.database import fetch_one
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
    },
]


class DemoDataService:
    @staticmethod
    async def load_demo_leads(validate_contacts: bool = True) -> dict:
        leads = []
        created = 0
        duplicates = 0
        skipped_existing = 0

        for row in DEMO_LEADS:
            existing_same_row = DemoDataService._same_row_exists(row)
            if existing_same_row:
                leads.append(existing_same_row)
                skipped_existing += 1
                continue

            lead, was_duplicate = await LeadService.create_or_update_from_upload(
                row,
                validate_contacts=validate_contacts,
            )
            leads.append(lead)
            if was_duplicate:
                duplicates += 1
            else:
                created += 1

        return {
            "total_rows": len(DEMO_LEADS),
            "created": created,
            "merged_duplicates": duplicates,
            "skipped_existing": skipped_existing,
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
