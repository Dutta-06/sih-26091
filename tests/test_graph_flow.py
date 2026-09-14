"""Graph control flow with light fake agents (offline, deterministic)."""

from __future__ import annotations

import sys
import types
import uuid

import pytest

from orchestrator.graph import NODE_MODULES, build_graph, route_after_review, run_case
from orchestrator.state import (
    ApplicationStatus,
    CaseState,
    CompetitorIntelligence,
    FeasibilityRecord,
    FinancialPlan,
    GrievanceEntry,
    HealthSnapshot,
    LaunchMilestone,
    LocationDetails,
    MarketReachIntelligence,
    OpportunityIntelligence,
    OutcomeLearningStatus,
    PricingIntelligence,
    RiskIntelligence,
    SessionMeta,
    SupplyChainIntelligence,
    TransactionRecord,
)
from module1_feasibility.profiling_agent import extract_profile_from_slots

OWN = {"profiling_agent", "discovery_agent", "swot_synthesis", "adversarial_review"}
INTEL = {
    "market_reach_agent": ("market_reach_intel", MarketReachIntelligence),
    "opportunity_agent": ("opportunity_intel", OpportunityIntelligence),
    "risk_agent": ("risk_intel", RiskIntelligence),
    "competitor_agent": ("competitor_intel", CompetitorIntelligence),
    "pricing_agent": ("pricing_intel", PricingIntelligence),
    "supply_chain_agent": ("supply_chain_intel", SupplyChainIntelligence),
}
TRANSITIONS = {"submit": ("documents_pending", "submitted"), "start_verification": ("submitted", "under_verification"),
               "sanction": ("under_verification", "sanctioned"), "disburse": ("sanctioned", "disbursed")}


