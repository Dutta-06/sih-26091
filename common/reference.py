"""Shared reference-data helpers used across agents.

* Business catalog lookup (``data/reference/business_catalog.json``)
* Coarse state/district fallbacks (``data/reference/state_reference.json``)
* Great-circle distance

All values returned from these helpers are planning assumptions and must be
labeled ``source_confidence="estimated"`` by the caller.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from typing import Any, Optional

from config.settings import settings

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict[str, Any]]:
    with open(settings.business_catalog_path, encoding="utf-8") as f:
        data = json.load(f)
    return {a["id"]: a for a in data["activities"]}


def get_activity(catalog_id: str) -> Optional[dict[str, Any]]:
    return load_catalog().get(catalog_id)


def _keyword_in(keyword: str, lowered: str) -> bool:
    """Whole-word match for Latin-script keywords ("bee" must not match "been"); substring for Indic scripts."""
    if keyword.isascii():
        return re.search(rf"(?<![a-z]){re.escape(keyword)}(?:s|es)?(?![a-z])", lowered) is not None
    return keyword in lowered


def match_activity(text: Optional[str]) -> Optional[dict[str, Any]]:
    """Best catalog match for free text (longest matching keyword wins)."""
    if not text:
        return None
    lowered = text.lower()
    best: tuple[int, Optional[dict[str, Any]]] = (0, None)
    for activity in load_catalog().values():
        for kw in activity["keywords"] + [activity["category"].lower()]:
            if len(kw) > best[0] and _keyword_in(kw.lower(), lowered):
                best = (len(kw), activity)
    return best[1]


@lru_cache(maxsize=1)
def load_state_reference() -> dict[str, Any]:
    with open(settings.state_reference_path, encoding="utf-8") as f:
        return json.load(f)


def _norm(name: str) -> str:
    return " ".join(name.lower().replace("-", " ").split())


def lookup_state(name: Optional[str]) -> Optional[tuple[str, dict[str, Any]]]:
    if not name:
        return None
    for state, info in load_state_reference()["states"].items():
        if _norm(name) in {_norm(state), *(_norm(a) for a in info.get("aliases", []))}:
            return state, info
    return None


def lookup_district(name: Optional[str]) -> Optional[tuple[str, dict[str, Any]]]:
    if not name:
        return None
    for district, info in load_state_reference()["districts"].items():
        if _norm(name) in {_norm(district), *(_norm(a) for a in info.get("aliases", []))}:
            return district, info
    return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def low_season_months(seasonal_index: list[float], threshold: float = 0.92) -> list[str]:
    return [MONTHS[i] for i, v in enumerate(seasonal_index[:12]) if v < threshold]
