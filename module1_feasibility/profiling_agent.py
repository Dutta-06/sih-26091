"""Entrepreneur Profiling Agent (Module 1, Section 5.1).

Reads: state.entrepreneur_profile (or conversational input slots)
Writes: state.entrepreneur_profile
Tech: Structured extraction against EntrepreneurProfile schema, early constraint identification.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import CaseState, EntrepreneurProfile, LocationDetails


def extract_profile_from_slots(
    location_query: str,
    available_capital: float,
    business_preference: str | None = None,
    skills: list[str] | None = None,
    assets: list[str] | None = None,
    preference_reason: str | None = None,
) -> EntrepreneurProfile:
    """Constructs a structured profile with parsed location components and early constraint validation."""
    # Disambiguate raw location text into structured parts
    parts = [p.strip() for p in location_query.split(",") if p.strip()]
    loc = LocationDetails(raw_query=location_query)
    if len(parts) >= 3:
        loc.village, loc.block, loc.district = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        loc.village, loc.district = parts[0], parts[1]
    elif len(parts) == 1:
        loc.district = parts[0]

    return EntrepreneurProfile(
        location_query=location_query,
        location=loc,
        available_capital=max(0.0, available_capital),
        skills=skills or ["Basic trade and agricultural handling"],
        assets=assets or ["Inherited village land / premises"],
        business_preference=business_preference,
        preference_reason=preference_reason or "Identified strong local market demand",
    )


def run(state: CaseState) -> dict[str, Any]:
    """LangGraph node callable."""
    profile = state.entrepreneur_profile
    if not profile:
        # Provide default profile if not yet populated by conversational router
        profile = extract_profile_from_slots(
            location_query="Bhadohi, Bhadohi, Uttar Pradesh",
            available_capital=100_000.0,
            business_preference="Dairy Farming",
        )
    return {"entrepreneur_profile": profile}
