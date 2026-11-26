"""CampusFest Growth Center — measure, diagnose, decide, execute, and ask the AI analyst."""
import json
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analyst
import db
import metrics

st.set_page_config(page_title="CampusFest Growth Center", page_icon="🎟️", layout="wide")
db.init_db()

NAVY, BLUE, AMBER, GREY = "#13294B", "#1F5FBF", "#D99A00", "#8A94A3"
DECISION_COLORS = {"scale": "#1E8E3E", "hold": GREY, "fix": AMBER, "stop / restructure": "#C5221F",
                   "insufficient data": GREY}


def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


# ---------------------------------------------------------------- sidebar
st.sidebar.title("🎟️ Growth Center")
st.sidebar.caption("CampusFest attendee campaign · source data 15 Jan–20 Apr 2025 (synthetic)")
page = st.sidebar.radio("Go to", ["Overview", "Campaigns", "Diagnose", "Plan & simulate", "Execute", "AI Analyst"])
as_of = st.sidebar.date_input("Data as of (end of day, IST)", value=date(2025, 4, 20),
                              min_value=date(2025, 1, 15), max_value=date(2025, 4, 20))
show_rate = st.sidebar.slider("Assumed show rate for projections", 0.40, 0.95, 0.69, 0.01,
                              help="Share of registrants expected to attend. 0.69 = CampusFest 2025 actual (1,925 of 2,800).")
with st.sidebar.expander("Decision thresholds"):
    scale_ratio = st.slider("Scale if cost ≤ × blended", 0.5, 1.0, 0.8, 0.05)
    stop_ratio = st.slider("Stop if cost ≥ × blended", 1.2, 3.0, 2.0, 0.1)
    min_show = st.slider("Fix if show rate below", 0.3, 0.9, 0.6, 0.05)
with st.sidebar.expander("Data"):
    st.caption(f"Storage: **{db.backend()}**")
    up = st.file_uploader("Replace with a changed workbook (.xlsx, same sheets)", type=["xlsx"])
    if up is not None and st.button("Rebuild from uploaded workbook"):
        try:
            db.init_from_upload(up.getvalue())
            st.success("Rebuilt from the uploaded workbook. Every view now uses it.")
        except Exception as ex:
            st.error(f"Could not read that workbook: {ex}")
    if st.button("Reset to original source data"):
        db.init_db(force=True)
        st.success("Database rebuilt from the original workbook.")
analyst.STATE["as_of"] = str(as_of)
analyst.STATE["show_rate"] = show_rate

d = db.load_all()
snap = metrics.snapshot(d, as_of)
tgt = metrics.target_at(d, as_of)
plan = db.read("campaign_plan")


def pct(a, b):
    return f"{100 * a / b:.0f}% of goal" if b else ""


