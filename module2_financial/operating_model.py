"""Indicative operating model and debt-service coverage (Module 2, TDD Sections 6.2-6.3).

Reads: catalog activity economics, optional PricingIntelligence / MarketReachIntelligence
Writes: nothing (pure functions used by financial_analyst_agent, scenario_digital_twin, adversarial_review)
Tech: deterministic arithmetic only; no language model computes any figure here.

Assumptions (all recorded in ``OperatingProjection.basis``; the projection is always "estimated"
because its base is a catalog planning assumption, not observed trading data):
* annual revenue = catalog ``annual_revenue_to_project_cost`` x project cost; surplus = revenue x
  catalog ``operating_margin``.
* Pricing adjustment: when the pricing analysis gives ``optimal_target_price`` and the catalog has a
  ``reference_price`` band, revenue is scaled by target / band midpoint, bounded to [0.80, 1.20].
  Volumes and the margin ratio are held constant (costs assumed to move with revenue).
* Market-reach adjustment: when ``consumer_base_estimate`` is known, revenue is scaled by
  sqrt(consumer_base / 10,000), bounded to [0.85, 1.10]. 10,000 is the population unit of the
  catalog's density benchmark, so a thinner local market trims revenue and a larger one lifts it slightly.
* Seasonal profile: the 12 monthly factors are normalised to mean 1.0 and averaged per calendar
  quarter (Q1 = Jan-Mar ... Q4 = Oct-Dec); quarterly surplus scales with the quarter factor.
* Break-even revenue drop: how far quarterly revenue can fall with operating costs unchanged
  (e.g. a price fall) before surplus equals the installment.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from common.reference import get_activity
from orchestrator.state import CaseState, MarketReachIntelligence, OperatingProjection, PricingIntelligence

PRICE_FACTOR_BOUNDS = (0.80, 1.20)
REACH_FACTOR_BOUNDS = (0.85, 1.10)
REFERENCE_CONSUMER_BASE = 10_000


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    return max(bounds[0], min(bounds[1], value))


def build_operating_projection(
    project_cost: float,
    activity: dict[str, Any],
    pricing: Optional[PricingIntelligence] = None,
    market_reach: Optional[MarketReachIntelligence] = None,
) -> OperatingProjection:
    """Indicative annual/quarterly operating surplus. Raises ValueError if catalog economics are missing."""
    ratio = (activity or {}).get("annual_revenue_to_project_cost")
    margin = (activity or {}).get("operating_margin")
    if ratio is None or margin is None:
        raise ValueError("Activity lacks catalog economics (annual_revenue_to_project_cost, operating_margin).")
    name = activity.get("category") or activity.get("id") or "activity"
    revenue = project_cost * ratio
    basis = [
        f"Base revenue = {ratio:g} x project cost Rs {project_cost:,.0f} = Rs {revenue:,.0f}/year "
        f"(catalog planning assumption for {name}, estimated).",
        f"Operating margin {margin:.0%} of revenue (catalog planning assumption, estimated).",
    ]

    ref = activity.get("reference_price") or {}
    target = pricing.optimal_target_price if pricing else None
    if target and ref.get("low") is not None and ref.get("high") is not None:
        midpoint = (ref["low"] + ref["high"]) / 2
        raw = target / midpoint if midpoint > 0 else 1.0
        factor = _clamp(raw, PRICE_FACTOR_BOUNDS)
        revenue *= factor
        basis.append(
            f"Pricing adjustment x{factor:.3f}: target price {target:g} vs catalog reference midpoint {midpoint:g} "
            f"(raw ratio {raw:.3f}, bounded to {PRICE_FACTOR_BOUNDS}; pricing input {pricing.source_confidence})."
        )
    else:
        basis.append("No pricing adjustment: target price or catalog reference price unavailable.")

    consumers = market_reach.consumer_base_estimate if market_reach else None
    if consumers is not None:
        raw = math.sqrt(max(consumers, 0) / REFERENCE_CONSUMER_BASE)
        factor = _clamp(raw, REACH_FACTOR_BOUNDS)
        revenue *= factor
        basis.append(
            f"Market-reach adjustment x{factor:.3f}: consumer base {consumers:,} vs reference {REFERENCE_CONSUMER_BASE:,} "
            f"(sqrt ratio {raw:.3f}, bounded to {REACH_FACTOR_BOUNDS}; market reach input {market_reach.source_confidence})."
        )
    else:
        basis.append("No market-reach adjustment: consumer base estimate unavailable.")

    surplus = revenue * margin
    return OperatingProjection(
        annual_revenue=round(revenue, 2),
        operating_margin=round(margin, 4),
        annual_operating_surplus=round(surplus, 2),
        quarterly_operating_surplus=round(surplus / 4, 2),
        basis=basis,
        source_confidence="estimated",
    )


def dscr(surplus: float, installment: float) -> float:
    """Debt-service coverage ratio; +inf when nothing is due. Negative surplus gives a negative ratio."""
    if installment <= 0:
        return float("inf")
    return round(surplus / installment, 2)


COMFORTABLE_DSCR = 1.25


def coverage_band(ratio: float) -> str:
    """'does not cover' (< 1.0), 'thin' (1.0 to < 1.25) or 'comfortable' (>= 1.25)."""
    if ratio < 1.0:
        return "does not cover"
    return "thin" if ratio < COMFORTABLE_DSCR else "comfortable"


def quarter_factors(seasonal_index: list[float]) -> list[float]:
    """Calendar-quarter factors (Q1..Q4) from 12 monthly factors normalised to mean 1.0."""
    if len(seasonal_index) != 12:
        raise ValueError("seasonal_index must contain 12 monthly factors (Jan..Dec).")
    mean = sum(seasonal_index) / 12
    if mean <= 0:
        raise ValueError("seasonal_index must have a positive mean.")
    norm = [v / mean for v in seasonal_index]
    return [round(sum(norm[q * 3:q * 3 + 3]) / 3, 4) for q in range(4)]


def quarterly_dscr_profile(projection: OperatingProjection, installment: float, seasonal_index: list[float]) -> list[float]:
    """DSCR for each calendar quarter: quarterly surplus x quarter factor / installment."""
    return [dscr(projection.quarterly_operating_surplus * f, installment) for f in quarter_factors(seasonal_index)]


def break_even_revenue_drop_pct(projection: OperatingProjection, installment: float) -> Optional[float]:
    """Revenue fall (%, costs unchanged) at which surplus equals the installment; negative = already short."""
    quarterly_revenue = projection.annual_revenue / 4
    if quarterly_revenue <= 0:
        return None
    return round((projection.quarterly_operating_surplus - installment) / quarterly_revenue * 100, 2)


def case_activity(state: CaseState) -> Optional[dict[str, Any]]:
    """Catalog entry for the activity under assessment (selected candidate, else feasibility record)."""
    candidate = state.selected_candidate()
    catalog_id = (candidate.catalog_id if candidate else "") or (
        state.feasibility_record.selected_catalog_id if state.feasibility_record else ""
    )
    return get_activity(catalog_id) if catalog_id else None


def case_pricing(state: CaseState) -> Optional[PricingIntelligence]:
    return state.pricing_intel or (state.market_intelligence.pricing if state.market_intelligence else None)


def case_market_reach(state: CaseState) -> Optional[MarketReachIntelligence]:
    return state.market_reach_intel or (state.market_intelligence.market_reach if state.market_intelligence else None)


def preview_debt_service(available_capital: float, activity: dict[str, Any]) -> dict[str, Any]:
    """Quick coverage preview for adversarial review (catalog economics only, no Module 1 adjustments)."""
    from module2_financial.financial_engine import build_financial_plan

    plan = build_financial_plan(available_capital, (activity or {}).get("category", ""))
    out: dict[str, Any] = {
        "project_cost": plan.computed_project_cost,
        "eligible": plan.eligibility_status == "eligible",
        "quarterly_installment": plan.regular_quarterly_installment if plan.eligibility_status == "eligible" else None,
        "quarterly_surplus": None,
        "base_dscr": None,
        "min_seasonal_dscr": None,
    }
    if plan.computed_project_cost <= 0:
        return out
    try:
        projection = build_operating_projection(plan.computed_project_cost, activity)
    except ValueError:
        return out
    out["quarterly_surplus"] = projection.quarterly_operating_surplus
    if not out["eligible"]:
        return out
    installment = plan.regular_quarterly_installment
    out["base_dscr"] = dscr(projection.quarterly_operating_surplus, installment)
    profile = activity.get("seasonal_profile") or []
    if len(profile) == 12:
        out["min_seasonal_dscr"] = min(quarterly_dscr_profile(projection, installment, profile))
    return out
