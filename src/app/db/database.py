import sqlite3
from pathlib import Path
from typing import Any, Iterable
from src.app.core.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    territory TEXT DEFAULT '',
    property_type TEXT DEFAULT '',
    email_provider TEXT DEFAULT 'gmail',
    email_username TEXT DEFAULT '',
    email_password TEXT DEFAULT '',
    smtp_host TEXT DEFAULT '',
    smtp_port INTEGER DEFAULT 587,
    smtp_use_tls INTEGER DEFAULT 1,
    email_account_active INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    source TEXT DEFAULT '',
    property_type TEXT DEFAULT '',
    configuration TEXT DEFAULT '',
    location_preference TEXT DEFAULT '',
    budget TEXT DEFAULT '',
    timeline TEXT DEFAULT '',
    message TEXT DEFAULT '',
    email_status TEXT DEFAULT 'pending',
    phone_status TEXT DEFAULT 'pending',
    sms_capable TEXT DEFAULT '',
    carrier TEXT DEFAULT '',
    line_type TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    score_band TEXT DEFAULT 'Cold',
    score_breakdown TEXT DEFAULT '',
    validation_status TEXT DEFAULT 'Pending',
    validation_remarks TEXT DEFAULT '',
    status TEXT DEFAULT 'New',
    assigned_agent_id INTEGER,
    followup_step INTEGER DEFAULT 0,
    automation_status TEXT DEFAULT 'not_started',
    next_followup_at TEXT,
    last_contacted_at TEXT,
    replied_at TEXT,
    email_draft_subject TEXT DEFAULT '',
    email_draft_body TEXT DEFAULT '',
    email_sent_status TEXT DEFAULT 'not_sent',
    email_sent_at TEXT,
    call_consent INTEGER DEFAULT 0,
    do_not_call INTEGER DEFAULT 0,
    duplicate_of INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(assigned_agent_id) REFERENCES agents(id),
    FOREIGN KEY(duplicate_of) REFERENCES leads(id)
);

CREATE TABLE IF NOT EXISTS email_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    property_type TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    reply_rate REAL DEFAULT 0,
    conversion_rate REAL DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    template_id INTEGER,
    channel TEXT DEFAULT 'email',
    direction TEXT DEFAULT 'outbound',
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    status TEXT DEFAULT 'queued',
    error TEXT DEFAULT '',
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(lead_id) REFERENCES leads(id),
    FOREIGN KEY(template_id) REFERENCES email_templates(id)
);

CREATE TABLE IF NOT EXISTS email_generation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    template_id INTEGER,
    provider TEXT DEFAULT '',
    campaign_type TEXT DEFAULT '',
    tone TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    final_subject TEXT DEFAULT '',
    final_body TEXT DEFAULT '',
    selected_version TEXT DEFAULT 'generated',
    user_action TEXT DEFAULT 'generated',
    user_feedback TEXT DEFAULT '',
    guardrail_passed INTEGER DEFAULT 1,
    guardrail_issues TEXT DEFAULT '[]',
    judge_score INTEGER DEFAULT 0,
    judge_status TEXT DEFAULT 'pending',
    judge_reason TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    review_status TEXT DEFAULT '',
    admin_note TEXT DEFAULT '',
    llm_provider TEXT DEFAULT '',
    model TEXT DEFAULT '',
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(lead_id) REFERENCES leads(id),
    FOREIGN KEY(template_id) REFERENCES email_templates(id)
);

CREATE TABLE IF NOT EXISTS call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    agent_id INTEGER,
    call_sid TEXT DEFAULT '',
    script TEXT DEFAULT '',
    status TEXT DEFAULT 'queued',
    duration INTEGER DEFAULT 0,
    recording_sid TEXT DEFAULT '',
    recording_url TEXT DEFAULT '',
    recording_status TEXT DEFAULT '',
    recording_duration INTEGER DEFAULT 0,
    recording_available_at TEXT,
    error_message TEXT DEFAULT '',
    called_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(lead_id) REFERENCES leads(id),
    FOREIGN KEY(agent_id) REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT '',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection() -> sqlite3.Connection:
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        _migrate_existing_schema(conn)
        _seed_defaults(conn)


def fetch_all(query: str, params: Iterable[Any] = ()) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]


def fetch_one(query: str, params: Iterable[Any] = ()) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(query, tuple(params)).fetchone()
        return dict(row) if row else None


def execute(query: str, params: Iterable[Any] = ()) -> int:
    with get_connection() as conn:
        cur = conn.execute(query, tuple(params))
        conn.commit()
        return int(cur.lastrowid)


def execute_many(query: str, rows: list[Iterable[Any]]) -> None:
    with get_connection() as conn:
        conn.executemany(query, rows)
        conn.commit()