# ---------------------------------------------------------------- overview
if page == "Overview":
    st.title("Overview")
    st.caption(f"Target plan in force: **{tgt['target_version']}** (from {pd.Timestamp(tgt['effective_at']).date()})")
    c = st.columns(4)
    c[0].metric("Identified external people", f"{snap['identified_people']:,}",
                pct(snap["identified_people"], tgt["identified_external_people_goal"]))
    c[1].metric("Registered external people", f"{snap['registered_people']:,}",
                pct(snap["registered_people"], tgt["registration_goal"]))
    c[2].metric("Verified unique visitors", f"{snap['verified_visitors']:,}",
                pct(snap["verified_visitors"], tgt["unique_external_visitors_goal"]))
    c[3].metric("Marketing spend (net)", f"₹{snap['spend_inr']:,}",
                f"{100 * snap['spend_inr'] / tgt['marketing_budget_inr']:.0f}% of ₹{tgt['marketing_budget_inr']:,} budget",
                delta_color="off")

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("Funnel (identified people → visitors)")
        stages = ["Identified", "Registered", "Confirmed (latest status)", "Verified visitor"]
        vals = [snap["identified_people"], snap["registered_people"], snap["status_confirmed"], snap["verified_visitors"]]
        fig = go.Figure(go.Funnel(y=stages, x=vals, textinfo="value+percent previous",
                                  marker={"color": [NAVY, BLUE, "#5B8DD9", AMBER]}))
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
        st.caption(f"Anonymous activity: {snap['impressions']:,} impressions · {snap['clicks']:,} clicks · "
                   f"{snap['landing_page_sessions']:,} sessions · {snap['registration_starts_anonymous']:,} form starts "
                   f"(events, not people). Walk-ins without registration: {snap.get('walk_in_visitors_without_registration', 0)}.")
    with right:
        st.subheader("Projection")
        p = metrics.projection(d, as_of, show_rate)
        if p["mode"] == "actual":
            st.metric("Final verified visitors (actual)", f"{p['verified_visitors']:,}",
                      f"{p['verified_visitors'] - tgt['unique_external_visitors_goal']:+,} vs goal")
        else:
            st.metric("Projected verified visitors", f"{p['projected_verified_visitors']:,}",
                      f"{p['projected_verified_visitors'] - tgt['unique_external_visitors_goal']:+,} vs goal")
            st.caption(f"{p['registrations_so_far']:,} registrations + {p['recent_registrations_per_day']}/day "
                       f"(last 14 days) × {p['days_to_event']} days → {p['projected_registrations']:,} registrations; "
                       f"× {show_rate:.0%} assumed show rate × 1.065 walk-ins. **Assumption-based.**")
        st.subheader("Cost efficiency")
        st.metric("Cost per registration", f"₹{snap['cost_per_registration_inr'] or 0:,}")
        if snap["cost_per_visitor_inr"]:
            st.metric("Cost per verified visitor", f"₹{snap['cost_per_visitor_inr']:,}")

    st.subheader("Pacing: cumulative registrations and spend")
    ext = set(d["people"].loc[d["people"].person_type == "external", "person_id"])
    regs = d["registrations"][d["registrations"].person_id.isin(ext)]
    e = metrics.end_of(as_of)
    days = pd.date_range("2025-01-15", pd.Timestamp(as_of), freq="D")
    cum_reg = [regs[regs.registered_at <= metrics.end_of(x)].person_id.nunique() for x in days]
    dd = d["daily"].copy()
    dd["activity_date"] = pd.to_datetime(dd.activity_date)
    sp = dd.groupby("activity_date").marketing_spend_inr.sum().reindex(days, fill_value=0).cumsum()
    pace = pd.DataFrame({"date": days, "registrations": cum_reg, "spend_inr": sp.values})
    a, b = st.columns(2)
    f1 = px.line(pace, x="date", y="registrations", color_discrete_sequence=[BLUE])
    f1.add_hline(y=tgt["registration_goal"], line_dash="dash", line_color=AMBER, annotation_text="goal")
    f1.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
    a.plotly_chart(f1, width="stretch")
    f2 = px.line(pace, x="date", y="spend_inr", color_discrete_sequence=[NAVY])
    f2.add_hline(y=tgt["marketing_budget_inr"], line_dash="dash", line_color=AMBER, annotation_text="budget")
    f2.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
    b.plotly_chart(f2, width="stretch")

