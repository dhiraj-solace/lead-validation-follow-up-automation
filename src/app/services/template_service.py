from src.app.db.database import execute, fetch_all, fetch_one

class TemplateService:
    @staticmethod
    def list_templates() -> list[dict]:
        return fetch_all("SELECT * FROM email_templates ORDER BY active DESC, category, name")
    
    @staticmethod
    def create_template(data: dict) -> dict:
        template_id = execute(
            """
            INSERT INTO email_templates
            (name, category, property_type, subject, body, reply_rate, conversion_rate, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["category"],
                data.get("property_type", ""),
                data["subject"],
                data["body"],
                data.get("reply_rate", 0),
                data.get("conversion_rate", 0),
                1 if data.get("active", True) else 0,
            ),
        )
        return TemplateService.get_template(template_id)

    @staticmethod
    def get_template(template_id: int) -> dict | None:
        return fetch_one("SELECT * FROM email_templates WHERE id = ?", (template_id,))

    @staticmethod
    def select_template(lead: dict) -> dict | None:
        template = fetch_one(
            """
            SELECT *
            FROM email_templates
            WHERE active = 1
              AND lower(category) = lower(?)
              AND (property_type = '' OR lower(property_type) = lower(?))
            ORDER BY conversion_rate DESC, reply_rate DESC, id ASC
            LIMIT 1
            """,
            (lead.get("score_band", "Cold"), lead.get("property_type", "")),
        )
        if template:
            return template

        return fetch_one(
            """
            SELECT *
            FROM email_templates
            WHERE active = 1
            ORDER BY conversion_rate DESC, reply_rate DESC, id ASC
            LIMIT 1
            """
        )
    
    @staticmethod
    def render(template: str, lead: dict, agent: dict | None = None) -> str:
        values = {
            "name": lead.get("name", ""),
            "email": lead.get("email", ""),
            "phone": lead.get("phone", ""),
            "source": lead.get("source", ""),
            "property_type": lead.get("property_type", "property"),
            "configuration": lead.get("configuration", "suitable"),
            "location_preference": lead.get("location_preference", "your preferred location"),
            "budget": lead.get("budget", "your budget"),
            "timeline": lead.get("timeline", ""),
            "agent_name": (agent or {}).get("name", "Sales Team"),
        }

        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", str(value or ""))
        return rendered
