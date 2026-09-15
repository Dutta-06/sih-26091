"""Location resolution: LGD/Census tables -> Nominatim -> reference centroid (TECHNICAL_SETUP §8.1).

Resolves "village, block, district, state" style text (or free text such as
"Bhadohi, Uttar Pradesh") to a ``LocationDetails``. Repeated village names are
disambiguated with the stated district/state against the LGD code table
(``settings.lgd_data_path``); coordinates come from the Census village table
(``settings.census_data_path``), from OpenStreetMap Nominatim in live mode
(rate-limited to ``nominatim_min_interval_seconds``, results cached per
process as the usage policy requires), or finally from the coarse district
headquarters / state capital coordinates in ``common.reference``.

Confidence: rows flagged ``is_sample=1`` (the shipped fixtures) and every
reference-centroid fallback are "estimated"; a real LGD/Census download or a
live Nominatim hit is "real". ``resolve_location`` never raises.
"""

from __future__ import annotations

import csv
import logging
import re
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from common.net import DataUnavailable, require_live
from common.reference import load_state_reference, lookup_district, lookup_state
from config.settings import settings
from data_connectors import http_request, user_agent
from orchestrator.state import LocationDetails

logger = logging.getLogger(__name__)

_cache: dict[tuple[str, ...], LocationDetails] = {}
_rate_lock = threading.Lock()
_last_request = 0.0


def _norm(value: Optional[str]) -> str:
    text = " ".join(str(value or "").lower().replace("-", " ").split())
    return re.sub(r"\s+(district|dist\.?|tehsil|block)$", "", text)


def clear_cache() -> None:
    _cache.clear()
    _read_table.cache_clear()


@lru_cache(maxsize=8)
def _read_table(path: str) -> tuple[dict[str, str], ...]:
    p = Path(path)
    if not p.exists():
        logger.warning("Location table not found at %s; skipping", p)
        return ()
    with p.open(newline="", encoding="utf-8") as f:
        return tuple(dict(r) for r in csv.DictReader(f))


def _is_sample(row: dict[str, str]) -> bool:
    return str(row.get("is_sample", "")).strip().lower() in {"1", "true", "yes"}


# --- Query parsing -----------------------------------------------------------

def _find_in_text(names: dict[str, list[str]], text: str) -> Optional[tuple[str, str]]:
    """Longest reference name (or alias) occurring as whole words in ``text`` -> (canonical, matched)."""
    best: Optional[tuple[str, str]] = None
    for canonical, aliases in names.items():
        for name in [canonical, *aliases]:
            if re.search(rf"\b{re.escape(_norm(name))}\b", _norm(text)) and (not best or len(name) > len(best[1])):
                best = (canonical, name)
    return best


def parse_query(query: str) -> dict[str, Optional[str]]:
    parts = [p.strip() for p in re.split(r"[,;\n]", query or "") if p.strip()]
    parsed: dict[str, Optional[str]] = dict.fromkeys(("village", "block", "district", "state", "place"))
    ref = load_state_reference()

    for p in reversed(parts):
        if hit := lookup_state(p):
            parsed["state"] = hit[0]
            parts.remove(p)
            break
    if not parsed["state"] and len(parts) == 1:
        if found := _find_in_text({s: [] for s in ref["states"]}, parts[0]):
            parsed["state"] = found[0]
            rest = re.sub(rf"\b{re.escape(_norm(found[1]))}\b", " ", _norm(parts[0])).strip()
            parts = [rest] if rest else []
    if not parsed["state"] and len(parts) >= 3:
        parsed["state"] = parts.pop()

    if len(parts) >= 3:
        parsed["village"], parsed["block"], parsed["district"] = parts[0], parts[1], parts[-1]
    elif len(parts) == 2:
        parsed["village"], parsed["district"] = parts
    elif parts:
        parsed["place"] = parts[0]
    return parsed


# --- Table lookup (LGD codes + Census village coordinates) --------------------

