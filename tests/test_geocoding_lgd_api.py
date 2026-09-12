"""
Tests for the (unverified-shape, see geocoding.py docstring) NAPIX LGD API
disambiguation path: it should be preferred over the local CSV table when
enabled and configured, and disambiguation should still fall back to the
local table when the API call fails or returns nothing.
"""
from __future__ import annotations

from data_connectors import geocoding

_TWO_CANDIDATES = [
    {
        "display_name": "Sample Village A, Sample District, Sample State, India",
        "lat": "20.0005",
        "lon": "78.0005",
    },
    {
        "display_name": "Sample Village A, Other District, Other State, India",
        "lat": "25.0000",
        "lon": "85.0000",
    },
]

_LGD_API_FIXTURE = {
    "district": "Sample District",
    "state": "Sample State",
    "lgd_code": "API-999001",
}


def test_disambiguation_prefers_live_api_when_enabled(monkeypatch):
    monkeypatch.setattr(geocoding.settings, "lgd_api_enabled", True)
    monkeypatch.setattr(geocoding.settings, "lgd_api_key", "fake-subscriber-key")

    result = geocoding.geocode_location(
        "Sample Village A",
        offline_fixture=_TWO_CANDIDATES,
        lgd_api_fixture=_LGD_API_FIXTURE,
    )

    assert result.lgd_code == "API-999001"
    assert result.source_confidence == "real"
    assert result.lat == 20.0005  # the Sample District/State candidate, not Other


def test_disambiguation_falls_back_to_local_table_when_api_disabled(monkeypatch):
    monkeypatch.setattr(geocoding.settings, "lgd_api_enabled", False)

    result = geocoding.geocode_location("Sample Village A", offline_fixture=_TWO_CANDIDATES)

    # Local sample_lgd_codes.csv has a "Sample Village A" / Sample District /
    # Sample State row, so the local-table path should still resolve it.
    assert result.lgd_code == "999001"
    assert result.source_confidence == "real"


def test_disambiguation_falls_back_when_api_returns_nothing(monkeypatch):
    monkeypatch.setattr(geocoding.settings, "lgd_api_enabled", True)
    monkeypatch.setattr(geocoding.settings, "lgd_api_key", "fake-subscriber-key")

    result = geocoding.geocode_location(
        "Sample Village A",
        offline_fixture=_TWO_CANDIDATES,
        lgd_api_fixture=None,
    )

    # API fixture of None simulates "API reachable but found nothing" --
    # _lookup_lgd_via_api returns it as-is (None), so disambiguation should
    # fall through to the local CSV table rather than erroring.
    assert result.lgd_code == "999001"
