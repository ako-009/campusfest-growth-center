"""Metric engine for the CampusFest attendee data.

Rules from the dataset's Read me: deduplicate repeated source IDs; a date means the end of
that day (IST); use the latest status version per registration at or before the date;
only admitted + verified check-ins of external people count as attendance; a person
is counted once however many admission events they have.
"""
import pandas as pd

TABLES = {
    "Event": "event", "Targets": "targets", "Campaigns": "campaigns",
    "Daily Marketing": "daily", "People": "people", "Interest and Engagement": "interactions",
    "Registrations": "registrations", "Registration History": "reg_history", "Check-ins": "checkins",
}
DEDUP_KEYS = {"daily": "activity_id", "people": "person_id", "interactions": "interaction_id",
              "registrations": "registration_id", "reg_history": "history_id", "checkins": "event_id"}


def load_excel(path):
    x = pd.ExcelFile(path)
    data = {}
    for sheet, name in TABLES.items():
        df = x.parse(sheet)
        if name in DEDUP_KEYS:
            df = df.drop_duplicates(DEDUP_KEYS[name])
        data[name] = df
    return data


def end_of(date):
    return pd.Timestamp(date).normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)


def target_at(d, date):
    t = d["targets"].sort_values("effective_at")
    t = t[t.effective_at <= end_of(date)]
    return (t.iloc[-1] if len(t) else d["targets"].sort_values("effective_at").iloc[0]).to_dict()


def latest_status(d, date):
    h = d["reg_history"]
    h = h[h.effective_at <= end_of(date)].sort_values(["registration_id", "effective_at", "history_id"])
    return h.groupby("registration_id").tail(1).set_index("registration_id")["status"]


def snapshot(d, date, campaign_id=None):
    """Funnel counts as of the end of `date`, optionally for one campaign."""
    e = end_of(date)
    people = d["people"]
    ext = set(people.loc[people.person_type == "external", "person_id"])
    p = people[(people.person_type == "external") & (people.first_seen_at <= e)]
    regs = d["registrations"]
    regs = regs[(regs.registered_at <= e) & regs.person_id.isin(ext)]
    daily = d["daily"][pd.to_datetime(d["daily"].activity_date) <= e]
    chk = d["checkins"]
    chk = chk[(chk.occurred_at <= e) & (chk.result == "admitted") & (chk.verification == "verified")
              & chk.person_id.isin(ext)]
    if campaign_id:
        p = p[p.first_campaign_id == campaign_id]
        regs = regs[regs.campaign_id == campaign_id]
        daily = daily[daily.campaign_id == campaign_id]
        reg_ids = set(regs.registration_id)
        chk = chk[chk.registration_id.isin(reg_ids)]
    st = latest_status(d, date)
    st = st[st.index.isin(set(regs.registration_id))]
    spend = int(daily.marketing_spend_inr.sum())
    registered = regs.person_id.nunique()
    visitors = chk.person_id.nunique()
    out = {
        "as_of": str(pd.Timestamp(date).date()),
        "impressions": int(daily.impressions.sum()),
        "clicks": int(daily.clicks.sum()),
        "landing_page_sessions": int(daily.landing_page_sessions.sum()),
        "registration_starts_anonymous": int(daily.registration_starts.sum()),
        "identified_people": int(p.person_id.nunique()),
        "registered_people": int(registered),
        "status_confirmed": int((st == "confirmed").sum()),
        "status_interested": int((st == "interested").sum()),
        "status_waitlisted": int((st == "waitlisted").sum()),
        "status_cancelled": int((st == "cancelled").sum()),
        "verified_visitors": int(visitors),
        "spend_inr": spend,
        "cost_per_registration_inr": round(spend / registered) if registered else None,
        "cost_per_visitor_inr": round(spend / visitors) if visitors else None,
        "registration_to_visit_pct": round(100 * visitors / registered, 1) if registered else None,
        "identified_to_registration_pct": round(100 * registered / p.person_id.nunique(), 1) if len(p) else None,
    }
    if not campaign_id:
        walk = chk[chk.registration_id.isna()].person_id.nunique()
        out["walk_in_visitors_without_registration"] = int(walk)
    return out


def campaign_table(d, date):
    rows = []
    for _, c in d["campaigns"].iterrows():
        s = snapshot(d, date, c.campaign_id)
        rows.append({"campaign_id": c.campaign_id, "campaign": c.campaign_name, "owner": c.owner_name,
                     "channel": c.channel, **{k: v for k, v in s.items() if k != "as_of"}})
    return pd.DataFrame(rows)


