"""
Shared case state persistence (TDD Section 4.1: "State management" and
"Session persistence").

This build has no pre-existing orchestrator or persistence layer to plug
into (scratch build, per instruction). CaseStateStore is the seam the
future orchestrator's checkpointing (Section 4.1: "checkpoint state so a
case can be resumed after a gap of days or months") is expected to
implement against. InMemoryCaseStateStore is a placeholder only — it does
not persist across process restarts and must be swapped for a real
backing store (e.g. a database-backed LangGraph checkpointer) before this
is anything but a dev/test harness. This is called out explicitly rather
than left implicit so it isn't mistaken for a finished persistence layer.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone

from src.schemas import CaseState


class CaseStateStore(abc.ABC):
    @abc.abstractmethod
    async def get(self, case_id: str) -> CaseState | None: ...

    @abc.abstractmethod
    async def save(self, case_state: CaseState) -> None: ...


class InMemoryCaseStateStore(CaseStateStore):
    """Dev/test placeholder only. Not durable across process restarts."""

    def __init__(self) -> None:
        self._cases: dict[str, CaseState] = {}

    async def get(self, case_id: str) -> CaseState | None:
        return self._cases.get(case_id)

    async def save(self, case_state: CaseState) -> None:
        case_state.updated_at = datetime.now(timezone.utc).isoformat()
        self._cases[case_state.case_id] = case_state
