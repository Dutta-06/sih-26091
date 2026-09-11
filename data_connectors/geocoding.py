"""
Geocoding + LGD disambiguation connector (TECHNICAL_SETUP.md Section 8.1).

Tech: OpenStreetMap Nominatim for geocoding, Local Government Directory
(LGD) code tables for disambiguating repeated place names.

Feasibility note (from IMPLEMENTATION_PLAN.md Section 3): the public
Nominatim endpoint enforces a hard 1 request/second ceiling and its usage
policy discourages bulk/scripted use -- this module rate-limits itself,
caches every result in-process, and never issues concurrent requests, per
that policy: https://operations.osmfoundation.org/policies/nominatim/
Self-hosting Nominatim is the documented follow-up for real production
volume; swap NOMINATIM_BASE_URL to point at a self-hosted instance when
that's ready.
"""
from __future__ import annotations

import csv
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

_last_request_time = 0.0
_cache: dict[str, "GeocodeResult"] = {}
_LGD_TABLE: Optional[list[dict]] = None


@dataclass
class GeocodeResult:
    matched_name: str
    lat: float
    lon: float
    lgd_code: Optional[str]
    source_confidence: str  # "real" if disambiguated via LGD, else "estimated"
    raw_candidates: int


def _rate_limit() -> None:
    """Enforce Nominatim's documented 1 request/second ceiling."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < settings.nominatim_min_interval_seconds:
        time.sleep(settings.nominatim_min_interval_seconds - elapsed)
    _last_request_time = time.monotonic()


def _load_lgd_table() -> list[dict]:
    path = Path(settings.lgd_data_path)
    if not path.exists():
        logger.warning(
            "LGD lookup table not found at %s; place-name disambiguation "
            "will be skipped and results will be labeled 'estimated'.",
            path,
        )
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _lgd_table() -> list[dict]:
    global _LGD_TABLE
    if _LGD_TABLE is None:
        _LGD_TABLE = _load_lgd_table()
    return _LGD_TABLE


def _disambiguate_with_lgd(query: str, candidates: list[dict]) -> dict:
    """When Nominatim returns more than one candidate for an ambiguous place
    name, prefer the one whose district/state also matches an LGD row for
    that village name."""
    table = _lgd_table()
    if not table:
        return candidates[0]

    query_lower = query.lower()
    lgd_matches = [row for row in table if row["village_name"].lower() in query_lower]
    if len(lgd_matches) == 1:
        lgd_row = lgd_matches[0]
        for cand in candidates:
            addr = cand.get("display_name", "").lower()
            if lgd_row["district"].lower() in addr and lgd_row["state"].lower() in addr:
                cand = dict(cand)
                cand["_lgd_code"] = lgd_row["lgd_code"]
                return cand
    return candidates[0]


def geocode_location(
    query: str, *, offline_fixture: Optional[list[dict]] = None
) -> GeocodeResult:
    """
    Resolve a free-text village/block/district name to coordinates.

    `offline_fixture` injects a canned Nominatim-shaped response instead of
    hitting the network -- used by tests, and usable for any offline run
    where a pre-fetched result set is available (this also satisfies the
    Nominatim policy's mandatory-caching requirement for repeat queries).
    """
    cache_key = query.strip().lower()
    if cache_key in _cache:
        return _cache[cache_key]

    if offline_fixture is not None:
        candidates = offline_fixture
    else:
        _rate_limit()
        resp = requests.get(
            f"{settings.nominatim_base_url}/search",
            params={"q": query, "format": "jsonv2", "limit": 5, "countrycodes": "in"},
            headers={"User-Agent": settings.nominatim_user_agent},
            timeout=15,
        )
        resp.raise_for_status()
        candidates = resp.json()

    if not candidates:
        raise ValueError(f"No geocoding match found for {query!r}")

    chosen = _disambiguate_with_lgd(query, candidates) if len(candidates) > 1 else candidates[0]
    lgd_code = chosen.get("_lgd_code")

    result = GeocodeResult(
        matched_name=chosen.get("display_name", query),
        lat=float(chosen["lat"]),
        lon=float(chosen["lon"]),
        lgd_code=lgd_code,
        source_confidence="real" if lgd_code else "estimated",
        raw_candidates=len(candidates),
    )
    _cache[cache_key] = result
    return result
