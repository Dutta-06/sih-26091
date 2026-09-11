"""
Market Reach Agent test, run fully offline against canned Nominatim/Overpass
responses so it never depends on network access or live rate limits.
"""
from __future__ import annotations

from module1_feasibility import market_reach_agent
from data_connectors import geocoding, overpass
from orchestrator.state import CaseState, EntrepreneurProfile, SessionMeta

_NOMINATIM_FIXTURE = [
    {
        "display_name": "Sample Village A, Sample District, Sample State, India",
        "lat": "20.0005",
        "lon": "78.0005",
    }
]

_OVERPASS_FIXTURE = [
    {"tags": {"shop": "general", "name": "Sample General Store"}, "lat": 20.001, "lon": 78.001},
    {"tags": {"amenity": "marketplace", "name": "Sample Weekly Market"}, "lat": 20.002, "lon": 78.0015},
]

# Capture the real implementations before any test monkeypatches them, so
# the fake versions below can still delegate into real disambiguation /
# parsing logic instead of hitting the network.
_real_geocode_location = geocoding.geocode_location
_real_query_pois = overpass.query_pois


def test_market_reach_agent_end_to_end(monkeypatch):
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
        entrepreneur_profile=EntrepreneurProfile(location_query="Sample Village A"),
        selected_business_category="dairy",
        session_meta=SessionMeta(session_id="test-session"),
    )

    result = market_reach_agent.run(state)

    output = result.market_intelligence.market_reach
    assert output is not None
    assert output.population_within_radius > 0
    assert output.population_data_year == 2011
    assert len(output.distribution_points) == 2
    assert output.source_confidence == "estimated"
    assert output.resolved_lat == 20.0005
    assert output.resolved_lon == 78.0005


def test_market_reach_agent_requires_profile():
    import pytest

    state = CaseState(session_meta=SessionMeta(session_id="test-session"))
    with pytest.raises(ValueError):
        market_reach_agent.run(state)