# ---------------------------------------------------------------- campaigns
elif page == "Campaigns":
    st.title("Campaigns")
    t = metrics.decision_table(d, as_of, scale_ratio, stop_ratio, min_show)
    t = t.merge(plan[["campaign_id", "planned_budget_inr", "status"]], on="campaign_id", how="left")
    metric = t.metric_used.iloc[0]
    st.caption(f"Decision rule uses **{metric.replace('_', ' ')}** "
               f"({'after the event' if metric == 'cost_per_visitor_inr' else 'before the event'}). "
               "Adjust thresholds in the sidebar.")
    show = t[["campaign", "owner", "status", "planned_budget_inr", "spend_inr", "identified_people", "registered_people",
              "status_cancelled", "verified_visitors", "cost_per_registration_inr", "cost_per_visitor_inr",
              "registration_to_visit_pct", "decision", "reason"]]
    show = show.rename(columns={"planned_budget_inr": "plan ₹", "spend_inr": "spent ₹", "identified_people": "identified",
                                "registered_people": "registered", "status_cancelled": "cancelled",
                                "verified_visitors": "visitors", "cost_per_registration_inr": "₹/registration",
                                "cost_per_visitor_inr": "₹/visitor", "registration_to_visit_pct": "show %"})
    st.dataframe(show.style.apply(lambda col: [f"color: {DECISION_COLORS.get(v, '')}; font-weight: 600" for v in col],
                                  subset=["decision"]), width="stretch", hide_index=True)
    a, b = st.columns(2)
    fig = px.bar(t.sort_values(metric), x=metric, y="campaign", color="decision", orientation="h",
                 color_discrete_map=DECISION_COLORS, title=metric.replace("_", " "))
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
    a.plotly_chart(fig, width="stretch")
    fig2 = px.scatter(t, x="spend_inr", y="verified_visitors" if metric == "cost_per_visitor_inr" else "registered_people",
                      size="identified_people", color="decision", hover_name="campaign", color_discrete_map=DECISION_COLORS,
                      title="Spend vs outcome (hover for campaign)")
    fig2.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
    b.plotly_chart(fig2, width="stretch")

    flagged = t[t.decision.isin(["stop / restructure", "fix", "scale"])]
    if len(flagged):
        st.subheader("Turn flags into tasks")
        for _, r in flagged.iterrows():
            verb = {"stop / restructure": "Pause or restructure", "fix": "Fix show rate of", "scale": "Scale up"}[r.decision]
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{verb} {r.campaign}**: {r.reason}")
            if c2.button("Create task", key=f"flagtask_{r.campaign_id}"):
                tid = db.add_task(f"{verb} {r.campaign}", r.campaign_id, r.owner,
                                  str((pd.Timestamp(as_of) + pd.Timedelta(days=3)).date()),
                                  "high" if r.decision != "scale" else "medium", r.reason, source="decision flag")
                st.success(f"Task #{tid} created and assigned to {r.owner} (see Execute → Tasks).")

    st.subheader("Campaign detail")
    name = st.selectbox("Campaign", d["campaigns"].campaign_name)
    cid = d["campaigns"].set_index("campaign_name").loc[name, "campaign_id"]
    sr = metrics.stage_rates(d, as_of, cid)
    k = st.columns(5)
    k[0].metric("Identified → registered", f"{sr['identified_to_registered_pct'] or 0}%")
    k[1].metric("Cancelled or waitlisted", f"{sr['cancelled_or_waitlisted_pct'] or 0}%")
    k[2].metric("Registered → visited", f"{sr['registered_to_visit_pct'] or 0}%")
    k[3].metric("Opt-outs (of identified)", f"{sr['opt_out_pct_of_identified'] or 0}%")
    k[4].metric("Session → form start", f"{sr['session_to_form_start_pct'] or 0}%")
    w = metrics.weekly(d, as_of, cid)
    fig3 = go.Figure()
    fig3.add_bar(x=w.week_ending, y=w.registrations, name="registrations", marker_color=BLUE)
    fig3.add_scatter(x=w.week_ending, y=w.cost_per_registration_inr, name="₹ per registration", yaxis="y2",
                     line=dict(color=AMBER))
    fig3.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                       yaxis2=dict(overlaying="y", side="right", title="₹ per registration"))
    st.plotly_chart(fig3, width="stretch")

