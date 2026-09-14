import math
from types import SimpleNamespace

import pytest

from common.net import DataUnavailable
from data_connectors import osrm
from module1_feasibility import risk_agent
from orchestrator import stores
from orchestrator.state import (BusinessCandidate, CaseState, EntrepreneurProfile, LocationDetails, MonthlyPrice,
                                SessionMeta)
from rag import ingest_risk_taxonomy, vector_store


def _unavailable(*_a, **_k):
    raise DataUnavailable("offline")


@pytest.fixture(autouse=True)
def _offline_connectors(monkeypatch):
    vector_store.reset()
    monkeypatch.setattr(risk_agent, "overpass", SimpleNamespace(query_pois=_unavailable), raising=False)
    monkeypatch.setattr(risk_agent, "agmarknet", SimpleNamespace(fetch_monthly_prices=_unavailable), raising=False)


def make_state(catalog_id="dairy_farming", lat=25.45, lon=82.60, method="nominatim", conf="real",
               district="Bhadohi", commodity=None, constraints=None):
    loc = LocationDetails(latitude=lat, longitude=lon, district=district, state="Uttar Pradesh",
                          resolution_method=method, source_confidence=conf)
    profile = EntrepreneurProfile(location_query="x", location=loc, constraints=constraints or [])
    return CaseState(entrepreneur_profile=profile, session_meta=SessionMeta(session_id="t"),
                     business_shortlist=[BusinessCandidate(category=catalog_id, catalog_id=catalog_id, commodity=commodity)])


def test_unknown_route_is_not_low():
    state = make_state(lat=None, lon=None, method="unresolved", conf="estimated")
    risk = risk_agent.run(state)["risk_intel"]
    assert risk.road_distance_to_hub_km is None
    assert risk.route_distance_method == "unavailable"
    assert risk.supply_route_risk == "medium"
    assert any("unknown" in l for l in risk.limitations)
    assert risk.source_confidence == "estimated"


def test_district_centroid_location_gives_unavailable_distance():
    state = make_state(lat=25.39, lon=82.57, method="lgd_table")  # exactly Bhadohi HQ reference coords
    risk = risk_agent.run(state)["risk_intel"]
    assert risk.route_distance_method == "unavailable" and risk.road_distance_to_hub_km is None


def test_haversine_fallback_is_labeled_estimated():
    risk = risk_agent.run(make_state())["risk_intel"]
    assert risk.route_distance_method == "haversine_estimate"
    expected = risk_agent.haversine_km(25.45, 82.60, 25.39, 82.57) * 1.3
    assert risk.road_distance_to_hub_km == pytest.approx(expected, abs=0.1)
    route_src = risk.sources[0]
    assert route_src.source_confidence == "estimated"
    assert any("OSRM unavailable" in l for l in risk.limitations)


def test_osrm_mocked(monkeypatch):
    monkeypatch.setattr(risk_agent.osrm, "road_distance_km", lambda *a: 48.0)
    risk = risk_agent.run(make_state())["risk_intel"]
    assert risk.route_distance_method == "osrm"
    assert risk.road_distance_to_hub_km == 48.0
    assert risk.supply_route_risk == "high"  # perishable dairy: > 25 km
    assert risk.sources[0].source_confidence == "real"
    assert risk.source_confidence == "estimated"  # seasonal still from catalog


def test_osrm_connector_parses_and_gates(monkeypatch):
    with pytest.raises(DataUnavailable):
        osrm.road_distance_km(25.0, 82.0, 25.1, 82.1)
    monkeypatch.setattr(osrm, "require_live", lambda name: None)
    calls = {}

    class Resp:
        def raise_for_status(self): pass
        def json(self): return {"code": "Ok", "routes": [{"distance": 12345.0}]}

    def fake_get(url, params=None, timeout=None):
        calls["url"] = url
        return Resp()

    monkeypatch.setattr(osrm.httpx, "get", fake_get)
    assert osrm.road_distance_km(25.0, 82.0, 25.1, 82.1) == pytest.approx(12.345)
    assert "/route/v1/driving/82.0,25.0;82.1,25.1" in calls["url"]


