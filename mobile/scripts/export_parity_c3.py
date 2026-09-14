"""Export parity fixtures for the C3 on-device core (money & lifecycle).

Runs the real backend functions on fixed inputs and writes mobile/src/core/__fixtures__/c3.json.
Run from the repository root:  python mobile/scripts/export_parity_c3.py
"""

import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_MODE", "offline")

from common.reference import get_activity  # noqa: E402
from data_connectors.sms_parser import _parse_date, parse_one  # noqa: E402
from module2_financial import documentation_agent as docs  # noqa: E402
from module2_financial.financial_engine import build_financial_plan  # noqa: E402
from module2_financial.operating_model import build_operating_projection  # noqa: E402
from module3_monitoring import grievance_engine, health_score_agent, ongoing_monitoring_agent  # noqa: E402
from module3_monitoring import launch_copilot, outcome_learning_loop  # noqa: E402
from orchestrator import stores  # noqa: E402
from orchestrator.state import (  # noqa: E402
    ApplicationStatus, CaseState, FeasibilityRecord, HealthSnapshot, SessionMeta, TransactionRecord,
)

OUT = ROOT / "mobile" / "src" / "core" / "__fixtures__" / "c3.json"

# ---------------------------------------------------------------- SMS
MESSAGES = [
    "Dear Customer, Rs.350.00 credited to A/c XX4821 on 05-01-26 by UPI from ramesh.k@okaxis. UPI Ref 601234567890",
    "Rs 1,200.00 deposited in A/c XX4821 by cash at CDM on 15-03-2026. Avl Bal Rs 8,420.00 -Bank",
    "A/c XX4821 debited by Rs 2,450.00 on 08Jan26 towards UPI payment to kapdaghar@ybl. Not you? Call 1800111109",
    "INR 3,100.00 debited from A/c XX4821 on 12-Feb-2026 via NEFT to SHREE TRADERS. Avl Bal INR 5,230.10",
    "Rs 640.00 paid from A/c XX4821 on 12/03/2026 for electricity bill (BBPS). Thank you.",
    "Loan EMI of Rs 10,801.00 debited from A/c XX4821 on 28-06-26 via NACH for loan A/c XX7091.",
    "Your OTP for transaction of Rs 5,000 is 482913. Do not share it with anyone.",
    "Congratulations! You are pre-approved for a personal loan of Rs 2,00,000. Apply now!",
    "Your EMI of Rs 10,801 will be debited on 30-09-2026. Maintain sufficient balance.",
    "आपके खाते XX4821 में ₹500 credited हुए दिनांक 05-02-2026 UPI द्वारा",
    "प्रिय ग्राहक, आपके खाते से Rs 2,000 debited किए गए 14-Mar-26 को ATM से",
    "₹५०० received in your account via UPI on ०७-०४-२०२६",
    "Rs.750 credited to your a/c by IMPS",
    "Sent Rs.1,500.00 From HDFC Bank A/C x9087 To meena.s@oksbi On 21/05/26 Ref 612345678901",
    "Rs 4,000.00 withdrawn at ATM on 03-Jun-2026 from A/c XX4821. Avl bal Rs 1,230.00",
    "Purchase of INR 899.00 on card XX1234 at POS AMAZON on 2026-06-11. Avl Limit INR 45,000",
    "Avl Bal Rs 12,000.00 in A/c XX4821. Rs 300.00 Cr on 11-07-2026 UPI/ramesh",
    "ECS instalment of Rs 3,200 debited on 31 Jul 2026 for loan a/c 55512",
    "Request money of Rs 500 from anil@ybl. Pay via UPI app.",
    "Rs 250.00 transferred to A/c XX1111 on 31-02-2026 via IMPS; valid date 01-03-2026",
    "Your a/c XX4821 is credited with INR 1,250.50 on 7 August 2026 NEFT from SCHOOL UNIFORM ORDER",
    "Get a lucky draw win! Rs 10,000 cashback offer",
    "Dr Rs 450 A/c XX4821 20-08-26 UPI/kavita88@paytm",
    "Payment of Rs. 1,080.00 received from school via NEFT on 5-9-26",
    "Hello, your balance is low.",
    "Rs 12,000 spent on your debit card ending 4821 at SINGER SEWING on 10-Sep-26",
]

