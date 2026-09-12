"""Adversarial (Red-Team) Review Agent (Module 1, Section 5.10).

Reads: state.feasibility_record.swot, state.market_intelligence
Writes: state.feasibility_record.verdict, state.feasibility_record.rejection_history
Tech: Self-critique / red-team verification authorized to reject unviable choices and force return to discovery.
"""

from __future__ import annotations

from typing import Any, Literal
from orchestrator.state import CaseState, FeasibilityRecord


def evaluate_adversarial_critique(
    category: str,
    available_capital: float,
    saturation_score: float,
    z_score_competition: float,
) -> tuple[Literal["viable", "marginal", "not_recommended"], str, list[str]]:
    """Strict red-team evaluator that checks for unviable business assumptions."""
    critiques: list[str] = []

    # 1. Capital adequacy check
    min_required_margin = 15_000.0  # ₹15k margin needed for even the smallest ₹1.5L project
    if available_capital < min_required_margin:
        critiques.append(
            f"Insufficient Capital: Stated margin ₹{available_capital:,.0f} cannot support setup overheads."
        )
        return "not_recommended", "Capital below minimum threshold for viable enterprise scale.", critiques

    # 2. Market saturation check (Red-team looks for hyper-crowded copycats)
    if saturation_score > 0.85 and z_score_competition > 2.0:
        critiques.append(
            f"Hyper-Saturation: Local block already oversaturated with {category}. High risk of business stagnation."
        )
        return (
            "not_recommended",
            "Severe local market saturation; recommendation is to pivot to an adjacent unserved niche.",
            critiques,
        )

    if saturation_score > 0.65 or z_score_competition > 1.2:
        critiques.append("Moderate Saturation: Margins may be pressured by existing local players.")
        return (
            "marginal",
            "Viable only with strict product differentiation or confirmed institutional off-take agreements.",
            critiques,
        )

    # 3. Passes adversarial scrutiny
    critiques.append("Verified Viability: Favorable demand-to-competition ratio and adequate capital backing.")
    return (
        "viable",
        "Business plan demonstrates sound market fundamentals and acceptable risk parameters.",
        critiques,
    )


def run(state: CaseState) -> dict[str, Any]:
    feasibility = state.feasibility_record or FeasibilityRecord()
    selected = feasibility.selected_category or "Dairy Farming"

    capital = state.entrepreneur_profile.available_capital if state.entrepreneur_profile else 100_000.0
    sat_score = state.market_intelligence.opportunity.saturation_score if state.market_intelligence else 0.3
    z_score = state.market_intelligence.competitor.z_score_vs_district if state.market_intelligence else 0.0

    verdict, reasoning, critiques = evaluate_adversarial_critique(
        category=selected,
        available_capital=capital,
        saturation_score=sat_score,
        z_score_competition=z_score,
    )

    feasibility.verdict = verdict
    feasibility.verdict_reasoning = reasoning
    feasibility.adversarial_critique = critiques

    # If rejected, record in rejection history so Business Discovery excludes it on loop-back
    if verdict in ("not_recommended", "marginal") and selected not in feasibility.rejection_history:
        feasibility.rejection_history.append(selected)

    return {"feasibility_record": feasibility}
