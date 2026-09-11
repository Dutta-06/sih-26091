"""
Geographic utilities for the mock database layer.

Scope note: this module is deliberately limited to straight-line distance
math used for *database-level* proximity filtering (e.g. "businesses
within 10 km of point X"). It is NOT a routing system. Actual road
distance / travel time continues to be handled by the existing
RoutingAdapter (src/adapters/routing_adapter.py, OSRM) once the mock/real
adapter layer is wired in — that is out of scope for this milestone.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """Returns (lat_min, lat_max, lon_min, lon_max) that fully contains a
    circle of radius_km around (lat, lon). Used as a cheap SQL-level
    prefilter before the exact Haversine check, so radius queries don't
    have to Haversine-scan an entire table.

    Longitude degrees shrink with latitude (~cos(lat)); this widens the
    box near the poles and narrows it near the equator, which is correct
    behavior for a conservative (over-inclusive) prefilter.
    """
    lat_delta = radius_km / 111.32  # ~km per degree latitude, roughly constant
    cos_lat = max(math.cos(math.radians(lat)), 0.01)  # avoid div-by-zero near poles
    lon_delta = radius_km / (111.32 * cos_lat)

    return (lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta)