sms = []
for m in MESSAGES:
    rec = parse_one(m)
    has_date = _parse_date(m) is not None
    sms.append({"message": m, "result": None if rec is None else {
        "at": rec.occurred_at if has_date else None, "direction": rec.direction, "amount": rec.amount,
        "channel": rec.channel, "isLoanRepayment": rec.is_loan_repayment}})


# ---------------------------------------------------------------- monitoring aggregation + health scoring
def txn(date: str, direction: str, amount: float, loan: bool = False, channel: str = "upi") -> TransactionRecord:
    return TransactionRecord(occurred_at=f"{date}T00:00:00+00:00", direction=direction, amount=amount,
                             channel=channel, is_loan_repayment=loan)


def month_batch(rng: random.Random, year: int, month: int, revenue: float, expenses: float, repay: float = 0.0,
                days: int = 28, n_credits: int = 20) -> list[TransactionRecord]:
    out = []
    for i in range(n_credits):
        d = 1 + (i * days) // n_credits
        out.append(txn(f"{year}-{month:02d}-{d:02d}", "credit", round(revenue / n_credits * (0.7 + 0.6 * rng.random()), 2)))
    for i in range(3):
        out.append(txn(f"{year}-{month:02d}-{3 + i * 8:02d}", "debit", round(expenses / 3, 2), channel="neft_imps"))
    if repay:
        out.append(txn(f"{year}-{month:02d}-{days:02d}", "debit", repay, loan=True, channel="other"))
    return out


def case(capital: float, activity_id: str, disbursed: str | None) -> CaseState:
    plan = build_financial_plan(capital)
    act = get_activity(activity_id)
    if plan.computed_project_cost > 0:
        plan.operating_projection = build_operating_projection(plan.computed_project_cost, act)
    return CaseState(
        session_meta=SessionMeta(session_id="parity", consent_sms_monitoring=True),
        feasibility_record=FeasibilityRecord(selected_catalog_id=activity_id),
        financial_plan=plan,
        application_status=ApplicationStatus(disbursement_date=disbursed),
    )


def run_scenario(name: str, capital: float, activity_id: str, disbursed: str | None, batches) -> dict:
    state = case(capital, activity_id, disbursed)
    out = []
    for batch in batches:
        state.session_meta.pending_transactions = batch
        state = state.model_copy(update=ongoing_monitoring_agent.run(state))
        state = state.model_copy(update=health_score_agent.run(state))
        s = state.monitoring_record[-1]
        out.append({
            "days": int(s.period_label.rsplit("(", 1)[1].split()[0]),
            "revenue": s.reported_revenue, "baseline": s.projected_baseline_revenue, "expenses": s.reported_expenses,
            "surplus": s.operating_surplus, "installmentDue": s.installment_due, "status": s.loan_installment_status,
            "creditIndex": s.approximate_creditworthiness_index, "score": s.health_score, "band": s.health_band,
            "earlyWarning": s.early_warning_flag, "intervention": s.intervention_type,
        })
    return {"name": name, "capital": capital, "activity": activity_id, "disbursedOn": disbursed,
            "batches": [[{"at": t.occurred_at, "direction": t.direction, "amount": t.amount, "channel": t.channel,
                          "isLoanRepayment": t.is_loan_repayment} for t in b] for b in batches],
            "expected": out}


rng = random.Random(26091)
scenarios = [
    run_scenario("tailoring healthy then shock", 12_000, "tailoring", "2026-01-01", [
        month_batch(rng, 2026, 1, 13_000, 4_500),
        month_batch(rng, 2026, 3, 14_000, 5_000, repay=1_950),
        month_batch(rng, 2026, 7, 6_000, 8_000),
        month_batch(rng, 2026, 8, 5_000, 7_500, n_credits=6),
    ]),
    run_scenario("dairy expense spike", 50_000, "dairy_farming", "2026-01-10", [
        month_batch(rng, 2026, 4, 40_000, 20_000),
        month_batch(rng, 2026, 5, 36_000, 34_000),
        month_batch(rng, 2026, 6, 30_000, 12_000, n_credits=30),
    ]),
    run_scenario("quarter overdue no disbursement date", 12_000, "tailoring", None, [
        [txn("2026-01-02", "credit", 9_000), txn("2026-02-14", "credit", 8_000), txn("2026-04-10", "credit", 7_000),
         txn("2026-03-01", "debit", 6_000, channel="other")],
        [txn("2026-05-01", "credit", 400), txn("2026-05-03", "credit", 300)],
        [txn("2026-06-01", "debit", 900, loan=True), txn("2026-06-20", "debit", 500), txn("2026-06-21", "credit", 2_500)],
    ]),
    run_scenario("outside scheme", 600_000, "flour_mill", None, [
        month_batch(rng, 2026, 2, 400_000, 200_000),
    ]),
]

