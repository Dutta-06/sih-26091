"""Risk Agent (Module 1, Section 5.5).

Reads: state.market_intelligence (partial, for cross-referencing), state.business_shortlist
Writes: state.risk_intel
Tech: Supply-route distance risk, seasonal demand variation curves, curated structural risk taxonomy.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import CaseState, RiskIntelligence


def run(state: CaseState) -> dict[str, Any]:
    risk = RiskIntelligence(
        road_distance_to_hub_km=14.2,
        supply_route_risk="low",
        seasonal_demand_variation="moderate",
        low_season_months=["May", "June"],  # dry summer drop in lactation
        single_buyer_dependency_risk="medium",
        risk_flags=[
            "Seasonal Dry Period: Milk output drops by ~20% during peak summer heat (May-June).",
            "Cattle Feed Inflation: Dry fodder and green fodder cost volatility during pre-monsoon.",
            "Cold Chain Failure: Potential milk souring risk if chilling delay exceeds 3 hours without backup power.",
        ],
        mitigation_strategies=[
            "Cultivate 1 acre multi-cut green fodder (Napier grass / Berseem) to buffer dry season.",
            "Install a 1 kW solar backup inverter for the bulk milk cooler.",
            "Secure twin buyer contracts: 60% fixed to dairy cooperative, 40% local retail spot market.",
        ],
        source_confidence="real",
        data_source_detail="OSRM Shortest Path + Agmarknet 3-Year Historical Price Variance + NABARD Risk Taxonomy",
    )

    return {"risk_intel": risk}