def daily_series(d, date, campaign_id=None):
    e = end_of(date)
    dd = d["daily"].copy()
    dd["activity_date"] = pd.to_datetime(dd.activity_date)
    dd = dd[dd.activity_date <= e]
    if campaign_id:
        dd = dd[dd.campaign_id == campaign_id]
    return dd.groupby("activity_date")[["impressions", "clicks", "landing_page_sessions",
                                        "registration_starts", "marketing_spend_inr"]].sum().reset_index()


if __name__ == "__main__":
    d = load_excel("attendee_dataset.xlsx")
    for date in ["2025-03-15", "2025-04-11", "2025-04-20"]:
        print(date, snapshot(d, date))
        print(target_at(d, date))
    pd.set_option("display.width", 250)
    print(campaign_table(d, "2025-04-20")[["campaign", "spend_inr", "identified_people", "registered_people",
                                           "status_confirmed", "status_cancelled", "verified_visitors",
                                           "cost_per_registration_inr", "cost_per_visitor_inr", "registration_to_visit_pct"]].to_string())


# ---------------------------------------------------------------- diagnostics & decisions

def event_start(d):
    return pd.Timestamp(d["event"].iloc[0].event_starts_at)


def stage_rates(d, date, campaign_id=None):
    """Conversion and leakage at each funnel stage, plus identified-engagement counts."""
    s = snapshot(d, date, campaign_id)
    e = end_of(date)
    it = d["interactions"]
    ext = set(d["people"].loc[d["people"].person_type == "external", "person_id"])
    it = it[(it.occurred_at <= e) & it.person_id.isin(ext)]
    if campaign_id:
        it = it[it.campaign_id == campaign_id]
    counts = it.groupby("event_type").person_id.nunique().to_dict()
    reg = s["registered_people"] or 0
    return {
        "identified_people": s["identified_people"],
        "registered_people": reg,
        "identified_to_registered_pct": s["identified_to_registration_pct"],
        "latest_status": {k: s[f"status_{k}"] for k in ["confirmed", "interested", "waitlisted", "cancelled"]},
        "cancelled_or_waitlisted_pct": round(100 * (s["status_cancelled"] + s["status_waitlisted"]) / reg, 1) if reg else None,
        "verified_visitors": s["verified_visitors"],
        "registered_to_visit_pct": s["registration_to_visit_pct"],
        "people_with_engagement_action": {k: int(v) for k, v in counts.items()},
        "opt_out_pct_of_identified": round(100 * counts.get("opted_out", 0) / s["identified_people"], 1) if s["identified_people"] else None,
        "click_to_session_pct": round(100 * s["landing_page_sessions"] / s["clicks"], 1) if s["clicks"] else None,
        "session_to_form_start_pct": round(100 * s["registration_starts_anonymous"] / s["landing_page_sessions"], 1) if s["landing_page_sessions"] else None,
    }


def weekly(d, date, campaign_id=None):
    """Weekly spend, identified people, registrations and cost per registration up to `date`."""
    e = end_of(date)
    ext = set(d["people"].loc[d["people"].person_type == "external", "person_id"])
    dd = d["daily"].copy()
    dd["activity_date"] = pd.to_datetime(dd.activity_date)
    dd = dd[dd.activity_date <= e]
    r = d["registrations"]
    r = r[(r.registered_at <= e) & r.person_id.isin(ext)]
    if campaign_id:
        dd = dd[dd.campaign_id == campaign_id]
        r = r[r.campaign_id == campaign_id]
    w1 = dd.groupby(pd.Grouper(key="activity_date", freq="W-SUN")).agg(spend_inr=("marketing_spend_inr", "sum"),
                                                                       clicks=("clicks", "sum"))
    w2 = r.groupby(pd.Grouper(key="registered_at", freq="W-SUN")).person_id.nunique().rename("registrations")
    w = w1.join(w2, how="outer").fillna(0)
    w.index.name = "week_ending"
    regs = w.registrations.astype(float).where(w.registrations > 0)
    w["cost_per_registration_inr"] = (w.spend_inr.astype(float) / regs).round(0)
    return w.reset_index()


