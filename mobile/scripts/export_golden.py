"""Export golden values from the Python financial engine for the mobile app's TypeScript port.

Run from the repository root:  python mobile/scripts/export_golden.py
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_MODE", "offline")

from common.reference import get_activity  # noqa: E402
from module2_financial.financial_engine import build_financial_plan  # noqa: E402
from module2_financial.operating_model import preview_debt_service  # noqa: E402

CAPITALS = [5_000, 12_000, 13_999, 14_000, 15_000, 50_000, 100_000, 499_999, 500_000, 600_000]
ACTIVITIES = ["handloom_weaving", "tailoring", "dairy_farming", "beauty_parlour", "grocery_kirana"]

plans = []
for capital in CAPITALS:
    p = build_financial_plan(capital)
    plans.append({
        "capital": capital,
        "eligible": p.eligibility_status == "eligible",
        "projectCost": p.computed_project_cost,
        "loan": p.maximum_loan_eligibility,
        "tier": p.scheme_tier.name if p.scheme_tier else None,
        "capApplied": p.loan_cap_applied,
        "regularInstallment": p.regular_quarterly_installment,
        "totalInterest": p.total_interest_payable,
        "quarters": len(p.repayment_schedule),
    })

previews = []
for activity_id in ACTIVITIES:
    for capital in (12_000, 100_000):
        v = preview_debt_service(capital, get_activity(activity_id))
        previews.append({"activity": activity_id, "capital": capital, "baseDscr": v["base_dscr"],
                         "minSeasonalDscr": v["min_seasonal_dscr"], "quarterlySurplus": v["quarterly_surplus"]})

out = ROOT / "mobile" / "src" / "engine" / "golden.json"
out.write_text(json.dumps({"plans": plans, "previews": previews}, indent=2), encoding="utf-8")
print(f"Wrote {out}")
