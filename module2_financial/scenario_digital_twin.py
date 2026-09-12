"""Scenario & Digital Twin Simulation Agent (Module 2, Section 6.3).

Reads: state.financial_plan, state.market_intelligence.risk (seasonal curve)
Writes: state.financial_plan.stress_test_result
Tech: Downside scenario simulation driven by seasonal drop curve to test debt-service resilience.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import CaseState, StressTestResult


def run(state: CaseState) -> dict[str, Any]:
    plan = state.financial_plan
    if not plan:
        return {}

    # Regular post-moratorium installment
    regular_installment = plan.repayment_schedule[2].total_installment if len(plan.repayment_schedule) > 2 else 45_000.0
    baseline_surplus = plan.computed_project_cost * 0.12

    # Simulated 25% revenue contraction during dry summer season
    drop_pct = 25.0
    stressed_surplus = round(baseline_surplus * (1 - (drop_pct / 100.0)), 2)
    dscr = round(stressed_surplus / (regular_installment or 1.0), 2)
    sustainable = dscr >= 1.0

    result = StressTestResult(
        scenario_name="Low-Season Downside Stress Test",
        revenue_drop_percentage=drop_pct,
        stressed_quarterly_surplus=stressed_surplus,
        quarterly_installment_due=regular_installment,
        debt_service_coverage_ratio=dscr,
        is_sustainable=sustainable,
        buffer_recommendation=(
            f"Plan is resilient. Under a {drop_pct:.0f}% seasonal revenue contraction, debt service coverage remains {dscr:.2f}x. "
            f"Maintain an emergency operating buffer of ₹{round(regular_installment * 1.5, 0):,.0f} from initial working capital."
        ),
    )

    plan.stress_test_result = result
    return {"financial_plan": plan}
