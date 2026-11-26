"""Target model for a 2-day college festival in Delhi NCR.
Channel unit costs and show rates come from CampusFest 2025 history (see metrics.py);
saturation, budget and new levers are assumptions, stated below."""
import math
from metrics import load_excel, campaign_table
d = load_excel("attendee_dataset.xlsx")
hist = campaign_table(d, "2025-04-20").set_index("campaign")
SAT = 0.30          # assumption: cost per registration rises 30% per doubling of spend
WALKIN = 125 / 1925 # history: walk-ins per registered visitor
def cpr(name, spend):
    h = hist.loc[name]; base_spend, base_cpr = h.spend_inr, h.cost_per_registration_inr
    mult = max(spend / base_spend, 1)
    return base_cpr * (1 + SAT * math.log2(mult)) if mult > 1 else base_cpr
def show(name): return hist.loc[name].registration_to_visit_pct / 100
BASE = {"College Partnerships": 160000, "Student Referrals": 100000, "Campus Ambassadors": 110000,
        "Community Groups": 60000, "Organic Search": 30000, "Paid Social": 90000, "Creator Partners": 30000}
def run(plan, show_lift=0.0, extra_regs=0, label=""):
    tot_r = tot_v = tot_s = 0
    rows = []
    for k, s in plan.items():
        c = cpr(k, s); r = s / c; v = r * min(show(k) + show_lift, 0.95)
        rows.append((k, s, round(c), round(r), round(show(k) * 100 + show_lift * 100), round(v)))
        tot_r += r; tot_v += v; tot_s += s
    ref_v = extra_regs * min(0.75 + show_lift, 0.95)
    tot_r += extra_regs; tot_v += ref_v
    walk = tot_v * WALKIN
    print(f"\n== {label}: spend {tot_s:,}")
    for row in rows: print("  %-22s spend %7d  CPR %4d  regs %5d  show %3d%%  visitors %5d" % row)
    if extra_regs: print(f"  extra (squad passes + referral loop) regs {extra_regs}, visitors {round(ref_v)}")
    print(f"  registrations {round(tot_r)}, registered visitors {round(tot_v)}, walk-ins {round(walk)}, TOTAL {round(tot_v + walk)}, CPV {round(tot_s / (tot_v + walk))}")
print(hist[["spend_inr","registered_people","verified_visitors","cost_per_registration_inr","cost_per_visitor_inr","registration_to_visit_pct"]])
run(BASE, label="BASE (Rs 5.8 L + 0.2 L contingency)")
# stretch: same budget, + show-rate engine (+8 pp), + squad passes & referral loop:
#   squad passes: 300 society squads x 4 extra friends = 1,200 regs at ~zero media cost
#   referral loop: 25% of 6,000 confirmed registrants refer 1 friend = 1,500 regs (reward cost inside referral budget)
run(BASE, show_lift=0.08, extra_regs=2700, label="STRETCH")
