"""
Tests for the SHRUG centroid loader against a small local CSV fixture
(not real SHRUG data -- see data_connectors/shrug.py for why this project
can't auto-download real SHRUG files).
"""
from __future__ import annotations

import pytest

from data_connectors import shrug


def test_load_centroids(tmp_path):
    csv_path = tmp_path / "shrug_keys_sample.csv"
    csv_path.write_text(
        "pc11_village_id,latitude,longitude\n"
        "123456,20.0000,78.0000\n"
        "789012,20.0500,78.0500\n"
    )

    centroids = shrug.load_centroids(csv_path)

    assert centroids == {
        "123456": (20.0000, 78.0000),
        "789012": (20.0500, 78.0500),
    }


def test_load_centroids_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        shrug.load_centroids(tmp_path / "does_not_exist.csv")


def test_load_centroids_requires_configured_path():
    with pytest.raises(ValueError):
        shrug.load_centroids(None)
