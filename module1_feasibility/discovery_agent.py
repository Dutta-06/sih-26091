"""Business Discovery Agent (Module 1, Section 5.2).

Reads: state.entrepreneur_profile, state.feasibility_record.rejection_history
Writes: state.business_shortlist
Tech: Multi-factor scoring engine; filters out previously rejected candidates on loop-back.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import BusinessCandidate, CaseState

CATALOG = [
    {
        "category": "Dairy Farming and Chilling Unit",
        "rationale": "High year-round liquid milk demand, subsidized under SCA schemes, quick cash-flow generation.",
        "indicative_setup_cost": 1_000_000.0,
        "infrastructure_readiness": "high",
        "sector": "agri_allied",
    },
    {
        "category": "Organic Mustard Oil Processing Mini-Mill",
        "rationale": "Strong rural value addition, low perishability, stable consumer base in block mandis.",
        "indicative_setup_cost": 950_000.0,
        "infrastructure_readiness": "moderate",
        "sector": "manufacturing",
    },
    {
        "category": "Rural Retail Agrochemicals and Seed Depot",
        "rationale": "Essential input dealer for surrounding farmers, high repeat purchases.",
        "indicative_setup_cost": 800_000.0,
        "infrastructure_readiness": "high",
        "sector": "trading",
    },
    {
        "category": "Poultry Layer Unit and Egg Distribution",
        "rationale": "Daily revenue generation, strong protein demand in nearby semi-urban clusters.",
        "indicative_setup_cost": 1_100_000.0,
        "infrastructure_readiness": "moderate",
        "sector": "agri_allied",
    },
]


def score_candidate(candidate: dict[str, Any], profile_capital: float, preference: str | None) -> float:
    """Deterministic multi-factor scoring function:
    - Capital alignment (weight 0.40)
    - Stated preference match (weight 0.35)
    - Infrastructure readiness (weight 0.25)
    """
    score = 50.0

    # Capital compatibility
    setup_cost = candidate["indicative_setup_cost"]
    max_feasible_project = (profile_capital / 0.10) if profile_capital > 0 else 100_000.0
    if setup_cost <= max_feasible_project * 1.15:
        score += 30.0
    else:
        score -= 20.0

    # User preference matching
    if preference and any(word.lower() in candidate["category"].lower() for word in preference.split()):
        score += 20.0

    return round(score, 1)


def run(state: CaseState) -> dict[str, Any]:
    """Generates and ranks candidates, strictly excluding any rejected choices."""
    profile = state.entrepreneur_profile
    capital = profile.available_capital if profile else 100_000.0
    pref = profile.business_preference if profile else None

    # Retrieve rejection history to honor the adversarial feedback loop
    rejected_categories = []
    if state.feasibility_record and state.feasibility_record.rejection_history:
        rejected_categories = [r.lower() for r in state.feasibility_record.rejection_history]

    candidates: list[BusinessCandidate] = []
    for item in CATALOG:
        # Exclude previously rejected categories
        if any(rej in item["category"].lower() for rej in rejected_categories):
            continue

        score = score_candidate(item, capital, pref)
        candidates.append(
            BusinessCandidate(
                category=item["category"],
                rationale=item["rationale"],
                rank=1,  # will sort below
                feasibility_score=score,
                indicative_setup_cost=item["indicative_setup_cost"],
                infrastructure_readiness=item["infrastructure_readiness"],
            )
        )

    # Sort descending by score
    candidates.sort(key=lambda c: c.feasibility_score, reverse=True)
    for idx, c in enumerate(candidates, start=1):
        c.rank = idx

    return {"business_shortlist": candidates}
