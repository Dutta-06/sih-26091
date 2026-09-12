"""Session Persistence and Checkpointing Layer (Section 4).

Manages checkpointing so a case state can be paused, persisted, and resumed
across long lifecycles (profiling -> feasibility -> sanction -> monitoring).
"""

from __future__ import annotations

import sys
from typing import TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

# In-memory singleton checkpointer
_memory_checkpointer = MemorySaver()


def get_checkpointer():
    """Returns the configured checkpointer backend (MemorySaver for development/testing)."""
    return _memory_checkpointer


def test_checkpoint() -> bool:
    """CLI test helper per TECHNICAL_SETUP.md Section 4:
    python -m orchestrator.persistence --test-checkpoint
    """
    class MinimalTestState(TypedDict):
        status: str

    def node_step(state: MinimalTestState):
        return {"status": "persisted_ok"}

    builder = StateGraph(MinimalTestState)
    builder.add_node("test_step", node_step)
    builder.set_entry_point("test_step")
    builder.set_finish_point("test_step")

    checkpointer = get_checkpointer()
    app = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "test_persistence_session_001"}}
    app.invoke({"status": "initial"}, config=config)

    retrieved = app.get_state(config)
    assert retrieved is not None
    assert retrieved.values.get("status") == "persisted_ok"
    print("Checkpoint persistence verified successfully!")
    return True


if __name__ == "__main__":
    if "--test-checkpoint" in sys.argv:
        test_checkpoint()
