from common.net import DataUnavailable
from common.reference import get_activity
from module1_feasibility import supply_chain_agent as sc
from orchestrator.state import BusinessCandidate, CaseState, EntrepreneurProfile, LocationDetails, SessionMeta

LAT, LON = 25.39, 82.57


def make_state(catalog_id="dairy_farming", method="census_table"):
    loc = LocationDetails(district="Bhadohi", state="Uttar Pradesh", latitude=LAT, longitude=LON, resolution_method=method)
    return CaseState(
        entrepreneur_profile=EntrepreneurProfile(location_query="x", location=loc),
        business_shortlist=[BusinessCandidate(category="x", catalog_id=catalog_id)],
        session_meta=SessionMeta(session_id="t"),
    )


def test_offline_generic_chain_no_invented_suppliers(monkeypatch):
    def offline(*a, **k):
        raise DataUnavailable("overpass: skipped (DATA_MODE=offline)")
    monkeypatch.setattr(sc.overpass, "query_pois", offline, raising=False)
    intel = sc.run(make_state())["supply_chain_intel"]
    assert intel.major_suppliers == [] and intel.source_confidence == "estimated"
    assert all(n.source_confidence == "estimated" and n.distance_km is None for n in intel.nodes)
    roles = {n.role for n in intel.nodes}
    assert {"input_supplier", "enterprise", "logistics", "buyer"} <= roles
    assert intel.lead_time_days is None and intel.raw_material_availability == "unknown"
    assert sc.LOGISTICS in intel.single_points_of_failure
    assert any("Perishable" in v for v in intel.critical_vulnerabilities)  # dairy is perishable
    assert intel.limitations


def test_spof_single_buyer_and_single_supplier():
    act = {"key_inputs": ["Yarn", "Dyes"], "buyers": ["Master weavers"]}
    g = sc.build_graph(act, [{"name": "Real Yarn Depot", "distance_km": 4.2, "tag": "shop=wholesale"}])
    spof = sc.single_points_of_failure(g)
    assert set(spof) == {sc.LOGISTICS, "Master weavers", "Real Yarn Depot"}
    assert sc.ENTERPRISE not in spof


def test_multiple_buyers_not_spof():
    g = sc.build_graph(get_activity("tailoring"), [])
    assert sc.single_points_of_failure(g) == [sc.LOGISTICS]


def test_live_suppliers_attached_with_distance(monkeypatch):
    pois = [
        {"name": "Far Mandi", "lat": LAT + 0.15, "lon": LON, "tags": {"amenity": "marketplace"}, "osm_type": "node"},
        {"name": "Kisan Seva Kendra", "lat": LAT + 0.02, "lon": LON, "tags": {"shop": "agrarian"}, "osm_type": "way"},
        {"name": None, "lat": LAT, "lon": LON, "tags": {"shop": "wholesale"}, "osm_type": "node"},
    ]
    seen = {}
    monkeypatch.setattr(sc.overpass, "query_pois", lambda lat, lon, r, tags: seen.update(r=r, tags=tags) or pois, raising=False)
    intel = sc.run(make_state())["supply_chain_intel"]
    assert seen["r"] == 25_000 and ("shop", "agrarian") in seen["tags"]
    assert intel.major_suppliers == ["Kisan Seva Kendra", "Far Mandi"]
    real = [n for n in intel.nodes if n.source_confidence == "real"]
    assert len(real) == 2 and all(n.distance_km and n.distance_km > 0 for n in real)
    assert intel.raw_material_availability == "locally_available"
    assert intel.alternate_sources and "Far Mandi" in intel.alternate_sources[0]


def test_live_zero_suppliers_is_unknown_not_scarce(monkeypatch):
    monkeypatch.setattr(sc.overpass, "query_pois", lambda *a, **k: [], raising=False)
    intel = sc.run(make_state())["supply_chain_intel"]
    assert intel.raw_material_availability == "unknown" and intel.major_suppliers == []
    assert any("No located input supplier" in v for v in intel.critical_vulnerabilities)


def test_coarse_location_skips_supplier_search(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("should not query at a state centroid")
    monkeypatch.setattr(sc.overpass, "query_pois", fail, raising=False)
    intel = sc.run(make_state(method="state_centroid"))["supply_chain_intel"]
    assert intel.major_suppliers == [] and any("state level" in lim for lim in intel.limitations)


def test_connector_unavailable_degrades(monkeypatch):
    def unavailable(*a, **k):
        raise DataUnavailable("overpass down")
    monkeypatch.setattr(sc.overpass, "query_pois", unavailable, raising=False)
    intel = sc.run(make_state("tailoring"))["supply_chain_intel"]
    assert intel.major_suppliers == [] and any("overpass down" in lim for lim in intel.limitations)


def test_no_activity():
    intel = sc.run(make_state("nope"))["supply_chain_intel"]
    assert intel.nodes == [] and intel.limitations
