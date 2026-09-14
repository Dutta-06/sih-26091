import math

import pytest

from common.net import DataUnavailable
from common.reference import get_activity
from config.settings import settings
from data_connectors import udyam
from module1_feasibility import competitor_agent as ca
from orchestrator.state import BusinessCandidate, CaseState, EntrepreneurProfile, LocationDetails, SessionMeta

LAT, LON = 25.39, 82.57


def make_state(catalog_id="tailoring", method="census_table", lat=LAT, lon=LON):
    loc = LocationDetails(district="Bhadohi", state="Uttar Pradesh", latitude=lat, longitude=lon, resolution_method=method)
    return CaseState(
        entrepreneur_profile=EntrepreneurProfile(location_query="Bhadohi", location=loc),
        business_shortlist=[BusinessCandidate(category="x", catalog_id=catalog_id)],
        session_meta=SessionMeta(session_id="t"),
    )


def write_csv(tmp_path, rows, header="NIC_Code,District,State,EnterpriseName,Latitude,Longitude"):
    path = tmp_path / "udyam.csv"
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def no_overpass(monkeypatch):
    def fail(*a, **k):
        raise DataUnavailable("overpass: offline")
    monkeypatch.setattr(ca.overpass, "query_pois", fail, raising=False)


def test_nic_prefix_match():
    assert udyam.nic_matches("14101", "1410")
    assert udyam.nic_matches("14", "1410")
    assert not udyam.nic_matches("1392", "1410")
    assert not udyam.nic_matches("", "1410")


def test_udyam_csv_parsing_counts_district_state_and_radius(tmp_path, monkeypatch):
    path = write_csv(tmp_path, [
        f"14101,Bhadohi,Uttar Pradesh,Sharma Tailors,{LAT + 0.01},{LON}",
        f"1410,Bhadohi,Uttar Pradesh,,{LAT},{LON + 0.01}",
        "14109,Varanasi,Uttar Pradesh,Far Away Tailors,25.32,82.97",
        f"13920,Bhadohi,Uttar Pradesh,Carpet Co,{LAT},{LON}",
    ])
    monkeypatch.setattr(settings, "udyam_dataset_path", path)
    m = udyam.find_enterprises("1410", "bhadohi", "Uttar Pradesh", LAT, LON, 10.0)
    assert (m.district_count, m.state_count) == (2, 3)
    assert m.has_coordinates and len(m.nearby) == 2 and m.nearby[0]["distance_km"] <= m.nearby[1]["distance_km"]


def test_udyam_unconfigured_raises(monkeypatch):
    monkeypatch.setattr(settings, "udyam_dataset_path", None)
    with pytest.raises(DataUnavailable):
        udyam.find_enterprises("1410", "Bhadohi", "Uttar Pradesh")


def test_tier_udyam_unavailable_by_default(monkeypatch):
    monkeypatch.setattr(settings, "udyam_dataset_path", None)
    r = ca.tier_udyam(get_activity("tailoring"), make_state().entrepreneur_profile.location, 10.0)
    assert r.attempt.status == "unavailable" and r.count is None


def test_tier_udyam_used_only_real_names(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "udyam_dataset_path", write_csv(tmp_path, [
        f"14101,Bhadohi,Uttar Pradesh,Sharma Tailors,{LAT},{LON}", f"14101,Bhadohi,Uttar Pradesh,,{LAT},{LON}"]))
    r = ca.tier_udyam(get_activity("tailoring"), make_state().entrepreneur_profile.location, 10.0)
    assert r.attempt.status == "used" and r.count == 2 and [c.name for c in r.competitors] == ["Sharma Tailors"]


def test_tier_overpass_offline_and_skipped_for_coarse_location(no_overpass):
    act = get_activity("tailoring")
    assert ca.tier_overpass(act, make_state().entrepreneur_profile.location, 10).attempt.status == "unavailable"
    coarse = make_state(method="state_centroid").entrepreneur_profile.location
    assert ca.tier_overpass(act, coarse, 10).attempt.status == "skipped"


