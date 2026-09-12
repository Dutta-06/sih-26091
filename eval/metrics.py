"""Evaluation Metrics (Section 10).

Scores agent outputs for:
- Structural correctness (Pydantic schema conformance)
- Mandatory confidence tagging ("real" vs "estimated")
- Deterministic numerical precision against golden baselines
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import CaseState


def evaluate_confidence_compliance(state: CaseState) -> dict[str, Any]:
    """Verifies that all 6 parallel intelligence branches carry valid confidence labels."""
    market = state.market_intelligence
    if not market:
        return {"passed": False, "score": 0.0, "details": "market_intelligence is None"}

    branches = [
        ("market_reach", getattr(market.market_reach, "source_confidence", None)),
        ("opportunity", getattr(market.opportunity, "source_confidence", None)),
        ("risk", getattr(market.risk, "source_confidence", None)),
        ("competitor", getattr(market.competitor, "source_confidence", None)),
        ("pricing", getattr(market.pricing, "source_confidence", None)),
        ("supply_chain", getattr(market.supply_chain, "source_confidence", None)),
    ]

    valid = 0
    details = {}
    for name, tag in branches:
        is_valid = tag in ("real", "estimated")
        details[name] = {"confidence": tag, "valid": is_valid}
        if is_valid:
            valid += 1

    score = round((valid / len(branches)) * 100.0, 1)
    return {
        "passed": score == 100.0,
        "score": score,
        "valid_branches": valid,
        "total_branches": len(branches),
        "details": details,
    }


def evaluate_financial_plan_precision(plan, expected: dict[str, Any]) -> dict[str, Any]:
    """Compares computed financial outputs against golden reference values."""
    checks = {
        "project_cost": plan.computed_project_cost == expected["project_cost"],
        "loan_eligibility": plan.maximum_loan_eligibility == expected["loan_eligibility"],
        "scheme_tier": plan.scheme_tier.name == expected["scheme_tier"],
        "interest_rate": plan.scheme_tier.interest_rate == expected["interest_rate"],
        "tenure_years": plan.scheme_tier.tenure_years == expected["tenure_years"],
        "moratorium_months": plan.scheme_tier.moratorium_months == expected["moratorium_months"],
        "total_quarters": len(plan.repayment_schedule) == expected["total_quarters"],
    }
    all_passed = all(checks.values())
    return {"passed": all_passed, "checks": checks}
