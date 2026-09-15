"""query_pois: nwr + out center query, element parsing, offline gate, retry. HTTP mocked."""

from __future__ import annotations

import httpx
import pytest

import data_connectors
from common.net import DataUnavailable
from config.settings import settings
from data_connectors import overpass

_ELEMENTS = [
    {"type": "node", "id": 1, "lat": 25.01, "lon": 82.01, "tags": {"name": "Weekly Haat", "amenity": "marketplace"}},
    {"type": "way", "id": 2, "center": {"lat": 25.02, "lon": 82.02}, "tags": {"landuse": "retail"}},
    {"type": "relation", "id": 3, "tags": {"shop": "general"}},  # no coordinates -> skipped
]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    overpass.clear_cache()
    monkeypatch.setattr(data_connectors.time, "sleep", lambda s: None)
    yield
    overpass.clear_cache()


def _live(monkeypatch, responses):
    monkeypatch.setattr(settings, "data_mode", "live")
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        status, payload = responses.pop(0)
        return httpx.Response(status, json=payload, request=httpx.Request(method, url))

    monkeypatch.setattr(data_connectors.httpx, "request", fake_request)
    return calls


def test_offline_raises_data_unavailable():
    with pytest.raises(DataUnavailable):
        overpass.query_pois(25.0, 82.0, 1000, [("amenity", "marketplace")])


def test_build_query_uses_nwr_and_center():
    q = overpass.build_query(25.0, 82.0, 5000, [("amenity", "marketplace"), ("shop", "*")])
    assert 'nwr["amenity"="marketplace"](around:5000,25.000000,82.000000);' in q
    assert 'nwr["shop"](around:' in q
    assert "out center" in q


def test_live_parses_nodes_and_ways(monkeypatch):
    calls = _live(monkeypatch, [(200, {"elements": _ELEMENTS})])
    pois = overpass.query_pois(25.0, 82.0, 5000, [("amenity", "marketplace"), ("landuse", "retail")])
    assert len(pois) == 2
    assert pois[0] == {"name": "Weekly Haat", "lat": 25.01, "lon": 82.01, "tags": _ELEMENTS[0]["tags"],
                       "osm_type": "node", "type": "amenity=marketplace"}
    assert pois[1]["osm_type"] == "way" and pois[1]["lat"] == 25.02
    assert pois[1]["name"] is None
    assert calls[0]["headers"]["User-Agent"]
    # cached: a repeat query makes no further request
    overpass.query_pois(25.0, 82.0, 5000, [("landuse", "retail"), ("amenity", "marketplace")])
    assert len(calls) == 1


def test_poi_type_prefers_meaningful_tag_over_name():
    assert overpass.poi_type({"name": "Ram Tailors", "craft": "tailor"}) == "craft=tailor"
    assert overpass.poi_type({"name": "x"}) is None


def test_retry_once_then_raise(monkeypatch):
    calls = _live(monkeypatch, [(429, {}), (504, {}), (200, {"elements": []})])
    with pytest.raises(DataUnavailable):
        overpass.query_pois(25.0, 82.0, 1000, [("amenity", "marketplace")])
    assert len(calls) == 2
