"""SWOT Synthesis Agent (Module 1, Section 5.9).

Reads: all six parallel intelligence sub-fields (fan-in)
Writes: state.market_intelligence (unified) and state.feasibility_record.swot
Tech: Fan-in aggregation into structured Pydantic SWOT schema grounded on micro-enterprise budget.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import (
    CaseState,
    FeasibilityRecord,
    MarketIntelligence,
    SWOTAnalysis,
)


def run(state: CaseState) -> dict[str, Any]:
    # Gather the 6 parallel outputs (with fallbacks if any were None)
    reach = state.market_reach_intel
    opp = state.opportunity_intel
    risk = state.risk_intel
    comp = state.competitor_intel
    pricing = state.pricing_intel
    supply = state.supply_chain_intel

    # Unify into single MarketIntelligence object
    unified_market = MarketIntelligence(
        market_reach=reach or getattr(state.market_intelligence, "market_reach", None) or MarketIntelligence().market_reach,
        opportunity=opp or getattr(state.market_intelligence, "opportunity", None) or MarketIntelligence().opportunity,
        risk=risk or getattr(state.market_intelligence, "risk", None) or MarketIntelligence().risk,
        competitor=comp or getattr(state.market_intelligence, "competitor", None) or MarketIntelligence().competitor,
        pricing=pricing or getattr(state.market_intelligence, "pricing", None) or MarketIntelligence().pricing,
        supply_chain=supply or getattr(state.market_intelligence, "supply_chain", None) or MarketIntelligence().supply_chain,
    )

    selected_category = state.business_shortlist[0].category if state.business_shortlist else "Dairy Farming"

    swot = SWOTAnalysis(
        strengths=[
            f"Strong local demand: Immediate consumer base of ~{unified_market.market_reach.consumer_base_estimate:,} persons within 10 km.",
            f"Favorable competitive density (z-score: {unified_market.competitor.z_score_vs_district:.2f} vs district baseline).",
            f"Optimal pricing margin: ₹{unified_market.pricing.optimal_target_price:.2f}/unit gives sound operating margin.",
        ],
        weaknesses=[
            "Working capital vulnerability to seasonal dry-period fodder price spikes.",
            f"Strict time window: Raw produce requires rapid chilling within {unified_market.supply_chain.lead_time_days} days/hours.",
        ],
        opportunities=[
            f"High-margin niche: {unified_market.opportunity.sector_niche}.",
            f"Unserved avenues: {', '.join(unified_market.opportunity.unserved_demand_niches[:2])}.",
            f"Bulk buyer agreements with nearby collection centers like {unified_market.market_reach.distribution_points[0].name if unified_market.market_reach.distribution_points else 'APMC'}.",
        ],
        threats=[
            f"Seasonal production drop ({', '.join(unified_market.risk.low_season_months)}).",
            "Power outages disrupting chilling tanks if no generator/solar backup is configured.",
            "Potential single-buyer leverage if selling 100% output to one middleman.",
        ],
        budget_scaling_notes="Feasible within standard SCA 10% margin / 90% loan concessional financing ceiling.",
    )

    feasibility = state.feasibility_record or FeasibilityRecord(selected_category=selected_category)
    feasibility.selected_category = selected_category
    feasibility.swot = swot

    return {
        "market_intelligence": unified_market,
        "feasibility_record": feasibility,
    }
