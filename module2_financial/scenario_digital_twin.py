"""Scenario / Digital Twin stress test (Module 2, TDD Section 6.3).

Reads: state.financial_plan (regular_quarterly_installment, operating_projection),
       state.market_intelligence.risk.seasonal_index | state.risk_intel.seasonal_index
       (fallback: catalog seasonal_profile of state.selected_candidate().catalog_id)
Writes: state.financial_plan.stress_test_result (primary low-season case), .scenarios
Tech: deterministic calendar-quarter simulation over one stressed year driven by the Risk Agent's
      seasonal curve; four scenarios: low season, low season + 15% price fall, low season + input-cost
      shock (margin -5 points), and the break-even revenue drop. No LLM computes or phrases verdicts.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from module2_financial.operating_model import (
    break_even_revenue_drop_pct,
    build_operating_projection,
    case_activity,
    case_market_reach,
    case_pricing,
    coverage_band,
    quarter_factors,
    quarterly_dscr_profile,
)
from orchestrator.state import CaseState, OperatingProjection, StressTestResult

PRICE_DROP = 0.15
MARGIN_SHOCK = 0.05
BUFFER_ROUNDING = 1_000
QUARTERS = ["Q1 (Jan-Mar)", "Q2 (Apr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dec)"]
FLAT = [1.0] * 12


def seasonal_curve(state: CaseState, activity: Optional[dict[str, Any]]) -> tuple[Optional[list[float]], str]:
    """(12 monthly factors, basis). Prefers the risk analysis; falls back to the catalog profile."""
    for risk in (state.market_intelligence.risk if state.market_intelligence else None, state.risk_intel):
        if risk is not None and len(risk.seasonal_index) == 12:
            detail = f": {risk.seasonal_basis}" if risk.seasonal_basis else ""
            return list(risk.seasonal_index), f"Risk analysis seasonal index ({risk.source_confidence}){detail}"
    if activity and len(activity.get("seasonal_profile") or []) == 12:
        return list(activity["seasonal_profile"]), (
            "Catalog seasonal profile (estimated planning assumption); the risk analysis seasonal curve was unavailable"
        )
    return None, "No seasonal curve available"


def _stressed(base: OperatingProjection, revenue_factor: float = 1.0, margin_delta: float = 0.0,
              note: str = "") -> OperatingProjection:
    """Revenue scaled with costs unchanged, and/or margin shifted by ``margin_delta`` (fraction of base revenue)."""
    revenue = base.annual_revenue * revenue_factor
    costs = base.annual_revenue - base.annual_operating_surplus
    surplus = revenue - costs - base.annual_revenue * margin_delta
    return OperatingProjection(
        annual_revenue=round(revenue, 2),
        operating_margin=round(surplus / revenue, 4) if revenue else 0.0,
        annual_operating_surplus=round(surplus, 2),
        quarterly_operating_surplus=round(surplus / 4, 2),
        basis=base.basis + ([note] if note else []),
    )


def simulate(name: str, projection: OperatingProjection, installment: float, monthly_index: list[float],
             revenue_drop_pct: float, seasonal_basis: str, working_capital: float) -> StressTestResult:
    factors = quarter_factors(monthly_index)
    surpluses = [round(projection.quarterly_operating_surplus * f, 2) for f in factors]
    ratios = quarterly_dscr_profile(projection, installment, monthly_index)
    worst = min(range(4), key=lambda q: ratios[q])
    deficits = [round(max(0.0, installment - s), 2) if r < 1.0 else 0.0 for s, r in zip(surpluses, ratios)]
    shortfall = sum(deficits)
    deficit_quarters = sum(1 for d in deficits if d > 0)
    min_ratio = ratios[worst]
    sustainable = min_ratio >= 1.0

    if sustainable:
        advice = (
            f"Coverage stays at or above {min_ratio:.2f}x in every quarter (weakest: {QUARTERS[worst]}, "
            f"{coverage_band(min_ratio)}); no shortfall under this scenario."
        )
        if coverage_band(min_ratio) == "thin":
            advice += f" Keeping one installment (Rs {installment:,.0f}) in reserve is prudent because coverage is thin."
    else:
        buffer = math.ceil(shortfall / BUFFER_ROUNDING) * BUFFER_ROUNDING
        weak = ", ".join(QUARTERS[q] for q in range(4) if deficits[q] > 0)
        fits = "fits within" if buffer <= working_capital else "exceeds"
        advice = (
            f"Not sustainable: surplus falls short of the Rs {installment:,.0f} installment in {deficit_quarters} "
            f"quarter(s) ({weak}); lowest coverage {min_ratio:.2f}x. Shortfall over a year totals Rs {shortfall:,.0f}. "
            f"Set aside at least Rs {buffer:,.0f} before those quarters; this {fits} the Rs {working_capital:,.0f} "
            "working-capital allocation."
        )
    return StressTestResult(
        scenario_name=name,
        revenue_drop_percentage=round(revenue_drop_pct, 2),
        seasonal_basis=seasonal_basis,
        stressed_quarterly_surplus=surpluses[worst],
        quarterly_installment_due=installment,
        debt_service_coverage_ratio=min_ratio,
        quarterly_dscr=ratios,
        deficit_quarters=deficit_quarters,
        is_sustainable=sustainable,
        buffer_recommendation=advice,
        source_confidence="estimated",
    )


def run(state: CaseState) -> dict[str, Any]:
    plan = state.financial_plan
    if plan is None or plan.eligibility_status != "eligible" or plan.regular_quarterly_installment <= 0:
        return {}
    activity = case_activity(state)
    projection = plan.operating_projection
    if projection is None:
        try:
            projection = build_operating_projection(
                plan.computed_project_cost, activity or {}, case_pricing(state), case_market_reach(state)
            )
        except ValueError:
            return {}
    index, basis = seasonal_curve(state, activity)
    if index is None:
        return {}

    installment = plan.regular_quarterly_installment
    wc = plan.working_capital_requirement
    low_drop = (1 - min(quarter_factors(index))) * 100
    scenarios = [
        simulate("Low-season downside", projection, installment, index, low_drop, basis, wc),
        simulate(f"Low season + {PRICE_DROP:.0%} price fall",
                 _stressed(projection, 1 - PRICE_DROP, note=f"Price fall of {PRICE_DROP:.0%} with costs unchanged."),
                 installment, index, (1 - min(quarter_factors(index)) * (1 - PRICE_DROP)) * 100, basis, wc),
        simulate(f"Low season + input-cost shock (margin -{MARGIN_SHOCK * 100:g} points)",
                 _stressed(projection, margin_delta=MARGIN_SHOCK,
                           note=f"Input costs up by {MARGIN_SHOCK * 100:g}% of revenue."),
                 installment, index, low_drop, basis, wc),
    ]
    break_even = break_even_revenue_drop_pct(projection, installment)
    if break_even is not None:
        exact = (projection.quarterly_operating_surplus - installment) / (projection.annual_revenue / 4) * 100
        drop = max(exact, 0.0)
        scenarios.append(simulate(
            f"Break-even revenue drop ({break_even:.1f}%, costs unchanged, no seasonality)"
            if break_even > 0 else "Break-even: base case already below coverage (no drop applied)",
            _stressed(projection, 1 - drop / 100), installment, FLAT, drop,
            "Flat year (no seasonality) to isolate the break-even revenue level", wc,
        ))
    return {"financial_plan": plan.model_copy(update={"stress_test_result": scenarios[0], "scenarios": scenarios})}
