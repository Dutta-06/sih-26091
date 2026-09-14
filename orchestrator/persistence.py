"""Session persistence and checkpointing (TDD 4.1, TECHNICAL_SETUP 4).

Reads/Writes: whole ``CaseState`` snapshots per session
Tech: LangGraph ``MemorySaver`` checkpointer for in-run state (``langgraph-checkpoint-sqlite`` is not a
dependency), plus durable case snapshots so a case can be resumed after days or months:
* ``CHECKPOINT_BACKEND=sqlite`` (default): ``orchestrator.stores.save_session/load_session`` in SQLite at
  ``settings.sqlite_db_path`` — survives process restarts.
* ``CHECKPOINT_BACKEND=memory``: snapshots kept in this process only (tests/dev).

CLI: ``python -m orchestrator.persistence --init-db`` | ``--test-checkpoint``
"""

from __future__ import annotations

import sys
from typing import Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel
from langgraph.graph import END, START, StateGraph

from config.settings import settings
from orchestrator import state as state_module
from orchestrator import stores
from orchestrator.state import CaseState, utc_now_iso

# Allow the checkpointer to restore the CaseState sub-models written by nodes (and nothing else).
_STATE_MODELS = [("orchestrator.state", name) for name, obj in vars(state_module).items()
                 if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == "orchestrator.state"]
_memory_checkpointer = MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=_STATE_MODELS))
_memory_snapshots: dict[str, str] = {}


def get_checkpointer() -> MemorySaver:
    return _memory_checkpointer


def save_case(state: CaseState) -> None:
    meta = state.session_meta.model_copy(update={"updated_at": utc_now_iso()})
    state = state.model_copy(update={"session_meta": meta})
    payload = state.model_dump_json()
    if settings.checkpoint_backend == "sqlite":
        stores.save_session(meta.session_id, payload)
    else:
        _memory_snapshots[meta.session_id] = payload


def load_case(session_id: str) -> Optional[CaseState]:
    if settings.checkpoint_backend == "sqlite":
        payload = stores.load_session(session_id)
    else:
        payload = _memory_snapshots.get(session_id)
    return CaseState.model_validate_json(payload) if payload else None


def init_db() -> None:
    with stores.connect():
        pass
    print(f"Initialised SQLite store at {settings.sqlite_db_path}")


def test_checkpoint() -> bool:
    class MinimalState(TypedDict):
        status: str

    builder = StateGraph(MinimalState)
    builder.add_node("step", lambda s: {"status": "persisted_ok"})
    builder.add_edge(START, "step")
    builder.add_edge("step", END)
    app = builder.compile(checkpointer=get_checkpointer())
    config = {"configurable": {"thread_id": "persistence_selftest"}}
    app.invoke({"status": "initial"}, config=config)
    assert app.get_state(config).values.get("status") == "persisted_ok"
    print("Checkpoint persistence verified.")
    return True


if __name__ == "__main__":
    if "--init-db" in sys.argv:
        init_db()
    if "--test-checkpoint" in sys.argv:
        test_checkpoint()
