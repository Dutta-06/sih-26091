"""
Census 2011 village-level population lookup (TECHNICAL_SETUP.md Section 8.2).

Tech: spatial nearest-neighbor query (KD-tree) over the Census 2011
population grid, per design doc Section 5.3.

DATA CAVEAT (see IMPLEMENTATION_PLAN.md Section 3): the file shipped at
data/census/sample_villages.csv is a small, clearly-labeled SAMPLE fixture
with synthetic place names, for local testing only -- it is NOT real Census
data. Every output of this module is therefore always tagged "estimated",
both because Census 2011 is 15 years stale and, while sample data is in use,
because the underlying numbers are fabricated for testing.

Before any real use: download the actual village-level Primary Census
Abstract from data.gov.in and point CENSUS_DATA_PATH at it (same three
columns: lat, lon, population, plus village_name/district/state), per
TECHNICAL_SETUP.md Section 8.2.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.spatial import cKDTree

from config.settings import settings

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0


@dataclass
class PopulationEstimate:
    population_within_radius: int
    villages_counted: int
    data_year: int
    source_confidence: str  # always "estimated" -- see module docstring
    is_sample_data: bool


class _CensusIndex:
    def __init__(self, csv_path: Path):
        self.villages: list[dict] = []
        self.is_sample_data = "sample" in csv_path.name.lower()
        self._tree: Optional[cKDTree] = None
        self._load(csv_path)

    def _load(self, csv_path: Path) -> None:
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Census data file not found at {csv_path}. "
                f"See TECHNICAL_SETUP.md Section 8.2 to provision it."
            )
        with csv_path.open(newline="", encoding="utf-8") as f:
            self.villages = list(csv.DictReader(f))
        if not self.villages:
            raise ValueError(f"Census data file at {csv_path} has no rows.")

        lat = np.radians(np.array([float(v["lat"]) for v in self.villages]))
        lon = np.radians(np.array([float(v["lon"]) for v in self.villages]))
        xyz = np.column_stack(
            [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
        )
        self._tree = cKDTree(xyz)

    def query_radius(self, lat: float, lon: float, radius_km: float) -> list[dict]:
        lat_r, lon_r = np.radians(lat), np.radians(lon)
        point = np.array(
            [np.cos(lat_r) * np.cos(lon_r), np.cos(lat_r) * np.sin(lon_r), np.sin(lat_r)]
        )
        # Chord-length equivalent of the requested great-circle radius, so a
        # KD-tree built on unit-sphere xyz coordinates can be queried directly.
        chord = 2 * EARTH_RADIUS_KM * np.sin(radius_km / (2 * EARTH_RADIUS_KM))
        idxs = self._tree.query_ball_point(point, r=chord)
        return [self.villages[i] for i in idxs]


_index: Optional[_CensusIndex] = None


def _get_index() -> _CensusIndex:
    global _index
    if _index is None:
        _index = _CensusIndex(Path(settings.census_data_path))
    return _index


def population_within_radius(lat: float, lon: float, radius_km: float) -> PopulationEstimate:
    idx = _get_index()
    matches = idx.query_radius(lat, lon, radius_km)
    total_population = sum(int(v["population"]) for v in matches)
    return PopulationEstimate(
        population_within_radius=total_population,
        villages_counted=len(matches),
        data_year=2011,
        source_confidence="estimated",
        is_sample_data=idx.is_sample_data,
    )
