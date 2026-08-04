from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import Any, Iterable

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument

from src.app.core.config import settings


client: MongoClient | None = None
logger = logging.getLogger(__name__)


def _db():
    global client
    if client is None:
        logger.info("mongo.connect.start db=%s", settings.MONGODB_DB_NAME)
        client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=8000)
    return client[settings.MONGODB_DB_NAME]


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _clean(doc: dict | None) -> dict | None:
    if not doc:
        return None
    data = dict(doc)
    data.pop("_id", None)
    return data


def _clean_many(rows: Iterable[dict]) -> list[dict]:
    return [_clean(row) or {} for row in rows]


def _lead_defaults(row: dict) -> dict:
    row.setdefault("email_status", "pending")
    row.setdefault("phone_status", "pending")
    row.setdefault("score", 0)
    row.setdefault("score_band", "Cold")
    row.setdefault("score_breakdown", "")
    row.setdefault("validation_status", row.get("status") or "Pending")
    row.setdefault("validation_remarks", "")
    row.setdefault("status", row.get("validation_status") or "Pending")
    row.setdefault("automation_status", "not_started")
    return row


def _next_id(collection: str) -> int:
    row = _db().counters.find_one_and_update(
        {"_id": collection},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(row["seq"])


def _insert(collection: str, data: dict) -> int:
    row = {key: value for key, value in data.items() if value is not None}
    row["id"] = _next_id(collection)
    row.setdefault("created_at", _now())
    row.setdefault("updated_at", row["created_at"])
    _db()[collection].insert_one(row)
    return int(row["id"])


def _sort_key(*fields: tuple[str, int]):
    return [(field, direction) for field, direction in fields]


def _lower(value: object) -> str:
    return str(value or "").strip().lower()


def init_db() -> None:
    db = _db()
    db.command("ping")
    logger.info("mongo.ping.ok db=%s", settings.MONGODB_DB_NAME)
    for name in ["agents", "leads", "email_templates", "message_logs", "email_generation_history", "call_logs"]:
        db[name].create_index("id", unique=True)
    db.leads.create_index("email")
    db.leads.create_index("phone")
    db.leads.create_index("assigned_agent_id")
    db.message_logs.create_index([("lead_id", ASCENDING), ("sent_at", DESCENDING)])
    db.call_logs.create_index([("lead_id", ASCENDING), ("called_at", DESCENDING)])
    db.email_generation_history.create_index([("lead_id", ASCENDING), ("id", DESCENDING)])
    _seed_defaults()
    logger.info("mongo.init.complete db=%s", settings.MONGODB_DB_NAME)


def fetch_one(query: str, params: Iterable[Any] = ()) -> dict | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def fetch_all(query: str, params: Iterable[Any] = ()) -> list[dict]:
    q = _normalize_query(query)
    params = tuple(params or ())

    if "from agents" in q:
        return _fetch_agents(q, params)
    if "from email_templates" in q:
        return _fetch_templates(q, params)
    if "from app_settings" in q:
        return _fetch_app_settings(q, params)
    if "from leads" in q or "from leads l" in q:
        return _fetch_leads(q, params)
    if "from message_logs" in q:
        return _fetch_message_logs(q, params)
    if "from call_logs" in q or "from call_logs c" in q:
        return _fetch_call_logs(q, params)
    if "from email_generation_history" in q or "from email_generation_history h" in q:
        return _fetch_email_history(q, params)

    raise NotImplementedError(f"Mongo query not implemented: {query.strip()[:160]}")


def execute(query: str, params: Iterable[Any] = ()) -> int:
    q = _normalize_query(query)
    params = tuple(params or ())

    if q.startswith("insert into agents"):
        fields = [
            "name",
            "email",
            "territory",
            "property_type",
            "email_provider",
            "email_username",
            "email_password",
            "smtp_host",
            "smtp_port",
            "smtp_use_tls",
            "email_account_active",
            "active",
        ]
        return _insert("agents", dict(zip(fields, params)))

    if q.startswith("insert into email_templates"):
        fields = ["name", "category", "property_type", "subject", "body", "reply_rate", "conversion_rate", "active"]
        return _insert("email_templates", dict(zip(fields, params)))

    if q.startswith("insert into leads"):
        return _insert("leads", _lead_insert_payload(q, params))

    if q.startswith("insert into message_logs"):
        return _insert("message_logs", _message_insert_payload(q, params))

    if q.startswith("insert into call_logs"):
        return _insert("call_logs", _call_insert_payload(q, params))

    if q.startswith("insert into email_generation_history"):
        fields = [
            "lead_id",
            "template_id",
            "provider",
            "campaign_type",
            "tone",
            "subject",
            "body",
            "final_subject",
            "final_body",
            "selected_version",
            "user_action",
            "user_feedback",
            "guardrail_passed",
            "guardrail_issues",
            "judge_score",
            "judge_status",
            "judge_reason",
            "is_active",
            "review_status",
            "llm_provider",
            "model",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "estimated_cost",
            "latency_ms",
            "error_message",
        ]
        return _insert("email_generation_history", dict(zip(fields, params)))

    if q.startswith("insert into app_settings"):
        value = params[0] if params else "false"
        _db().app_settings.update_one(
            {"key": "auto_email_send_enabled"},
            {"$set": {"key": "auto_email_send_enabled", "value": value, "updated_at": _now()}},
            upsert=True,
        )
        return 0

    if q.startswith("update leads"):
        return _update_leads(q, params)
    if q.startswith("update call_logs"):
        return _update_call_logs(q, params)
    if q.startswith("update email_generation_history"):
        return _update_email_history(q, params)
    if q.startswith("delete from leads"):
        if "duplicate_of = ?" in q:
            _db().leads.delete_many({"duplicate_of": int(params[0])})
        else:
            _db().leads.delete_one({"id": int(params[0])})
        return 0
    if q.startswith("delete from message_logs"):
        _db().message_logs.delete_many({"lead_id": int(params[0])})
        return 0
    if q.startswith("delete from call_logs"):
        _db().call_logs.delete_many({"lead_id": int(params[0])})
        return 0
    if q.startswith("delete from email_generation_history"):
        _db().email_generation_history.delete_many({"lead_id": int(params[0])})
        return 0

    raise NotImplementedError(f"Mongo execute not implemented: {query.strip()[:160]}")


def execute_many(query: str, rows: list[Iterable[Any]]) -> None:
    for row in rows:
        execute(query, row)


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


def _fetch_agents(q: str, params: tuple[Any, ...]) -> list[dict]:
    db = _db()
    if "where id = ?" in q:
        return _clean_many(db.agents.find({"id": int(params[0])}).limit(1))

    rows = _clean_many(db.agents.find({}))
    if "count(l.id) as active_leads" in q:
        territory = _lower(params[0]) if params else ""
        property_type = _lower(params[2]) if len(params) > 2 else ""
        filtered = []
        for agent in rows:
            if int(agent.get("active") or 0) != 1:
                continue
            if territory and agent.get("territory") and _lower(agent.get("territory")) != territory:
                continue
            if property_type and agent.get("property_type") and _lower(agent.get("property_type")) != property_type:
                continue
            active_leads = db.leads.count_documents(
                {"assigned_agent_id": agent["id"], "status": {"$nin": ["Cold", "Responded"]}}
            )
            filtered.append({**agent, "active_leads": active_leads})
        rows = filtered
        rows.sort(key=lambda item: (item.get("active_leads", 0), item.get("id", 0)))
        return rows[:1] if "limit 1" in q else rows

    rows.sort(key=lambda item: (-int(item.get("active") or 0), str(item.get("name") or "")))
    return rows


def _fetch_templates(q: str, params: tuple[Any, ...]) -> list[dict]:
    db = _db()
    if "where id = ?" in q:
        return _clean_many(db.email_templates.find({"id": int(params[0])}).limit(1))

    rows = _clean_many(db.email_templates.find({}))
    if "where active = 1" in q and "lower(category)" in q:
        category = _lower(params[0])
        property_type = _lower(params[1]) if len(params) > 1 else ""
        rows = [
            row
            for row in rows
            if int(row.get("active") or 0) == 1
            and _lower(row.get("category")) == category
            and (not row.get("property_type") or _lower(row.get("property_type")) == property_type)
        ]
    elif "where active = 1" in q:
        rows = [row for row in rows if int(row.get("active") or 0) == 1]

    if "conversion_rate desc" in q:
        rows.sort(key=lambda item: (-(float(item.get("conversion_rate") or 0)), -(float(item.get("reply_rate") or 0)), item.get("id", 0)))
    else:
        rows.sort(key=lambda item: (-int(item.get("active") or 0), str(item.get("category") or ""), str(item.get("name") or "")))
    return rows[:1] if "limit 1" in q else rows


def _fetch_app_settings(q: str, params: tuple[Any, ...]) -> list[dict]:
    if "where key = 'auto_email_send_enabled'" in q:
        return _clean_many(_db().app_settings.find({"key": "auto_email_send_enabled"}).limit(1))
    return _clean_many(_db().app_settings.find({}))


def _fetch_leads(q: str, params: tuple[Any, ...]) -> list[dict]:
    db = _db()
    rows = [_lead_defaults(row) for row in _clean_many(db.leads.find({}))]

    if "count(*) as total" in q:
        return [_dashboard(rows)]

    if "where l.id = ?" in q or "where id = ?" in q:
        rows = [row for row in rows if int(row.get("id") or 0) == int(params[0])]
    elif "lower(email) = lower(?) and phone = ? and lower(name) = lower(?)" in q:
        email, phone, name = params
        rows = [row for row in rows if _lower(row.get("email")) == _lower(email) and row.get("phone") == phone and _lower(row.get("name")) == _lower(name)]
    elif "lower(email) = lower(?)" in q:
        email = params[0]
        rows = [row for row in rows if _lower(row.get("email")) == _lower(email)]
        rows.sort(key=lambda row: (1 if row.get("status") == "Duplicate" else 0, row.get("id", 0)))
        return rows[:1]
    elif "where phone = ?" in q:
        phone = params[0]
        rows = [row for row in rows if row.get("phone") == phone]
        rows.sort(key=lambda row: (1 if row.get("status") == "Duplicate" else 0, row.get("id", 0)))
        return rows[:1]
    elif "where l.score_band = 'hot'" in q:
        rows = [row for row in rows if row.get("score_band") == "Hot" and row.get("validation_status") == "Valid" and row.get("status") != "Duplicate"]
    elif "where automation_status = 'active'" in q and "next_followup_at <= ?" in q:
        now = str(params[0])
        rows = [row for row in rows if row.get("automation_status") == "active" and row.get("next_followup_at") and str(row.get("next_followup_at")) <= now]
        rows.sort(key=lambda row: str(row.get("next_followup_at") or ""))
        return [{"id": row["id"]} for row in rows]
    elif "where l.automation_status = 'active'" in q:
        rows = [row for row in rows if row.get("automation_status") == "active"]
    elif "where" in q and "l.status = ?" in q:
        status = params[0]
        rows = [row for row in rows if row.get("status") == status]
        if len(params) > 1:
            rows = [row for row in rows if row.get("score_band") == params[1]]
    elif "where" in q and "l.score_band = ?" in q:
        rows = [row for row in rows if row.get("score_band") == params[0]]

    rows = [_with_agent(row) for row in rows]
    if "order by l.score desc" in q:
        rows.sort(key=lambda row: (-(int(row.get("score") or 0)), str(row.get("updated_at") or "")), reverse=False)
    elif "order by l.next_followup_at" in q:
        rows.sort(key=lambda row: (str(row.get("next_followup_at") or ""), -(int(row.get("score") or 0))))
    else:
        rows.sort(key=lambda row: (str(row.get("updated_at") or ""), int(row.get("id") or 0)), reverse=True)
    return rows[:1] if "limit 1" in q else rows


def _fetch_message_logs(q: str, params: tuple[Any, ...]) -> list[dict]:
    rows = _clean_many(_db().message_logs.find({}))
    if "where lead_id = ?" in q:
        rows = [row for row in rows if int(row.get("lead_id") or 0) == int(params[0])]
    if "channel = 'whatsapp'" in q:
        rows = [row for row in rows if row.get("channel") == "whatsapp" and str(row.get("subject") or "").startswith("Demo WhatsApp")]
    rows.sort(key=lambda row: (str(row.get("sent_at") or ""), int(row.get("id") or 0)), reverse=True)
    return rows[:1] if "limit 1" in q else rows


def _fetch_call_logs(q: str, params: tuple[Any, ...]) -> list[dict]:
    rows = _clean_many(_db().call_logs.find({}))
    if "where id = ?" in q:
        rows = [row for row in rows if int(row.get("id") or 0) == int(params[0])]
    elif "where lead_id = ?" in q:
        rows = [row for row in rows if int(row.get("lead_id") or 0) == int(params[0])]
        if "status in" in q:
            rows = [row for row in rows if row.get("status") in {"queued", "ringing", "answered", "completed"}]
        if "call_sid like 'demo-call-%'" in q:
            rows = [row for row in rows if str(row.get("call_sid") or "").startswith("DEMO-CALL-")]
    if "left join agents" in q:
        rows = [_with_call_agent(row) for row in rows]
    rows.sort(key=lambda row: (str(row.get("called_at") or ""), int(row.get("id") or 0)), reverse=True)
    return rows[:1] if "limit 1" in q else rows


def _fetch_email_history(q: str, params: tuple[Any, ...]) -> list[dict]:
    rows = _clean_many(_db().email_generation_history.find({}))
    if "where lead_id = ?" in q:
        rows = [row for row in rows if int(row.get("lead_id") or 0) == int(params[0])]
    elif "where h.id = ?" in q or "where id = ?" in q:
        rows = [row for row in rows if int(row.get("id") or 0) == int(params[0])]
    elif "count(*) as total" in q:
        return [_learning_stats(rows)]
    elif "avg(attempt_count)" in q:
        return [{"avg_attempts": _avg_attempts(rows)}]
    elif "user_action in ('approved', 'sent')" in q and "limit 40" in q:
        rows = [row for row in rows if row.get("user_action") in {"approved", "sent"} and int(row.get("is_active", 1) or 0) == 1 and row.get("final_body")]
    elif "guardrail_passed = 0" in q and "limit 40" in q:
        rows = [
            row
            for row in rows
            if int(row.get("is_active", 1) or 0) == 1
            and row.get("body")
            and (row.get("user_action") == "rejected" or int(row.get("guardrail_passed") or 0) == 0 or row.get("judge_status") in {"needs_review", "blocked"})
        ]
    elif "from email_generation_history h" in q:
        rows = _filter_admin_history(rows, q, params)

    if "left join leads" in q:
        rows = [_with_history_lead(row) for row in rows]
    rows.sort(key=lambda row: (str(row.get("updated_at") or row.get("created_at") or ""), int(row.get("id") or 0)), reverse=True)
    limit = 250 if "limit 250" in q else 40 if "limit 40" in q else 1 if "limit 1" in q else None
    return rows[:limit] if limit else rows


def _with_agent(row: dict) -> dict:
    if not row.get("assigned_agent_id"):
        return row
    agent = _clean(_db().agents.find_one({"id": int(row["assigned_agent_id"])})) or {}
    return {
        **row,
        "assigned_agent_name": agent.get("name"),
        "assigned_agent_email": agent.get("email"),
        "assigned_agent_email_provider": agent.get("email_provider"),
        "assigned_agent_email_account_active": agent.get("email_account_active"),
    }


def _with_call_agent(row: dict) -> dict:
    if not row.get("agent_id"):
        return row
    agent = _clean(_db().agents.find_one({"id": int(row["agent_id"])})) or {}
    return {**row, "agent_name": agent.get("name")}


def _with_history_lead(row: dict) -> dict:
    lead = _clean(_db().leads.find_one({"id": int(row.get("lead_id") or 0)})) or {}
    return {
        **row,
        "lead_name": lead.get("name"),
        "lead_email": lead.get("email"),
        "lead_score_band": lead.get("score_band"),
        "lead_property_type": lead.get("property_type"),
        "lead_location_preference": lead.get("location_preference"),
    }


def _dashboard(rows: list[dict]) -> dict:
    return {
        "total": len(rows),
        "hot": sum(1 for row in rows if row.get("score_band") == "Hot"),
        "warm": sum(1 for row in rows if row.get("score_band") == "Warm"),
        "cold": sum(1 for row in rows if row.get("score_band") == "Cold"),
        "invalid": sum(1 for row in rows if row.get("validation_status") == "Invalid"),
        "duplicate": sum(1 for row in rows if row.get("validation_status") == "Duplicate"),
        "valid_emails": sum(1 for row in rows if row.get("email_status") == "valid"),
        "valid_phones": sum(1 for row in rows if row.get("phone_status") == "valid"),
        "active_followups": sum(1 for row in rows if row.get("automation_status") == "active"),
        "emails_sent": sum(1 for row in rows if row.get("email_sent_status") == "sent"),
        "responded": sum(1 for row in rows if row.get("status") == "Responded"),
    }


def _learning_stats(rows: list[dict]) -> dict:
    active = [row for row in rows if int(row.get("is_active", 1) or 0) == 1]
    scores = [float(row.get("judge_score") or 0) for row in rows]
    latencies = [float(row.get("latency_ms") or 0) for row in rows if float(row.get("latency_ms") or 0) > 0]
    return {
        "total": len(rows),
        "gold": sum(1 for row in active if row.get("user_action") in {"approved", "sent"}),
        "error": sum(1 for row in active if row.get("user_action") == "rejected" or int(row.get("guardrail_passed") or 0) == 0 or row.get("judge_status") in {"needs_review", "blocked"}),
        "inactive": sum(1 for row in rows if int(row.get("is_active", 1) or 0) == 0),
        "avg_judge_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in rows),
        "estimated_cost": round(sum(float(row.get("estimated_cost") or 0) for row in rows), 4),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 0) if latencies else 0,
    }


