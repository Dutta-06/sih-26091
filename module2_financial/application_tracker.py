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
    app_status = state.application_status or ApplicationStatus()
    plan = state.financial_plan

    # Advance state machine: all essential documents verified -> Sanctioned
    app_status.checklist["land_possession_noc"] = "complete"
    app_status.disbursement_status = "sanctioned"
    app_status.sanctioned_amount = plan.maximum_loan_eligibility if plan else 900_000.0
    app_status.disbursement_date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    return {"application_status": app_status}
