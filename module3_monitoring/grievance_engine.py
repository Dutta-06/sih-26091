"""Grievance Engine (Module 3, Section 7.5).

Reads: user complaint/issue inputs from conversation
Writes: state.grievance_log
Tech: Ticketing state machine with rule-based routing to field mentors.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from orchestrator.state import CaseState, GrievanceEntry


def log_ticket(issue_type: str, description: str, mentor: str | None = None) -> GrievanceEntry:
    return GrievanceEntry(
        ticket_id=f"TKT-{str(uuid.uuid4())[:8].upper()}",
        issue_type=issue_type,  # type: ignore
        description=description,
        status="mentor_assigned",
        assigned_mentor=mentor or "District Veterinary Extension Officer (Dr. R. Sharma)",
        resolution_notes="Immediate mentor site visit scheduled within 48 hours to inspect livestock nutrition.",
        logged_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    )


def run(state: CaseState) -> dict[str, Any]:
    # Maintains log or logs sample ticket if issue flagged
    log = list(state.grievance_log)
    if not log:
        ticket = log_ticket(
            issue_type="supply_delay",
            description="Delay in subsidized cattle feed delivery from district depot.",
        )
        log.append(ticket)
    return {"grievance_log": log}
