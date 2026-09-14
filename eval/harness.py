"""Evaluation Harness (TECHNICAL_SETUP.md Section 10).

    python -m eval.harness --module all
    python -m eval.harness --module module1_feasibility
    python -m eval.harness --module module2_financial

Module 2 runs standalone (no graph import): golden cases for every branch of the deterministic
financial engine, plus a structural/consistency check of the reasoning periphery (analyst, stress
test, policy explanation) on the canonical case. Module 1 builds and invokes the full graph.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.metrics import (
    compare,
    evaluate_confidence_compliance,
    evaluate_financial_plan_precision,
    evaluate_schedule_precision,
)

GOLDEN_PATH = Path(__file__).parent / "golden_cases" / "golden_financial_cases.json"


def _node_state(inp: dict):
    from orchestrator.state import BusinessCandidate, CaseState, EntrepreneurProfile, FeasibilityRecord, SessionMeta

    state = CaseState(session_meta=SessionMeta(session_id="eval"))
    if inp.get("available_capital") is not None:
        state.entrepreneur_profile = EntrepreneurProfile(location_query="eval", available_capital=inp["available_capital"])
    if inp.get("feasibility_verdict") is not None:
        state.feasibility_record = FeasibilityRecord(verdict=inp["feasibility_verdict"])
    if inp.get("category"):
        state.business_shortlist = [BusinessCandidate(category=inp["category"])]
    return state


def _run_case(case: dict) -> dict:
    from module2_financial import financial_engine as fe

    kind, inp, exp = case.get("kind", "plan"), case["inputs"], case["expected_outputs"]
    if kind == "plan":
        return evaluate_financial_plan_precision(fe.build_financial_plan(inp["available_capital"], inp.get("category", "")), exp)
    if kind == "schedule":
        return evaluate_schedule_precision(*fe.generate_quarterly_schedule(**inp), exp)
    if kind == "error":
        try:
            getattr(fe, inp["function"])(inp["argument"])
        except ValueError as exc:
            return {"passed": exp["error_contains"] in str(exc), "checks": {"error": str(exc)}}
        return {"passed": False, "checks": {"error": "no ValueError raised"}}
    if kind == "node":
        update = fe.run(_node_state(inp))
        plan = update.get("financial_plan")
        exp = dict(exp)
        produced = exp.pop("plan_produced")
        if (plan is not None) != produced:
            return {"passed": False, "checks": {"plan_produced": plan is not None}}
        return evaluate_financial_plan_precision(plan, exp) if plan is not None else {"passed": True, "checks": {}}
    return {"passed": False, "checks": {"kind": f"unknown case kind {kind!r}"}}


def run_financial_eval() -> bool:
    print("Running Module 2 Financial Engine golden evaluation...")
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    all_passed = True
    for case in cases:
        result = _run_case(case)
        print(f"  [{'PASS' if result['passed'] else 'FAIL'}] {case['case_id']}"
              + ("" if result["passed"] else f": {result['checks']}"))
        all_passed &= result["passed"]
    periphery_passed = run_periphery_eval()
    return all_passed and periphery_passed


def run_periphery_eval() -> bool:
    """Canonical dairy case through analyst -> stress test -> policy: labels and wording must match numbers."""
    from module2_financial import financial_analyst_agent, financial_engine, policy_scheme_agent, scenario_digital_twin
    from module2_financial.operating_model import coverage_band
    from orchestrator.state import BusinessCandidate

    print("Running Module 2 reasoning-periphery consistency evaluation...")
    state = _node_state({"available_capital": 100000.0, "feasibility_verdict": "viable"})
    state.business_shortlist = [BusinessCandidate(category="Dairy Farming (Milch Animals)", catalog_id="dairy_farming")]
    state.financial_plan = financial_engine.run(state)["financial_plan"]
    figures = state.financial_plan.model_dump(include={"computed_project_cost", "maximum_loan_eligibility",
                                                       "scheme_tier", "repayment_schedule"})
    for agent in (financial_analyst_agent, scenario_digital_twin, policy_scheme_agent):
        state.financial_plan = agent.run(state).get("financial_plan", state.financial_plan)
    plan = state.financial_plan
    ratio = plan.base_debt_service_coverage_ratio
    getters = {
        "figures_unchanged": lambda: plan.model_dump(include=set(figures)) == figures,
        "projection_estimated": lambda: plan.operating_projection is not None and plan.operating_projection.source_confidence == "estimated",
        "commentary_states_band": lambda: ratio is not None and f"{ratio:.2f}x" in plan.analyst_commentary
        and {"does not cover": "does not cover", "thin": "thinly", "comfortable": "comfortably"}[coverage_band(ratio)] in plan.analyst_commentary,
        "four_scenarios": lambda: len(plan.scenarios),
        "sustainability_wording": lambda: all(s.is_sustainable == ("Not sustainable" not in s.buffer_recommendation)
                                              and s.is_sustainable == (s.debt_service_coverage_ratio >= 1.0) for s in plan.scenarios),
        "policy_sourced": lambda: bool(plan.policy_sources) and bool(plan.required_documents) and bool(plan.process_steps),
    }
    result = compare(getters, {"figures_unchanged": True, "projection_estimated": True, "commentary_states_band": True,
                               "four_scenarios": 4, "sustainability_wording": True, "policy_sourced": True})
    print(f"  [{'PASS' if result['passed'] else 'FAIL'}] periphery_canonical_dairy: DSCR {ratio}x, "
          f"low-season min DSCR {plan.stress_test_result.debt_service_coverage_ratio if plan.stress_test_result else None}x"
          + ("" if result["passed"] else f" {result['checks']}"))
    return result["passed"]


def run_feasibility_eval() -> bool:
    from orchestrator.graph import build_graph
    from orchestrator.router import route_conversational_turn
    from orchestrator.state import CaseState

    print("Running Module 1 Feasibility & Confidence Tag Evaluation...")
    app = build_graph(with_checkpointer=False)
    state = route_conversational_turn("I have 1 lakh rupees and want to start a Dairy in Bhadohi")[0]
    res = app.invoke(state)
    final_state = CaseState.model_validate(res) if isinstance(res, dict) else res
    comp = evaluate_confidence_compliance(final_state)
    if comp["passed"]:
        print(f"  [PASS] 6-Agent Confidence Compliance: 100% ({comp['valid_branches']}/{comp['total_branches']} branches verified)")
    else:
        print(f"  [FAIL] Confidence compliance failed: {comp['details']}")
    return comp["passed"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluation harness runner.")
    parser.add_argument("--module", default="all", choices=["all", "module1_feasibility", "module2_financial"])
    args = parser.parse_args()

    results = []
    if args.module in ("all", "module2_financial"):
        results.append(run_financial_eval())
    if args.module in ("all", "module1_feasibility"):
        results.append(run_feasibility_eval())

    if all(results):
        print("\nAll evaluation suites passed.")
        sys.exit(0)
    print("\nEvaluation harness encountered failures.")
    sys.exit(1)


if __name__ == "__main__":
    main()