def projection(d, date, show_rate=0.69, lookback_days=14):
    """Projected verified visitors. Before the event: registrations so far plus the recent daily
    run-rate until the event, times an assumed show rate, plus walk-ins at the historical ratio.
    After the event: actuals."""
    e = end_of(date)
    start = event_start(d)
    s = snapshot(d, date)
    if e >= start + pd.Timedelta(days=2):
        return {"mode": "actual", "verified_visitors": s["verified_visitors"]}
    ext = set(d["people"].loc[d["people"].person_type == "external", "person_id"])
    r = d["registrations"]
    r = r[r.person_id.isin(ext)]
    recent = r[(r.registered_at <= e) & (r.registered_at > e - pd.Timedelta(days=lookback_days))].person_id.nunique()
    per_day = recent / lookback_days
    days_left = max((start.normalize() - pd.Timestamp(date).normalize()).days, 0)
    regs_final = s["registered_people"] + per_day * days_left
    walk_in_ratio = 0.065  # assumption: 125 walk-ins per 1,925 registered visitors at CampusFest 2025
    visitors = regs_final * show_rate * (1 + walk_in_ratio)
    return {"mode": "projection", "registrations_so_far": s["registered_people"],
            "recent_registrations_per_day": round(per_day, 1), "days_to_event": days_left,
            "projected_registrations": round(regs_final), "assumed_show_rate": show_rate,
            "assumed_walk_in_ratio": walk_in_ratio, "projected_verified_visitors": round(visitors)}


def decision_table(d, date, scale_ratio=0.8, stop_ratio=2.0, min_show=0.6):
    """Scale / hold / fix / stop flags. After the event the rule uses cost per verified visitor;
    before it, cost per registration plus the cancelled-or-waitlisted share."""
    t = campaign_table(d, date)
    post = t.verified_visitors.sum() > 0
    metric = "cost_per_visitor_inr" if post else "cost_per_registration_inr"
    tot = snapshot(d, date)
    blended = tot["cost_per_visitor_inr"] if post else tot["cost_per_registration_inr"]
    flags, reasons = [], []
    for _, r in t.iterrows():
        c = r[metric]
        leak = (r.status_cancelled + r.status_waitlisted) / r.registered_people if r.registered_people else 0
        showr = r.registration_to_visit_pct / 100 if post and r.registration_to_visit_pct is not None else None
        if c is None or pd.isna(c):
            flags.append("insufficient data"); reasons.append("No registrations or visitors yet.")
        elif c >= stop_ratio * blended:
            flags.append("stop / restructure"); reasons.append(f"{metric} ₹{c:.0f} is ≥{stop_ratio}× blended ₹{blended}.")
        elif post and showr is not None and showr < min_show:
            flags.append("fix"); reasons.append(f"Show rate {showr:.0%} is below {min_show:.0%}.")
        elif not post and leak > 0.15:
            flags.append("fix"); reasons.append(f"{leak:.0%} of registrations cancelled or waitlisted.")
        elif c <= scale_ratio * blended:
            flags.append("scale"); reasons.append(f"{metric} ₹{c:.0f} is ≤{scale_ratio}× blended ₹{blended}.")
        else:
            flags.append("hold"); reasons.append(f"{metric} ₹{c:.0f} is near blended ₹{blended}.")
    t["decision"] = flags
    t["reason"] = reasons
    t["metric_used"] = metric
    return t


def simulate_reallocation(d, date, budgets, saturation=0.30, show_rate=None):
    """Projected registrations and visitors if each campaign gets `budgets[campaign_id]` (₹).
    Uses each campaign's observed cost per registration up to `date`, raised by `saturation`
    for every doubling of spend (assumption), and its observed show rate (or `show_rate`)."""
    import math
    t = campaign_table(d, date).set_index("campaign_id")
    rows = []
    for cid, row in t.iterrows():
        new = float(budgets.get(cid, row.spend_inr))
        base_cpr = row.cost_per_registration_inr
        if not base_cpr or pd.isna(base_cpr) or row.spend_inr <= 0:
            rows.append({"campaign_id": cid, "campaign": row.campaign, "budget_inr": round(new), "cost_per_registration_inr": None,
                         "registrations": 0, "show_rate": None, "visitors": 0, "note": "no cost history yet"})
            continue
        mult = new / row.spend_inr
        cpr = base_cpr * (1 + saturation * math.log2(mult)) if mult > 1 else base_cpr
        regs = new / cpr
        sr = show_rate if show_rate is not None else ((row.registration_to_visit_pct or 69) / 100 or 0.69)
        rows.append({"campaign_id": cid, "campaign": row.campaign, "budget_inr": round(new),
                     "cost_per_registration_inr": round(cpr), "registrations": round(regs),
                     "show_rate": round(sr, 3), "visitors": round(regs * sr)})
    out = pd.DataFrame(rows)
    return out