def _avg_attempts(rows: list[dict]) -> float:
    attempts: dict[str, int] = {}
    for row in rows:
        if not str(row.get("provider") or "").startswith("openrouter_attempt_"):
            continue
        key = f"{row.get('lead_id')}:{str(row.get('created_at') or '')[:16]}"
        attempts[key] = attempts.get(key, 0) + 1
    return round(sum(attempts.values()) / len(attempts), 1) if attempts else 0


def _filter_admin_history(rows: list[dict], q: str, params: tuple[Any, ...]) -> list[dict]:
    params_iter = iter(params)
    if "h.user_action in ('approved', 'sent')" in q:
        rows = [row for row in rows if row.get("user_action") in {"approved", "sent"}]
    elif "h.user_action = 'rejected'" in q:
        rows = [row for row in rows if row.get("user_action") == "rejected" or int(row.get("guardrail_passed") or 0) == 0 or row.get("judge_status") in {"needs_review", "blocked"}]
    elif "h.user_action = ?" in q:
        status = next(params_iter, "")
        rows = [row for row in rows if row.get("user_action") == status]
    if "coalesce(h.is_active, 1) = 1" in q:
        rows = [row for row in rows if int(row.get("is_active", 1) or 0) == 1]
    elif "coalesce(h.is_active, 1) = 0" in q:
        rows = [row for row in rows if int(row.get("is_active", 1) or 0) == 0]
    if "lower(h.campaign_type) = lower(?)" in q:
        campaign = next(params_iter, "")
        rows = [row for row in rows if _lower(row.get("campaign_type")) == _lower(campaign)]
    return rows