def test_marketplace_poi_used_as_hub(monkeypatch):
    pois = [{"name": "Gopiganj haat", "lat": 25.46, "lon": 82.61, "tags": {}, "osm_type": "node"}]
    monkeypatch.setattr(risk_agent, "overpass", SimpleNamespace(query_pois=lambda *a, **k: pois))
    risk = risk_agent.run(make_state())["risk_intel"]
    assert "Gopiganj haat" in risk.sources[0].detail
    assert risk.supply_route_risk == "low"


def _synthetic_prices(months=36):
    out = []
    for i in range(months):
        m = i % 12
        seasonal = 0.55 if m in (5, 6) else 1.08  # planted deep Jun/Jul low season (swing > 50% of average)
        trend = 1000 + 5 * i
        out.append(MonthlyPrice(month=f"{2022 + i // 12}-{m + 1:02d}", modal_price=trend * seasonal))
    return out


def test_seasonal_decomposition_recovers_planted_low_season(monkeypatch):
    index = risk_agent.seasonal_decomposition(_synthetic_prices())
    assert len(index) == 12 and math.isclose(sum(index) / 12, 1.0, abs_tol=1e-3)
    assert risk_agent.low_season_months(index) == ["Jun", "Jul"]

    monkeypatch.setattr(risk_agent, "agmarknet", SimpleNamespace(fetch_monthly_prices=lambda *a, **k: _synthetic_prices()))
    monkeypatch.setattr(risk_agent.osrm, "road_distance_km", lambda *a: 20.0)
    risk = risk_agent.run(make_state("goat_rearing", commodity="Goat"))["risk_intel"]
    assert risk.low_season_months == ["Jun", "Jul"]
    assert "Agmarknet" in risk.seasonal_basis
    assert risk.seasonal_demand_variation == "high"
    assert risk.source_confidence == "real"


def test_short_price_history_and_catalog_fallback_estimated(monkeypatch):
    monkeypatch.setattr(risk_agent, "agmarknet",
                        SimpleNamespace(fetch_monthly_prices=lambda *a, **k: _synthetic_prices(12)))
    risk = risk_agent.run(make_state("goat_rearing", commodity="Goat"))["risk_intel"]
    assert risk.seasonal_basis.startswith("catalog seasonal profile")
    assert risk.sources[1].source_confidence == "estimated"
    assert len(risk.seasonal_index) == 12 and math.isclose(sum(risk.seasonal_index) / 12, 1.0, abs_tol=1e-3)
    assert risk.source_confidence == "estimated"


def test_single_buyer_flag_for_one_buyer_activity():
    risk = risk_agent.run(make_state("grocery_kirana"))["risk_intel"]
    assert risk.single_buyer_dependency_risk == "high"
    flag = next(f for f in risk.risk_flags if f.title == "Single-buyer dependency")
    assert flag.category == "structural" and flag.mitigation


def test_taxonomy_retrieval_from_profile_statement():
    state = make_state("tailoring", constraints=["I will sell everything to one buyer, a single boutique owner"])
    risk = risk_agent.run(state)["risk_intel"]
    assert risk.single_buyer_dependency_risk == "medium"
    assert any("Single-buyer" in f.title for f in risk.risk_flags)


def test_catalog_attribute_rules():
    mill = risk_agent.run(make_state("flour_mill"))["risk_intel"]
    assert any(f.title == "Power reliability" and f.severity == "high" for f in mill.risk_flags)
    fish = risk_agent.run(make_state("fisheries_pond"))["risk_intel"]
    assert any(f.title.startswith("Climate and disease") for f in fish.risk_flags)
    assert any(f.title == "Perishability and cold chain" for f in fish.risk_flags)


def test_local_feedback_becomes_flags():
    stores.add_local_feedback("funded_entrepreneur", "Bhadohi", "milk collection", "Collection centre paid 45 days late",
                              catalog_id="dairy_farming", rating=2)
    risk = risk_agent.run(make_state())["risk_intel"]
    fb = [f for f in risk.risk_flags if f.category == "local_feedback"]
    assert fb and fb[0].severity == "high" and "45 days" in fb[0].description


def test_no_candidate_degrades():
    state = CaseState(session_meta=SessionMeta(session_id="t"))
    risk = risk_agent.run(state)["risk_intel"]
    assert risk.limitations and risk.source_confidence == "estimated"


def test_ingest_script_validates_corpus(capsys):
    assert ingest_risk_taxonomy.main([]) == 0
    assert "documents" in capsys.readouterr().out