# ---------------------------------------------------------------- diagnose
elif page == "Diagnose":
    st.title("Diagnose")
    rows = []
    for _, c in d["campaigns"].iterrows():
        sr = metrics.stage_rates(d, as_of, c.campaign_id)
        rows.append({"campaign": c.campaign_name, "identified → registered %": sr["identified_to_registered_pct"],
                     "cancelled or waitlisted %": sr["cancelled_or_waitlisted_pct"],
                     "registered → visited %": sr["registered_to_visit_pct"],
                     "opt-out % of identified": sr["opt_out_pct_of_identified"],
                     "session → form start %": sr["session_to_form_start_pct"]})
    stg = pd.DataFrame(rows)
    st.subheader("Where each campaign leaks")
    st.dataframe(stg.style.background_gradient(cmap="RdYlGn", subset=["identified → registered %", "registered → visited %"])
                 .background_gradient(cmap="RdYlGn_r", subset=["cancelled or waitlisted %", "opt-out % of identified"]),
                 width="stretch", hide_index=True)

    st.subheader("Automatic findings")
    findings = []
    gap = {"identified people": (snap["identified_people"], tgt["identified_external_people_goal"]),
           "registrations": (snap["registered_people"], tgt["registration_goal"]),
           "verified visitors": (snap["verified_visitors"], tgt["unique_external_visitors_goal"])}
    for k_, (v, g) in gap.items():
        if g and v < g:
            findings.append(f"**{k_.capitalize()}** at {v:,} vs goal {g:,} ({100 * v / g:.0f}%): short by {g - v:,}.")
    dt = metrics.decision_table(d, as_of, scale_ratio, stop_ratio, min_show)
    for _, r in dt[dt.decision.isin(["stop / restructure", "fix"])].iterrows():
        findings.append(f"**{r.campaign}** flagged *{r.decision}*: {r.reason}")
    if stg["registered → visited %"].fillna(0).max() > 0:
        lo = stg.sort_values("registered → visited %").iloc[0]
        hi = stg.sort_values("registered → visited %").iloc[-1]
        findings.append(f"Show-rate spread: {lo.campaign} {lo['registered → visited %']}% vs {hi.campaign} "
                        f"{hi['registered → visited %']}%. Registrations from low-show channels are worth less.")
    w_all = metrics.weekly(d, as_of)
    if len(w_all) >= 4:
        last2 = w_all.tail(2)
        prev = w_all.iloc[-6:-2]
        c_last = last2.spend_inr.sum() / max(last2.registrations.sum(), 1)
        c_prev = prev.spend_inr.sum() / max(prev.registrations.sum(), 1)
        findings.append(f"Cost per registration in the last 2 weeks: ₹{c_last:.0f} vs ₹{c_prev:.0f} in the 4 weeks before "
                        f"({'rising' if c_last > c_prev * 1.1 else 'falling' if c_last < c_prev * 0.9 else 'stable'}).")
    for f in findings:
        st.markdown(f"- {f}")
    st.caption("Findings are computed from the data at the selected date; they are signals to investigate, not proof of cause.")

    st.subheader("Weekly trend, all campaigns")
    fig = go.Figure()
    fig.add_bar(x=w_all.week_ending, y=w_all.registrations, name="registrations", marker_color=BLUE)
    fig.add_scatter(x=w_all.week_ending, y=w_all.spend_inr, name="spend ₹", yaxis="y2", line=dict(color=NAVY))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis2=dict(overlaying="y", side="right"))
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- plan & simulate
elif page == "Plan & simulate":
    st.title("Plan & simulate")
    st.caption("Set a budget per campaign and see projected registrations and visitors. Model: observed cost per "
               "registration, rising 30% per doubling of spend (assumption), times observed show rate (69% before the event).")
    cur = metrics.campaign_table(d, as_of)
    budgets = {}
    cols = st.columns(4)
    for i, (_, r) in enumerate(cur.iterrows()):
        default = int(plan.set_index("campaign_id").loc[r.campaign_id, "planned_budget_inr"])
        budgets[r.campaign_id] = cols[i % 4].number_input(f"{r.campaign} (spent ₹{r.spend_inr:,})", 0, 1_000_000,
                                                          default, 1000, key=f"b_{r.campaign_id}")
    sim = metrics.simulate_reallocation(d, as_of, budgets)
    base = metrics.simulate_reallocation(d, as_of, {})
    a, b, c = st.columns(3)
    a.metric("Scenario budget", f"₹{int(sim.budget_inr.sum()):,}", f"₹{int(sim.budget_inr.sum() - base.budget_inr.sum()):+,} vs spend so far")
    b.metric("Projected registrations", f"{int(sim.registrations.sum()):,}", f"{int(sim.registrations.sum() - base.registrations.sum()):+,}")
    c.metric("Projected visitors", f"{int(sim.visitors.sum()):,}", f"{int(sim.visitors.sum() - base.visitors.sum()):+,}")
    st.dataframe(sim, width="stretch", hide_index=True)
    if st.button("Save these budgets as the campaign plan"):
        for cid, v in budgets.items():
            db.update_plan(cid, planned_budget_inr=v)
        st.success("Plan saved. Campaign and AI Analyst views now use it.")

