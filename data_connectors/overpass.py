"""
OSM Overpass API connector for nearby markets / points of interest
(TECHNICAL_SETUP.md Section 8.3).

Feasibility note (IMPLEMENTATION_PLAN.md Section 3): the public Overpass
endpoint has no hard published numeric rate limit, but the OSM Foundation's
API usage policy discourages heavy/production use of the public instance
and steers heavy users toward self-hosting
(https://operations.osmfoundation.org/policies/api/). This module caches
every query result in-process; self-host Overpass via Docker and point
OVERPASS_BASE_URL at it for real production volume.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

from config.settings import settings

_cache: dict[str, list[dict]] = {}

_DEFAULT_TAGS = [
    "shop",
    "amenity=marketplace",
    "amenity=bank",
    "amenity=fuel",
]


@dataclass
class POIResult:
    name: str
    poi_type: str
    lat: float
    lon: float


def _build_query(lat: float, lon: float, radius_m: int, tags: list[str]) -> str:
    clauses = []
    for tag in tags:
        if "=" in tag:
            k, v = tag.split("=", 1)
            clauses.append(f'node["{k}"="{v}"](around:{radius_m},{lat},{lon});')
        else:
            clauses.append(f'node["{tag}"](around:{radius_m},{lat},{lon});')
    body = "\n".join(clauses)
    return f"[out:json][timeout:25];({body});out center;"


def query_pois(
    lat: float,
    lon: float,
    radius_m: int,
    tags: Optional[list[str]] = None,
    *,
    offline_fixture: Optional[list[dict]] = None,
) -> list[POIResult]:
    """Query nearby points of interest within `radius_m` meters of (lat, lon).

    `offline_fixture` injects canned Overpass "elements" instead of hitting
    the network -- used by tests.
    """
    tags = tags or _DEFAULT_TAGS
    cache_key = f"{lat:.4f}:{lon:.4f}:{radius_m}:{','.join(sorted(tags))}"

    if cache_key in _cache:
        elements = _cache[cache_key]
    elif offline_fixture is not None:
        elements = offline_fixture
        _cache[cache_key] = elements
    else:
        query = _build_query(lat, lon, radius_m, tags)
        resp = requests.post(
            f"{settings.overpass_base_url}/interpreter",
            data={"data": query},
            timeout=30,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        _cache[cache_key] = elements

    results = []
    for el in elements:
        tags_dict = el.get("tags", {})
        name = tags_dict.get("name", "unnamed")
        poi_type = next(iter(tags_dict.keys()), "unknown")
        results.append(POIResult(name=name, poi_type=poi_type, lat=el.get("lat"), lon=el.get("lon")))
    return results


def poi_density_per_1000(poi_count: int, population: int) -> float:
    """POIs per 1,000 residents -- used by the Opportunity Agent as a
    saturation proxy in the absence of a dedicated Competitor Agent (see
    IMPLEMENTATION_PLAN.md Section 4)."""
    if population <= 0:
        return 0.0
    return (poi_count / population) * 1000