def _table_candidates(query: str, parsed: dict[str, Optional[str]]) -> list[dict[str, Any]]:
    lgd = _read_table(str(settings.lgd_data_path))
    census = _read_table(str(settings.census_data_path))
    name = parsed["village"] or parsed["place"]
    rows = [("lgd", r) for r in lgd] + [("census", r) for r in census]
    matched = [(kind, r) for kind, r in rows if name and _norm(r.get("village_name")) == _norm(name)]
    if not matched and "," not in query:
        hits = [(kind, r) for kind, r in rows
                if r.get("village_name") and re.search(rf"\b{re.escape(_norm(r['village_name']))}\b", _norm(query))]
        longest = max((len(_norm(r["village_name"])) for _, r in hits), default=0)
        matched = [(kind, r) for kind, r in hits if len(_norm(r["village_name"])) == longest]

    def agrees(row: dict[str, str], field: str, stated: Optional[str]) -> bool:
        # An empty table value never counts as a match for a stated name.
        return not stated or (bool(row.get(field)) and _norm(row[field]) == _norm(stated))

    district = parsed["district"] or (parsed["place"] if parsed["village"] else None)
    matched = [(k, r) for k, r in matched if agrees(r, "district", district) and agrees(r, "state", parsed["state"])]

    def key(r: dict[str, str]) -> tuple[str, str, str]:
        return _norm(r.get("village_name")), _norm(r.get("district")), _norm(r.get("state"))

    def place(r: dict[str, str]) -> dict[str, Any]:
        return {"village": r.get("village_name"), "district": r.get("district") or None,
                "state": r.get("state") or None, "sample": _is_sample(r)}

    census_rows = [r for k, r in matched if k == "census"]
    places = []
    for r in (r for k, r in matched if k == "lgd"):  # one place per LGD code
        p = place(r) | {"lgd_code": r.get("lgd_code") or None, "block": r.get("block") or None}
        same = [c for c in census_rows if key(c) == key(r) and all(key(r))]
        if len(same) == 1:
            census_rows.remove(same[0])
            p["sample"] = p["sample"] or _is_sample(same[0])
            p["lat"], p["lon"] = same[0].get("lat"), same[0].get("lon")
        places.append(p)
    places += [place(c) | {"lat": c.get("lat"), "lon": c.get("lon")} for c in census_rows]
    for p in places:
        try:
            p["lat"], p["lon"] = float(p["lat"]), float(p["lon"])
        except (KeyError, TypeError, ValueError):
            p["lat"] = p["lon"] = None
    return places


# --- Nominatim ----------------------------------------------------------------

def _rate_limit() -> None:
    global _last_request
    with _rate_lock:
        wait = settings.nominatim_min_interval_seconds - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def _address_values(candidate: dict[str, Any]) -> set[str]:
    values = {_norm(v) for v in (candidate.get("address") or {}).values() if isinstance(v, str)}
    return values | {_norm(p) for p in str(candidate.get("display_name", "")).split(",")}


def _matches(candidate: dict[str, Any], district: Optional[str], state: Optional[str]) -> bool:
    if not district and not state:
        return False
    values = _address_values(candidate)
    return (not district or _norm(district) in values) and (not state or _norm(state) in values)


def nominatim_search(query: str) -> list[dict[str, Any]]:
    """Raw Nominatim candidates (raises ``DataUnavailable``)."""
    require_live("nominatim")
    _rate_limit()
    resp = http_request(
        "nominatim", "GET", f"{settings.nominatim_base_url.rstrip('/')}/search",
        params={"q": query, "format": "jsonv2", "addressdetails": 1, "limit": 5, "countrycodes": "in"},
        headers={"User-Agent": user_agent()},
    )
    try:
        data = resp.json()
    except ValueError as exc:
        raise DataUnavailable(f"nominatim: invalid JSON ({exc})") from exc
    return data if isinstance(data, list) else []