def _lead_insert_payload(q: str, params: tuple[Any, ...]) -> dict:
    if len(params) == 26:
        fields = [
            "name", "email", "phone", "source", "property_type", "configuration", "location_preference",
            "budget", "timeline", "message", "email_status", "phone_status", "sms_capable", "carrier",
            "line_type", "score", "score_band", "score_breakdown", "validation_status", "validation_remarks",
            "status", "assigned_agent_id", "automation_status", "next_followup_at", "call_consent", "do_not_call",
        ]
    elif len(params) == 17:
        fields = [
            "name", "email", "phone", "source", "property_type", "configuration", "location_preference",
            "budget", "timeline", "message", "score", "score_band", "score_breakdown", "validation_remarks",
            "call_consent", "do_not_call", "duplicate_of",
        ]
        data = dict(zip(fields, params))
        data.update({"email_status": "skipped", "phone_status": "skipped", "validation_status": "Duplicate", "status": "Duplicate", "automation_status": "stopped"})
        return data
    else:
        fields = [
            "name", "email", "phone", "source", "property_type", "configuration", "location_preference",
            "budget", "timeline", "message", "email_status", "phone_status", "sms_capable", "carrier",
            "line_type", "score", "score_band", "score_breakdown", "validation_status", "validation_remarks",
            "status", "assigned_agent_id", "automation_status", "next_followup_at", "call_consent", "do_not_call",
        ][: len(params)]
    return dict(zip(fields, params))


