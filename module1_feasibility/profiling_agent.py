"""Entrepreneur Profiling Agent (Module 1, TDD 5.1).

Reads: state.entrepreneur_profile (slots filled conversationally by orchestrator.router)
Writes: state.entrepreneur_profile (resolved location, early constraints)
Tech: structured Pydantic profile; location via data_connectors.geocoding.resolve_location;
deterministic early-constraint rules so later stages never evaluate an infeasible option.
"""

from __future__ import annotations

from typing import Any, Optional

from common.reference import match_activity
from orchestrator.state import CaseState, EntrepreneurProfile, LocationDetails

MARGIN_SHARE = 0.10  # scheme: beneficiary contributes 10% of project cost
SCHEME_MAX_PROJECT_COST = 5_000_000.0  # Rs 50 lakh ceiling


def affordable_project_cost(capital: float) -> float:
    """Project cost the stated margin supports, capped at the scheme ceiling."""
    return min(max(capital, 0.0) / MARGIN_SHARE, SCHEME_MAX_PROJECT_COST)


def extract_profile_from_slots(
    location_query: str,
    available_capital: float,
    business_preference: Optional[str] = None,
    skills: Optional[list[str]] = None,
    assets: Optional[list[str]] = None,
    preference_reason: Optional[str] = None,
    land_or_premises: Optional[str] = None,
) -> EntrepreneurProfile:
    """Structured profile from router slots. Nothing is invented: unknown fields stay empty."""
    return EntrepreneurProfile(
        location_query=location_query or "",
        location=LocationDetails(raw_query=location_query or ""),
        available_capital=max(0.0, float(available_capital or 0.0)),
        skills=skills or [],
        assets=assets or [],
        land_or_premises=land_or_premises,
        business_preference=business_preference,
        preference_reason=preference_reason,
    )


def identify_constraints(profile: EntrepreneurProfile) -> list[str]:
    capital = profile.available_capital
    if capital <= 0:
        return ["No margin capital stated; project cost cannot be sized."]
    constraints: list[str] = []
    raw_project = capital / MARGIN_SHARE
    affordable = affordable_project_cost(capital)
    if raw_project > SCHEME_MAX_PROJECT_COST:
        constraints.append(
            f"Stated capital Rs {capital:,.0f} implies a project of Rs {raw_project:,.0f}, above the scheme ceiling "
            f"of Rs {SCHEME_MAX_PROJECT_COST:,.0f}; the case is outside the concessional scheme range."
        )
    preferred = match_activity(profile.business_preference)
    if preferred and preferred["min_project_cost"] > affordable:
        constraints.append(
            f"Preferred activity '{preferred['category']}' needs a project of at least Rs {preferred['min_project_cost']:,.0f}; "
            f"capital Rs {capital:,.0f} supports only Rs {affordable:,.0f} (10% margin). It will not be assessed."
        )
    if profile.location.resolution_method == "unresolved":
        constraints.append("Location could not be resolved; local analyses will rely on coarse estimates.")
    return constraints


def _resolve(profile: EntrepreneurProfile) -> LocationDetails:
    loc = profile.location
    if loc.latitude is not None and loc.longitude is not None or not profile.location_query:
        return loc
    try:
        from data_connectors.geocoding import resolve_location

        resolved = resolve_location(profile.location_query)
    except Exception as exc:  # connector missing or broken: degrade, never invent coordinates
        return loc.model_copy(update={
            "raw_query": profile.location_query,
            "notes": [*loc.notes, f"Location resolution unavailable: {exc}"],
        })
    return resolved.model_copy(update={"raw_query": resolved.raw_query or profile.location_query})


def run(state: CaseState) -> dict[str, Any]:
    if state.entrepreneur_profile is None:
        return {}
    profile = state.entrepreneur_profile.model_copy(deep=True)
    profile.location = _resolve(profile)
    profile.constraints = identify_constraints(profile)
    return {"entrepreneur_profile": profile}