def _module(name: str, **funcs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in funcs.items():
        setattr(mod, k, v)
    return mod


def install_fakes(monkeypatch, calls: list[str] | None = None, dscr: float = 1.6) -> list[str]:
    """Replace every non-orchestration agent (and connectors used by F's agents) with light fakes."""
    calls = [] if calls is None else calls

    def track(name, fn):
        def run(state):
            calls.append(name)
            return fn(state)
        return run

    fakes = {name: (lambda s, a=attr, c=cls: {a: c()}) for name, (attr, cls) in INTEL.items()}

    def engine(s):
        cap = s.entrepreneur_profile.available_capital
        if cap / 0.10 > 5_000_000:
            return {"financial_plan": FinancialPlan(eligibility_status="outside_scheme_range", available_margin_capital=cap,
                                                    ineligibility_reason="project above Rs 50 lakh")}
        return {"financial_plan": FinancialPlan(available_margin_capital=cap, computed_project_cost=cap / 0.10,
                                                maximum_loan_eligibility=cap / 0.10 * 0.9)}

    def documentation(s):
        app = s.application_status or ApplicationStatus(disbursement_status="documents_pending", next_required_field="full_name")
        return {"application_status": app}

    def apply_event(state, event, actor="officer", reason="", amount=None):
        current = state.application_status.disbursement_status if state.application_status else "not_applied"
        if event not in TRANSITIONS or TRANSITIONS[event][0] != current:
            raise ValueError(f"illegal transition {event} from {current}")
        return {"application_status": (state.application_status or ApplicationStatus()).model_copy(
            update={"disbursement_status": TRANSITIONS[event][1]})}

    def record_field(state, field, value):
        state.application_status.form_data[field] = value
        state.application_status.next_required_field = None
        return True, f"Recorded {field}."

    fakes.update({
        "financial_engine": engine,
        "financial_analyst": lambda s: {},
        "scenario_digital_twin": lambda s: {},
        "policy_scheme": lambda s: {},
        "documentation": documentation,
        "application_tracker": lambda s: {},
        "procurement_coordinator": lambda s: {},
        "launch_copilot": lambda s: {"launch_roadmap": [LaunchMilestone(phase_number=1, title="Register on Udyam", target_week=1, tasks=["register"])]},
        "ongoing_monitoring": lambda s: {"monitoring_record": [*s.monitoring_record, HealthSnapshot(
            transactions_parsed=len(s.session_meta.pending_transactions), is_consent_verified=True)]},
        "health_score": lambda s: {},
        "grievance_engine": lambda s: {"grievance_log": [*s.grievance_log, GrievanceEntry(
            ticket_id=f"G-{len(s.grievance_log) + 1}", issue_type="other", description=s.session_meta.pending_grievance_text or "")]},
        "outcome_learning_loop": lambda s: {"outcome_learning": OutcomeLearningStatus(status_note="fake")},
    })
    for node, fn in fakes.items():
        name = NODE_MODULES[node]
        extra = {"apply_event": apply_event} if node == "application_tracker" else {"record_field": record_field} if node == "documentation" else {}
        monkeypatch.setitem(sys.modules, name, _module(name, run=track(node, fn), **extra))
    for node in OWN:  # real orchestration-owned agents, tracked
        mod = __import__(NODE_MODULES[node], fromlist=["run"])
        monkeypatch.setattr(mod, "run", track(node, mod.run))

    monkeypatch.setitem(sys.modules, "data_connectors.geocoding", _module(
        "data_connectors.geocoding", resolve_location=lambda q: LocationDetails(raw_query=q, district="Bhadohi", state="Uttar Pradesh",
                                                                                 resolution_method="state_centroid")))
    monkeypatch.setitem(sys.modules, "data_connectors.sms_parser", _module(
        "data_connectors.sms_parser", parse_notifications=lambda msgs: [TransactionRecord(
            occurred_at="2026-09-01", direction="credit", amount=1500.0, channel="upi") for m in msgs if "credited" in m.lower()]))
    import module1_feasibility.adversarial_review as review
    monkeypatch.setattr(review, "_preview", lambda cap, act: {
        "project_cost": cap / 0.10, "eligible": cap / 0.10 <= 5_000_000, "quarterly_installment": 10_000.0,
        "quarterly_surplus": 10_000.0 * dscr, "base_dscr": dscr, "min_seasonal_dscr": dscr})
    return calls


def _case(capital: float, activity: str, reason: str | None = None) -> CaseState:
    state = CaseState(session_meta=SessionMeta(session_id=f"t_{uuid.uuid4().hex[:6]}", requested_stage="profiling"))
    state.entrepreneur_profile = extract_profile_from_slots("Bhadohi, Uttar Pradesh", capital, activity, preference_reason=reason)
    return state


def test_graph_compiles_with_all_nodes():
    nodes = build_graph(with_checkpointer=True).get_graph().nodes
    for name in ["entry_router", *NODE_MODULES]:
        assert name in nodes


def test_micro_finance_tailoring_runs_to_application_without_recursion(monkeypatch):
    calls = install_fakes(monkeypatch)
    final = run_case(build_graph(), _case(12_000, "Tailoring and Garment Stitching Unit", "I know stitching"), recursion_limit=40)
    record = final.feasibility_record
    assert record.verdict == "viable" and record.selected_catalog_id == "tailoring"
    assert final.business_shortlist[0].is_user_preference
    assert "I know stitching" in record.preference_reason_context
    assert calls.count("swot_synthesis") == 1 and calls.count("profiling_agent") == 1
    assert final.financial_plan.eligibility_status == "eligible"
    # application pauses: no Module 3 before sanction and disbursement
    assert final.application_status.disbursement_status == "documents_pending"
    assert "procurement_coordinator" not in calls and not final.launch_roadmap


def test_rejection_loop_is_bounded(monkeypatch):
    from config.settings import settings

    calls = install_fakes(monkeypatch, dscr=0.5)  # every activity fails coverage
    final = run_case(build_graph(), _case(100_000, "dairy"), recursion_limit=60)
    record = final.feasibility_record
    assert record.verdict == "not_recommended" and record.alternatives_exhausted
    assert len(record.rejection_history) == settings.max_feasibility_attempts
    assert calls.count("adversarial_review") == settings.max_feasibility_attempts
    assert record.rejection_history[0].catalog_id == "dairy_farming"
    assert len({r.catalog_id for r in record.rejection_history}) == settings.max_feasibility_attempts
    assert final.financial_plan is None


def test_outside_scheme_range_ends_after_profiling(monkeypatch):
    """TDD 5.1: a capital that cannot enter any scheme tier is stopped before feasibility is evaluated."""
    calls = install_fakes(monkeypatch)
    final = run_case(build_graph(), _case(600_000, "dairy"))
    assert "discovery_agent" not in calls and final.financial_plan is None and final.application_status is None
    assert final.session_meta.current_stage == "not_eligible"
    assert any("ceiling" in c for c in final.entrepreneur_profile.constraints)


def test_disbursement_reentry_runs_launch(monkeypatch):
    calls = install_fakes(monkeypatch)
    state = _case(12_000, "tailoring")
    state.application_status = ApplicationStatus(disbursement_status="sanctioned")
    state.session_meta.requested_stage = "launch"
    assert run_case(build_graph(), state).launch_roadmap == []  # not yet disbursed -> gate holds
    state.application_status = ApplicationStatus(disbursement_status="disbursed")
    final = run_case(build_graph(), state)
    assert final.launch_roadmap and calls[-2:] == ["procurement_coordinator", "launch_copilot"]
    assert "profiling_agent" not in calls


def test_grievance_entry(monkeypatch):
    calls = install_fakes(monkeypatch)
    state = CaseState(session_meta=SessionMeta(session_id="g1", requested_stage="grievance",
                                               pending_grievance_text="machine broken"))
    final = run_case(build_graph(), state)
    assert calls == ["grievance_engine", "outcome_learning_loop"]
    assert final.grievance_log[0].description == "machine broken"


def test_monitoring_entry_requires_consent(monkeypatch):
    calls = install_fakes(monkeypatch)
    tx = TransactionRecord(occurred_at="2026-09-01", direction="credit", amount=900.0)
    state = CaseState(session_meta=SessionMeta(session_id="m1", requested_stage="monitoring", pending_transactions=[tx]))
    assert run_case(build_graph(), state).monitoring_record == [] and calls == []
    state.session_meta.consent_sms_monitoring = True
    final = run_case(build_graph(), state)
    assert calls == ["ongoing_monitoring", "health_score", "outcome_learning_loop"]
    assert final.monitoring_record[0].transactions_parsed == 1


def test_scheme_inquiry_stops_after_policy(monkeypatch):
    calls = install_fakes(monkeypatch)
    state = _case(100_000, "dairy")
    state.session_meta.requested_stage = "scheme_inquiry"
    run_case(build_graph(), state)
    assert calls == ["policy_scheme"]


@pytest.mark.parametrize("verdict,exhausted,attempt,expected", [
    ("viable", False, 1, "financial_engine"), ("marginal", False, 2, "discovery_agent"),
    ("not_recommended", True, 2, "__end__"), ("marginal", False, 99, "__end__")])
def test_route_after_review(verdict, exhausted, attempt, expected):
    state = CaseState(session_meta=SessionMeta(session_id="r"), feasibility_record=FeasibilityRecord(
        verdict=verdict, alternatives_exhausted=exhausted, attempt_number=attempt))
    assert route_after_review(state) == expected