def _message_insert_payload(q: str, params: tuple[Any, ...]) -> dict:
    if "template_id" in q:
        lead_id, template_id, subject, body, status, error = params
        return {"lead_id": lead_id, "template_id": template_id, "channel": "email", "direction": "outbound", "subject": subject, "body": body, "status": status, "error": error, "sent_at": _now()}
    if "values (?, 'email', 'inbound'" in q:
        lead_id, body = params
        return {"lead_id": lead_id, "channel": "email", "direction": "inbound", "subject": "", "body": body, "status": "received", "error": "", "sent_at": _now()}
    if "values (?, 'whatsapp'" in q:
        lead_id, subject, body, status, error = params[:5]
        sent_at = params[5] if len(params) > 5 else _now()
        return {"lead_id": lead_id, "channel": "whatsapp", "direction": "outbound", "subject": subject, "body": body, "status": status, "error": error, "sent_at": sent_at}
    lead_id, subject, body, status, error = params
    return {"lead_id": lead_id, "channel": "email", "direction": "outbound", "subject": subject, "body": body, "status": status, "error": error, "sent_at": _now()}


def _call_insert_payload(q: str, params: tuple[Any, ...]) -> dict:
    if len(params) == 3:
        lead_id, agent_id, script = params
        return {"lead_id": lead_id, "agent_id": agent_id, "script": script, "status": "queued", "duration": 0, "called_at": _now()}
    fields = [
        "lead_id", "agent_id", "call_sid", "script", "status", "duration", "recording_sid", "recording_url",
        "recording_status", "recording_duration", "recording_available_at", "error_message", "called_at", "updated_at",
    ]
    return dict(zip(fields, params))


