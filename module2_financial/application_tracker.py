"""Application Tracker and Disbursement Agent (Module 2, Section 6.6).

Reads: state.application_status
Writes: state.application_status.checklist, state.application_status.disbursement_status
Tech: Rule-based checklist state machine (verification -> sanction -> disbursement).
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from orchestrator.state import ApplicationStatus, CaseState


def run(state: CaseState) -> dict[str, Any]:
    app_status = state.application_status
    if not app_status:
        app_status = ApplicationStatus()

    plan = state.financial_plan

    # 1. Determine checklist completion
    all_complete = all(status == "complete" for status in app_status.checklist.values())
    
    # 2. State Machine Transitions
    if not all_complete:
        app_status.disbursement_status = "documents_pending"
    else:
        if app_status.disbursement_status in ["not_applied", "documents_pending"]:
            app_status.disbursement_status = "under_verification"
        elif app_status.disbursement_status == "under_verification":
            app_status.disbursement_status = "sanctioned"
            app_status.sanctioned_amount = plan.maximum_loan_eligibility if plan else 0.0
        elif app_status.disbursement_status == "sanctioned":
            app_status.disbursement_status = "disbursed"
            app_status.disbursement_date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    return {"application_status": app_status}
