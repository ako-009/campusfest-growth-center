"""Embedded AI growth analyst. Gemini answers by calling the tools below, which read the live
database through metrics.py. Writes (tasks, budget/status changes) are only *proposed*; the user
confirms them in the UI before anything is saved."""
import json
import os

import pandas as pd

import db
import metrics

STATE = {"as_of": "2025-04-20", "show_rate": 0.69, "pending": []}


def _data():
    return db.load_all()


def _clean(obj):
    """Make pandas/numpy output JSON-safe for the model."""
    if isinstance(obj, pd.DataFrame):
        return json.loads(obj.to_json(orient="records", date_format="iso"))
    return json.loads(json.dumps(obj, default=str))


def _date(as_of_date):
    return as_of_date or STATE["as_of"]


def _campaign_id(d, campaign):
    if not campaign:
        return None
    c = d["campaigns"]
    key = campaign.strip().lower()
    hit = c[(c.campaign_id.str.lower() == key) | (c.campaign_name.str.lower() == key)]
    if hit.empty:
        hit = c[c.campaign_name.str.lower().str.contains(key, regex=False)]
    if hit.empty:
        raise ValueError(f"No campaign matches '{campaign}'. Known: {', '.join(c.campaign_name)}")
    return hit.iloc[0].campaign_id


# ---------------------------------------------------------------- tools the model can call

def get_overview(as_of_date: str = "") -> dict:
    """Whole-festival funnel as of the end of a date (YYYY-MM-DD; empty = the dashboard's selected date):
    reach events, identified people, registrations, latest registration statuses, verified visitors,
    spend, cost per registration/visitor, the target plan in force, gaps to target, budget used,
    and a projection of final visitors."""
    d = _data()
    date = _date(as_of_date)
    s = metrics.snapshot(d, date)
    t = metrics.target_at(d, date)
    proj = metrics.projection(d, date, STATE["show_rate"])
    gaps = {
        "identified_people_vs_goal": f"{s['identified_people']} / {t['identified_external_people_goal']}",
        "registrations_vs_goal": f"{s['registered_people']} / {t['registration_goal']}",
        "verified_visitors_vs_goal": f"{s['verified_visitors']} / {t['unique_external_visitors_goal']}",
        "spend_vs_budget_inr": f"{s['spend_inr']} / {t['marketing_budget_inr']}",
    }
    return _clean({"funnel": s, "target_plan_in_force": t, "progress": gaps, "projection": proj})


def get_campaign_metrics(as_of_date: str = "") -> list:
    """One row per campaign as of a date: spend, impressions, clicks, sessions, identified people
    (first-touch), registrations (recorded acquisition source), latest statuses, verified visitors,
    cost per registration, cost per verified visitor, show rate, plus the rule-based decision flag
    (scale / hold / fix / stop) and its reason, and the team's planned budget and status."""
    d = _data()
    t = metrics.decision_table(d, _date(as_of_date))
    plan = db.read("campaign_plan")[["campaign_id", "planned_budget_inr", "status", "decision_note"]]
    return _clean(t.merge(plan, on="campaign_id", how="left"))


def get_campaign_detail(campaign: str, as_of_date: str = "") -> dict:
    """Deep dive on one campaign (name or ID such as C02): funnel stage conversions and leakage
    (cancellations, waitlist, opt-outs, click-to-session, session-to-form-start) and weekly trend of
    spend, registrations and cost per registration."""
    d = _data()
    cid = _campaign_id(d, campaign)
    date = _date(as_of_date)
    return _clean({"campaign_id": cid, "stages": metrics.stage_rates(d, date, cid),
                   "weekly": metrics.weekly(d, date, cid)})


def get_daily_trend(campaign: str = "", start_date: str = "2025-01-15", end_date: str = "") -> list:
    """Daily anonymous activity (impressions, clicks, landing-page sessions, form starts, spend in ₹)
    for one campaign or all campaigns (empty) between two dates inclusive."""
    d = _data()
    cid = _campaign_id(d, campaign) if campaign else None
    s = metrics.daily_series(d, _date(end_date), cid)
    s = s[s.activity_date >= pd.Timestamp(start_date)]
    return _clean(s)


def simulate_budget_reallocation(budgets_json: str, as_of_date: str = "") -> dict:
    """What-if: give campaigns new budgets. budgets_json is a JSON object of campaign ID → ₹ budget,
    e.g. {"C02": 40000, "C04": 75000}; campaigns not listed keep their spend so far. Uses each
    campaign's observed cost per registration (raised 30% per doubling of spend, an ASSUMPTION) and
    its observed show rate. Returns per-campaign and total projected registrations and visitors."""
    d = _data()
    budgets = json.loads(budgets_json) if budgets_json else {}
    sim = metrics.simulate_reallocation(d, _date(as_of_date), budgets)
    base = metrics.simulate_reallocation(d, _date(as_of_date), {})
    return _clean({"scenario": sim, "scenario_totals": {"budget_inr": int(sim.budget_inr.sum()),
                   "registrations": int(sim.registrations.sum()), "visitors": int(sim.visitors.sum())},
                   "current_totals": {"budget_inr": int(base.budget_inr.sum()),
                   "registrations": int(base.registrations.sum()), "visitors": int(base.visitors.sum())},
                   "assumptions": "Cost per registration rises 30% per doubling of spend; show rate as observed; "
                                  "pre-event show rate defaults to 69%. Model output, not evidence."})


