"""Population within a radius from Census 2011 village points (TECHNICAL_SETUP §8.2).

Tech: KD-tree (scipy ``cKDTree`` on unit-sphere xyz) over village centroids in
``settings.census_data_path`` (columns ``village_code, village_name, district,
state, lat, lon, population, is_sample``).

* The shipped ``data/census/sample_villages.csv`` is a SAMPLE fixture with
  synthetic place names; rows with ``is_sample=1`` are always "estimated".
* A table built with ``python -m data_connectors.census --build-index``
  (data.gov.in Census PCA records joined with SHRUG village centroids on the
  normalised village code) is real open data, though dated 2011.
* A point the table does not cover never becomes population 0: it falls back
  to π r² × the state's Census 2011 density (``common.reference``), labeled
  estimated, or ``None`` if the state is unknown.
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.spatial import cKDTree

from common.reference import lookup_state
from config.settings import settings
from data_connectors import datagovin, shrug
from orchestrator.state import Confidence

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0088
DATA_YEAR = 2011
FIELDS = ["village_code", "village_name", "district", "state", "lat", "lon", "population", "is_sample"]


def normalise_code(code: object) -> Optional[str]:
    """'000123', '123', 123 and '123.0' all map to '123'; blank -> None."""
    text = str(code).strip() if code is not None else ""
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    return (text.lstrip("0") or "0") if text.isdigit() else text


@dataclass
class _Index:
    rows: list[dict]
    tree: Optional[cKDTree]


_index: Optional[_Index] = None
_index_path: Optional[str] = None


def _xyz(lat, lon) -> np.ndarray:
    lat, lon = np.radians(lat), np.radians(lon)
    return np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])


def _get_index() -> _Index:
    global _index, _index_path
    path = Path(settings.census_data_path)
    if _index is not None and _index_path == str(path):
        return _index
    rows: list[dict] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    r["lat"], r["lon"], r["population"] = float(r["lat"]), float(r["lon"]), int(float(r["population"]))
                except (KeyError, TypeError, ValueError):
                    continue
                r["is_sample"] = str(r.get("is_sample", "")).strip().lower() in {"1", "true", "yes"}
                rows.append(r)
    else:
        logger.warning("Census table not found at %s", path)
    tree = cKDTree(_xyz(np.array([r["lat"] for r in rows]), np.array([r["lon"] for r in rows]))) if rows else None
    _index, _index_path = _Index(rows, tree), str(path)
    return _index


def reset_index() -> None:
    global _index, _index_path
    _index, _index_path = None, None


def villages_within(lat: float, lon: float, radius_km: float) -> list[dict]:
    idx = _get_index()
    if idx.tree is None:
        return []
    chord = 2 * math.sin(radius_km / (2 * EARTH_RADIUS_KM))  # unit-sphere chord for the great-circle radius
    return [idx.rows[i] for i in idx.tree.query_ball_point(_xyz(lat, lon)[0], r=chord)]


def state_density_estimate(radius_km: float, state: Optional[str]) -> tuple[Optional[int], Confidence, str, list[str]]:
    hit = lookup_state(state)
    if not hit:
        return None, "estimated", "population unavailable", [
            f"No Census village data covers this point and the state ({state or 'unknown'}) is not in the "
            "state reference table, so population within the radius is unknown."
        ]
    name, info = hit
    population = int(round(math.pi * radius_km ** 2 * info["density"]))
    return population, "estimated", (
        f"π × {radius_km:g}² km² × {info['density']} persons/km² (Census 2011 state density, {name})"
    ), [
        "Population is a coarse state-density estimate: it includes urban population and ignores local "
        "settlement patterns, so it can overstate a rural catchment considerably."
    ]


def population_within_radius(lat: float, lon: float, radius_km: float,
                             state: Optional[str]) -> tuple[Optional[int], Confidence, str, list[str]]:
    """(population, confidence, basis text, limitations)."""
    matches = villages_within(lat, lon, radius_km) if lat is not None and lon is not None else []
    if not matches:
        return state_density_estimate(radius_km, state)
    total = sum(r["population"] for r in matches)
    sample = any(r["is_sample"] for r in matches)
    limitations = [f"Census {DATA_YEAR} figures are dated; current population is likely different."]
    if sample:
        limitations.append("Villages come from the bundled SAMPLE census fixture (synthetic names and "
                            "numbers); build a real table with `python -m data_connectors.census --build-index`.")
    limitations.append("Only villages present in the loaded census table are counted; towns and villages "
                       "missing from the table are excluded.")
    basis = (f"Sum of Census {DATA_YEAR} population of {len(matches)} village(s) within {radius_km:g} km"
             f"{' (sample fixture rows)' if sample else ''}")
    return total, ("estimated" if sample else "real"), basis, limitations


def build_index(
    resource_ids: Optional[dict[str, str]] = None,
    shrug_keys_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    *,
    datagovin_fixtures: Optional[dict[str, list[dict]]] = None,
    shrug_centroids: Optional[dict[str, tuple[float, float]]] = None,
) -> int:
    """Join data.gov.in Census PCA records with SHRUG centroids on the normalised village code.

    Records without a centroid are skipped (never guessed). Returns rows written.
    """
    resource_ids = resource_ids if resource_ids is not None else settings.census_resource_ids
    if not resource_ids:
        raise ValueError("No census_resource_ids configured (CENSUS_RESOURCE_IDS): set the data.gov.in resource_id "
                         "of each state's Village/Town-wise Primary Census Abstract.")
    raw = shrug_centroids if shrug_centroids is not None else shrug.load_centroids(shrug_keys_path)
    centroids = {normalise_code(k): v for k, v in raw.items()}

    rows, skipped = [], 0
    for label, resource_id in resource_ids.items():
        fixture = datagovin_fixtures.get(label) if datagovin_fixtures else None
        for rec in datagovin.fetch_resource_records(resource_id, offline_fixture=fixture):
            code = normalise_code(rec.get(settings.census_api_village_code_field))
            centroid = centroids.get(code)
            if centroid is None:
                skipped += 1
                continue
            try:
                population = int(float(rec.get(settings.census_api_population_field)))
            except (TypeError, ValueError):
                logger.warning("Skipping record with unparseable population: %r", rec)
                continue
            rows.append({
                "village_code": code,
                "village_name": rec.get(settings.census_api_village_name_field, ""),
                "district": rec.get(settings.census_api_district_field, ""),
                "state": rec.get(settings.census_api_state_field, ""),
                "lat": centroid[0], "lon": centroid[1], "population": population, "is_sample": 0,
            })
    if not rows:
        raise ValueError("Join produced zero rows: check the village-code fields of data.gov.in and SHRUG.")

    out_path = Path(output_path or settings.census_data_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote %d villages to %s (%d skipped: no SHRUG centroid)", len(rows), out_path, skipped)
    reset_index()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the census population + centroid table")
    parser.add_argument("--build-index", action="store_true",
                        help="Fetch Census PCA from data.gov.in (DATA_MODE=live), join SHRUG centroids, write CENSUS_DATA_PATH")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if not args.build_index:
        parser.print_help()
        return
    print(f"Wrote {build_index()} villages to {settings.census_data_path}")


if __name__ == "__main__":
    main()