def _update_leads(q: str, params: tuple[Any, ...]) -> int:
    db = _db()
    if "set name = ?" in q:
        fields = [
            "name", "email", "phone", "source", "property_type", "configuration", "location_preference", "budget",
            "timeline", "message", "email_status", "phone_status", "sms_capable", "carrier", "line_type", "score",
            "score_band", "score_breakdown", "validation_status", "validation_remarks", "status", "assigned_agent_id",
            "automation_status", "next_followup_at", "call_consent", "do_not_call",
        ]
        data = dict(zip(fields, params[:-1]))
        data["duplicate_of"] = None
        data["updated_at"] = _now()
        db.leads.update_one({"id": int(params[-1])}, {"$set": data})
    elif "set status = 'responded'" in q:
        replied_at, lead_id = params
        db.leads.update_one({"id": int(lead_id)}, {"$set": {"status": "Responded", "automation_status": "stopped", "replied_at": replied_at, "next_followup_at": None, "updated_at": _now()}})
    elif "set followup_step = ?" in q:
        step, status, last_contacted_at, next_followup_at, lead_id = params
        db.leads.update_one({"id": int(lead_id)}, {"$set": {"followup_step": step, "automation_status": status, "last_contacted_at": last_contacted_at, "next_followup_at": next_followup_at, "updated_at": _now()}})
    elif "set email_sent_status = 'sent'" in q:
        db.leads.update_one({"id": int(params[0])}, {"$set": {"email_sent_status": "sent", "email_sent_at": _now(), "updated_at": _now()}})
    elif "set status = 'cold', score_band = 'cold'" in q:
        db.leads.update_one({"id": int(params[0])}, {"$set": {"status": "Cold", "score_band": "Cold", "updated_at": _now()}})
    elif "set email_draft_subject = ?" in q and "email_sent_status" not in q:
        subject, body, lead_id = params
        db.leads.update_one({"id": int(lead_id)}, {"$set": {"email_draft_subject": subject, "email_draft_body": body, "updated_at": _now()}})
    elif "set email_draft_subject = ?" in q and "email_sent_status" in q:
        subject, body, email_status, sent_at, contacted_at, lead_id = params
        db.leads.update_one({"id": int(lead_id)}, {"$set": {"email_draft_subject": subject, "email_draft_body": body, "email_sent_status": email_status, "email_sent_at": sent_at, "last_contacted_at": contacted_at, "updated_at": _now()}})
    elif "set call_consent = ?" in q and "do_not_call = ?" in q and len(params) == 3:
        call_consent, do_not_call, lead_id = params
        db.leads.update_one({"id": int(lead_id)}, {"$set": {"call_consent": call_consent, "do_not_call": do_not_call, "updated_at": _now()}})
    elif "set email_status = ?" in q:
        fields = ["email_status", "phone_status", "score", "score_band", "score_breakdown", "validation_status", "validation_remarks", "status", "assigned_agent_id", "automation_status", "call_consent", "do_not_call"]
        data = dict(zip(fields, params[:-1]))
        data["updated_at"] = _now()
        db.leads.update_one({"id": int(params[-1])}, {"$set": data})
    else:
        raise NotImplementedError(f"Mongo leads update not implemented: {q}")
    return 0


