"""Health Score and Early Warning Agent (Module 3, Section 7.4).

Reads: state.monitoring_record, state.financial_plan
Writes: updates to latest HealthSnapshot (health_score, early_warning_flag, suggested_intervention)
Tech: Anomaly scoring comparing actuals against original plan; early warning trigger with actionable remedies.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import CaseState


def run(state: CaseState) -> dict[str, Any]:
    if not state.monitoring_record:
        return {}

    records = list(state.monitoring_record)
    latest = records[-1]

    # Evaluate cash-flow health
    if latest.projected_baseline_revenue > 0:
        ratio = latest.reported_revenue / latest.projected_baseline_revenue
    else:
        ratio = 1.0

    if ratio < 0.70:
        latest.health_score = 55.0
        latest.early_warning_flag = True
        latest.warning_reason = "Actual revenue trailing >30% below feasibility projections."
        latest.suggested_intervention = "Deploy pricing adjustment and schedule prompt outreach with an assigned agricultural mentor."
    elif ratio < 0.90:
        latest.health_score = 72.0
        latest.early_warning_flag = False
        latest.suggested_intervention = "Monitor fodder costs closely; consider pooled feed procurement."
    else:
        latest.health_score = 91.0
        latest.early_warning_flag = False
        latest.suggested_intervention = "Enterprise operating comfortably above target safety margin."

    records[-1] = latest
    return {"monitoring_record": records}
