"""Evaluation Metrics (TECHNICAL_SETUP.md Section 10).

Scores agent outputs for:
- Structural correctness (Pydantic schema conformance)
- Mandatory confidence tagging ("real" vs "estimated")
- Deterministic numerical precision against golden baselines
"""

from __future__ import annotations

from typing import Any, Callable

from orchestrator.state import CaseState, FinancialPlan, QuarterlyRepaymentInstallment

MONEY_TOLERANCE = 0.005


def evaluate_confidence_compliance(state: CaseState) -> dict[str, Any]:
    """Verifies that all 6 parallel intelligence branches carry valid confidence labels."""
    market = state.market_intelligence
    if not market:
        return {"passed": False, "score": 0.0, "details": "market_intelligence is None"}

    names = ("market_reach", "opportunity", "risk", "competitor", "pricing", "supply_chain")
    details = {}
    for name in names:
        tag = getattr(getattr(market, name, None), "source_confidence", None)
        details[name] = {"confidence": tag, "valid": tag in ("real", "estimated")}
    valid = sum(1 for d in details.values() if d["valid"])
    score = round(valid / len(names) * 100.0, 1)
    return {"passed": score == 100.0, "score": score, "valid_branches": valid,
            "total_branches": len(names), "details": details}


def _schedule_metrics(schedule: list[QuarterlyRepaymentInstallment]) -> dict[str, Callable[[], Any]]:
    return {
        "total_quarters": lambda: len(schedule),
        "moratorium_quarters": lambda: sum(1 for i in schedule if i.is_moratorium),
        "first_quarter_interest": lambda: schedule[0].interest_payment if schedule else None,
        "principal_total": lambda: round(sum(i.principal_payment for i in schedule), 2),
        "last_closing_balance": lambda: schedule[-1].closing_balance if schedule else None,
    }


def _matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        return actual == expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(actual - expected) <= MONEY_TOLERANCE
    return actual == expected


def compare(getters: dict[str, Callable[[], Any]], expected: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for key, value in expected.items():
        if key not in getters:
            checks[key] = False  # unknown expectation keys fail loudly instead of being skipped
            continue
        checks[key] = _matches(getters[key](), value)
    return {"passed": all(checks.values()), "checks": checks}


def evaluate_schedule_precision(schedule: list[QuarterlyRepaymentInstallment], total_interest: float,
                                total_repayment: float, expected: dict[str, Any]) -> dict[str, Any]:
    getters = _schedule_metrics(schedule)
    getters.update(total_interest=lambda: total_interest, total_repayment=lambda: total_repayment)
    return compare(getters, expected)


def evaluate_financial_plan_precision(plan: FinancialPlan, expected: dict[str, Any]) -> dict[str, Any]:
    """Compares computed financial outputs against the golden reference values present in ``expected``."""
    tier = plan.scheme_tier
    getters: dict[str, Callable[[], Any]] = {
        "eligibility_status": lambda: plan.eligibility_status,
        "has_ineligibility_reason": lambda: bool(plan.ineligibility_reason),
        "project_cost": lambda: plan.computed_project_cost,
        "loan_eligibility": lambda: plan.maximum_loan_eligibility,
        "margin_percentage": lambda: plan.margin_percentage,
        "loan_percentage": lambda: plan.loan_percentage,
        "loan_cap_applied": lambda: plan.loan_cap_applied,
        "scheme_tier": lambda: tier.name if tier else None,
        "interest_rate": lambda: tier.interest_rate if tier else None,
        "tenure_years": lambda: tier.tenure_years if tier else None,
        "moratorium_months": lambda: tier.moratorium_months if tier else None,
        "regular_quarterly_installment": lambda: plan.regular_quarterly_installment,
        "total_interest": lambda: plan.total_interest_payable,
        "total_repayment": lambda: plan.total_repayment_amount,
        "working_capital": lambda: plan.working_capital_requirement,
        "capex": lambda: plan.capital_expenditure_allocation,
        **_schedule_metrics(plan.repayment_schedule),
    }
    return compare(getters, expected)
