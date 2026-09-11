"""
Opportunity Agent tests against the sample reference corpus, covering both
the POI-density fallback (no Competitor Agent) and the preferred path once
competitor data is present in state.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import settings
from module1_feasibility import opportunity_agent
from orchestrator.state import (
    CaseState,
    MarketIntelligence,
    MarketReachOutput,
    POI,
    SessionMeta,
)
from rag.ingest_sector_reports import ingest


@pytest.fixture(scope="module", autouse=True)
def _ensure_vector_store():
    # Mirrors `python -m rag.ingest_sector_reports` -- build the vector
    # store from the sample corpus once for this test module.
    ingest(Path(settings.reference_corpus_path))


def _market_reach(poi_count: int, population: int) -> MarketReachOutput:
    return MarketReachOutput(
        population_within_radius=population,
        radius_km=10.0,
        distribution_points=[
            POI(name=f"Sample POI {i}", type="shop", lat=20.0, lon=78.0) for i in range(poi_count)
        ],
        resolved_lat=20.0,
        resolved_lon=78.0,
        source_confidence="estimated",
    )


def test_opportunity_agent_poi_density_fallback():
    state = CaseState(
        selected_business_category="dairy",
        market_intelligence=MarketIntelligence(market_reach=_market_reach(poi_count=1, population=2000)),
        session_meta=SessionMeta(session_id="test-session"),
    )

    result = opportunity_agent.run(state)

    output = result.market_intelligence.opportunity
    assert output is not None
    assert len(output.sub_niches) > 0
    assert output.source_confidence == "estimated"
    for niche in output.sub_niches:
        assert niche.saturation in ("low", "medium", "high")
        assert niche.saturation_basis == "poi_density_proxy"
        assert niche.source_confidence == "estimated"


def test_opportunity_agent_prefers_competitor_data_when_present():
    state = CaseState(
        selected_business_category="handloom",
        market_intelligence=MarketIntelligence(
            market_reach=_market_reach(poi_count=1, population=2000),
            competitor={"saturation": "high"},
        ),
        session_meta=SessionMeta(session_id="test-session"),
    )

    result = opportunity_agent.run(state)

    output = result.market_intelligence.opportunity
    assert output.source_confidence == "real"
    assert all(n.saturation_basis == "competitor_agent" for n in output.sub_niches)
    assert all(n.saturation == "high" for n in output.sub_niches)


def test_opportunity_agent_requires_selected_category():
    state = CaseState(session_meta=SessionMeta(session_id="test-session"))
    with pytest.raises(ValueError):
        opportunity_agent.run(state)
