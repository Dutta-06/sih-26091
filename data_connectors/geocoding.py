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

LGD DISAMBIGUATION -- API STATUS (see IMPLEMENTATION_PLAN.md Section 3):
the government's real LGD data can be reached two ways. LGD_API_ENABLED
turns on a live call to the NAPIX LGD API (dev.napix.gov.in); NAPIX is a
subscribe-and-approve government API-exchange platform, not an instant
self-serve key like data.gov.in -- getting a working lgd_api_key requires
registering on the portal and being granted access to that specific API
product, and I could not reach napix.gov.in from this build environment to
confirm the exact endpoint path or response shape, so
_lookup_lgd_via_api() below is written against NAPIX's documented general
request pattern (subscriber key + JSON) and should be checked against your
own Consumer Guidelines PDF once you have access, not trusted blind. The
simpler, unconditionally-free alternative is downloading the real LGD
directory CSV from lgdirectory.gov.in and pointing LGD_DATA_PATH at it --
that path needs no API and no approval. Either way, when neither is
configured (or the live call fails), this module falls back to whatever
LGD_DATA_PATH points at, exactly as before.
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


# Sentinel distinguishing "no fixture given -> hit the real network" from
# "fixture explicitly given as None -> simulate the API being reachable but
# finding no match" -- a plain `None` default can't tell those apart.
_NO_FIXTURE = object()


def _lookup_lgd_via_api(village_name: str, *, offline_fixture=_NO_FIXTURE) -> Optional[dict]:
    """
    Live lookup against the NAPIX LGD API.

    UNVERIFIED ENDPOINT SHAPE: written against NAPIX's documented general
    request pattern (subscriber key in an `Authorization` header, JSON
    response) because napix.gov.in could not be reached from this build
    environment to confirm the real path/params/response fields for this
    specific API product -- confirm against your NAPIX Consumer Guidelines
    PDF once you have subscriber access and adjust the request/parsing below
    if it differs. Returns None (never raises) on any failure, so a bad or
    unconfirmed integration degrades to the local CSV table rather than
    breaking geocoding.
    """
    if offline_fixture is not _NO_FIXTURE:
        return offline_fixture

    try:
        resp = requests.get(
            f"{settings.lgd_api_base_url}/village/search",
            params={"name": village_name},
            headers={"Authorization": f"Bearer {settings.lgd_api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or resp.json().get("data") or []
        return results[0] if results else None
    except Exception:
        logger.warning(
            "NAPIX LGD API lookup failed for %r; falling back to local LGD_DATA_PATH table. "
            "This endpoint's shape is unverified -- see this module's docstring.",
            village_name,
            exc_info=True,
        )
        return None


def _disambiguate_with_lgd(
    query: str, candidates: list[dict], *, lgd_api_fixture=_NO_FIXTURE
) -> dict:
    """When Nominatim returns more than one candidate for an ambiguous place
    name, prefer the one whose district/state also matches a real LGD
    record for that village name -- from the live NAPIX API when configured
    and reachable, otherwise from the local LGD_DATA_PATH table."""
    if settings.lgd_api_enabled and settings.lgd_api_key:
        api_row = _lookup_lgd_via_api(query, offline_fixture=lgd_api_fixture)
        if api_row:
            district = str(api_row.get("district", "")).lower()
            state = str(api_row.get("state", "")).lower()
            lgd_code = api_row.get("lgd_code") or api_row.get("code")
            for cand in candidates:
                addr = cand.get("display_name", "").lower()
                if district in addr and state in addr and lgd_code:
                    cand = dict(cand)
                    cand["_lgd_code"] = lgd_code
                    return cand

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
    query: str,
    *,
    offline_fixture: Optional[list[dict]] = None,
    lgd_api_fixture=_NO_FIXTURE,
) -> GeocodeResult:
    """
    Resolve a free-text village/block/district name to coordinates.

    `offline_fixture` injects a canned Nominatim-shaped response instead of
    hitting the network -- used by tests, and usable for any offline run
    where a pre-fetched result set is available (this also satisfies the
    Nominatim policy's mandatory-caching requirement for repeat queries).
    `lgd_api_fixture` similarly injects a canned NAPIX LGD API response.
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

    chosen = (
        _disambiguate_with_lgd(query, candidates, lgd_api_fixture=lgd_api_fixture)
        if len(candidates) > 1
        else candidates[0]
    )
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
