# CampusFest Growth Center — RISA Labs Growth APM assignment

**Abhishek Kumar Ojha · IIT Kharagpur** · Challenge A (Attendee Growth) · City: Delhi NCR

Three deliverables:
1. **Strategy deck** (3 slides, PDF): target, ranked bets, signals and thresholds.
2. **Growth Center** (this repo): a Streamlit app with an analytics dashboard, a campaign and task manager, and an embedded AI analyst (Gemini) that works on the live data.
3. **This README**: research, assumptions, calculations, framework, setup, tools, testing and limitations.

---

## 1. Research and sourced facts

| Fact | Value | Source |
|---|---|---|
| DU undergraduate admissions 2025–26 | 72,230 students across 69 colleges | Careers360, Nov 2025 (DU University Court report) |
| DU UG students on roll (derived) | ≈ 2.2 lakh (72k a year × 3 years) | Derived from the row above |
| IPU (GGSIPU) total students | 93,000+ students, 120+ affiliated colleges | ipu.ac.in (via MSM Unify) |
| Largest Delhi fest benchmark | IIT Delhi Rendezvous: 1,60,000+ footfall, 1,200+ colleges, 4 days | rdv-iitd.org |
| CampusFest 2025 outcomes | 2,050 verified external visitors on ₹2,74,000 net spend; goal 2,200 | Provided dataset (synthetic) |

**Why Delhi NCR:** largest concentration of college students in India, dense Metro links between campuses, and proven appetite for large fests. Trade-off: competition from big fests (RDV, DU college fests), so we win on groups and referrals rather than headline stars.

## 2. What the 2025 data says (all from the dataset)

