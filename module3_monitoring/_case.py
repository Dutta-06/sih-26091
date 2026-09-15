"""Small shared lookups over CaseState for Module 3 agents."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from common.reference import get_activity
from orchestrator.state import CaseState


def catalog_id(state: CaseState) -> str:
    cand = state.selected_candidate()
    if cand and cand.catalog_id:
        return cand.catalog_id
    return state.feasibility_record.selected_catalog_id if state.feasibility_record else ""


def activity(state: CaseState) -> Optional[dict[str, Any]]:
    cid = catalog_id(state)
    return get_activity(cid) if cid else None


def district(state: CaseState) -> Optional[str]:
    profile = state.entrepreneur_profile
    return profile.location.district if profile and profile.location.district else None


def intel(state: CaseState, name: str) -> Any:
    """Fanned-in intelligence (market_intelligence.<name>) or the flat per-agent field."""
    if state.market_intelligence is not None:
        return getattr(state.market_intelligence, name)
    return getattr(state, f"{name}_intel", None)


def parse_ts(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        ts = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)
