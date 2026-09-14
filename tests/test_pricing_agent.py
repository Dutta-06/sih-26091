import pytest

from common.net import DataUnavailable
from config.settings import settings
from data_connectors import secc
from module1_feasibility import pricing_agent as pa
from orchestrator.state import BusinessCandidate, CaseState, EntrepreneurProfile, LocationDetails, MonthlyPrice, SessionMeta


def make_state(catalog_id, district="Bhadohi", state="Uttar Pradesh", commodity=None):
    loc = LocationDetails(district=district, state=state, resolution_method="census_table")
    return CaseState(
        entrepreneur_profile=EntrepreneurProfile(location_query="x", location=loc),
        business_shortlist=[BusinessCandidate(category="x", catalog_id=catalog_id, commodity=commodity)],
        session_meta=SessionMeta(session_id="t"),
    )


def test_non_agri_uses_state_tier_proxy_all_labeled_estimated(monkeypatch):
    monkeypatch.setattr(settings, "secc_dataset_path", None)
    intel = pa.run(make_state("tailoring"))["pricing_intel"]
    assert intel.price_source_type == "purchasing_power_proxy" and intel.source_confidence == "estimated"
    assert intel.purchasing_power_index == 0.85 and intel.regional_purchasing_power_proxy == "low"  # UP tier low
    assert intel.min_market_price == round(120 * 0.85, 2) and intel.max_market_price == round(450 * 0.85, 2)
    assert len(intel.price_points) == 3 and all(p.source_confidence == "estimated" for p in intel.price_points)
    assert not intel.monthly_price_history and intel.limitations
    assert all(s.source_confidence == "estimated" for s in intel.sources)


def test_agri_offline_falls_back_to_estimate_with_limitation():
    intel = pa.run(make_state("flour_mill"))["pricing_intel"]  # catalog commodity Wheat
    assert intel.price_source_type == "purchasing_power_proxy" and intel.source_confidence == "estimated"
    assert any("Wheat" in lim for lim in intel.limitations)


def test_agri_real_data_path(monkeypatch):
    history = [MonthlyPrice(month=f"2025-{m:02d}", modal_price=2000 + 10 * m) for m in range(1, 13)]
    seen = {}

    def fake(commodity, state, district, months=36):
        seen.update(commodity=commodity, state=state, district=district, months=months)
        return history

    monkeypatch.setattr(pa.agmarknet, "fetch_monthly_prices", fake)
    intel = pa.run(make_state("flour_mill"))["pricing_intel"]
    assert seen == {"commodity": "Wheat", "state": "Uttar Pradesh", "district": "Bhadohi", "months": 36}
    assert intel.price_source_type == "direct_market_data" and intel.source_confidence == "real"
    assert intel.min_market_price < intel.optimal_target_price < intel.max_market_price
    assert intel.optimal_target_price == 2065.0
    assert all(p.source_confidence == "real" for p in intel.price_points)
    assert intel.monthly_price_history == history and intel.purchasing_power_index is None


def test_secc_dataset_index(tmp_path, monkeypatch):
    path = tmp_path / "secc.csv"
    path.write_text("District,State,AssetIndex\nBhadohi,Uttar Pradesh,75\n", encoding="utf-8")
    monkeypatch.setattr(settings, "secc_dataset_path", path)
    assert secc.purchasing_power_index("bhadohi", "Uttar Pradesh") == (75.0, 1.1)
    with pytest.raises(DataUnavailable):
        secc.purchasing_power_index("Gaya", "Bihar")
    intel = pa.run(make_state("tailoring"))["pricing_intel"]
    assert intel.purchasing_power_index == 1.1 and intel.regional_purchasing_power_proxy == "high"
    assert intel.source_confidence == "estimated"


def test_unknown_state_keeps_unscaled_estimate_and_says_so(monkeypatch):
    monkeypatch.setattr(settings, "secc_dataset_path", None)
    intel = pa.run(make_state("tailoring", district=None, state=None))["pricing_intel"]
    assert intel.purchasing_power_index is None and intel.regional_purchasing_power_proxy is None
    assert intel.min_market_price == 120 and any("No state" in lim for lim in intel.limitations)


def test_no_activity_is_unavailable():
    state = make_state("does_not_exist")
    intel = pa.run(state)["pricing_intel"]
    assert intel.price_source_type == "unavailable" and intel.min_market_price is None and intel.limitations


def test_activity_without_reference_price_is_unavailable():
    intel = pa.proxy_price_intel({"price_unit": "INR"}, LocationDetails(), ["prior"])
    assert intel.price_source_type == "unavailable" and intel.optimal_target_price is None
    assert intel.limitations[0] == "prior"
