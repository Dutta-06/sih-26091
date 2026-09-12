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

Before any real use, run:
    python -m data_connectors.census --build-index
which pulls real population figures from the data.gov.in API
(data_connectors/datagovin.py) and joins them with real village centroid
coordinates from SHRUG (data_connectors/shrug.py) -- since raw Census PCA
data has no lat/lon of its own -- writing the result to CENSUS_DATA_PATH in
the same shape this module already expects. See IMPLEMENTATION_PLAN.md
Section 3 for why both pieces are needed and what each requires.
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
from data_connectors import datagovin, shrug

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


def build_index(
    resource_ids: Optional[dict[str, str]] = None,
    shrug_keys_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    *,
    datagovin_fixtures: Optional[dict[str, list[dict]]] = None,
    shrug_centroids: Optional[dict[str, tuple[float, float]]] = None,
) -> int:
    """
    Build a real CENSUS_DATA_PATH-shaped CSV by joining data.gov.in Census
    population records with SHRUG centroid coordinates on the shared
    village code.

    `datagovin_fixtures` / `shrug_centroids` let tests inject canned data
    instead of hitting the network or reading a real SHRUG file.

    Returns the number of villages written. Rows whose village code has no
    matching SHRUG centroid are skipped (and counted) rather than guessed at
    -- a population figure with no coordinate is useless to the radius query
    this module exists to answer.
    """
    resource_ids = resource_ids or settings.census_resource_ids
    if not resource_ids:
        raise ValueError(
            "No census_resource_ids configured. Look up the resource_id for "
            "each state/district's Village/Town-wise Primary Census "
            "Abstract dataset on data.gov.in and set CENSUS_RESOURCE_IDS."
        )

    centroids = shrug_centroids if shrug_centroids is not None else shrug.load_centroids(shrug_keys_path)

    rows: list[dict] = []
    skipped_no_centroid = 0

    for label, resource_id in resource_ids.items():
        fixture = datagovin_fixtures.get(label) if datagovin_fixtures else None
        records = datagovin.fetch_resource_records(resource_id, offline_fixture=fixture)

        for rec in records:
            village_id = rec.get(settings.census_api_village_code_field)
            centroid = centroids.get(str(village_id)) if village_id is not None else None
            if centroid is None:
                skipped_no_centroid += 1
                continue

            try:
                population = int(rec.get(settings.census_api_population_field, 0))
            except (TypeError, ValueError):
                logger.warning("Skipping record with unparseable population: %r", rec)
                continue

            rows.append(
                {
                    "village_name": rec.get(settings.census_api_village_name_field, "unknown"),
                    "district": rec.get(settings.census_api_district_field, label),
                    "state": rec.get(settings.census_api_state_field, label),
                    "lat": centroid[0],
                    "lon": centroid[1],
                    "population": population,
                }
            )

    if not rows:
        raise ValueError(
            "Join produced zero rows -- either no records came back from "
            "data.gov.in, or none of their village codes matched a SHRUG "
            "centroid. Check census_api_village_code_field against a real "
            "response and shrug_id_field against your SHRUG file."
        )

    out_path = Path(output_path or settings.census_data_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["village_name", "district", "state", "lat", "lon", "population"])
        writer.writeheader()
        writer.writerows(rows)

    logger.info(
        "Wrote %d villages to %s (%d records skipped: no SHRUG centroid match)",
        len(rows),
        out_path,
        skipped_no_centroid,
    )

    global _index
    _index = None  # force reload on next population_within_radius() call

    return len(rows)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build or refresh the census population+centroid index")
    parser.add_argument(
        "--build-index",
        action="store_true",
        help="Fetch real Census data from data.gov.in, join with SHRUG centroids, write CENSUS_DATA_PATH",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.build_index:
        n = build_index()
        print(f"Wrote {n} villages to {settings.census_data_path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