def _update_call_logs(q: str, params: tuple[Any, ...]) -> int:
    db = _db()
    call_id = int(params[-1])
    if "set status = 'failed'" in q:
        data = {"status": "failed", "error_message": params[0], "updated_at": _now()}
    elif "set call_sid = ?" in q:
        data = {"call_sid": params[0], "status": "queued", "recording_status": "requested", "updated_at": _now()}
    elif "duration = 0" in q:
        data = {"call_sid": params[0], "status": "queued", "duration": 0, "recording_sid": params[1], "recording_url": params[2], "recording_status": "completed", "recording_duration": 42, "recording_available_at": _now(), "error_message": params[3], "updated_at": _now()}
    elif "duration = ?" in q and "recording_sid" not in q:
        data = {"status": params[0], "duration": int(params[1] or 0), "updated_at": _now()}
        if params[2]:
            data["call_sid"] = params[2]
    elif "recording_sid" in q:
        data = {"recording_status": params[2], "recording_duration": int(params[3] or 0), "updated_at": _now()}
        if params[0]:
            data["recording_sid"] = params[0]
        if params[1]:
            data["recording_url"] = params[1]
        if params[4]:
            data["call_sid"] = params[4]
        if params[2] == "completed" and params[1]:
            data["recording_available_at"] = _now()
    else:
        raise NotImplementedError(f"Mongo call update not implemented: {q}")
    db.call_logs.update_one({"id": call_id}, {"$set": data})
    return 0