# pure scoring on fixed records (health_score_agent only)
FIXED = [  # (label, days, transactions, revenue, baseline, surplus, installment_due, status)
    ("2026-01-01 to 2026-01-31 (31 days)", 31, 40, 12_000, 12_000, 5_000, 3_000, "paid"),
    ("2026-02-01 to 2026-02-28 (28 days)", 28, 20, 12_000, 13_000, -1_000, 3_000, "unknown"),
    ("2026-03-01 to 2026-03-31 (31 days)", 31, 12, 6_000, 9_000, 3_500, 3_000, "grace_period"),
    ("2026-04-01 to 2026-04-30 (30 days)", 30, 30, 6_000, 12_000, 1_000, 0, "unknown"),
    ("2026-05-01 to 2026-05-31 (31 days)", 31, 30, 0, 0, 0, 0, "unknown"),
    ("2026-06-01 to 2026-06-30 (30 days)", 30, 30, 9_000, 10_000, 3_000, 3_000, "overdue"),
    ("2026-07-01 to 2026-07-31 (31 days)", 31, 30, 5_000, 12_000, 4_000, 2_000, "not_due"),
    ("2026-08-01 to 2026-08-31 (31 days)", 31, 30, 3_000, 12_000, 2_000, 0, "unknown"),
    ("2026-09-01 to 2026-09-30 (30 days)", 30, 30, 3_000, 12_000, 2_000, 0, "unknown"),
]
state = case(12_000, "tailoring", None)
scored = []
records = []
for label, days, n, rev, base, surplus, due, status in FIXED:
    records.append(HealthSnapshot(period_label=label, transactions_parsed=n, reported_revenue=rev,
                                  projected_baseline_revenue=base, reported_expenses=rev - surplus,
                                  operating_surplus=surplus, installment_due=due, loan_installment_status=status))
    state.monitoring_record = list(records)
    state = state.model_copy(update=health_score_agent.run(state))
    records = list(state.monitoring_record)
    s = records[-1]
    scored.append({"days": days, "transactionsParsed": n, "revenue": rev, "baseline": base, "expenses": rev - surplus,
                   "surplus": surplus, "installmentDue": due, "status": status,
                   "score": s.health_score, "band": s.health_band, "earlyWarning": s.early_warning_flag,
                   "intervention": s.intervention_type})

# ---------------------------------------------------------------- outcomes
seed = json.loads((ROOT / "data" / "synthetic" / "seed_outcomes.json").read_text(encoding="utf-8"))["records"]
REAL = [
    {"catalog_id": "tailoring", "district": "Sitapur", "intervention_type": "pricing_adjustment", "health_before": 45, "health_after": 62, "is_synthetic": False},
    {"catalog_id": "tailoring", "district": "Sitapur", "intervention_type": "pricing_adjustment", "health_before": 50, "health_after": 58, "is_synthetic": False},
    {"catalog_id": "tailoring", "district": "Lucknow", "intervention_type": "repayment_counselling", "health_before": 40, "health_after": 38, "is_synthetic": False},
    {"catalog_id": "dairy_farming", "district": "Sitapur", "intervention_type": "supply_chain_change", "health_before": 52, "health_after": 49, "is_synthetic": False},
]


def fake_records(real):
    def outcome_records(catalog_id=None):
        rows = [dict(r, improved=int(r["health_after"] > r["health_before"])) for r in seed + real]
        return [r for r in rows if not catalog_id or r["catalog_id"] == catalog_id]
    return outcome_records


