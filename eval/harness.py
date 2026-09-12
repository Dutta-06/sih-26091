"""Evaluation Harness (Section 10).

Executes automated regression checks across golden cases:
- python -m eval.harness --module all
- python -m eval.harness --module module1_feasibility
- python -m eval.harness --module module2_financial
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from orchestrator.graph import build_graph
from orchestrator.router import route_conversational_turn
from orchestrator.state import CaseState
from eval.metrics import evaluate_confidence_compliance, evaluate_financial_plan_precision


GOLDEN_PATH = Path(__file__).parent / "golden_cases" / "golden_financial_cases.json"


def run_financial_eval() -> bool:
    print("Running Module 2 Financial Engine Golden Evaluation...")
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    from module2_financial.financial_engine import build_financial_plan

    all_passed = True
    for case in cases:
        case_id = case["case_id"]
        inp = case["inputs"]
        exp = case["expected_outputs"]

        plan = build_financial_plan(inp["available_capital"], inp["category"])
        result = evaluate_financial_plan_precision(plan, exp)

        if result["passed"]:
            print(f"  [PASS] {case_id}: Project Cost Rs. {plan.computed_project_cost:,.0f} | Loan Rs. {plan.maximum_loan_eligibility:,.0f} ({plan.scheme_tier.display_name})")
        else:
            print(f"  [FAIL] {case_id}: {result['checks']}")
            all_passed = False

    return all_passed


def run_feasibility_eval() -> bool:
    print("Running Module 1 Feasibility & Confidence Tag Evaluation...")
    app = build_graph(with_checkpointer=False)
    
    init_msg = "I have 1 lakh rupees and want to start a Dairy in Bhadohi"
    state, _ = route_conversational_turn(init_msg)

    res = app.invoke(state)
    final_state = CaseState.model_validate(res) if isinstance(res, dict) else res

    comp = evaluate_confidence_compliance(final_state)
    if comp["passed"]:
        print(f"  [PASS] 6-Agent Confidence Compliance: 100% ({comp['valid_branches']}/{comp['total_branches']} branches verified)")
    else:
        print(f"  [FAIL] Confidence compliance failed: {comp['details']}")

    return comp["passed"]


def main():
    parser = argparse.ArgumentParser(description="Evaluation harness runner.")
    parser.add_argument("--module", type=str, default="all", choices=["all", "module1_feasibility", "module2_financial"])
    args = parser.parse_args()

    results = []
    if args.module in ("all", "module2_financial"):
        results.append(run_financial_eval())

    if args.module in ("all", "module1_feasibility"):
        results.append(run_feasibility_eval())

    if all(results):
        print("\nAll Evaluation Harness Suites Passed Successfully! (Zero Regressions)")
        sys.exit(0)
    else:
        print("\nEvaluation Harness Encountered Failures.")
        sys.exit(1)


if __name__ == "__main__":
    main()
