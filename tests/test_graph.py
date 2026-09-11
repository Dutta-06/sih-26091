"""
End-to-end test of the compiled LangGraph pipeline (both agents), fully
offline via monkeypatched network connectors.
"""
from __future__ import annotations

from pathlib import Path
import uuid

from config.settings import settings
from data_connectors import geocoding, overpass
from orchestrator.graph import build_graph
from orchestrator.state import CaseState, EntrepreneurProfile, SessionMeta
from rag.ingest_sector_reports import ingest

_NOMINATIM_FIXTURE = [
    {
        "display_name": "Sample Village A, Sample District, Sample State, India",
        "lat": "20.0005",
        "lon": "78.0005",
    }
]
_OVERPASS_FIXTURE = [
    {"tags": {"shop": "general", "name": "Sample General Store"}, "lat": 20.001, "lon": 78.001},
]

_real_geocode_location = geocoding.geocode_location
_real_query_pois = overpass.query_pois


def test_full_graph_runs_both_agents(monkeypatch):
    ingest(Path(settings.reference_corpus_path))

    monkeypatch.setattr(
        geocoding,
        "geocode_location",
        lambda query, **kw: _real_geocode_location(query, offline_fixture=_NOMINATIM_FIXTURE),
    )
    monkeypatch.setattr(
        overpass,
        "query_pois",
        lambda lat, lon, radius_m, tags=None, **kw: _real_query_pois(
            lat, lon, radius_m, tags, offline_fixture=_OVERPASS_FIXTURE
        ),
    )

    state = CaseState(
        entrepreneur_profile=EntrepreneurProfile(location_query="Sample Village A", available_capital=100000.0),
        selected_business_category="dairy",
        session_meta=SessionMeta(session_id=str(uuid.uuid4())),
    )

    graph = build_graph()
    result = graph.invoke(state)
    final_state = result if isinstance(result, CaseState) else CaseState.model_validate(result)

    assert final_state.market_intelligence.market_reach is not None
    assert final_state.market_intelligence.opportunity is not None
    assert len(final_state.market_intelligence.opportunity.sub_niches) > 0