def _migrate_existing_schema(conn: sqlite3.Connection) -> None:
    agent_columns = {row["name"] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
    agent_additions = {
        "email_provider": "TEXT DEFAULT 'gmail'",
        "email_username": "TEXT DEFAULT ''",
        "email_password": "TEXT DEFAULT ''",
        "smtp_host": "TEXT DEFAULT ''",
        "smtp_port": "INTEGER DEFAULT 587",
        "smtp_use_tls": "INTEGER DEFAULT 1",
        "email_account_active": "INTEGER DEFAULT 1",
    }
    for column, definition in agent_additions.items():
        if column not in agent_columns:
            conn.execute(f"ALTER TABLE agents ADD COLUMN {column} {definition}")
    conn.execute("UPDATE agents SET email_username = email WHERE email_username = '' OR email_username IS NULL")

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
    additions = {
        "email_status": "TEXT DEFAULT 'pending'",
        "phone_status": "TEXT DEFAULT 'pending'",
        "sms_capable": "TEXT DEFAULT ''",
        "carrier": "TEXT DEFAULT ''",
        "line_type": "TEXT DEFAULT ''",
        "score": "INTEGER DEFAULT 0",
        "score_band": "TEXT DEFAULT 'Cold'",
        "score_breakdown": "TEXT DEFAULT ''",
        "validation_status": "TEXT DEFAULT 'Pending'",
        "validation_remarks": "TEXT DEFAULT ''",
        "assigned_agent_id": "INTEGER",
        "followup_step": "INTEGER DEFAULT 0",
        "automation_status": "TEXT DEFAULT 'not_started'",
        "next_followup_at": "TEXT",
        "last_contacted_at": "TEXT",
        "replied_at": "TEXT",
        "email_draft_subject": "TEXT DEFAULT ''",
        "email_draft_body": "TEXT DEFAULT ''",
        "email_sent_status": "TEXT DEFAULT 'not_sent'",
        "email_sent_at": "TEXT",
        "call_consent": "INTEGER DEFAULT 0",
        "do_not_call": "INTEGER DEFAULT 0",
        "duplicate_of": "INTEGER",
        "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in additions.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {column} {definition}")

    history_columns = {row["name"] for row in conn.execute("PRAGMA table_info(email_generation_history)").fetchall()}
    history_additions = {
        "is_active": "INTEGER DEFAULT 1",
        "review_status": "TEXT DEFAULT ''",
        "admin_note": "TEXT DEFAULT ''",
        "llm_provider": "TEXT DEFAULT ''",
        "model": "TEXT DEFAULT ''",
        "prompt_tokens": "INTEGER DEFAULT 0",
        "completion_tokens": "INTEGER DEFAULT 0",
        "total_tokens": "INTEGER DEFAULT 0",
        "estimated_cost": "REAL DEFAULT 0",
        "latency_ms": "INTEGER DEFAULT 0",
        "error_message": "TEXT DEFAULT ''",
    }
    for column, definition in history_additions.items():
        if column not in history_columns:
            conn.execute(f"ALTER TABLE email_generation_history ADD COLUMN {column} {definition}")
    conn.execute(
        """
        UPDATE email_generation_history
        SET review_status = user_action
        WHERE review_status = '' OR review_status IS NULL
        """
    )

    call_columns = {row["name"] for row in conn.execute("PRAGMA table_info(call_logs)").fetchall()}
    call_additions = {
        "recording_sid": "TEXT DEFAULT ''",
        "recording_url": "TEXT DEFAULT ''",
        "recording_status": "TEXT DEFAULT ''",
        "recording_duration": "INTEGER DEFAULT 0",
        "recording_available_at": "TEXT",
    }
    for column, definition in call_additions.items():
        if column not in call_columns:
            conn.execute(f"ALTER TABLE call_logs ADD COLUMN {column} {definition}")

    conn.execute(
        """
        INSERT OR IGNORE INTO app_settings (key, value)
        VALUES ('auto_email_send_enabled', 'false')
        """
    )


def _seed_defaults(conn: sqlite3.Connection) -> None:
    agent_count = conn.execute("SELECT COUNT(*) AS count FROM agents").fetchone()["count"]
    if agent_count == 0:
        conn.executemany(
            """
            INSERT INTO agents (name, email, territory, property_type, active)
            VALUES (?, ?, ?, ?, 1)
            """,
            [
                ("Amit Sales", "amit@example.com", "Wakad", "Apartment"),
                ("Priya Sales", "priya@example.com", "Baner", "Villa"),
            ],
        )

    template_count = conn.execute("SELECT COUNT(*) AS count FROM email_templates").fetchone()["count"]
    if template_count == 0:
        conn.executemany(
            """
            INSERT INTO email_templates
            (name, category, property_type, subject, body, reply_rate, conversion_rate, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            [
                (
                    "Hot apartment first touch",
                    "Hot",
                    "Apartment",
                    "Shortlisted {configuration} options in {location_preference}",
                    "Hi {name},\n\nBased on your interest in {configuration} {property_type} options around {location_preference}, we have a few matches that may fit {budget}. Would you like me to share the best options?\n\nRegards,\n{agent_name}",
                    0.32,
                    0.18,
                ),
                (
                    "Warm general nurture",
                    "Warm",
                    "",
                    "Property options matching your requirement",
                    "Hi {name},\n\nThanks for your inquiry. We can help you compare suitable {property_type} options around {location_preference}. Would you like a quick shortlist?\n\nRegards,\n{agent_name}",
                    0.21,
                    0.09,
                ),
                (
                    "Cold monthly nurture",
                    "Cold",
                    "",
                    "New property updates for {location_preference}",
                    "Hi {name},\n\nSharing a quick update in case you are still exploring properties around {location_preference}. We can send matching options whenever you are ready.\n\nRegards,\n{agent_name}",
                    0.08,
                    0.03,
                ),
            ],
        )
