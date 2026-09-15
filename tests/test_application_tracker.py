import pytest

from module2_financial import application_tracker as tracker
from module2_financial.financial_engine import build_financial_plan
from orchestrator.state import ApplicationStatus, CaseState, SessionMeta


def make_state(checklist=None, status="not_applied"):
    return CaseState(
        session_meta=SessionMeta(session_id="a"),
        financial_plan=build_financial_plan(100_000, "Dairy"),
        application_status=ApplicationStatus(checklist=checklist or {}, disbursement_status=status),
    )


def test_enum_mirrors_schema_literal():
    from typing import get_args
    from orchestrator.state import DisbursementStatus

    assert {s.value for s in tracker.ApplicationState} == set(get_args(DisbursementStatus))


def test_run_incomplete_documents_goes_to_pending():
    state = make_state({"identity_proof": "complete", "bank_passbook": "missing"})
    app = tracker.run(state)["application_status"]
    assert app.disbursement_status == "documents_pending"
    assert app.status_history[-1].actor == "system"


def test_run_all_complete_auto_submits_but_never_sanctions():
    state = make_state({"identity_proof": "complete", "bank_passbook": "complete"}, "documents_pending")
    app = tracker.run(state)["application_status"]
    assert app.disbursement_status == "submitted"
    state.application_status = app
    assert tracker.run(state)["application_status"].disbursement_status == "submitted"


def test_run_without_checklist_does_nothing():
    assert tracker.run(make_state())["application_status"].disbursement_status == "not_applied"


def test_full_officer_flow_and_sanction_cap():
    state = make_state({"identity_proof": "complete"}, "submitted")
    cap = state.financial_plan.maximum_loan_eligibility
    tracker.apply_event(state, "start_verification")
    with pytest.raises(ValueError):
        tracker.apply_event(state, "sanction", amount=cap + 10_000)
    assert state.application_status.disbursement_status == "under_verification"
    tracker.apply_event(state, "sanction", reason="verified")
    assert state.application_status.sanctioned_amount == pytest.approx(cap)
    update = tracker.apply_event(state, "disburse")
    app = update["application_status"]
    assert app.disbursement_status == "disbursed" and app.disbursement_date
    assert [t.to_status for t in app.status_history] == ["under_verification", "sanctioned", "disbursed"]


def test_illegal_transitions_raise():
    state = make_state({"identity_proof": "missing"}, "documents_pending")
    for event in ("sanction", "disburse", "start_verification", "reject"):
        with pytest.raises(ValueError):
            tracker.apply_event(state, event)
    with pytest.raises(ValueError, match="not all complete"):
        tracker.apply_event(state, "submit")
    with pytest.raises(ValueError, match="Unknown event"):
        tracker.apply_event(state, "mark_document")
    assert state.application_status.status_history == []


def test_reject_is_terminal():
    state = make_state({"x": "complete"}, "under_verification")
    tracker.apply_event(state, "reject", reason="land title unclear")
    assert state.application_status.disbursement_status == "rejected"
    with pytest.raises(ValueError):
        tracker.apply_event(state, "submit")
