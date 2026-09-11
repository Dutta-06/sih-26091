"""
Opportunity Agent (design doc Section 5.3 / Figure 3; TECHNICAL_SETUP.md
Section 5.4).

Reads:  state.selected_business_category
        state.market_intelligence.competitor   (used when present -- not
            built in this two-agent scope, so normally None; see the
            integration note below)
        state.market_intelligence.market_reach (used as a fallback
            saturation proxy when competitor data is absent)
Writes: state.market_intelligence.opportunity

Tech: RAG pipeline (TF-IDF/FAISS by default -- see rag/vector_store.py for
the embedding-model swap point) over the NABARD/KVIC sector-report corpus;
rule-based saturation classification.

KNOWN LIMITATION (IMPLEMENTATION_PLAN.md Section 1 and Section 4): the full
design cross-checks each sub-niche against real competitor and demand data
from the Competitor and Pricing agents, neither of which is built here.
This agent substitutes an OSM point-of-interest density proxy -- POIs
within the same radius the Market Reach Agent already resolved, normalized
by population -- and tags every resulting sub-niche "estimated" rather than
"real" as a result. The moment `state.market_intelligence.competitor` is
populated by a future agent, this code path is skipped in favor of that
real signal -- no changes needed here to pick it up.
"""
from __future__ import annotations

import logging

from config.settings import settings
from data_connectors import overpass
from orchestrator.state import CaseState, OpportunityOutput, SubNiche
from rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

# POIs per 1,000 residents. Thresholds are a starting heuristic for the
# pilot, not a validated figure -- tune once real cases accumulate (see
# IMPLEMENTATION_PLAN.md Section 7).
_LOW_THRESHOLD = 2.0
_HIGH_THRESHOLD = 6.0


def _classify_saturation_from_density(density_per_1000: float) -> str:
    if density_per_1000 < _LOW_THRESHOLD:
        return "low"
    if density_per_1000 < _HIGH_THRESHOLD:
        return "medium"
    return "high"


def run(state: CaseState) -> CaseState:
    if state.selected_business_category is None:
        raise ValueError("opportunity_agent requires state.selected_business_category to be set")

    store = VectorStore()
    retrieved = store.query(state.selected_business_category, k=settings.opportunity_top_k)

    competitor = state.market_intelligence.competitor
    market_reach = state.market_intelligence.market_reach

    sub_niches: list[SubNiche] = []
    seen_sectors: set[str] = set()
    for doc in retrieved:
        sector = doc.metadata.get("sector", state.selected_business_category)
        if sector in seen_sectors:
            continue
        seen_sectors.add(sector)

        if competitor is not None:
            # Integration point for a future Competitor Agent.
            saturation = competitor.get("saturation", "medium")
            basis = "competitor_agent"
            confidence = "real"
        elif market_reach is not None:
            poi_count = len(market_reach.distribution_points)
            density = overpass.poi_density_per_1000(poi_count, market_reach.population_within_radius)
            saturation = _classify_saturation_from_density(density)
            basis = "poi_density_proxy"
            confidence = "estimated"
        else:
            saturation = "medium"
            basis = "no_signal_default"
            confidence = "estimated"

        sub_niches.append(
            SubNiche(
                name=sector,
                saturation=saturation,
                saturation_basis=basis,
                rationale=doc.text.strip()[:400],
                source_confidence=confidence,
            )
        )

    output = OpportunityOutput(
        sub_niches=sub_niches,
        source_confidence="real" if competitor is not None else "estimated",
    )
    # See market_reach_agent.py for why this is a reassignment rather than
    # an in-place mutation of state.market_intelligence.opportunity.
    market_intelligence = state.market_intelligence
    market_intelligence.opportunity = output
    state.market_intelligence = market_intelligence

    logger.info(
        "opportunity_agent: retrieved %d sub-niches for %r (basis=%s)",
        len(sub_niches),
        state.selected_business_category,
        "competitor_agent" if competitor is not None else "poi_density_proxy",
    )
    return state
