"""LangGraph control flow for the whole case lifecycle (TDD 4.1-4.2, TECHNICAL_SETUP 4).

Reads: session_meta.requested_stage (set by the router / API), verdicts and statuses written by agents
Writes: nothing itself; nodes return partial updates
Tech: LangGraph StateGraph over the Pydantic ``CaseState``; conditional edges re-enter any stage.

START -> entry_router -> by requested_stage:
  profiling       profiling_agent -> discovery_agent -> 6 parallel intel agents -> swot_synthesis
                  -> adversarial_review -> viable: financial_engine | rejected & alternatives left: discovery_agent
                  | exhausted: END
                  financial_engine -> eligible: financial_analyst -> scenario_digital_twin -> policy_scheme
                  -> documentation -> application_tracker | outside scheme range: END
                  application_tracker -> disbursed: procurement_coordinator -> launch_copilot -> END | else END (paused)
  application     documentation -> application_tracker -> (as above)
  launch          procurement_coordinator (only when disbursed)
  monitoring      ongoing_monitoring -> health_score -> outcome_learning_loop -> END (only with consent)
  grievance       grievance_engine -> outcome_learning_loop -> END
  scheme_inquiry  policy_scheme -> END

Agent modules are imported lazily inside each node so the graph compiles even while a module is being
rewritten, and tests can monkeypatch ``<module>.run``.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from config.settings import settings
from module2_financial.financial_engine import MARGIN_SHARE, TERM_LOAN_MAX_PROJECT_COST
from orchestrator.persistence import get_checkpointer
from orchestrator.state import CaseState

INTEL_NODES = ["market_reach_agent", "opportunity_agent", "risk_agent", "competitor_agent", "pricing_agent", "supply_chain_agent"]

NODE_MODULES: dict[str, str] = {
    "profiling_agent": "module1_feasibility.profiling_agent",
    "discovery_agent": "module1_feasibility.discovery_agent",
    **{name: f"module1_feasibility.{name}" for name in INTEL_NODES},
    "swot_synthesis": "module1_feasibility.swot_synthesis",
    "adversarial_review": "module1_feasibility.adversarial_review",
    "financial_engine": "module2_financial.financial_engine",
    "financial_analyst": "module2_financial.financial_analyst_agent",
    "scenario_digital_twin": "module2_financial.scenario_digital_twin",
    "policy_scheme": "module2_financial.policy_scheme_agent",
    "documentation": "module2_financial.documentation_agent",
    "application_tracker": "module2_financial.application_tracker",
    "procurement_coordinator": "module3_monitoring.procurement_coordinator",
    "launch_copilot": "module3_monitoring.launch_copilot",
    "ongoing_monitoring": "module3_monitoring.ongoing_monitoring_agent",
    "health_score": "module3_monitoring.health_score_agent",
    "grievance_engine": "module3_monitoring.grievance_engine",
    "outcome_learning_loop": "module3_monitoring.outcome_learning_loop",
}

ENTRY_NODES = {
    "profiling": "profiling_agent",
    "application": "documentation",
    "launch": "procurement_coordinator",
    "monitoring": "ongoing_monitoring",
    "grievance": "grievance_engine",
    "scheme_inquiry": "policy_scheme",
}


def _node(module_name: str) -> Callable[[CaseState], dict[str, Any]]:
    def call(state: CaseState) -> dict[str, Any]:
        return importlib.import_module(module_name).run(state) or {}

    call.__name__ = module_name.rsplit(".", 1)[-1]
    return call


def entry_router(state: CaseState) -> dict[str, Any]:
    stage = state.session_meta.requested_stage or "profiling"
    return {"session_meta": state.session_meta.model_copy(update={"current_stage": stage})}


def route_entry(state: CaseState) -> str:
    meta = state.session_meta
    stage = meta.requested_stage or "profiling"
    if stage == "monitoring" and not meta.consent_sms_monitoring:
        return END
    if stage == "launch" and (not state.application_status or state.application_status.disbursement_status != "disbursed"):
        return END
    if stage == "application" and not _eligible(state):
        return END
    return ENTRY_NODES[stage]


def route_after_profiling(state: CaseState) -> str:
    """TDD 5.1: stop before feasibility when the stated capital cannot enter any scheme tier."""
    profile = state.entrepreneur_profile
    if not profile or profile.available_capital <= 0:
        return END
    within_scheme = profile.available_capital / MARGIN_SHARE <= TERM_LOAN_MAX_PROJECT_COST
    return "discovery_agent" if within_scheme else END


def route_after_discovery(state: CaseState) -> list[str] | str:
    return list(INTEL_NODES) if state.business_shortlist else END


def route_after_review(state: CaseState) -> str:
    record = state.feasibility_record
    if record is None:
        return END
    if record.verdict == "viable":
        return "financial_engine"
    if record.alternatives_exhausted or record.attempt_number > settings.max_feasibility_attempts:
        return END
    return "discovery_agent"


def _eligible(state: CaseState) -> bool:
    return bool(state.financial_plan and state.financial_plan.eligibility_status == "eligible")


def route_after_financial_engine(state: CaseState) -> str:
    return "financial_analyst" if _eligible(state) else END


def route_after_policy(state: CaseState) -> str:
    """Scheme questions stop after the explanation; the main pipeline continues to documentation."""
    return END if state.session_meta.requested_stage == "scheme_inquiry" else "documentation"


def route_after_tracker(state: CaseState) -> str:
    status = state.application_status.disbursement_status if state.application_status else None
    return "procurement_coordinator" if status == "disbursed" else END


def build_graph(with_checkpointer: bool = True):
    g = StateGraph(CaseState)
    g.add_node("entry_router", entry_router)
    for name, module in NODE_MODULES.items():
        g.add_node(name, _node(module))

    g.add_edge(START, "entry_router")
    g.add_conditional_edges("entry_router", route_entry, [*ENTRY_NODES.values(), END])
    g.add_conditional_edges("profiling_agent", route_after_profiling, ["discovery_agent", END])
    g.add_conditional_edges("discovery_agent", route_after_discovery, [*INTEL_NODES, END])
    for name in INTEL_NODES:
        g.add_edge(name, "swot_synthesis")  # same superstep -> swot runs once per pass
    g.add_edge("swot_synthesis", "adversarial_review")
    g.add_conditional_edges("adversarial_review", route_after_review, ["financial_engine", "discovery_agent", END])
    g.add_conditional_edges("financial_engine", route_after_financial_engine, ["financial_analyst", END])
    g.add_edge("financial_analyst", "scenario_digital_twin")
    g.add_edge("scenario_digital_twin", "policy_scheme")
    g.add_conditional_edges("policy_scheme", route_after_policy, ["documentation", END])
    g.add_edge("documentation", "application_tracker")
    g.add_conditional_edges("application_tracker", route_after_tracker, ["procurement_coordinator", END])
    g.add_edge("procurement_coordinator", "launch_copilot")
    g.add_edge("launch_copilot", END)
    g.add_edge("ongoing_monitoring", "health_score")
    g.add_edge("health_score", "outcome_learning_loop")
    g.add_edge("grievance_engine", "outcome_learning_loop")
    g.add_edge("outcome_learning_loop", END)
    return g.compile(checkpointer=get_checkpointer() if with_checkpointer else None)


def agent_node_count(app) -> int:
    return len([n for n in app.get_graph().nodes if not n.startswith("__")])


def run_case(app, state: CaseState, recursion_limit: int = 100) -> CaseState:
    """Invoke the compiled graph for one entry and return the validated resulting state.

    The whole state is passed as a dict so every channel (including cleared ``None`` fields) is written
    over any earlier checkpoint on the same thread.
    """
    config = {"configurable": {"thread_id": state.session_meta.session_id}, "recursion_limit": recursion_limit}
    result = app.invoke(state.model_dump(), config=config)
    case = result if isinstance(result, CaseState) else CaseState.model_validate(result)
    case.session_meta.current_stage = lifecycle_stage(case)
    return case


def lifecycle_stage(state: CaseState) -> str:
    """Where the case stands after a run, derived from what the state actually contains."""
    app_status, plan, record = state.application_status, state.financial_plan, state.feasibility_record
    if state.monitoring_record:
        return "post_disbursement_monitoring"
    if state.launch_roadmap:
        return "launch"
    if app_status and app_status.disbursement_status != "not_applied":
        return f"application_{app_status.disbursement_status}"
    if plan and plan.eligibility_status != "eligible":
        return "not_eligible"
    if plan:
        return "financial_structuring"
    if record and record.verdict != "viable" and record.alternatives_exhausted:
        return "feasibility_closed_no_viable_option"
    if record:
        return "feasibility_assessment"
    profile = state.entrepreneur_profile
    if profile and profile.available_capital > 0 and not state.business_shortlist:
        return "not_eligible" if profile.constraints else "no_affordable_activity"
    return "profiling"


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        compiled = build_graph(with_checkpointer=True)
        print(f"Graph compiled: {agent_node_count(compiled)} nodes (+ START/END)")
