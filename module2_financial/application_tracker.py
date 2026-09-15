"""Application Tracker and Disbursement (Module 2, TDD 6.6 / TECHNICAL_SETUP.md 6.6).

Reads: state.application_status (checklist, disbursement_status), state.financial_plan.maximum_loan_eligibility
Writes: state.application_status.disbursement_status, .status_history, .sanctioned_amount, .disbursement_date
Tech: explicit enum-based state machine. The node only moves between not_applied / documents_pending /
      submitted based on the document checklist; verification, sanction, disbursement and rejection happen
      only through officer events (apply_event), never automatically.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from orchestrator.state import ApplicationStatus, CaseState, StatusTransition, utc_now_iso


class ApplicationState(str, Enum):
    NOT_APPLIED = "not_applied"
    DOCUMENTS_PENDING = "documents_pending"
    SUBMITTED = "submitted"
    UNDER_VERIFICATION = "under_verification"
    SANCTIONED = "sanctioned"
    DISBURSED = "disbursed"
    REJECTED = "rejected"


class ChecklistState(str, Enum):
    COMPLETE = "complete"
    PENDING = "pending"
    MISSING = "missing"


S = ApplicationState
TRANSITIONS: dict[tuple[ApplicationState, str], ApplicationState] = {
    (S.NOT_APPLIED, "request_documents"): S.DOCUMENTS_PENDING,
    (S.NOT_APPLIED, "submit"): S.SUBMITTED,
    (S.DOCUMENTS_PENDING, "submit"): S.SUBMITTED,
    (S.SUBMITTED, "return_documents"): S.DOCUMENTS_PENDING,
    (S.UNDER_VERIFICATION, "return_documents"): S.DOCUMENTS_PENDING,
    (S.SUBMITTED, "start_verification"): S.UNDER_VERIFICATION,
    (S.UNDER_VERIFICATION, "sanction"): S.SANCTIONED,
    (S.SANCTIONED, "disburse"): S.DISBURSED,
    (S.SUBMITTED, "reject"): S.REJECTED,
    (S.UNDER_VERIFICATION, "reject"): S.REJECTED,
    (S.SANCTIONED, "reject"): S.REJECTED,
}
EVENTS = sorted({event for _, event in TRANSITIONS})


def allowed_events(status: str) -> list[str]:
    return [event for (src, event) in TRANSITIONS if src == ApplicationState(status)]


def checklist_complete(checklist: dict[str, str]) -> bool:
    return bool(checklist) and all(ChecklistState(v) is ChecklistState.COMPLETE for v in checklist.values())


def _transition(app: ApplicationStatus, event: str, actor: str, reason: str) -> ApplicationState:
    current = ApplicationState(app.disbursement_status)
    target = TRANSITIONS.get((current, event))
    if target is None:
        raise ValueError(f"Illegal transition: '{event}' from '{current.value}' (allowed: {allowed_events(current)})")
    app.status_history.append(StatusTransition(from_status=current.value, to_status=target.value,
                                               reason=reason, actor=actor))
    app.disbursement_status = target.value
    return target


def apply_event(state: CaseState, event: str, actor: str = "officer", reason: str = "",
                amount: Optional[float] = None) -> dict[str, Any]:
    """Apply one event; mutates ``state.application_status`` and returns the partial update."""
    if event not in EVENTS:
        raise ValueError(f"Unknown event '{event}' (known: {EVENTS})")
    app = state.application_status or ApplicationStatus()
    if event == "submit" and not checklist_complete(app.checklist):
        raise ValueError("Cannot submit: required documents are not all complete.")
    if event == "sanction":
        cap = state.financial_plan.maximum_loan_eligibility if state.financial_plan else 0.0
        amount = cap if amount is None else float(amount)
        if amount <= 0:
            raise ValueError("Sanction requires a positive amount (no loan eligibility on record).")
        if cap > 0 and amount > cap + 0.5:
            raise ValueError(f"Sanction amount {amount:,.0f} exceeds maximum loan eligibility {cap:,.0f}.")
    _transition(app, event, actor, reason)
    if event == "sanction":
        app.sanctioned_amount = round(amount, 2)
    elif event == "disburse":
        app.disbursement_date = utc_now_iso()[:10]
    state.application_status = app
    return {"application_status": app}


def run(state: CaseState) -> dict[str, Any]:
    app = (state.application_status or ApplicationStatus()).model_copy(deep=True)
    current = ApplicationState(app.disbursement_status)
    if current in (S.NOT_APPLIED, S.DOCUMENTS_PENDING) and app.checklist:
        if checklist_complete(app.checklist):
            _transition(app, "submit", "system", "All required documents marked complete.")
        elif current is S.NOT_APPLIED:
            pending = [k for k, v in app.checklist.items() if v != ChecklistState.COMPLETE.value]
            _transition(app, "request_documents", "system", f"Outstanding documents: {', '.join(pending)}")
    return {"application_status": app}