Rules applied (from the dataset's *Read me*): duplicate source IDs removed (2 daily-marketing rows, 4 status rows, 20 check-in rows); a date means end of day IST; latest status version per registration; attendance = **admitted + verified** check-ins of **external** people, each person once.

| Campaign | Spend ₹ | Registered | Visitors | ₹ / registration | ₹ / visitor | Show rate |
|---|---|---|---|---|---|---|
| Campus Ambassadors | 42,000 | 520 | 390 | 81 | 108 | 75.0% |
| Paid Social | 93,000 | 680 | 340 | 137 | 274 | 50.0% |
| Creator Partners | 59,000 | 350 | 175 | 169 | 337 | 50.0% |
| College Partnerships | 31,000 | 450 | 385 | 69 | 81 | 85.6% |
| Student Referrals | 19,000 | 350 | 275 | 54 | 69 | 78.6% |
| Organic Search | 14,000 | 250 | 195 | 56 | 72 | 78.0% |
| Community Groups | 16,000 | 200 | 165 | 80 | 97 | 82.5% |
| **Total** | **2,74,000** | **2,800** | **2,050** (1,925 registered + 125 walk-ins) | **98** | **134** | **68.8%** |

Goals (revised plan, 15 Mar): 3,600 identified · 3,200 registrations · 2,200 visitors · ₹3,00,000 budget. Actual: 3,625 identified (met), 2,800 registrations (87.5%), 2,050 visitors (93%), ₹2,74,000 spent.

**Insight:** Paid Social and Creators took 56% of spend but delivered 25% of visitors, at half the show rate of partnership and referral channels. Registrations from them are worth half as much.

## 3. Target model (slide 1)

**Assumptions** (not sourced): budget ₹6,00,000 (₹5,80,000 to channels + ₹20,000 reserve); cost per registration rises **30% per doubling** of a channel's spend; walk-ins = 6.5% of registered visitors (125 / 1,925 in 2025); venue capacity 5,000 a day.

Per channel: `registrations = budget ÷ (2025 ₹/registration × (1 + 0.30 × log2(budget ÷ 2025 spend)))`; `visitors = registrations × 2025 show rate`; total visitors × 1.065 for walk-ins.

| Channel | Budget ₹ | ₹/reg | Registrations | Show | Visitors |
|---|---|---|---|---|---|
| College partnerships | 1,80,000 | 122 | 1,481 | 86% | 1,268 |
| Student referrals | 1,20,000 | 97 | 1,236 | 79% | 972 |
| Campus ambassadors | 1,10,000 | 115 | 959 | 75% | 719 |
| Community groups | 70,000 | 131 | 534 | 82% | 440 |
| Organic search | 30,000 | 74 | 403 | 78% | 314 |
| Paid social (retarget) | 50,000 | 137 | 365 | 50% | 182 |
| Creators | 20,000 | 169 | 118 | 50% | 59 |
| **Base total** | **5,80,000** | **114** | **5,096** | | **3,955 + 257 walk-ins = 4,212** |

- **Base: 4,200 verified visitors** at ₹138 each.
- **Stretch: 7,000 (7,032)**, same budget: squad passes (+1,200 registrations: 300 squads × 4 friends), referral loop (+1,500: 25% of ≈6,000 registrants refer one friend, 75% show), and the show-rate engine (+8 points on every channel). ₹82 per visitor.
- **Reach check:** in 2025, 1,029,015 impressions gave 3,625 identified people (≈284 impressions each) and 77.2% of identified people registered. Base needs 5,096 / 0.772 ≈ 6,600 identified ≈ 1.9M impressions.
- **Sanity checks:** reallocating the *same* ₹2,80,000 by the same rules gives 2,426 visitors vs 2,050 actual (+18%), so the gain is not only from more money. Stretch = ~3% of DU UG students alone; ≤3,500 a day vs 5,000 capacity.
- Ideas measured one at a time add +430 (show-rate engine), +960 (squad passes) and +1,200 (referral loop) = 2,590; together they add 2,820, because the higher show rate also applies to squad and referral registrations.
- Re-run: `python model.py`.

## 4. Prioritisation framework (slide 2)

**ICE = Impact × Confidence × Ease**, each 1–10. Impact = incremental visitors from the model; Confidence = how directly 2025 data supports it; Ease = cost, time and dependencies.

| # | Idea | +Visitors | I·C·E | Call |
|---|---|---|---|---|
| 1 | Show-rate engine (reminders, transfer-not-cancel, waitlist auto-fill) | +430 | 8·8·9 = 576 | Double down |
| 2 | Society Squad Passes | +960 | 9·7·8 = 504 | Double down |
| 3 | Referral loop (bring 3, skip the queue) | +1,200 | 8·6·8 = 384 | Scale if K ≥ 0.25 |
| 4 | Paid social: retargeting only | saves ₹43k | 4·8·9 = 288 | Keep small |
| 5 | Inter-college qualifiers | +400 (assumed upside) | 6·5·5 = 150 | Test only |

Rejected: celebrity headliner, Metro/hoarding ads, broad creator awareness, discounts on an already-free pass.

## 5. The Growth Center (app)

| Page | What it does |
|---|---|
| **Overview** | KPIs vs the target plan in force at the selected date, funnel, projection (actual after the event), pacing of registrations and spend |
| **Campaigns** | Per-campaign table with scale / hold / fix / stop flags (thresholds editable in the sidebar), one-click "Create task" for each flagged campaign, spend-vs-outcome charts, campaign drill-down with stage conversions and weekly cost per registration |
| **Diagnose** | Leakage heat map by stage, automatic findings (gaps to goal, flagged campaigns, show-rate spread, cost trend) |
| **Plan & simulate** | Budget per campaign → projected registrations and visitors; save as the campaign plan |
| **Execute** | Task manager (add, edit, assign, due dates, status), campaign plan editor, daily marketing entry, targets editor, change log |
| **AI Analyst** | Gemini chat grounded in the live database, with tool calls shown and confirm-before-save actions |

**Every number is recomputed from the database on each view**. Data can be changed three ways: edit records in Execute (daily marketing, targets, campaign plan, tasks); upload a changed copy of the workbook (sidebar → Data), which rebuilds everything; or reset to the original data. **Storage** is Postgres when `DATABASE_URL` is set (permanent, recommended: free Supabase), otherwise SQLite. Any edit (a new day of spend, a changed target, a task) updates all analytics and the AI analyst immediately. The **"Data as of" date** in the sidebar replays the campaign at any day between 15 Jan and 20 Apr 2025, without future data leaking in.

### The AI analyst

- **Grounded:** Gemini can only get numbers by calling 10 tools: `get_overview`, `get_campaign_metrics`, `get_campaign_detail`, `get_daily_trend`, `simulate_budget_reallocation`, `move_budget` (exact before → after for "move ₹X from A to B"), `list_tasks`, `run_sql` (one read-only SELECT on a read-only connection), `propose_task`, `propose_plan_change`. The tools use the same metric engine as the dashboard.
- **Honest:** the system prompt requires every figure to come from a tool, separates evidence from assumptions, and makes it say when the data can't answer (e.g. gender, college names, ticket revenue, sentiment). Tool errors are returned to the model so it can correct itself.
- **Connected to execution:** it proposes tasks or plan changes; they appear as cards under the chat and are saved only when the user clicks **Confirm**.
- **Follow-ups:** the conversation history is sent with each question.
- **Rate limits:** Gemini's free tier allows few requests a minute; if the main model is rate-limited or busy, the app retries once with a fallback model (`gemini-2.5-flash-lite`) and says so.

Demo workflow: "Which campaign is the biggest bottleneck?" → "What happens if we move ₹40,000 from Paid Social to College Partnerships?" → "Create a task for that" → Confirm → the task appears in Execute → "What share of our visitors were women?" (the analyst says the data has no gender field).

## 6. Setup

**Local**
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add your Gemini key
streamlit run app.py
```

**Deploy (free, ~10 minutes)**
1. Push this folder to a GitHub repo (keep `attendee_dataset.xlsx` in it).
2. share.streamlit.io → New app → pick the repo, main file `app.py`.
3. (Recommended, 5 min) Permanent storage: create a free project at supabase.com → Connect → copy the **Transaction pooler** URI and put your database password in it.
4. Advanced settings → Secrets: paste `GEMINI_API_KEY = "…"` (free key from aistudio.google.com) and `DATABASE_URL = "…"` (step 3). See `.streamlit/secrets.toml.example`.
5. Deploy and share the URL. The sidebar's Data panel shows which storage is active.

The database (`growth.db`) is built from the workbook on first run. The sidebar's **Data → Reset** button rebuilds it from the original source data for testing.

## 7. Tools used

Python 3, Streamlit, pandas, Plotly, SQLAlchemy with SQLite or Supabase Postgres (free plan), Google Gen AI SDK (`google-genai`) with Gemini 2.5 Flash on the free tier, Streamlit Community Cloud (free). Claude (Anthropic) was used as a coding and analysis assistant; I reviewed the logic, ran the numbers and tested the app. No templates were reused.

## 8. Testing done

- Metric engine checked against hand counts: 2,050 verified external visitors (2,090 if internal/staff/test people are wrongly included), 2,800 external registrations, ₹2,74,000 net spend (₹2,76,500 on 11 Apr before vendor credits).
- Every page run headless at 15 Jan, 1 Feb, 1 Mar, 15 Mar and 20 Apr 2025 with no errors (Streamlit AppTest), on both SQLite and a real Postgres 16 database.
- Changed-data test: a workbook with Paid Social spend doubled and the visitor goal raised to 2,500 was uploaded; spend became ₹3,67,000, Paid Social's cost per visitor ₹547 (flag: stop), the goal 2,500. Reset restored the original numbers.
- One-click task from a decision flag creates a task with owner and due date, visible in Execute and to the AI analyst.
- Edits tested: adding a ₹5,000 day raised spend 2,74,000 → 2,79,000 everywhere; tasks and plan changes persist and are logged.
- AI tools tested directly: unknown campaign names and invalid SQL return errors to the model; write statements are refused, including a `WITH … DELETE` trick on Postgres (blocked by the read-only transaction). The live Gemini calls could not be tested from my build machine; test them after deploying (5 example questions are on the AI Analyst page).

## 9. Known limitations

- Without `DATABASE_URL`, Streamlit Cloud's disk is not permanent: edits are lost when the app restarts or wakes from sleep. With Supabase they persist.
- Per-campaign planned budgets and seed tasks are **simulated** (the source has only a total budget).
- Pre-event projections use an assumed show rate (sidebar, default 69%).
- Attribution follows the dataset (registration source campaign); no multi-touch model.
- The model's 30% saturation and the stretch levers are assumptions to validate in the first two weeks (slide 3 thresholds).
- The AI answer quality depends on Gemini; numbers come from tools, but wording should still be read critically.
