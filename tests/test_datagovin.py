"""
Tests for the data.gov.in API client, covering pagination and the missing
API-key error path. Network calls are mocked via monkeypatch rather than
offline_fixture, to actually exercise the pagination logic.
"""
from __future__ import annotations

import pytest

from data_connectors import datagovin


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_resource_records_paginates(monkeypatch):
    pages = [
        {"status": "ok", "total": 5, "count": 2, "records": [{"id": 1}, {"id": 2}]},
        {"status": "ok", "total": 5, "count": 2, "records": [{"id": 3}, {"id": 4}]},
        {"status": "ok", "total": 5, "count": 1, "records": [{"id": 5}]},
    ]
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        page = pages[calls["n"]]
        calls["n"] += 1
        return _FakeResponse(page)

    monkeypatch.setattr(datagovin.requests, "get", fake_get)
    monkeypatch.setattr(datagovin, "settings", type("S", (), {"data_gov_in_api_key": "fake-key", "data_gov_in_base_url": "https://api.data.gov.in"})())

    records = datagovin.fetch_resource_records("some-resource-id", page_size=2, request_delay_seconds=0)

    assert [r["id"] for r in records] == [1, 2, 3, 4, 5]
    assert calls["n"] == 3


def test_fetch_resource_records_requires_api_key(monkeypatch):
    monkeypatch.setattr(datagovin, "settings", type("S", (), {"data_gov_in_api_key": None})())
    with pytest.raises(datagovin.DataGovInError):
        datagovin.fetch_resource_records("some-resource-id")


def test_fetch_resource_records_offline_fixture_bypasses_network():
    result = datagovin.fetch_resource_records("unused", offline_fixture=[{"id": 1}])
    assert result == [{"id": 1}]