def _from_nominatim(query: str, parsed: dict[str, Optional[str]], places: list[dict[str, Any]],
                    loc: LocationDetails) -> bool:
    try:
        candidates = nominatim_search(query)
    except DataUnavailable as exc:
        loc.notes.append(str(exc))
        return False
    loc.candidates_considered = max(loc.candidates_considered, len(candidates))
    if not candidates:
        loc.notes.append("nominatim: no match")
        return False

    chosen, place = None, None
    if places:  # disambiguate repeated names with the LGD/Census table rows
        pairs = [(c, p) for c in candidates for p in places if _matches(c, p.get("district"), p.get("state"))]
        if len({id(p) for _, p in pairs}) == 1:
            chosen, place = pairs[0]
    district = parsed["district"] or (parsed["place"] if parsed["village"] else None)
    if chosen is None and (district or parsed["state"]):
        chosen = next((c for c in candidates if _matches(c, district, parsed["state"])), None)
    if chosen is None:
        if len(candidates) > 1 and (places or district or parsed["state"]):
            loc.notes.append("nominatim: candidates did not match the stated district/state")
            return False
        chosen = candidates[0]
        if len(candidates) > 1:
            loc.notes.append(f"nominatim: {len(candidates)} candidates, highest-ranked chosen (add district/state)")

    addr = chosen.get("address") or {}
    loc.latitude, loc.longitude = float(chosen["lat"]), float(chosen["lon"])
    loc.resolution_method, loc.source_confidence = "nominatim", "real"
    loc.village = loc.village or addr.get("village") or addr.get("hamlet") or addr.get("town")
    loc.district = loc.district or addr.get("state_district") or addr.get("county")
    loc.state = loc.state or addr.get("state")
    loc.pincode = loc.pincode or addr.get("postcode")
    if place and place.get("lgd_code"):
        loc.lgd_code = place["lgd_code"]
        loc.notes.append("LGD code attached after matching district/state")
    loc.notes.append(f"nominatim: {chosen.get('display_name', '')}")
    return True


# --- Public entry point ------------------------------------------------------

def _resolve(query: str) -> LocationDetails:
    parsed = parse_query(query)
    loc = LocationDetails(raw_query=query, village=parsed["village"], block=parsed["block"],
                          district=parsed["district"], state=parsed["state"])
    places = _table_candidates(query, parsed)
    loc.candidates_considered = len(places)

    if len(places) == 1:
        p = places[0]
        loc.village, loc.district, loc.state = p["village"], p["district"] or loc.district, p["state"] or loc.state
        loc.block = p.get("block") or loc.block
        loc.lgd_code = p.get("lgd_code")
        label = "sample fixture row" if p["sample"] else "table row"
        if p.get("lat") is not None:
            loc.latitude, loc.longitude = p["lat"], p["lon"]
            loc.resolution_method = "lgd_table" if loc.lgd_code else "census_table"
            loc.source_confidence = "estimated" if p["sample"] else "real"
            loc.notes.append(f"resolved from LGD/Census {label}")
            return loc
        loc.notes.append(f"LGD {label} matched but has no coordinates")
        places = [p]
    elif len(places) > 1:
        loc.notes.append(f"ambiguous place name: {len(places)} table matches; state the district/state")

    if _from_nominatim(query, parsed, places, loc):
        return loc

    district_name = next(
        (hit[0] for n in (loc.district, parsed["place"], parsed["village"]) if (hit := lookup_district(n))), None
    ) or ((found := _find_in_text({d: i.get("aliases", []) for d, i in load_state_reference()["districts"].items()},
                                  query)) and found[0])
    if district_name and (not loc.state or _norm(loc.state) == _norm(lookup_district(district_name)[1]["state"])):
        info = lookup_district(district_name)[1]
        loc.district, loc.state = district_name, info["state"]
        loc.latitude, loc.longitude = info["lat"], info["lon"]
        loc.resolution_method, loc.source_confidence = "state_centroid", "estimated"
        loc.notes.append(f"coarse fallback: district headquarters coordinates for {district_name}")
        return loc
    if state_hit := lookup_state(loc.state):
        loc.state = state_hit[0]
        loc.latitude, loc.longitude = state_hit[1]["lat"], state_hit[1]["lon"]
        loc.resolution_method, loc.source_confidence = "state_centroid", "estimated"
        loc.notes.append(f"coarse fallback: state capital coordinates for {state_hit[0]}")
        return loc
    loc.notes.append("location could not be resolved to coordinates")
    return loc


def resolve_location(query: str) -> LocationDetails:
    key = (_norm(query), settings.data_mode, str(settings.lgd_data_path), str(settings.census_data_path),
           settings.nominatim_base_url)
    if key not in _cache:
        try:
            _cache[key] = _resolve(query)
        except Exception as exc:  # never raise into the graph
            logger.exception("resolve_location failed for %r", query)
            _cache[key] = LocationDetails(raw_query=query, notes=[f"resolution error: {exc}"])
    return _cache[key].model_copy(deep=True)
