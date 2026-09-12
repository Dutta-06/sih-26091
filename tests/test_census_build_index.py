"""
Tests for census.build_index(): the join between mocked data.gov.in Census
records and SHRUG centroids, and the resulting index being immediately
queryable.
"""
from __future__ import annotations

import csv

import pytest

from data_connectors import census

_FAKE_CENSUS_RECORDS = {
    "sample_state": [
        {
            "village_code": "111",
            "village_name": "Built Village One",
            "district_name": "Built District",
            "state_name": "Built State",
            "tot_p": "3000",
        },
        {
            "village_code": "222",
            "village_name": "Built Village Two",
            "district_name": "Built District",
            "state_name": "Built State",
            "tot_p": "1500",
        },
        {
            # No matching SHRUG centroid below -- should be skipped, not guessed at.
            "village_code": "999",
            "village_name": "No Centroid Village",
            "district_name": "Built District",
            "state_name": "Built State",
            "tot_p": "500",
        },
    ]
}

_FAKE_CENTROIDS = {
    "111": (21.0000, 79.0000),
    "222": (21.0100, 79.0050),
}


def test_build_index_joins_and_writes_csv(tmp_path, monkeypatch):
    output_path = tmp_path / "built_villages.csv"

    n = census.build_index(
        resource_ids={"sample_state": "fake-resource-id"},
        output_path=output_path,
        datagovin_fixtures=_FAKE_CENSUS_RECORDS,
        shrug_centroids=_FAKE_CENTROIDS,
    )

    assert n == 2  # the no-centroid-match row is skipped

    with output_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    names = {r["village_name"] for r in rows}
    assert names == {"Built Village One", "Built Village Two"}
    assert all(r["population"] for r in rows)
    assert all(r["lat"] and r["lon"] for r in rows)


def test_build_index_raises_without_resource_ids():
    with pytest.raises(ValueError):
        census.build_index(resource_ids={}, shrug_centroids=_FAKE_CENTROIDS)


def test_build_index_output_is_queryable(tmp_path):
    output_path = tmp_path / "built_villages.csv"
    census.build_index(
        resource_ids={"sample_state": "fake-resource-id"},
        output_path=output_path,
        datagovin_fixtures=_FAKE_CENSUS_RECORDS,
        shrug_centroids=_FAKE_CENTROIDS,
    )

    # build_index() resets the module-level index cache, so the next
    # population_within_radius() call picks up the freshly-built file.
    import config.settings as settings_module

    settings_module.settings.census_data_path = output_path
    result = census.population_within_radius(21.005, 79.002, radius_km=5.0)

    assert result.population_within_radius == 4500  # 3000 + 1500
    assert result.villages_counted == 2
    assert result.is_sample_data is False
