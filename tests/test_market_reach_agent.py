"""Market Reach Agent: offline, POIs monkeypatched."""

from __future__ import annotations

import math

import pytest

from common.net import DataUnavailable
from data_connectors import census, overpass
from module1_feasibility import market_reach_agent
from orchestrator.state import CaseState, EntrepreneurProfile, LocationDetails, MarketReachIntelligence, SessionMeta


def _state(**loc) -> CaseState:
    return CaseState(
        entrepreneur_profile=EntrepreneurProfile(location_query="q", location=LocationDetails(**loc)),
        session_meta=SessionMeta(session_id="t"),
    )


_POIS = [
    {"name": "Sample Weekly Market", "lat": 20.02, "lon": 78.0, "tags": {"amenity": "marketplace"}, "osm_type": "node"},
    {"name": None, "lat": 20.005, "lon": 78.0, "tags": {"amenity": "bus_station"}, "osm_type": "way"},
    {"name": "General Store", "lat": 20.0, "lon": 78.01, "tags": {"shop": "general"}, "osm_type": "node"},
]


@pytest.fixture(autouse=True)
def _reset():
    census.reset_index()


def test_resolved_sample_location(monkeypatch):
    seen = {}

    def fake_pois(lat, lon, radius_m, tags):
        seen.update(radius_m=radius_m, tags=tags)
        return _POIS

    monkeypatch.setattr(overpass, "query_pois", fake_pois)
    out = market_reach_agent.run(_state(latitude=20.0, longitude=78.0, resolution_method="lgd_table",
                                        source_confidence="estimated", state="Sample State"))
    intel = out["market_reach_intel"]
    assert set(out) == {"market_reach_intel"}
    assert isinstance(intel, MarketReachIntelligence)
    assert intel.population_within_radius and intel.population_within_radius > 0
    assert intel.population_data_year == 2011
    assert intel.consumer_base_estimate == round(intel.population_within_radius * market_reach_agent.CATCHMENT_SHARE)
    assert intel.households_estimate == round(intel.population_within_radius / 4.8)
    assert intel.source_confidence == "estimated"  # sample census rows
    assert seen["radius_m"] == 10_000 and ("amenity", "marketplace") in seen["tags"]
    distances = [d.distance_km for d in intel.distribution_points]
    assert distances == sorted(distances) and all(d > 0 for d in distances)
    assert intel.distribution_points[0].type == "transport_hub"
    assert "Unnamed" in intel.distribution_points[0].name
    assert intel.nearby_mandis == ["Sample Weekly Market"]
    assert "catchment share" in intel.data_source_detail


def test_unresolved_location_has_no_population_or_pois(monkeypatch):
    monkeypatch.setattr(overpass, "query_pois", lambda *a, **k: pytest.fail("must not query POIs"))
    intel = market_reach_agent.run(_state())["market_reach_intel"]
    assert intel.population_within_radius is None
    assert intel.consumer_base_estimate is None
    assert intel.distribution_points == []
    assert intel.limitations


def test_missing_profile_degrades():
    intel = market_reach_agent.run(CaseState(session_meta=SessionMeta(session_id="t")))["market_reach_intel"]
    assert intel.population_within_radius is None and intel.limitations


def test_state_centroid_uses_density_and_skips_pois(monkeypatch):
    monkeypatch.setattr(overpass, "query_pois", lambda *a, **k: pytest.fail("must not query POIs"))
    intel = market_reach_agent.run(_state(latitude=25.39, longitude=82.57, district="Bhadohi", state="Uttar Pradesh",
                                          resolution_method="state_centroid"))["market_reach_intel"]
    assert intel.population_within_radius == round(math.pi * 100 * 829)
    assert intel.source_confidence == "estimated"
    assert intel.distribution_points == []
    assert any("centroid" in l for l in intel.limitations)


def test_offline_pois_become_limitation():
    intel = market_reach_agent.run(_state(latitude=20.0, longitude=78.0, resolution_method="census_table"))[
        "market_reach_intel"]
    assert intel.distribution_points == []
    assert any("Nearby markets unavailable" in l for l in intel.limitations)


def test_real_only_when_population_and_coordinates_real(monkeypatch):
    monkeypatch.setattr(census, "population_within_radius", lambda *a: (12000, "real", "real table", []))
    monkeypatch.setattr(overpass, "query_pois", lambda *a: [])
    real = market_reach_agent.run(_state(latitude=20.0, longitude=78.0, resolution_method="nominatim",
                                         source_confidence="real"))["market_reach_intel"]
    assert real.source_confidence == "real"
    assert any("not proof of absence" in l for l in real.limitations)

    est = market_reach_agent.run(_state(latitude=20.0, longitude=78.0, resolution_method="nominatim",
                                        source_confidence="estimated"))["market_reach_intel"]
    assert est.source_confidence == "estimated"


def test_overpass_failure_is_caught(monkeypatch):
    def boom(*a):
        raise DataUnavailable("overpass: HTTP 504")

    monkeypatch.setattr(overpass, "query_pois", boom)
    intel = market_reach_agent.run(_state(latitude=20.0, longitude=78.0, resolution_method="census_table"))[
        "market_reach_intel"]
    assert any("504" in l for l in intel.limitations)
