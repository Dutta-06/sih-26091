"""Census radius population, state-density fallback, build-index join, data.gov.in and SHRUG loaders."""

from __future__ import annotations

import csv
import math

import httpx
import pytest

import data_connectors
from common.net import DataUnavailable
from config.settings import settings
from data_connectors import census, datagovin, shrug

_RECORDS = {"state": [
    {"village_code": "000111", "village_name": "Built One", "district_name": "D", "state_name": "S", "tot_p": "3000"},
    {"village_code": "222", "village_name": "Built Two", "district_name": "D", "state_name": "S", "tot_p": "1500"},
    {"village_code": "999", "village_name": "No Centroid", "district_name": "D", "state_name": "S", "tot_p": "500"},
]}
_CENTROIDS = {"111": (21.0, 79.0), "0222": (21.01, 79.005)}


@pytest.fixture(autouse=True)
def _reset():
    census.reset_index()
    yield
    census.reset_index()


def test_sample_rows_sum_and_are_estimated():
    population, confidence, basis, limitations = census.population_within_radius(20.0, 78.0, 5.0, None)
    assert population == 3200 + 1800 + 2600 + 2900  # A, B, C and Alpha are within 5 km
    assert confidence == "estimated"
    assert "sample" in basis
    assert any("SAMPLE" in l for l in limitations)


def test_uncovered_point_uses_state_density_not_zero():
    population, confidence, basis, limitations = census.population_within_radius(25.39, 82.57, 10.0, "Uttar Pradesh")
    assert population == round(math.pi * 100 * 829)
    assert confidence == "estimated"
    assert "density" in basis
    assert any("urban" in l for l in limitations)


def test_uncovered_point_with_unknown_state_is_none():
    population, confidence, _, limitations = census.population_within_radius(25.39, 82.57, 10.0, None)
    assert population is None
    assert confidence == "estimated"
    assert limitations


def test_normalise_code():
    assert census.normalise_code("000123") == census.normalise_code(123) == census.normalise_code("123.0") == "123"
    assert census.normalise_code("") is None
    assert census.normalise_code("AB01") == "AB01"


def test_build_index_joins_on_normalised_codes_and_is_real(tmp_path, monkeypatch):
    out = tmp_path / "villages.csv"
    n = census.build_index(resource_ids={"state": "rid"}, output_path=out,
                           datagovin_fixtures=_RECORDS, shrug_centroids=_CENTROIDS)
    assert n == 2
    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert {r["village_code"] for r in rows} == {"111", "222"}
    assert all(r["is_sample"] == "0" for r in rows)

    monkeypatch.setattr(settings, "census_data_path", out)
    population, confidence, _, _ = census.population_within_radius(21.005, 79.002, 5.0, None)
    assert population == 4500
    assert confidence == "real"


def test_build_index_requires_resource_ids():
    with pytest.raises(ValueError):
        census.build_index(resource_ids={}, shrug_centroids=_CENTROIDS)


def test_datagovin_offline_raises_data_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "data_gov_in_api_key", "key")
    with pytest.raises(DataUnavailable):
        datagovin.fetch_resource_records("rid")


def test_datagovin_paginates_in_live_mode(monkeypatch):
    monkeypatch.setattr(settings, "data_mode", "live")
    monkeypatch.setattr(settings, "data_gov_in_api_key", "key")
    pages = [{"status": "ok", "total": 3, "records": [{"id": 1}, {"id": 2}]},
             {"status": "ok", "total": 3, "records": [{"id": 3}]}]
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(kwargs["params"]["offset"])
        return httpx.Response(200, json=pages[len(calls) - 1], request=httpx.Request(method, url))

    monkeypatch.setattr(data_connectors.httpx, "request", fake_request)
    records = datagovin.fetch_resource_records("rid", page_size=2, request_delay_seconds=0)
    assert [r["id"] for r in records] == [1, 2, 3]
    assert calls == [0, 2]


def test_datagovin_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "data_gov_in_api_key", None)
    with pytest.raises(datagovin.DataGovInError):
        datagovin.fetch_resource_records("rid")


def test_shrug_load_centroids(tmp_path):
    path = tmp_path / "shrug.csv"
    path.write_text("pc11_village_id,latitude,longitude\n123456,20.0,78.0\n", encoding="utf-8")
    assert shrug.load_centroids(path) == {"123456": (20.0, 78.0)}
    with pytest.raises(FileNotFoundError):
        shrug.load_centroids(tmp_path / "missing.csv")
