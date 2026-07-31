from src.app.db.database import execute, fetch_all, fetch_one

EMAIL_PROVIDER_DEFAULTS = {
    "gmail": {"label": "Gmail / Google Workspace", "smtp_host": "smtp.gmail.com", "smtp_port": 587, "smtp_use_tls": 1},
    "outlook": {"label": "Outlook / Microsoft 365", "smtp_host": "smtp.office365.com", "smtp_port": 587, "smtp_use_tls": 1},
    "yahoo": {"label": "Yahoo Mail", "smtp_host": "smtp.mail.yahoo.com", "smtp_port": 587, "smtp_use_tls": 1},
    "hostinger": {"label": "Hostinger Email", "smtp_host": "smtp.hostinger.com", "smtp_port": 587, "smtp_use_tls": 1},
    "custom": {"label": "Custom SMTP", "smtp_host": "", "smtp_port": 587, "smtp_use_tls": 1},
}


class AgentService:
    @staticmethod
    def list_agents() -> list[dict]:
        return fetch_all("SELECT * FROM agents ORDER BY active DESC, name")

    @staticmethod
    def create_agent(data: dict) -> dict:
        email_provider = AgentService._normalize_provider(data.get("email_provider", "gmail"))
        defaults = EMAIL_PROVIDER_DEFAULTS[email_provider]
        email_username = data.get("email_username") or data["email"]
        smtp_host = data.get("smtp_host") or defaults["smtp_host"]
        smtp_port = int(data.get("smtp_port") or defaults["smtp_port"] or 587)
        agent_id = execute(
            """
            INSERT INTO agents (
                name, email, territory, property_type, email_provider, email_username,
                email_password, smtp_host, smtp_port, smtp_use_tls, email_account_active, active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["email"],
                data.get("territory", ""),
                data.get("property_type", ""),
                email_provider,
                email_username,
                data.get("email_password", ""),
                smtp_host,
                smtp_port,
                1 if data.get("smtp_use_tls", True) else 0,
                1 if data.get("email_account_active", True) else 0,
                1 if data.get("active", True) else 0,
            ),
        )
        return AgentService.get_agent(agent_id)

    @staticmethod
    def get_agent(agent_id: int) -> dict | None:
        return fetch_one("SELECT * FROM agents WHERE id = ?", (agent_id,))

    @staticmethod
    def get_sender_config(agent: dict | None) -> dict | None:
        if not agent:
            return None
        if not int(agent.get("email_account_active") or 0):
            return None

        provider = AgentService._normalize_provider(agent.get("email_provider", "gmail"))
        defaults = EMAIL_PROVIDER_DEFAULTS[provider]
        smtp_host = agent.get("smtp_host") or defaults["smtp_host"]
        smtp_port = int(agent.get("smtp_port") or defaults["smtp_port"] or 587)
        from_email = agent.get("email_username") or agent.get("email") or ""

        return {
            "provider": provider,
            "provider_label": defaults["label"],
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_use_tls": bool(agent.get("smtp_use_tls", 1)),
            "smtp_username": from_email,
            "smtp_password": agent.get("email_password", ""),
            "from_email": from_email,
            "from_name": agent.get("name", "Sales Team"),
        }

    @staticmethod
    def choose_agent(lead: dict) -> dict | None:
        agents = fetch_all(
            """
            SELECT a.*, COUNT(l.id) AS active_leads
            FROM agents a
            LEFT JOIN leads l ON l.assigned_agent_id = a.id AND l.status NOT IN ('Cold', 'Responded')
            WHERE a.active = 1
              AND (? = '' OR a.territory = '' OR lower(a.territory) = lower(?))
              AND (? = '' OR a.property_type = '' OR lower(a.property_type) = lower(?))
            GROUP BY a.id
            ORDER BY active_leads ASC, a.id ASC
            LIMIT 1
            """,
            (
                lead.get("location_preference", ""),
                lead.get("location_preference", ""),
                lead.get("property_type", ""),
                lead.get("property_type", ""),
            ),
        )
        if agents:
            return agents[0]

        fallback = fetch_all(
            """
            SELECT a.*, COUNT(l.id) AS active_leads
            FROM agents a
            LEFT JOIN leads l ON l.assigned_agent_id = a.id AND l.status NOT IN ('Cold', 'Responded')
            WHERE a.active = 1
            GROUP BY a.id
            ORDER BY active_leads ASC, a.id ASC
            LIMIT 1
            """
        )
        return fallback[0] if fallback else None

    @staticmethod
    def _normalize_provider(value: str | None) -> str:
        provider = str(value or "gmail").strip().lower()
        return provider if provider in EMAIL_PROVIDER_DEFAULTS else "custom"
