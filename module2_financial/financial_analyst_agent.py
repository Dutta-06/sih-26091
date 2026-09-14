"""Financial Analyst Agent (Module 2, TDD Section 6.2).

Reads: state.financial_plan, state.pricing_intel | state.market_intelligence.pricing,
       state.market_reach_intel | state.market_intelligence.market_reach, state.selected_candidate().catalog_id
Writes: state.financial_plan.operating_projection, .base_debt_service_coverage_ratio,
        .analyst_commentary, .analyst_commentary_source
Tech: deterministic operating projection + DSCR + break-even margin of safety (operating_model.py);
      plain-language commentary from a template that states the actual numbers, optionally rephrased
      by common.llm.explain. Never alters the engine's figures.
"""

from __future__ import annotations

from typing import Any

from common.llm import explain
from module2_financial.operating_model import (
    break_even_revenue_drop_pct,
    build_operating_projection,
    case_activity,
    case_market_reach,
    case_pricing,
    coverage_band,
    dscr,
)
from orchestrator.state import CaseState, FinancialPlan, OperatingProjection

SYSTEM_PROMPT = (
    "You explain a concessional loan plan to a first-time rural entrepreneur in plain language. "
    "Rephrase the analysis you are given. Do not change, add or recompute any number, ratio or verdict."
)

_BAND_SENTENCE = {
    "does not cover": "the estimated surplus does not cover the regular installment",
    "thin": "the estimated surplus covers the regular installment, but only thinly",
    "comfortable": "the estimated surplus covers the regular installment comfortably",
}


def build_commentary(plan: FinancialPlan, projection: OperatingProjection, ratio: float) -> str:
    tier = plan.scheme_tier
    installment = plan.regular_quarterly_installment
    surplus = projection.quarterly_operating_surplus
    lines = [
        f"Your Rs {plan.available_margin_capital:,.0f} margin supports a project cost of Rs {plan.computed_project_cost:,.0f}; "
        f"the {tier.display_name} loan is Rs {plan.maximum_loan_eligibility:,.0f} at {tier.interest_rate * 100:g}% a year "
        f"over {tier.tenure_years} years, including a {tier.moratorium_months}-month moratorium.",
    ]
    if plan.loan_cap_applied:
        lines.append(
            f"The loan is capped at Rs {tier.max_loan_amount:,.0f}, so your own contribution is effectively "
            f"{plan.margin_percentage:g}% (Rs {plan.computed_project_cost - plan.maximum_loan_eligibility:,.0f})."
        )
    moratorium = [i for i in plan.repayment_schedule if i.is_moratorium]
    if moratorium:
        lines.append(f"During the moratorium you pay interest only: Rs {moratorium[0].total_installment:,.0f} per quarter.")
    lines.append(
        f"After that the regular installment is Rs {installment:,.0f} per quarter. Estimated operating surplus is "
        f"Rs {surplus:,.0f} per quarter, a coverage ratio of {ratio:.2f}x: {_BAND_SENTENCE[coverage_band(ratio)]}."
    )
    drop = break_even_revenue_drop_pct(projection, installment)
    if drop is None:
        lines.append("Margin of safety cannot be computed because projected revenue is zero.")
    elif drop > 0:
        lines.append(
            f"Margin of safety: revenue could fall by about {drop:.1f}% (with costs unchanged) before the surplus "
            f"no longer covers the installment."
        )
    else:
        lines.append(
            f"There is no margin of safety: the surplus already falls Rs {installment - surplus:,.0f} short per quarter; "
            f"revenue would need to rise by about {-drop:.1f}% with costs unchanged to break even."
        )
    lines.append(
        "Loan amount, rate, tenure and schedule are exact scheme-rule calculations. Revenue, margin and surplus are "
        "estimates: " + " ".join(projection.basis)
    )
    return "\n".join(lines)


def run(state: CaseState) -> dict[str, Any]:
    plan = state.financial_plan
    if plan is None or plan.eligibility_status != "eligible" or plan.scheme_tier is None:
        return {}
    activity = case_activity(state)
    try:
        projection = build_operating_projection(
            plan.computed_project_cost, activity or {}, case_pricing(state), case_market_reach(state)
        )
    except ValueError as exc:
        text = (
            f"Debt-service coverage was not assessed: {exc} The loan figures above are exact scheme-rule "
            "calculations, but whether the business can service them is unknown."
        )
        return {"financial_plan": plan.model_copy(update={
            "operating_projection": None, "base_debt_service_coverage_ratio": None,
            "analyst_commentary": text, "analyst_commentary_source": "deterministic_template",
        })}

    ratio = dscr(projection.quarterly_operating_surplus, plan.regular_quarterly_installment)
    template = build_commentary(plan, projection, ratio)
    text, source = explain(SYSTEM_PROMPT, f"Rephrase for the entrepreneur:\n\n{template}", template)
    return {"financial_plan": plan.model_copy(update={
        "operating_projection": projection,
        "base_debt_service_coverage_ratio": ratio,
        "analyst_commentary": text,
        "analyst_commentary_source": source,
    })}
