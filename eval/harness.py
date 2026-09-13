"""Command-line golden-case evaluation harness.

Examples:
    python3 -m eval.harness --module all
    python3 -m eval.harness --module module2_financial
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from module2_financial.financial_engine import (
    FinancialPlan,
    SchemeTerms,
    build_financial_plan,
)

from .metrics import score_case


ROOT = Path(__file__).parent
GOLDEN_CASES = ROOT / "golden_cases"


def serialize_plan(plan: FinancialPlan) -> dict[str, Any]:
    """Convert the engine output to stable values suitable for golden checks."""

    return {
        "available_capital": plan.available_capital,
        "scheme_name": plan.scheme_name,
        "project_cost": plan.project_cost,
        "capital_expenditure": plan.capital_expenditure,
        "working_capital_requirement": plan.working_capital_requirement,
        "loan_amount": plan.loan_amount,
        "loan_eligibility": plan.loan_eligibility.value,
        "scheme_tier.name": plan.scheme_tier.name if plan.scheme_tier else None,
        "scheme_tier.rate": plan.scheme_tier.rate if plan.scheme_tier else None,
        "scheme_tier.tenure_years": plan.scheme_tier.tenure_years if plan.scheme_tier else None,
        "scheme_tier.moratorium_months": (
            plan.scheme_tier.moratorium_months if plan.scheme_tier else None
        ),
        "repayment_schedule.length": len(plan.repayment_schedule),
        "repayment_schedule.0.period_type": (
            plan.repayment_schedule[0].period_type if plan.repayment_schedule else None
        ),
        "repayment_schedule.0.principal": (
            plan.repayment_schedule[0].principal if plan.repayment_schedule else None
        ),
        "repayment_schedule.-1.remaining_balance": (
            plan.repayment_schedule[-1].remaining_balance if plan.repayment_schedule else None
        ),
    }


def run_financial_cases(verbose: bool = False) -> tuple[int, int, list[str]]:
    cases_path = GOLDEN_CASES / "financial_engine.json"
    cases = json.loads(cases_path.read_text())
    passed = 0
    total = 0
    failures = []

    for case in cases:
        name = case["name"]
        try:
            inputs = dict(case["input"])
            if "scheme_terms" in inputs and inputs["scheme_terms"] is not None:
                inputs["scheme_terms"] = SchemeTerms(**inputs.pop("scheme_terms"))
            plan = build_financial_plan(**inputs)
            actual = serialize_plan(plan)
            if verbose:
                print(f"\nCASE: {name}")
                print(json.dumps(actual, indent=2, sort_keys=True))
        except Exception as error:
            failures.append(f"{name}: unexpected error: {error}")
            continue
        case_passed, case_total, case_failures = score_case(actual, case["expected"])
        passed += case_passed
        total += case_total
        failures.extend(f"{name}: {failure}" for failure in case_failures)

    return passed, total, failures


def run_module(module: str, verbose: bool = False) -> tuple[int, int, list[str]]:
    if module == "module2_financial":
        return run_financial_cases(verbose)
    if module == "module1_feasibility":
        return 0, 0, ["module1_feasibility: not implemented in this workspace"]
    if module == "all":
        passed, total, failures = run_financial_cases(verbose)
        print("module1_feasibility: skipped (not implemented in this workspace)")
        return passed, total, failures
    raise ValueError(f"unsupported module: {module}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run golden-case evaluations.")
    parser.add_argument(
        "--module",
        choices=("all", "module1_feasibility", "module2_financial"),
        default="all",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print each golden case's calculated output",
    )
    arguments = parser.parse_args()

    passed, total, failures = run_module(arguments.module, arguments.verbose)
    print(f"{arguments.module}: {passed}/{total} checks passed")
    for failure in failures:
        print(f"FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
