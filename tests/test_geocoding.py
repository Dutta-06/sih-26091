"""resolve_location: tables, disambiguation, Nominatim (mocked HTTP), fallbacks. No network."""

from __future__ import annotations

import logging

import httpx
import pytest

import data_connectors
from config.settings import settings
from data_connectors import geocoding


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    geocoding.clear_cache()
    monkeypatch.setattr(settings, "nominatim_min_interval_seconds", 0.0)
    monkeypatch.setattr(data_connectors.time, "sleep", lambda s: None)
    yield
    geocoding.clear_cache()


def _live(monkeypatch, responses):
    """Switch to live mode and serve queued httpx responses; returns the recorded calls."""
    monkeypatch.setattr(settings, "data_mode", "live")
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        status, payload = responses.pop(0)
        return httpx.Response(status, json=payload, request=httpx.Request(method, url))

    monkeypatch.setattr(data_connectors.httpx, "request", fake_request)
    return calls


def test_structured_query_resolves_from_sample_tables():
    loc = geocoding.resolve_location("Sample Village A, Sample District, Sample State")
    assert (loc.latitude, loc.longitude) == (20.0, 78.0)
    assert loc.lgd_code == "999001"
    assert loc.resolution_method == "lgd_table"
    assert loc.block == "Sample Block"
    assert loc.source_confidence == "estimated"  # sample fixture rows are never "real"


def test_village_name_is_not_matched_as_substring():
    loc = geocoding.resolve_location("Sample Village Alpha")
    assert loc.lgd_code == "999002"
    assert loc.district == "Other District"


def test_repeated_name_is_ambiguous_until_district_given():
    ambiguous = geocoding.resolve_location("Sample Village B")
    assert ambiguous.resolution_method == "unresolved"
    assert ambiguous.latitude is None
    assert ambiguous.candidates_considered == 2
    assert any("ambiguous" in n for n in ambiguous.notes)

    loc = geocoding.resolve_location("Sample Village B, Other District, Other State")
    assert loc.lgd_code == "999004"
    assert (loc.latitude, loc.longitude) == (24.0, 80.0)


def test_district_and_state_fallbacks_offline():
    loc = geocoding.resolve_location("Bhadohi, Uttar Pradesh")
    assert loc.resolution_method == "state_centroid"
    assert loc.district == "Bhadohi" and loc.state == "Uttar Pradesh"
    assert loc.source_confidence == "estimated"
    assert any("district headquarters" in n for n in loc.notes)

    free_text = geocoding.resolve_location("Bhadohi Uttar Pradesh")
    assert free_text.district == "Bhadohi"

    state_only = geocoding.resolve_location("Some Hamlet, Bihar")
    assert state_only.resolution_method == "state_centroid"
    assert state_only.state == "Bihar"
    assert any("state capital" in n for n in state_only.notes)


def test_unresolvable_query_never_raises():
    for query in ("zzqx", ""):
        loc = geocoding.resolve_location(query)
        assert loc.resolution_method == "unresolved"
        assert loc.latitude is None and loc.longitude is None


def test_nominatim_live_path_uses_user_agent_and_is_real(monkeypatch):
    calls = _live(monkeypatch, [(200, [{
        "display_name": "Gopiganj, Bhadohi, Uttar Pradesh, India", "lat": "25.28", "lon": "82.46",
        "address": {"town": "Gopiganj", "state_district": "Bhadohi", "state": "Uttar Pradesh", "postcode": "221303"},
    }])])
    loc = geocoding.resolve_location("Gopiganj, Bhadohi, Uttar Pradesh")
    assert loc.resolution_method == "nominatim"
    assert loc.source_confidence == "real"
    assert (loc.latitude, loc.longitude) == (25.28, 82.46)
    assert loc.pincode == "221303"
    assert calls[0]["headers"]["User-Agent"] == settings.nominatim_user_agent
    assert calls[0]["timeout"] == settings.http_timeout_seconds


def test_nominatim_rejects_candidates_outside_stated_district(monkeypatch):
    _live(monkeypatch, [(200, [
        {"display_name": "Rampur, Rampur, Uttar Pradesh, India", "lat": "28.8", "lon": "79.0",
         "address": {"village": "Rampur", "state_district": "Rampur", "state": "Uttar Pradesh"}},
        {"display_name": "Rampur, Varanasi, Uttar Pradesh, India", "lat": "25.3", "lon": "82.9",
         "address": {"village": "Rampur", "state_district": "Varanasi", "state": "Uttar Pradesh"}},
    ])])
    loc = geocoding.resolve_location("Rampur, Varanasi, Uttar Pradesh")
    assert (loc.latitude, loc.longitude) == (25.3, 82.9)


def test_empty_lgd_district_does_not_match_every_candidate(monkeypatch, tmp_path):
    table = tmp_path / "lgd.csv"
    table.write_text("village_name,block,district,state,lgd_code,is_sample\nRampur,,,,555,0\nRampur,,,,556,0\n",
                     encoding="utf-8")
    monkeypatch.setattr(settings, "lgd_data_path", table)
    _live(monkeypatch, [(200, [
        {"display_name": "Rampur, Rampur, Uttar Pradesh, India", "lat": "28.8", "lon": "79.0", "address": {}},
        {"display_name": "Rampur, Shimla, Himachal Pradesh, India", "lat": "31.4", "lon": "77.6", "address": {}},
    ])])
    loc = geocoding.resolve_location("Rampur")
    assert loc.lgd_code is None  # no LGD code attached on an empty-district "match"


def test_nominatim_429_retries_once_then_succeeds(monkeypatch):
    calls = _live(monkeypatch, [(429, {}), (200, [{"display_name": "X, Gaya, Bihar", "lat": "24.8", "lon": "85.0",
                                                   "address": {"state_district": "Gaya", "state": "Bihar"}}])])
    loc = geocoding.resolve_location("X, Gaya, Bihar")
    assert loc.resolution_method == "nominatim"
    assert len(calls) == 2


def test_nominatim_persistent_5xx_falls_back_without_retry_storm(monkeypatch):
    calls = _live(monkeypatch, [(503, {}), (503, {}), (503, {})])
    loc = geocoding.resolve_location("Somewhere, Gaya, Bihar")
    assert len(calls) == 2
    assert loc.resolution_method == "state_centroid"
    assert loc.district == "Gaya"
    assert any("HTTP 503" in n for n in loc.notes)


def test_cache_key_includes_data_mode(monkeypatch):
    offline = geocoding.resolve_location("Some Place, Gaya, Bihar")
    assert offline.resolution_method == "state_centroid"
    _live(monkeypatch, [(200, [{"display_name": "Some Place, Gaya, Bihar", "lat": "24.7", "lon": "85.1",
                                "address": {"state_district": "Gaya", "state": "Bihar"}}])])
    live = geocoding.resolve_location("Some Place, Gaya, Bihar")
    assert live.resolution_method == "nominatim"


def test_placeholder_user_agent_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr(data_connectors, "_warned_placeholder", False)
    monkeypatch.setattr(settings, "nominatim_user_agent", "app/1.0 (contact: set-your-email-here)")
    with caplog.at_level(logging.WARNING):
        data_connectors.user_agent()
    assert "placeholder" in caplog.text
