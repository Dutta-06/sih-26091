"""OSRM road-distance connector (TECHNICAL_SETUP.md Section 8.5).

Queries a self-hosted (or configured) OSRM ``/route/v1/driving`` endpoint for the
shortest driving route between two points. Raises ``DataUnavailable`` in offline
mode or on any failure; callers fall back to a labeled estimate.
"""

from __future__ import annotations

import httpx

from common.net import DataUnavailable, require_live
from config.settings import settings


def road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    require_live("osrm")
    url = f"{settings.osrm_base_url.rstrip('/')}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    try:
        response = httpx.get(url, params={"overview": "false"}, timeout=settings.http_timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise DataUnavailable(f"osrm: request failed ({exc})") from exc
    routes = data.get("routes") or []
    if data.get("code") not in (None, "Ok") or not routes or routes[0].get("distance") is None:
        raise DataUnavailable(f"osrm: no route ({data.get('code')})")
    return float(routes[0]["distance"]) / 1000.0