# ---------------------------------------------------------------- execute
elif page == "Execute":
    st.title("Execute")
    tab1, tab2, tab3, tab4 = st.tabs(["Tasks", "Campaign plan", "Log daily marketing", "Targets & change log"])
    with tab1:
        tasks = db.read("tasks")
        tasks["due_date"] = pd.to_datetime(tasks.due_date, errors="coerce").dt.date
        edited = st.data_editor(
            tasks.drop(columns=["created_at", "updated_at"]), num_rows="dynamic", width="stretch", hide_index=True,
            column_config={"status": st.column_config.SelectboxColumn(options=["open", "in progress", "done", "blocked"]),
                           "priority": st.column_config.SelectboxColumn(options=["high", "medium", "low"]),
                           "campaign_id": st.column_config.SelectboxColumn(options=[""] + list(d["campaigns"].campaign_id)),
                           "due_date": st.column_config.DateColumn(),
                           "task_id": st.column_config.NumberColumn(disabled=True)}, key="tasks_editor")
        if st.button("Save tasks"):
            e = edited.copy()
            missing = e.task_id.isna()
            start = int(tasks.task_id.max() or 0) + 1 if len(tasks) else 1
            e.loc[missing, "task_id"] = range(start, start + missing.sum())
            e["source"] = e.source.fillna("manual")
            now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            e["created_at"] = e.task_id.map(tasks.set_index("task_id").created_at).fillna(now)
            e["updated_at"] = now
            e["due_date"] = pd.to_datetime(e.due_date, errors="coerce")
            db.replace_table("tasks", e, f"{len(e)} tasks saved")
            st.success("Tasks saved.")
        overdue = tasks[(tasks.status != "done") & (pd.to_datetime(tasks.due_date) < pd.Timestamp(as_of))]
        if len(overdue):
            st.warning(f"{len(overdue)} open task(s) past due as of {as_of}.")
    with tab2:
        pe = st.data_editor(plan, width="stretch", hide_index=True, disabled=["campaign_id", "campaign_name"],
                            column_config={"status": st.column_config.SelectboxColumn(options=["active", "paused", "stopped"])})
        if st.button("Save campaign plan"):
            db.replace_table("campaign_plan", pe, "campaign plan edited")
            st.success("Campaign plan saved.")
        st.caption("Planned budgets were seeded by splitting the ₹3,00,000 revised budget in proportion to actual spend (simulated).")
    with tab3:
        st.caption("Add or correct a day of campaign activity. Every chart and the AI Analyst update immediately.")
        with st.form("daily"):
            cc = st.columns(4)
            camp = cc[0].selectbox("Campaign", d["campaigns"].campaign_name)
            day = cc[1].date_input("Date", value=as_of)
            spend = cc[2].number_input("Spend ₹ (net)", -100000, 1000000, 0, 500)
            imp = cc[3].number_input("Impressions", 0, 10_000_000, 0, 100)
            cc2 = st.columns(4)
            clicks = cc2[0].number_input("Clicks", 0, 1_000_000, 0, 10)
            reach = cc2[1].number_input("Reported reach", 0, 10_000_000, 0, 100)
            sess = cc2[2].number_input("Landing-page sessions", 0, 1_000_000, 0, 10)
            starts = cc2[3].number_input("Registration starts", 0, 100_000, 0, 1)
            if st.form_submit_button("Save day"):
                row = d["campaigns"].set_index("campaign_name").loc[camp]
                aid = f"AD-{row.campaign_id}-{pd.Timestamp(day):%m%d}-M"
                daily = d["daily"][d["daily"].activity_id != aid].copy()
                new = pd.DataFrame([{"campaign_name": camp, "owner_name": row.owner_name, "activity_date": pd.Timestamp(day),
                                     "impressions": imp, "clicks": clicks, "reported_reach": reach,
                                     "landing_page_sessions": sess, "registration_starts": starts,
                                     "marketing_spend_inr": spend, "platform": "manual entry", "activity_id": aid,
                                     "campaign_id": row.campaign_id, "owner_id": row.owner_id}])
                db.replace_table("daily", pd.concat([daily, new], ignore_index=True), f"daily {aid} saved")
                st.success(f"Saved {aid}.")
        st.dataframe(d["daily"].sort_values("activity_date", ascending=False).head(50), width="stretch", hide_index=True)
    with tab4:
        te = st.data_editor(d["targets"], num_rows="dynamic", width="stretch", hide_index=True)
        if st.button("Save targets"):
            db.replace_table("targets", te, "targets edited")
            st.success("Targets saved.")
        st.subheader("Change log")
        st.dataframe(db.read("change_log").sort_values("at", ascending=False), width="stretch", hide_index=True)

