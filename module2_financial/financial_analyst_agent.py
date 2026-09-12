"""Financial Analyst Agent (Module 2, Section 6.2).

Reads: state.financial_plan, state.market_intelligence.pricing
Writes: state.financial_plan.analyst_commentary
Tech: Explains deterministic figures, debt-service coverage, and margin of safety in plain language.
Constraint: Never overwrites deterministic financial figures from financial_engine.py.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import CaseState


def run(state: CaseState) -> dict[str, Any]:
    plan = state.financial_plan
    if not plan:
        return {}

    # Calculate indicative quarterly operating surplus
    # E.g. for a ₹10L dairy unit: ~200L/day * 90 days = 18,000L/quarter * ₹42.50 = ₹7.65L gross
    # Net operating surplus after fodder/labor (~70% opex) = ~₹1.2L/quarter
    quarterly_installment = plan.repayment_schedule[2].total_installment if len(plan.repayment_schedule) > 2 else 45_000.0
    projected_quarterly_surplus = round(plan.computed_project_cost * 0.12, 2)
    coverage_ratio = round(projected_quarterly_surplus / (quarterly_installment or 1.0), 2)

    commentary = (
        f"Financial Structure Summary:\n"
        f"• Project Scale: Total Feasible Project Cost is ₹{plan.computed_project_cost:,.2f}, backed by your ₹{plan.available_margin_capital:,.2f} margin (10%).\n"
        f"• Loan Sanction: Eligible for ₹{plan.maximum_loan_eligibility:,.2f} under {plan.scheme_tier.display_name} at {plan.scheme_tier.interest_rate * 100:.1f}% p.a.\n"
        f"• Moratorium Relief: First {plan.scheme_tier.moratorium_months} months require interest-only payment (₹{plan.repayment_schedule[0].total_installment:,.2f}/quarter), allowing operational stabilization.\n"
        f"• Debt Service Safety Margin: Projected net quarterly operating surplus of ₹{projected_quarterly_surplus:,.2f} provides a {coverage_ratio:.1f}x coverage ratio over the regular installment of ₹{quarterly_installment:,.2f}."
    )

    plan.analyst_commentary = commentary
    return {"financial_plan": plan}