def _update_email_history(q: str, params: tuple[Any, ...]) -> int:
    db = _db()
    if "set user_action = ?" in q:
        normalized, review_status, selected_check, admin_note, history_id = params
        data = {"user_action": normalized, "review_status": review_status, "admin_note": admin_note, "is_active": 1, "updated_at": _now()}
        if selected_check in {"approved", "sent"}:
            data["selected_version"] = "final"
        db.email_generation_history.update_one({"id": int(history_id)}, {"$set": data})
    elif "set is_active = ?" in q:
        is_active, admin_note, history_id = params
        data = {"is_active": is_active, "updated_at": _now()}
        if admin_note:
            data["admin_note"] = admin_note
        db.email_generation_history.update_one({"id": int(history_id)}, {"$set": data})
    else:
        raise NotImplementedError(f"Mongo email history update not implemented: {q}")
    return 0


def _seed_defaults() -> None:
    db = _db()
    if db.app_settings.count_documents({"key": "auto_email_send_enabled"}) == 0:
        db.app_settings.insert_one({"key": "auto_email_send_enabled", "value": "false", "updated_at": _now()})

    if db.agents.count_documents({}) == 0:
        for agent in [
            {"name": "Amit Sales", "email": "amit@example.com", "territory": "Wakad", "property_type": "Apartment", "active": 1},
            {"name": "Priya Sales", "email": "priya@example.com", "territory": "Baner", "property_type": "Villa", "active": 1},
        ]:
            agent.update({"email_provider": "gmail", "email_username": agent["email"], "email_password": "", "smtp_host": "", "smtp_port": 587, "smtp_use_tls": 1, "email_account_active": 1})
            _insert("agents", agent)

    if db.email_templates.count_documents({}) == 0:
        templates = [
            ("Hot apartment first touch", "Hot", "Apartment", "Shortlisted {configuration} options in {location_preference}", "Hi {name},\n\nBased on your interest in {configuration} {property_type} options around {location_preference}, we have a few matches that may fit {budget}. Would you like me to share the best options?\n\nRegards,\n{agent_name}", 0.32, 0.18),
            ("Warm general nurture", "Warm", "", "Property options matching your requirement", "Hi {name},\n\nThanks for your inquiry. We can help you compare suitable {property_type} options around {location_preference}. Would you like a quick shortlist?\n\nRegards,\n{agent_name}", 0.21, 0.09),
            ("Cold monthly nurture", "Cold", "", "New property updates for {location_preference}", "Hi {name},\n\nSharing a quick update in case you are still exploring properties around {location_preference}. We can send matching options whenever you are ready.\n\nRegards,\n{agent_name}", 0.08, 0.03),
        ]
        for name, category, property_type, subject, body, reply_rate, conversion_rate in templates:
            _insert("email_templates", {"name": name, "category": category, "property_type": property_type, "subject": subject, "body": body, "reply_rate": reply_rate, "conversion_rate": conversion_rate, "active": 1})