def test_tier_overpass_used(monkeypatch):
    pois = [{"name": "Tailor A", "lat": LAT + 0.02, "lon": LON, "tags": {}, "osm_type": "node"},
            {"name": None, "lat": LAT, "lon": LON, "tags": {}, "osm_type": "way"}]
    monkeypatch.setattr(ca.overpass, "query_pois", lambda *a, **k: pois, raising=False)
    r = ca.tier_overpass(get_activity("tailoring"), make_state().entrepreneur_profile.location, 10)
    assert r.count == 2 and [c.name for c in r.competitors] == ["Tailor A"] and r.competitors[0].distance_km > 0


def test_tier_web_search_never_fabricates():
    r = ca.tier_web_search({}, LocationDetails())
    assert r.attempt.status == "unavailable" and r.count is None and not r.competitors


def test_fallback_order_stops_at_first_used(monkeypatch):
    calls = []
    monkeypatch.setattr(ca, "tier_udyam", lambda *a: calls.append("u") or ca.TierResult(ca.TierAttempt(tier="udyam", status="no_data")))
    monkeypatch.setattr(ca, "tier_overpass", lambda *a: calls.append("o") or ca.TierResult(ca.TierAttempt(tier="overpass", status="used"), count=3))
    monkeypatch.setattr(ca, "tier_web_search", lambda *a: calls.append("w") or ca.TierResult(ca.TierAttempt(tier="web_search", status="unavailable")))
    used, attempts = ca.run_tiers({}, LocationDetails(), 10)
    assert calls == ["u", "o"] and used.attempt.tier == "overpass" and len(attempts) == 2


def test_no_data_is_unknown_not_good_news(monkeypatch, no_overpass):
    monkeypatch.setattr(settings, "udyam_dataset_path", None)
    intel = ca.run(make_state())["competitor_intel"]
    assert intel.estimated_competitor_count is None and intel.density_per_10k_population is None
    assert intel.saturation_level == "unknown" and intel.z_score_vs_district is None
    assert intel.fallback_tier_used == "none" and intel.source_confidence == "estimated"
    assert [t.tier for t in intel.tiers_attempted] == ["udyam", "overpass", "web_search"]
    assert intel.limitations and not intel.identified_competitors


def test_overpass_path_density_zscore_saturation(monkeypatch):
    monkeypatch.setattr(settings, "udyam_dataset_path", None)
    pois = [{"name": f"T{i}", "lat": LAT, "lon": LON + 0.001 * i, "tags": {}, "osm_type": "node"} for i in range(30)]
    monkeypatch.setattr(ca.overpass, "query_pois", lambda *a, **k: pois, raising=False)
    monkeypatch.setattr(ca.census, "population_within_radius",
                        lambda lat, lon, r, st: (40_000, "estimated", "sample census", ["sample"]), raising=False)
    intel = ca.run(make_state())["competitor_intel"]
    assert intel.fallback_tier_used == "overpass" and intel.estimated_competitor_count == 30
    assert intel.density_per_10k_population == 7.5
    expected = 5.0 * 40_000 / 10_000  # tailoring benchmark 5/10k
    assert intel.z_score_vs_district == round((30 - expected) / math.sqrt(expected), 2)
    assert intel.saturation_level == "high"  # 7.5 / 5 = 1.5
    assert intel.source_confidence == "estimated"  # population is estimated
    assert any(s.name.startswith("OpenStreetMap") and s.source_confidence == "real" for s in intel.sources)


def test_population_failure_leaves_density_unknown(monkeypatch):
    monkeypatch.setattr(settings, "udyam_dataset_path", None)
    monkeypatch.setattr(ca.overpass, "query_pois", lambda *a, **k: [{"name": "T", "lat": LAT, "lon": LON}], raising=False)
    def boom(*a, **k):
        raise DataUnavailable("census missing")
    monkeypatch.setattr(ca.census, "population_within_radius", boom, raising=False)
    intel = ca.run(make_state())["competitor_intel"]
    assert intel.estimated_competitor_count == 1 and intel.density_per_10k_population is None
    assert intel.saturation_level == "unknown" and intel.z_score_vs_state is None


def test_saturation_thresholds():
    assert ca.saturation_from_ratio(0.75, 1.0) == "low"
    assert ca.saturation_from_ratio(1.25, 1.0) == "medium"
    assert ca.saturation_from_ratio(1.3, 1.0) == "high"
    assert ca.saturation_from_ratio(None, 1.0) == "unknown"
