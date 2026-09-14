"""OpenStreetMap Overpass connector for nearby points of interest (TECHNICAL_SETUP §8.3).

Queries nodes, ways and relations (``nwr`` + ``out center``) so that markets
mapped as areas are found too. Results are cached per process; heavy use
should point ``OVERPASS_BASE_URL`` at a self-hosted instance (OSMF API policy).
Rural OSM coverage is sparse: an empty result means "not mapped", not
"does not exist".
"""

from __future__ import annotations

from typing import Any, Optional

from common.net import DataUnavailable, require_live
from config.settings import settings
from data_connectors import http_request, user_agent

# Tag keys that describe what a feature *is*, in priority order (never ``name``).
TYPE_KEYS = ("amenity", "shop", "craft", "office", "public_transport", "highway", "railway",
             "man_made", "industrial", "landuse", "building")

_cache: dict[tuple, list[dict[str, Any]]] = {}


def poi_type(tags: dict[str, str]) -> Optional[str]:
    for key in TYPE_KEYS:
        if tags.get(key):
            return f"{key}={tags[key]}"
    return None


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_query(lat: float, lon: float, radius_m: int, tags: list[tuple[str, str]]) -> str:
    around = f"(around:{int(radius_m)},{lat:.6f},{lon:.6f})"
    clauses = []
    for key, value in tags:
        selector = f'["{_escape(key)}"]' if value in ("", "*", None) else f'["{_escape(key)}"="{_escape(value)}"]'
        clauses.append(f"nwr{selector}{around};")
    return f"[out:json][timeout:25];({''.join(clauses)});out center tags;"


def query_pois(lat: float, lon: float, radius_m: int, tags: list[tuple[str, str]]) -> list[dict]:
    """POIs matching any (key, value) tag; value "" or "*" matches any value.

    Each dict: ``{name, lat, lon, tags, osm_type, type}`` (``name`` is None when
    the feature is unnamed in OSM). Raises ``DataUnavailable``.
    """
    if not tags:
        return []
    key = (round(lat, 4), round(lon, 4), int(radius_m), tuple(sorted((k, v or "") for k, v in tags)), settings.overpass_base_url)
    if key not in _cache:
        require_live("overpass")
        resp = http_request(
            "overpass", "POST", f"{settings.overpass_base_url.rstrip('/')}/interpreter",
            data={"data": build_query(lat, lon, radius_m, tags)},
            headers={"User-Agent": user_agent()},
        )
        try:
            elements = resp.json().get("elements", [])
        except ValueError as exc:
            raise DataUnavailable(f"overpass: invalid JSON ({exc})") from exc
        pois = []
        for el in elements:
            center = el.get("center") or {}
            el_lat, el_lon = el.get("lat", center.get("lat")), el.get("lon", center.get("lon"))
            if el_lat is None or el_lon is None:
                continue
            el_tags = el.get("tags") or {}
            pois.append({"name": el_tags.get("name") or el_tags.get("name:en"), "lat": float(el_lat),
                         "lon": float(el_lon), "tags": el_tags, "osm_type": el.get("type", "node"),
                         "type": poi_type(el_tags)})
        _cache[key] = pois
    return [dict(p) for p in _cache[key]]


def clear_cache() -> None:
    _cache.clear()
