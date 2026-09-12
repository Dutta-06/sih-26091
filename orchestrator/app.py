"""FastAPI Web Service for Central Orchestrator (Section 9).

Exposes REST endpoints for:
- /session: Initialize or resume an entrepreneur session
- /chat: Conversational turn with slot filling and assistant responses
- /pipeline/run: Programmatic direct execution of the multi-agent graph
- /state/{session_id}: Retrieve persisted CaseState
"""

from __future__ import annotations

import uuid
from typing import Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from orchestrator.graph import build_graph
from orchestrator.persistence import get_checkpointer
from orchestrator.router import route_conversational_turn
from orchestrator.state import CaseState, SessionMeta


app = FastAPI(
    title="Hyper-Local Business Advisory & Financial Structuring API",
    description="Central multi-agent orchestration pipeline for concessional credit advisory (SIH 26091)",
    version="1.0.0",
)

# Global compiled StateGraph instance
workflow_app = build_graph(with_checkpointer=True)
sessions: dict[str, CaseState] = {}


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    current_stage: str
    is_complete: bool
    state: Optional[dict[str, Any]] = None


class DirectRunRequest(BaseModel):
    available_capital: float = 100_000.0
    location: str = "Bhadohi, Bhadohi, Uttar Pradesh"
    business_category: str = "Dairy Farming"


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "sih-26091-orchestrator", "nodes": 24}


@app.post("/session", response_model=ChatResponse)
def create_or_resume_session(req: ChatRequest):
    session_id = req.session_id or f"session_{str(uuid.uuid4())[:8]}"
    existing_state = sessions.get(session_id)

    updated_state, reply = route_conversational_turn(req.message, existing_state)
    updated_state.session_meta.session_id = session_id
    sessions[session_id] = updated_state

    is_complete = False
    # If all slots filled, execute the graph
    if updated_state.session_meta.current_stage == "feasibility_assessment":
        config = {"configurable": {"thread_id": session_id}}
        result = workflow_app.invoke(updated_state, config=config)
        final_state = CaseState.model_validate(result) if isinstance(result, dict) else result
        sessions[session_id] = final_state
        is_complete = True
        reply += (
            f"\n\n[Analysis Complete] Feasible Project Cost: Rs. {final_state.financial_plan.computed_project_cost:,.2f} | "
            f"Loan Eligibility: Rs. {final_state.financial_plan.maximum_loan_eligibility:,.2f} under {final_state.financial_plan.scheme_tier.display_name}. "
            f"Adversarial Verdict: {final_state.feasibility_record.verdict.upper()}."
        )

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        current_stage=sessions[session_id].session_meta.current_stage,
        is_complete=is_complete,
        state=sessions[session_id].model_dump(),
    )


@app.post("/pipeline/run")
def run_direct_pipeline(req: DirectRunRequest):
    """Direct programmatic run of the full graph."""
    session_id = f"direct_{str(uuid.uuid4())[:8]}"
    initial_msg = (
        f"I have {req.available_capital:,.0f} rupees available margin capital and want to start a {req.business_category} in {req.location}"
    )
    init_state, _ = route_conversational_turn(initial_msg)
    init_state.session_meta.session_id = session_id

    config = {"configurable": {"thread_id": session_id}}
    result = workflow_app.invoke(init_state, config=config)
    final_state = CaseState.model_validate(result) if isinstance(result, dict) else result
    sessions[session_id] = final_state

    return {
        "session_id": session_id,
        "profile": final_state.entrepreneur_profile,
        "feasibility": final_state.feasibility_record,
        "financial_plan": final_state.financial_plan,
        "application_status": final_state.application_status,
        "monitoring_record": final_state.monitoring_record,
        "launch_roadmap": final_state.launch_roadmap,
    }


@app.get("/state/{session_id}")
def get_session_state(session_id: str):
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session ID not found")
    return state.model_dump()
