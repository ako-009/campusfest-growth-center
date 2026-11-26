"""Storage layer. One database holds the source data (deduplicated) and the team's working data
(campaign plans, tasks, change log). Every page and the AI analyst read from it, so an edit anywhere
updates every metric.

Storage: set DATABASE_URL (e.g. a free Supabase Postgres) in Streamlit secrets or the environment for
permanent storage; otherwise a local SQLite file is used (lost when a cloud container restarts)."""
import io
import os
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, inspect, text

from metrics import load_excel

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_XLSX = os.path.join(HERE, "attendee_dataset.xlsx")

DATE_COLS = {
    "event": ["history_start", "history_end", "event_starts_at", "event_ends_at"],
    "targets": ["effective_at"],
    "campaigns": ["created_at", "planned_start_at", "planned_end_at"],
    "daily": ["activity_date"],
    "people": ["first_seen_at"],
    "interactions": ["occurred_at"],
    "registrations": ["registered_at"],
    "reg_history": ["effective_at"],
    "checkins": ["occurred_at"],
    "tasks": ["due_date", "created_at", "updated_at"],
    "change_log": ["at"],
}
SOURCE_TABLES = ["event", "targets", "campaigns", "daily", "people", "interactions",
                 "registrations", "reg_history", "checkins"]
_ENGINE = None


def _url():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL", "")
        except Exception:
            url = ""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg2://" + url[len(prefix):]
    return url or "sqlite:///" + os.environ.get("GROWTH_DB", os.path.join(HERE, "growth.db"))


def engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(_url(), pool_pre_ping=True)
    return _ENGINE


def backend():
    return "Postgres (permanent)" if engine().dialect.name == "postgresql" else "SQLite (temporary on cloud)"


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _store(name, df):
    df = df.copy()
    for c in DATE_COLS.get(name, []):
        if c in df:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    with engine().begin() as con:
        df.to_sql(name, con, if_exists="replace", index=False)


def init_db(force=False, source=None):
    """Build the database from the source workbook (or an uploaded replacement) if it is empty."""
    if not force and inspect(engine()).has_table("campaign_plan"):
        return
    data = load_excel(source or SOURCE_XLSX)
    for name, df in data.items():
        _store(name, df)
    # Working data. Planned budgets are SIMULATED: the latest total budget split in proportion to
    # each campaign's actual spend (the source has no per-campaign budget).
    spend = data["daily"].groupby("campaign_id").marketing_spend_inr.sum()
    total_budget = int(data["targets"].sort_values("effective_at").iloc[-1].marketing_budget_inr)
    plan = data["campaigns"][["campaign_id", "campaign_name", "owner_name"]].copy()
    plan["planned_budget_inr"] = (plan.campaign_id.map(spend).fillna(0) / max(spend.sum(), 1) * total_budget).round(-3).astype(int)
    plan["status"] = "active"
    plan["decision_note"] = ""
    _store("campaign_plan", plan)
    tasks = pd.DataFrame([
        {"task_id": 1, "title": "Cut Paid Social prospecting; keep retargeting only", "campaign_id": "C02",
         "owner": "Arjun Verma", "due_date": "2025-03-20", "status": "open", "priority": "high",
         "source": "seed", "notes": "Example task (simulated)."},
        {"task_id": 2, "title": "Send WhatsApp reminder to confirmed registrants 48h before event",
         "campaign_id": "", "owner": "Dev Malhotra", "due_date": "2025-04-10", "status": "open",
         "priority": "medium", "source": "seed", "notes": "Example task (simulated)."},
    ])
    tasks["created_at"] = now()
    tasks["updated_at"] = now()
    _store("tasks", tasks)
    _store("change_log", pd.DataFrame([{"at": now(), "table_name": "all", "action": "rebuild",
                                        "detail": "database built from " + ("uploaded workbook" if source else "original workbook")}]))


def init_from_upload(file_bytes):
    init_db(force=True, source=io.BytesIO(file_bytes))


def read(name):
    with engine().connect() as con:
        df = pd.read_sql(text(f'SELECT * FROM "{name}"'), con)
    for c in DATE_COLS.get(name, []):
        if c in df:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def load_all():
    return {n: read(n) for n in SOURCE_TABLES}


def replace_table(name, df, detail=""):
    _store(name, df)
    log(name, "replace", detail)


def log(table_name, action, detail):
    with engine().begin() as con:
        con.execute(text('INSERT INTO change_log ("at", table_name, action, detail) VALUES (:a, :t, :ac, :d)'),
                    {"a": now(), "t": table_name, "ac": action, "d": str(detail)[:500]})


def add_task(title, campaign_id="", owner="", due_date="", priority="medium", notes="", source="manual"):
    tasks = read("tasks")
    tid = int(tasks.task_id.max()) + 1 if len(tasks) else 1
    due = str(pd.to_datetime(due_date).strftime("%Y-%m-%d %H:%M:%S")) if due_date else None
    with engine().begin() as con:
        con.execute(text("INSERT INTO tasks (task_id,title,campaign_id,owner,due_date,status,priority,source,notes,created_at,updated_at)"
                         " VALUES (:i,:t,:c,:o,:d,'open',:p,:s,:n,:ca,:ua)"),
                    {"i": tid, "t": title, "c": campaign_id or "", "o": owner or "", "d": due, "p": priority or "medium",
                     "s": source, "n": notes or "", "ca": now(), "ua": now()})
    log("tasks", "add", f"#{tid} {title}")
    return tid


def update_plan(campaign_id, planned_budget_inr=None, status=None, decision_note=None):
    with engine().begin() as con:
        if planned_budget_inr is not None:
            con.execute(text("UPDATE campaign_plan SET planned_budget_inr=:b WHERE campaign_id=:c"),
                        {"b": int(planned_budget_inr), "c": campaign_id})
        if status is not None:
            con.execute(text("UPDATE campaign_plan SET status=:s WHERE campaign_id=:c"), {"s": status, "c": campaign_id})
        if decision_note is not None:
            con.execute(text("UPDATE campaign_plan SET decision_note=:n WHERE campaign_id=:c"), {"n": decision_note, "c": campaign_id})
    log("campaign_plan", "update", f"{campaign_id}: budget={planned_budget_inr} status={status} note={decision_note}")


def read_only_query(sql, limit=200):
    """Run a single SELECT for the AI analyst inside a read-only transaction."""
    s = sql.strip().rstrip(";")
    if ";" in s or not s.lower().startswith(("select", "with")):
        raise ValueError("Only a single SELECT (or WITH ... SELECT) statement is allowed.")
    eng = engine()
    with eng.connect() as con:
        trans = con.begin()
        try:
            if eng.dialect.name == "postgresql":
                con.execute(text("SET TRANSACTION READ ONLY"))
            else:
                con.exec_driver_sql("PRAGMA query_only = ON")
            df = pd.read_sql(text(s), con)
        finally:
            if eng.dialect.name != "postgresql":
                con.exec_driver_sql("PRAGMA query_only = OFF")
            trans.rollback()
    return df.head(limit), len(df)