def list_tasks(status: str = "") -> list:
    """Tasks in the management tool, optionally filtered by status (open, in progress, done)."""
    t = db.read("tasks")
    if status:
        t = t[t.status.str.lower() == status.lower()]
    return _clean(t)


def run_sql(query: str) -> dict:
    """Run ONE read-only SQL SELECT on the SQLite database for questions the other tools do not cover.
    Tables: campaigns, daily, people, interactions, registrations, reg_history, checkins, targets,
    event, campaign_plan, tasks, change_log. Timestamps are text 'YYYY-MM-DD HH:MM:SS' (IST).
    Remember: count people with COUNT(DISTINCT person_id); filter people.person_type='external' for
    attendance; attendance = checkins with result='admitted' AND verification='verified';
    latest registration status = last reg_history row per registration_id by effective_at."""
    try:
        df, n = db.read_only_query(query)
        return {"rows_returned": n, "rows": _clean(df)}
    except Exception as e:  # report the error so the model can fix its query
        return {"error": str(e)}


def propose_task(title: str, campaign_id: str = "", owner: str = "", due_date: str = "",
                 priority: str = "medium", rationale: str = "") -> dict:
    """Propose a new task for the management tool. It is NOT saved until the user clicks Confirm in
    the chat panel. Include the evidence for it in `rationale`."""
    STATE["pending"].append({"type": "task", "title": title, "campaign_id": campaign_id, "owner": owner,
                             "due_date": due_date, "priority": priority, "rationale": rationale})
    return {"status": "proposed, awaiting the user's confirmation in the UI"}


def propose_plan_change(campaign_id: str, new_budget_inr: int = -1, new_status: str = "",
                        rationale: str = "") -> dict:
    """Propose changing a campaign's planned budget (₹; -1 = unchanged) and/or status (active,
    paused, stopped). NOT saved until the user clicks Confirm in the chat panel."""
    STATE["pending"].append({"type": "plan", "campaign_id": campaign_id,
                             "new_budget_inr": None if new_budget_inr is None or new_budget_inr < 0 else int(new_budget_inr),
                             "new_status": new_status or None, "rationale": rationale})
    return {"status": "proposed, awaiting the user's confirmation in the UI"}


def _safe(fn):
    """Return errors to the model as data instead of crashing the chat."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            return {"error": str(e)}
    return wrapper


TOOLS = [_safe(f) for f in [get_overview, get_campaign_metrics, get_campaign_detail, get_daily_trend,
         simulate_budget_reallocation, list_tasks, run_sql, propose_task, propose_plan_change]]

SYSTEM = """You are the Growth Analyst inside the CampusFest Growth Center, a tool a festival team uses
to maximise ACTUAL ATTENDANCE (unique verified external visitors). Today's selected analysis date is
{as_of}. Use it unless the user names another date.

Rules:
1. Every number you state must come from a tool call in this conversation. Never use general knowledge
   for figures. If you computed something, show the arithmetic briefly.
2. Data rules: a date means the end of that day (IST). People are counted by person_id, not name.
   Attendance = admitted AND verified check-ins of external people, each person once. Registrations
   are attributed to their recorded acquisition campaign; identified people to their first-touch
   campaign. Impressions, clicks, reach and sessions are anonymous events, not people. Spend is net of
   vendor credits. Per-campaign planned budgets and seed tasks are SIMULATED working data.
3. Separate EVIDENCE (observed data) from ASSUMPTIONS (projections, simulations, show-rate guesses).
4. If the data cannot answer (e.g. demographics, colleges, ticket revenue, sponsor money, sentiment,
   why someone did something, anything after 20 Apr 2025), say so plainly, say what data would be
   needed, and offer the closest answer the data does support.
5. For actions (tasks, budget or status changes) call propose_task / propose_plan_change and tell the
   user to confirm them below the chat. Never claim something was saved.
6. Be concise: lead with the answer, then 2-4 bullets of evidence, then a recommendation if useful.
"""


_CLIENTS = {}  # keep the client alive: the SDK closes its connection when the Client is garbage-collected


def make_chat(api_key, model, history):
    from google import genai
    from google.genai import types
    client = _CLIENTS.get(api_key)
    if client is None:
        client = _CLIENTS[api_key] = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM.format(as_of=STATE["as_of"]),
        tools=TOOLS,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=12),
    )
    hist = [types.Content(role=m["role"], parts=[types.Part(text=m["text"])]) for m in history]
    return client.chats.create(model=model, config=cfg, history=hist)


def tool_calls_from(response):
    """Names and arguments of the tools the model called, for the 'show your work' expander."""
    calls = []
    for c in (getattr(response, "automatic_function_calling_history", None) or []):
        for p in (c.parts or []):
            if getattr(p, "function_call", None):
                calls.append({"tool": p.function_call.name, "args": dict(p.function_call.args or {})})
    return calls
