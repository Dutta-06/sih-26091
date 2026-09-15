"""Export parity fixtures for the on-device Module 1 port (role C2).

Runs the real backend functions on fixed inputs:
  * module1_feasibility.adversarial_review.evaluate  (rules R1-R3, M1-M4)
  * module1_feasibility.risk_agent.seasonal_decomposition / structural_rules / overall_severity
  * module1_feasibility.competitor_agent.poisson_z, opportunity_agent.classify_saturation

Run from the repository root:  python mobile/scripts/export_parity_c2.py
"""

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_MODE", "offline")

from common.reference import get_activity  # noqa: E402
from module1_feasibility import risk_agent  # noqa: E402
from module1_feasibility.adversarial_review import evaluate  # noqa: E402
from module1_feasibility.competitor_agent import poisson_z  # noqa: E402
from module1_feasibility.opportunity_agent import classify_saturation  # noqa: E402
from module2_financial.operating_model import preview_debt_service  # noqa: E402
from orchestrator.state import (  # noqa: E402
    CompetitorIntelligence, MarketIntelligence, MonthlyPrice, OpportunityIntelligence, RiskFlag, RiskIntelligence, SubNiche,
)

CONF = ["market_reach", "opportunity", "risk", "competitor", "pricing", "supply_chain"]

# intel stubs: competitor saturation/z/count, niche saturations, risk flags (id, category, severity), estimated branches
STUBS = {
    "clean": {"sat": "low", "z": -1.0, "count": 3, "niches": ["low", "medium"], "flags": [], "estimated": []},
    "crowded_z": {"sat": "high", "z": 3.4, "count": 41, "niches": ["unknown"], "flags": [], "estimated": ["risk", "pricing"]},
    "crowded": {"sat": "high", "z": 1.2, "count": 20, "niches": [], "flags": [], "estimated": ["risk"]},
    "niches_saturated": {"sat": "medium", "z": 0.4, "count": 8, "niches": ["high", "high"], "flags": [], "estimated": []},
    "seasonal_highs": {"sat": "unknown", "z": None, "count": None, "niches": [],
                       "flags": [["seasonal_demand_variation", "seasonal", "high"], ["working_capital_strain", "structural", "high"],
                                 ["festival_season_concentration", "structural", "high"], ["route_distance", "route", "medium"]],
                       "estimated": CONF},
    "two_highs": {"sat": "medium", "z": 0.0, "count": 5, "niches": [],
                  "flags": [["route_distance", "route", "high"], ["power_reliability", "structural", "high"],
                            ["working_capital_strain", "structural", "high"]],
                  "estimated": ["risk", "supply_chain", "pricing"]},
    "none": None,
}
CASES = [
    (12_000, "handloom_weaving", "crowded_z"), (12_000, "handloom_weaving", "clean"), (12_000, "tailoring", "clean"),
    (12_000, "tailoring", "crowded"), (12_000, "tailoring", "niches_saturated"), (12_000, "tailoring", "two_highs"),
    (12_000, "tailoring", "seasonal_highs"), (12_000, "carpet_weaving", "clean"), (2_500, "tea_snack_stall", "clean"),
    (100_000, "dairy_farming", "clean"), (100_000, "dairy_farming", "two_highs"), (8_000, "beauty_parlour", "none"),
    (600_000, "grocery_kirana", "clean"), (30_000, "goat_rearing", "crowded"), (15_000, "grocery_kirana", "clean"),
    (50_000, "flour_mill", "seasonal_highs"), (14_000, "handloom_weaving", "clean"), (7_000, "mobile_repair", "crowded_z"),
]


def build_mi(stub):
    if stub is None:
        return None
    mi = MarketIntelligence(
        competitor=CompetitorIntelligence(saturation_level=stub["sat"], z_score_vs_district=stub["z"],
                                          estimated_competitor_count=stub["count"]),
        opportunity=OpportunityIntelligence(sub_niches=[SubNiche(name=f"n{i}", saturation_level=s) for i, s in enumerate(stub["niches"])]),
        risk=RiskIntelligence(risk_flags=[RiskFlag(risk_id=r, category=c, severity=s, title=r) for r, c, s in stub["flags"]]),
    )
    for branch in CONF:
        getattr(mi, branch).source_confidence = "estimated" if branch in stub["estimated"] else "real"
    return mi


review = []
for capital, activity_id, stub_id in CASES:
    activity = get_activity(activity_id)
    verdict, reasons, critique = evaluate(capital, activity, build_mi(STUBS[stub_id]), preview_debt_service(capital, activity))
    review.append({"capital": capital, "activity": activity_id, "stub": stub_id, "verdict": verdict,
                   "rules": [r.split(":")[0] for r in reasons], "notes": len(critique) - len(reasons)})


def series(start_year, n, fn):
    return [{"month": f"{start_year + (i // 12)}-{i % 12 + 1:02d}", "modal": round(fn(i), 2)} for i in range(n)]


SERIES = {
    "wheat_like": series(2022, 36, lambda i: (2000 + 8 * i) * (1 + 0.08 * math.sin(2 * math.pi * i / 12)) + (i * 37 % 11)),
    "goat_like": series(2021, 30, lambda i: 9000 * (1 + 0.2 * math.cos(2 * math.pi * (i - 6) / 12)) + 15 * i),
    "gappy": [p for j, p in enumerate(series(2022, 40, lambda i: 1500 + 100 * math.sin(i) + 5 * i)) if j not in (5, 17, 18, 29, 30, 31)],
    "short": series(2023, 20, lambda i: 100 + i),
}
seasonal = {k: risk_agent.seasonal_decomposition([MonthlyPrice(month=p["month"], modal_price=p["modal"]) for p in v])
            for k, v in SERIES.items()}

structural = []
for activity_id in ["dairy_farming", "goat_rearing", "poultry_backyard", "flour_mill", "food_processing_home", "grocery_kirana",
                    "tailoring", "handloom_weaving", "carpet_weaving", "mobile_repair", "beauty_parlour", "tea_snack_stall"]:
    activity = get_activity(activity_id)
    mean = sum(activity["seasonal_profile"]) / 12
    index = [round(v / mean, 4) for v in activity["seasonal_profile"]]
    low = [i for i, v in enumerate(index) if v < 0.92]
    for km in (None, 8.0, 30.0):
        route = {"km": km}
        seas = {"index": index, "low": low, "variation": risk_agent._variation(index)}
        rules = risk_agent.structural_rules(activity, route, seas)
        structural.append({"activity": activity_id, "km": km, "variation": seas["variation"], "low": low,
                           "rules": [[r, s] for r, s, _ in rules]})

severity_cases = [["low"], ["medium", "low"], ["high"], ["high", "high"], [], ["high", "medium", "high"]]
overall = [risk_agent.overall_severity([RiskFlag(category="structural", title="x", severity=s) for s in c]) for c in severity_cases]

stats = {
    "poisson": [[c, p, b, poisson_z(c, p, b)] for c, p, b in [(41, 60000, 1.5), (9, 60000, 5.0), (0, 1000, 2.0), (5, None, 2.0)]],
    "saturation": [[d, b, classify_saturation(d, b)[0]] for d, b in [(1.0, 2.0), (1.5, 2.0), (2.5, 2.0), (2.6, 2.0), (None, 1.0), (1.0, 0.0)]],
}

out = ROOT / "mobile" / "src" / "core" / "__fixtures__" / "c2.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"review": review, "stubs": STUBS, "series": SERIES, "seasonal": seasonal, "structural": structural,
                           "severityCases": severity_cases, "overall": overall, "stats": stats}, indent=1), encoding="utf-8")
print(f"Wrote {out}")
