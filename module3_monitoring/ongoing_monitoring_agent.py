"""Ongoing Monitoring Agent (Module 3, Section 7.3).

Reads: on-device transaction notification messages (strictly consent-gated)
Writes: state.monitoring_record (cash-flow snapshots)
Tech: Regex / structured template extraction of transaction alerts.
Constraint: Strictly consent-gated; never persist raw SMS text (parse and discard immediately).
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from orchestrator.state import CaseState, HealthSnapshot


def run(state: CaseState) -> dict[str, Any]:
    # Strictly verify user consent per Section 7.3
    if not state.session_meta.consent_sms_monitoring:
        # Graceful degradation if consent is not granted
        return {}

    plan = state.financial_plan
    baseline_rev = (plan.computed_project_cost * 0.28) if plan else 75_000.0

    # Simulated parsed aggregate transaction record
    snapshot = HealthSnapshot(
        timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        reported_revenue=78_400.0,
        projected_baseline_revenue=baseline_rev,
        reported_expenses=49_200.0,
        operating_surplus=29_200.0,
        loan_installment_status="paid",
        health_score=88.0,
        early_warning_flag=False,
        warning_reason=None,
        approximate_creditworthiness_index=735.0,  # clearly labeled approximate
        is_consent_verified=True,
    )

    records = list(state.monitoring_record)
    records.append(snapshot)
    return {"monitoring_record": records}