# ---------------------------------------------------------------- AI analyst
elif page == "AI Analyst":
    st.title("AI Growth Analyst")
    api_key = secret("GEMINI_API_KEY")
    model = secret("GEMINI_MODEL", "gemini-2.5-flash")
    fallback = secret("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite")
    st.caption(f"Answers come from tools that query the live database as of **{as_of}** · model `{model}`. "
               "It proposes tasks and plan changes; nothing is saved until you confirm.")
    if not api_key:
        st.error("Add GEMINI_API_KEY to the app's secrets to enable the analyst (see README).")
        st.stop()
    st.session_state.setdefault("msgs", [])
    examples = ["Are we on track for the visitor goal? Show the numbers.",
                "Which campaign is the biggest bottleneck, and at which stage?",
                "Move ₹40,000 from Paid Social to College Partnerships: what happens?",
                "Create a task to fix the weakest campaign's show rate.",
                "What share of our visitors were women?"]
    ex_cols = st.columns(len(examples))
    clicked = None
    for i, q in enumerate(examples):
        if ex_cols[i].button(q, key=f"ex{i}", width="stretch"):
            clicked = q
    for m in st.session_state.msgs:
        with st.chat_message("user" if m["role"] == "user" else "assistant"):
            st.markdown(m["text"])
            if m.get("calls"):
                with st.expander("Data the analyst used"):
                    st.json(m["calls"])
    q = st.chat_input("Ask about performance, bottlenecks, budgets or tasks…") or clicked
    if q:
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("Analysing the live data…"):
                import time
                text, calls = None, []
                attempts = [model, model, model] + ([fallback] if fallback and fallback != model else [])
                first_err = ""
                for i, m_ in enumerate(attempts):
                    analyst.STATE["pending"] = []
                    try:
                        chat = analyst.make_chat(api_key, m_, st.session_state.msgs)
                        resp = chat.send_message(q)
                        text = resp.text or "(No answer returned.)"
                        calls = analyst.tool_calls_from(resp)
                        if m_ != model:
                            text += f"\n\n_(Answered by fallback model `{m_}` because `{model}` was busy.)_"
                        break
                    except Exception as ex:
                        err = str(ex)
                        first_err = first_err or err
                        busy = any(k in err for k in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "overloaded", "500", "INTERNAL"])
                        if not busy and i < 3:
                            text = f"The analyst could not answer: `{err[:300]}`"
                            break
                        text = ("The AI service is busy or rate-limited right now; please ask again in a minute. "
                                f"(`{first_err[:200]}`)")
                        if i < 2:
                            time.sleep(4 * (i + 1))
            st.markdown(text)
            if calls:
                with st.expander("Data the analyst used"):
                    st.json(calls)
        st.session_state.msgs += [{"role": "user", "text": q}, {"role": "model", "text": text, "calls": calls}]
        st.session_state.pending = st.session_state.get("pending", []) + analyst.STATE["pending"]
        analyst.STATE["pending"] = []
        st.rerun()

    pending = st.session_state.get("pending", [])
    if pending:
        st.subheader("Proposed actions: confirm to save")
        for i, p in enumerate(list(pending)):
            with st.container(border=True):
                if p["type"] == "task":
                    st.markdown(f"**New task:** {p['title']}  \nCampaign: {p['campaign_id'] or '—'} · Owner: {p['owner'] or '—'} · "
                                f"Due: {p['due_date'] or '—'} · Priority: {p['priority']}  \n_Why:_ {p['rationale']}")
                else:
                    st.markdown(f"**Plan change for {p['campaign_id']}:** budget → {p['new_budget_inr'] or 'unchanged'}, "
                                f"status → {p['new_status'] or 'unchanged'}  \n_Why:_ {p['rationale']}")
                a, b = st.columns(2)
                if a.button("Confirm", key=f"ok{i}"):
                    if p["type"] == "task":
                        tid = db.add_task(p["title"], p["campaign_id"], p["owner"], p["due_date"], p["priority"],
                                          p["rationale"], source="ai analyst")
                        msg = f"✅ Task #{tid} saved: {p['title']}"
                    else:
                        db.update_plan(p["campaign_id"], p["new_budget_inr"], p["new_status"], p["rationale"][:300])
                        msg = f"✅ Plan updated for {p['campaign_id']}"
                    if st.session_state.msgs and st.session_state.msgs[-1]["role"] == "model":
                        st.session_state.msgs[-1]["text"] += f"\n\n{msg} (confirmed by user)."
                    else:
                        st.session_state.msgs.append({"role": "model", "text": msg + " (confirmed by user)."})
                    pending.pop(i)
                    st.rerun()
                if b.button("Discard", key=f"no{i}"):
                    pending.pop(i)
                    st.rerun()
    if st.session_state.msgs and st.button("Clear conversation"):
        st.session_state.msgs = []
        st.session_state.pending = []
        st.rerun()
