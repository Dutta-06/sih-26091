"""FastAPI service for the orchestrator (TDD 4, 5.6, 6.5-6.6, 7; TECHNICAL_SETUP 9).

Reads/Writes: CaseState snapshots via orchestrator.persistence; cross-case feedback via orchestrator.stores
Tech: FastAPI; every stage runs through the compiled LangGraph entered at ``session_meta.requested_stage``.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from orchestrator import language, persistence, stores
from orchestrator.graph import agent_node_count, build_graph, run_case
from orchestrator.router import route_conversational_turn
from orchestrator.state import CaseState, EntryStage

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Hyper-Local Business Advisory & Financial Structuring API (SIH 26091)", version="0.2.0")


@lru_cache(maxsize=1)
def workflow():
    return build_graph(with_checkpointer=True)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    current_stage: str
    ran_graph: bool
    state: dict[str, Any]


class DirectRunRequest(BaseModel):
    available_capital: float
    location: str
    business_category: str
    preference_reason: Optional[str] = None


class FieldRequest(BaseModel):
    field: str
    value: str


class EventRequest(BaseModel):
    event: str  # submit | start_verification | sanction | disburse | reject | return_documents (tracker validates)
    actor: str = "officer"
    reason: str = ""
    amount: Optional[float] = None


class ConsentRequest(BaseModel):
    consent: bool = True


class NotificationsRequest(BaseModel):
    messages: list[str]


class GrievanceRequest(BaseModel):
    text: str


class FeedbackRequest(BaseModel):
    district: str
    topic: str
    observation: str
    catalog_id: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)


# --- helpers ------------------------------------------------------------------

def _load(session_id: str) -> CaseState:
    state = persistence.load_case(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return state


def _run(state: CaseState, stage: Optional[EntryStage] = None) -> CaseState:
    if stage:
        state.session_meta.requested_stage = stage
    try:
        result = run_case(workflow(), state)
    except HTTPException:
        raise
    except Exception as exc:  # agent failure: report it, keep the pre-run state saved
        persistence.save_case(state)
        raise HTTPException(status_code=422, detail=f"Pipeline could not complete: {type(exc).__name__}: {exc}") from exc
    result.session_meta.requested_stage = None
    result.session_meta.pending_grievance_text = None
    result.session_meta.pending_transactions = []  # consumed by monitoring; never re-processed
    persistence.save_case(result)
    return result


def summarize(state: CaseState, stage: Optional[str] = "profiling") -> str:
    """Plain-language outcome of the stage just run, built only from values in state."""
    lines: list[str] = []
    if stage == "grievance":
        g = state.grievance_log[-1] if state.grievance_log else None
        return f"Grievance {g.ticket_id} logged as {g.issue_type.replace('_', ' ')} (status {g.status})." if g else ""
    if stage == "scheme_inquiry":
        plan = state.financial_plan
        if plan and plan.policy_explanation:
            return plan.policy_explanation
        return state.scheme_reference or "No scheme explanation is available for this case yet."
    if stage == "monitoring":
        snap = state.monitoring_record[-1] if state.monitoring_record else None
        if snap is None:
            return "No monitoring snapshot was produced."
        lines.append(f"Business health score {snap.health_score:.0f} ({snap.health_band})." if snap.health_score is not None
                     else "Health score not computed from the notifications received.")
        if snap.early_warning_flag:
            lines.append(f"Early warning: {snap.warning_reason}. {snap.suggested_intervention or ''}".strip())
        return "\n".join(lines)
    if stage in ("application", "launch"):
        state = state.model_copy(update={"feasibility_record": None, "financial_plan": None, "entrepreneur_profile": None})
    profile, record, plan, app_status = state.entrepreneur_profile, state.feasibility_record, state.financial_plan, state.application_status
    if profile and profile.constraints:
        lines.append("Constraints: " + " ".join(profile.constraints))
    if record:
        for entry in record.rejection_history:
            lines.append(f"Attempt {entry.attempt_number}: {entry.category} was {entry.verdict.replace('_', ' ')} - "
                         + "; ".join(entry.reasons))
        if record.verdict == "viable":
            lines.append(f"Recommended: {record.selected_category} (viable).")
        elif record.alternatives_exhausted:
            lines.append("No suitable activity passed review within the allowed attempts; rejection is a valid outcome. "
                         "Consider changing capital, location or activity.")
        if record.adversarial_critique:
            notes = [c for c in record.adversarial_critique if "estimates" in c]
            lines.extend(notes[:1])
    elif profile and not state.business_shortlist and not profile.constraints:
        lines.append("No catalog activity is affordable with the stated capital.")
    if not plan and state.session_meta.current_stage == "not_eligible":
        lines.append("Not eligible for the scheme, so feasibility and financial structuring were not run (see constraints).")
    if plan:
        if plan.eligibility_status != "eligible":
            lines.append(f"Not eligible for the scheme: {plan.ineligibility_reason or 'outside scheme range'}.")
        else:
            tier = plan.scheme_tier.display_name if plan.scheme_tier else "scheme"
            lines.append(f"Project cost Rs {plan.computed_project_cost:,.0f}; loan up to Rs {plan.maximum_loan_eligibility:,.0f} "
                         f"under {tier}; quarterly installment Rs {plan.regular_quarterly_installment:,.0f}.")
    if app_status:
        lines.append(f"Application status: {app_status.disbursement_status.replace('_', ' ')}.")
        if app_status.next_required_field:
            lines.append(app_status.next_required_prompt or f"Next, please provide: {app_status.next_required_field}.")
        elif missing := [k.replace("_", " ") for k, v in app_status.checklist.items() if v != "complete"]:
            lines.append("Documents still needed: " + ", ".join(missing) + ".")
    if state.launch_roadmap:
        lines.append(f"Launch roadmap ready with {len(state.launch_roadmap)} phases.")
    return "\n".join(lines)


def _chat(message: str, session_id: Optional[str]) -> ChatResponse:
    existing = persistence.load_case(session_id) if session_id else None
    state, reply, run_graph = route_conversational_turn(message, existing)
    if session_id:
        state.session_meta.session_id = session_id
    if run_graph:
        stage = state.session_meta.requested_stage
        state = _run(state)
        summary = summarize(state, stage)
        if summary:
            lang = state.session_meta.language_code
            reply = f"{reply}\n{language.from_english(summary, lang) if lang != 'en' else summary}"
    else:
        persistence.save_case(state)
    return ChatResponse(session_id=state.session_meta.session_id, reply=reply,
                        current_stage=state.session_meta.current_stage, ran_graph=run_graph, state=state.model_dump())


# --- endpoints ------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "healthy", "service": "sih-26091-orchestrator", "nodes": agent_node_count(workflow())}


@app.post("/session", response_model=ChatResponse)
def session_turn(req: ChatRequest) -> ChatResponse:
    return _chat(req.message, req.session_id)


@app.post("/session/{session_id}/voice", response_model=ChatResponse)
async def session_voice(session_id: str, audio: UploadFile = File(...)) -> ChatResponse:
    try:
        text = language.transcribe(await audio.read())
    except language.LanguageLayerUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return _chat(text, session_id if persistence.load_case(session_id) else None)


@app.post("/pipeline/run")
def pipeline_run(req: DirectRunRequest) -> dict[str, Any]:
    reason = f" because {req.preference_reason}" if req.preference_reason else ""
    message = f"I have Rs {req.available_capital:.0f} and want to start {req.business_category} in {req.location}{reason}"
    state, _, _ = route_conversational_turn(message, None)
    p = state.entrepreneur_profile
    state.entrepreneur_profile = p.model_copy(update={  # direct inputs are authoritative over text parsing
        "location_query": req.location, "available_capital": req.available_capital,
        "business_preference": p.business_preference or req.business_category,
        "location": p.location.model_copy(update={"raw_query": req.location})})
    state.session_meta.session_id = f"direct_{uuid.uuid4().hex[:8]}"
    state = _run(state, "profiling")
    return {"session_id": state.session_meta.session_id, "summary": summarize(state, "profiling"), "state": state.model_dump()}


@app.get("/state/{session_id}")
def get_state(session_id: str) -> dict[str, Any]:
    return _load(session_id).model_dump()


@app.post("/application/{session_id}/field")
def application_field(session_id: str, req: FieldRequest) -> dict[str, Any]:
    state = _load(session_id)
    if not state.financial_plan or state.financial_plan.eligibility_status != "eligible":
        raise HTTPException(status_code=409, detail="No eligible financial plan; the application has not started.")
    from module2_financial.documentation_agent import record_field

    accepted, message = record_field(state, req.field, req.value)
    if not accepted:
        persistence.save_case(state)
        return {"accepted": False, "message": message, "state": state.model_dump()}
    state = _run(state, "application")
    return {"accepted": True, "message": message, "summary": summarize(state, "application"), "state": state.model_dump()}


@app.post("/application/{session_id}/event")
def application_event(session_id: str, req: EventRequest) -> dict[str, Any]:
    state = _load(session_id)
    from module2_financial.application_tracker import apply_event

    try:
        update = apply_event(state, req.event, actor=req.actor, reason=req.reason, amount=req.amount)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    state = state.model_copy(update=update)
    if state.application_status and state.application_status.disbursement_status == "disbursed":
        state = _run(state, "launch")
    else:
        persistence.save_case(state)
    return {"disbursement_status": state.application_status.disbursement_status if state.application_status else None,
            "summary": summarize(state, "launch"), "state": state.model_dump()}


@app.post("/monitoring/{session_id}/consent")
def monitoring_consent(session_id: str, req: ConsentRequest) -> dict[str, Any]:
    state = _load(session_id)
    state.session_meta.consent_sms_monitoring = req.consent
    if not req.consent:
        state.session_meta.pending_transactions = []
    persistence.save_case(state)
    return {"consent_sms_monitoring": req.consent}


@app.post("/monitoring/{session_id}/notifications")
def monitoring_notifications(session_id: str, req: NotificationsRequest) -> dict[str, Any]:
    state = _load(session_id)
    if not state.session_meta.consent_sms_monitoring:
        raise HTTPException(status_code=403, detail="Monitoring consent has not been given.")
    from data_connectors.sms_parser import parse_notifications

    records = parse_notifications(list(req.messages))  # raw text is discarded here
    state.session_meta.pending_transactions = records
    state = _run(state, "monitoring")
    return {"transactions_parsed": len(records), "summary": summarize(state, "monitoring"), "state": state.model_dump()}


@app.post("/grievance/{session_id}")
def grievance(session_id: str, req: GrievanceRequest) -> dict[str, Any]:
    state = _load(session_id)
    state.session_meta.pending_grievance_text = req.text
    state.session_meta.last_intent = "raise_grievance"
    state = _run(state, "grievance")
    return {"grievance": state.grievance_log[-1].model_dump() if state.grievance_log else None, "state": state.model_dump()}


def _feedback(kind: str, req: FeedbackRequest) -> dict[str, Any]:
    stores.add_local_feedback(kind, req.district, req.topic, req.observation, catalog_id=req.catalog_id, rating=req.rating)
    return {"stored": True, "kind": kind}


@app.post("/feedback")
def funded_feedback(req: FeedbackRequest) -> dict[str, Any]:
    return _feedback("funded_entrepreneur", req)


@app.post("/survey")
def resident_survey(req: FeedbackRequest) -> dict[str, Any]:
    return _feedback("resident_survey", req)


def build_geojson(state: CaseState) -> dict[str, Any]:
    features: list[dict[str, Any]] = []

    def point(lat, lon, props):
        if lat is not None and lon is not None:
            features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props})

    loc = state.entrepreneur_profile.location if state.entrepreneur_profile else None
    reach = state.market_reach_intel or (state.market_intelligence.market_reach if state.market_intelligence else None)
    comp = state.competitor_intel or (state.market_intelligence.competitor if state.market_intelligence else None)
    if loc:
        point(loc.latitude, loc.longitude, {
            "kind": "entrepreneur", "name": loc.raw_query, "resolution_method": loc.resolution_method,
            "confidence": loc.source_confidence, "radius_km": reach.radius_km if reach else None})
    for d in (reach.distribution_points if reach else []):
        point(d.latitude, d.longitude, {"kind": "distribution_point", "name": d.name, "type": d.type,
                                         "distance_km": d.distance_km, "confidence": d.source_confidence})
    for c in (comp.identified_competitors if comp else []):
        point(c.latitude, c.longitude, {"kind": "competitor", "name": c.name, "distance_km": c.distance_km,
                                         "source": c.source, "confidence": comp.source_confidence})
    return {"type": "FeatureCollection", "features": features}


@app.get("/map/{session_id}")
def map_geojson(session_id: str) -> dict[str, Any]:
    return build_geojson(_load(session_id))


@app.get("/map/{session_id}/view", response_class=HTMLResponse)
def map_view(session_id: str) -> str:
    _load(session_id)
    return (STATIC / "map.html").read_text(encoding="utf-8").replace("{{SESSION_ID}}", session_id)
