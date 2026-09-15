"""Udyam Registration open dataset connector (TECHNICAL_SETUP.md Section 8.4).

Udyam Registration has no public live-query API; the ministry publishes periodic
bulk extracts (data.gov.in / msme.gov.in). A deployer downloads one and points
``UDYAM_DATASET_PATH`` at the CSV. Without it this connector raises
:class:`DataUnavailable` -- it never invents a registration count.

Column names are matched case-insensitively against common spellings:
NIC code (``NIC_Code``/``nic_code``/``ncs_code``/``nic_5_digit``), ``District``,
``State``, optional ``EnterpriseName`` and ``Latitude``/``Longitude``.
NIC matching is a prefix match on the catalog's 4-digit class (a 5-digit
sub-class ``01411`` matches class ``0141``; a 2-digit division ``01`` matches too).

    python -m data_connectors.udyam --summary
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from common.net import DataUnavailable
from common.reference import haversine_km
from config.settings import settings

_COLUMNS = {
    "nic": ("nic_code", "ncs_code", "nic_5_digit", "nic_4_digit", "nic", "nic_2008_code"),
    "district": ("district", "district_name"),
    "state": ("state", "state_name"),
    "name": ("enterprisename", "enterprise_name", "name_of_enterprise", "name"),
    "lat": ("latitude", "lat"),
    "lon": ("longitude", "lon", "lng"),
}


@dataclass
class UdyamMatches:
    """Registered enterprises matching an activity's NIC class."""

    dataset: str
    district_count: Optional[int] = None  # same NIC class, same district
    state_count: Optional[int] = None  # same NIC class, same state
    has_coordinates: bool = False
    nearby: list[dict] = field(default_factory=list)  # {name, lat, lon, distance_km} within radius


def nic_matches(code: str, nic_class: str) -> bool:
    digits = re.sub(r"\D", "", code or "")
    target = re.sub(r"\D", "", nic_class or "")
    n = min(4, len(digits), len(target))
    return n >= 2 and digits[:n] == target[:n]


def _norm(value: Optional[str]) -> str:
    return " ".join((value or "").lower().replace("-", " ").split())


def _resolve(header: list[str]) -> dict[str, Optional[str]]:
    lowered = {h.strip().lower(): h for h in header}
    return {key: next((lowered[c] for c in cands if c in lowered), None) for key, cands in _COLUMNS.items()}


def _float(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def find_enterprises(
    nic_class: str,
    district: Optional[str],
    state: Optional[str],
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_km: Optional[float] = None,
) -> UdyamMatches:
    """Scan the configured extract; raises ``DataUnavailable`` if it cannot be used."""
    path = settings.udyam_dataset_path
    if not path:
        raise DataUnavailable("udyam: UDYAM_DATASET_PATH not configured (no public live-query API exists)")
    path = Path(path)
    if not path.exists():
        raise DataUnavailable(f"udyam: dataset file not found at {path}")
    if not nic_class:
        raise DataUnavailable("udyam: activity has no NIC class to filter on")

    try:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            cols = _resolve(reader.fieldnames or [])
            if not cols["nic"] or not (cols["district"] or cols["state"]):
                raise DataUnavailable("udyam: dataset lacks a recognizable NIC code and District/State column")
            result = UdyamMatches(
                dataset=path.name,
                district_count=0 if district and cols["district"] else None,
                state_count=0 if state and cols["state"] else None,
                has_coordinates=bool(cols["lat"] and cols["lon"] and lat is not None and lon is not None and radius_km),
            )
            for row in reader:
                if not nic_matches(row.get(cols["nic"], ""), nic_class):
                    continue
                if result.state_count is not None and _norm(row.get(cols["state"])) == _norm(state):
                    result.state_count += 1
                if result.district_count is not None and _norm(row.get(cols["district"])) == _norm(district):
                    result.district_count += 1
                if result.has_coordinates:
                    plat, plon = _float(row.get(cols["lat"])), _float(row.get(cols["lon"]))
                    if plat is None or plon is None:
                        continue
                    dist = haversine_km(lat, lon, plat, plon)
                    if dist <= radius_km:
                        name = (row.get(cols["name"]) or "").strip() if cols["name"] else ""
                        result.nearby.append({"name": name or None, "lat": plat, "lon": plon, "distance_km": round(dist, 2)})
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        raise DataUnavailable(f"udyam: failed reading dataset ({exc})") from exc
    result.nearby.sort(key=lambda r: r["distance_km"])
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check the configured Udyam extract")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--nic", default="0141")
    parser.add_argument("--district")
    parser.add_argument("--state")
    args = parser.parse_args()
    print(find_enterprises(args.nic, args.district, args.state))