priors = []
for cid, dist, real in [("tailoring", None, []), ("tailoring", "Sitapur", REAL), ("tailoring", "sitapur", REAL),
                        ("dairy_farming", "Sitapur", REAL), ("beekeeping", None, []), ("unknown_activity", None, [])]:
    stores.outcome_records = fake_records(real)
    outcome_learning_loop.stores.outcome_records = stores.outcome_records
    outcome_learning_loop._ensure_seed = lambda: None
    st = outcome_learning_loop.category_prior(cid, dist)
    priors.append({"activity": cid, "district": dist, "real": real, "prior": st.category_prior,
                   "realRecords": st.real_records, "syntheticRecords": st.synthetic_records,
                   "dominant": st.is_synthetic_dominant})

# ---------------------------------------------------------------- grievances
TEXTS = [
    "My sewing machine is broken and the motor is not working",
    "EMI kist bharne mein dikkat hai, loan ka paisa nahi hai",
    "Supplier ne kapda nahi bheja, raw material delay ho gaya",
    "Mandi rate gir gaya, daam bahut sasta hai, no buyers",
    "मशीन खराब हो गई है",
    "किस्त नहीं भर पा रही, कर्ज बढ़ रहा है",
    "चारा देर से आया, माल की कमी",
    "दूध का भाव गिर गया",
    "I need help with something",
    "",
    "price and loan problem",
    "Feed stock late again; the delayed supply hurts",
    "machine repair kharab, rate low",
    "the damage from late payments",
    "Repayment is late",
]
SECTORS = [None, "animal_husbandry", "fisheries", "agri_allied", "textiles_apparel"]
grievances = [{"text": t, "issue": grievance_engine.classify_issue(t)} for t in TEXTS]
routes = [{"issue": i, "sector": s, "role": grievance_engine.route(i, s)[0], "intervention": grievance_engine.route(i, s)[1]}
          for i in grievance_engine.ROUTING for s in SECTORS]

# ---------------------------------------------------------------- validators
VALUES = {
    "phone_number": ["9876543210", "+91 98765 43210", "919876543210", "5876543210", "98765"],
    "aadhaar_number": ["2345 6789 0124", "123456789012", "23456789", "9999 9999 9999"],
    "pan_number": ["abcde1234f", "ABCDE 1234 F", "ABCD1234F"],
    "ifsc_code": ["sbin0001234", "SBIN1001234", "HDFC0ABC123"],
    "bank_account_number": ["1234 5678 90", "12345678", "123456789012345678", "1234567890123456789"],
    "pincode": ["261001", "061001", "26100"],
    "udyam_registration_number": ["udyam-up-45-0012345", "UDYAM-UP-4-0012345"],
    "full_name": ["  Sunita   Devi ", "S"],
}
validators = [{"field": f, "value": v, "ok": docs.COLLECTABLE[f].validator(v)[0],
               "result": docs.COLLECTABLE[f].validator(v)[1] if docs.COLLECTABLE[f].validator(v)[0] else None}
              for f, vs in VALUES.items() for v in vs]

# ---------------------------------------------------------------- launch windows
launch = []
for capital, activity_id in [(12_000, "tailoring"), (50_000, "dairy_farming"), (600_000, "flour_mill"), (15_000, "poultry_backyard")]:
    st = case(capital, activity_id, None)
    ms = launch_copilot.run(st)["launch_roadmap"]
    launch.append({"capital": capital, "activity": activity_id, "weeks": [m.target_week for m in ms],
                   "themes": [m.theme for m in ms], "taskCounts": [len(m.tasks) for m in ms]})

# ---------------------------------------------------------------- policy lists (requires scikit-learn)
policy = []
try:
    from module2_financial.policy_scheme_agent import explain_scheme
    for tier in ["micro_finance", "term_loan", None]:
        r = explain_scheme(tier)
        policy.append({"tier": tier, "documents": r["required_documents"], "steps": r["process_steps"],
                       "ruleHeadings": [c.heading for c in r["rule_chunks"]]})
except ImportError as exc:  # pragma: no cover
    print("policy parity skipped:", exc)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"sms": sms, "monitoring": scenarios, "scoring": scored, "priors": priors,
                           "grievances": grievances, "routes": routes, "validators": validators,
                           "launch": launch, "policy": policy}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}: {len(sms)} sms, {len(scenarios)} monitoring scenarios, {len(scored)} scored, "
      f"{len(priors)} priors, {len(grievances)} grievances, {len(policy)} policy tiers")
