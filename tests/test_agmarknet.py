import httpx
import pytest

from common.net import DataUnavailable
from config.settings import settings
from data_connectors import agmarknet

RECORDS = [
    {"arrival_date": "03/01/2026", "modal_price": "2400"},
    {"arrival_date": "20/01/2026", "modal_price": "2600"},
    {"arrival_date": "05/02/2026", "modal_price": "2500"},
    {"arrival_date": "bad", "modal_price": "2500"},
    {"arrival_date": "07/02/2026", "modal_price": "NR"},
]


def test_parse_records_monthly_median():
    series = agmarknet.parse_records(RECORDS)
    assert [(p.month, p.modal_price) for p in series] == [("2026-01", 2500.0), ("2026-02", 2500.0)]
    assert len(agmarknet.parse_records(RECORDS, months=1)) == 1


def test_offline_raises():
    with pytest.raises(DataUnavailable):
        agmarknet.fetch_monthly_prices("Wheat", "Uttar Pradesh", None)


def test_live_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "data_mode", "live")
    monkeypatch.setattr(settings, "data_gov_in_api_key", None)
    with pytest.raises(DataUnavailable):
        agmarknet.fetch_monthly_prices("Wheat", "Uttar Pradesh", None)


def test_live_parses_fake_response_and_falls_back_to_state(monkeypatch):
    monkeypatch.setattr(settings, "data_mode", "live")
    monkeypatch.setattr(settings, "data_gov_in_api_key", "k")
    seen = []

    def fake_get(url, params=None, timeout=None):
        seen.append(dict(params, url=url))
        body = {"records": [] if "filters[district]" in params else RECORDS, "total": 5}
        return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(agmarknet.httpx, "get", fake_get)
    series = agmarknet.fetch_monthly_prices("Wheat", "Uttar Pradesh", "Bhadohi")
    assert len(series) == 2 and len(seen) == 2
    assert seen[0]["filters[district]"] == "Bhadohi" and "filters[district]" not in seen[1]
    assert seen[0]["url"].endswith(f"/resource/{settings.commodity_price_resource_id}")


def test_live_http_error_is_data_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "data_mode", "live")
    monkeypatch.setattr(settings, "data_gov_in_api_key", "k")
    monkeypatch.setattr(agmarknet.httpx, "get",
                        lambda url, **k: httpx.Response(500, request=httpx.Request("GET", url)))
    with pytest.raises(DataUnavailable):
        agmarknet.fetch_monthly_prices("Wheat", "Uttar Pradesh", None)
