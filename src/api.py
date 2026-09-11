"""
FastAPI app for the Module 1 local-intelligence prototype.

NOTE ON PROVENANCE: this file did not exist in the repository as supplied
(there was no src/api.py) — only the LangGraph wiring in src/graph.py and
the three agents. It is created here, minimally, purely so the requested
flow

    Swagger -> FastAPI /analyze -> LangGraph -> agents -> CaseState -> JSON

is actually runnable end-to-end. It intentionally does nothing beyond
translating a request into a CaseState, calling
src.graph.run_market_intelligence, and returning the result — no new
business logic, no new schemas (reuses src/schemas.py's CaseState /
SelectedBusiness as-is).

DATA_MODE (src/config.py, default "mock") governs whether the graph's
three agents read from data/mock.db or use the live-adapter tiers; this
endpoint does not need to know which, since that's resolved inside each
agent. Interactive docs are FastAPI's default: /docs (Swagger UI) and
/redoc.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.config import settings
from src.graph import run_market_intelligence
from src.schemas import CaseState, SelectedBusiness

app = FastAPI(
    title="Hyper-Local Business Advisory — Module 1 Local Intelligence",
    description=(
        "Runs the Competitor, Pricing, and Supply Chain agents (fanned out via LangGraph) for a "
        "given entrepreneur profile and selected business, and returns the merged case state. "
        f"Current DATA_MODE default: '{settings.data_mode}' (see src/config.py / DATA_MODE env var)."
    ),
    version="0.1.0",
)


class LocationIn(BaseModel):
    village: Optional[str] = None
    block: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SelectedBusinessIn(BaseModel):
    name: str
    sector: Optional[str] = None
    ncs_code: Optional[str] = None


class AnalyzeRequest(BaseModel):
    case_id: str = Field(..., description="Caller-supplied case identifier.")
    location: LocationIn
    available_capital: Optional[float] = None
    selected_business: SelectedBusinessIn

    # Per-agent knobs, passed straight through to the graph (see
    # src/graph.py::MarketIntelligenceGraphState) — all optional.
    radius_meters: int = 5000
    supply_chain_radius_meters: int = 15000
    commodity: Optional[str] = Field(
        default=None,
        description="Product/commodity name for the Pricing Agent (required in mock mode to get "
        "anything other than INSUFFICIENT_DATA — see data/mock.db's `prices` table).",
    )
    unit: Optional[str] = None
    base_reference_price: Optional[float] = Field(
        default=None,
        description="Only used by the real-data purchasing-power estimate tier (DATA_MODE=real); "
        "the mock tier does not use it.",
    )
    district_population: Optional[float] = None
    state_population: Optional[float] = None


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "data_mode": settings.data_mode}


@app.post("/analyze", response_model=None)
async def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    """Runs the Competitor / Pricing / Supply Chain agents in parallel
    (via the existing LangGraph fan-out/fan-in graph) for the given case,
    and returns the merged CaseState as JSON."""
    case_state = CaseState(
        case_id=request.case_id,
        entrepreneur_profile={
            "location": request.location.model_dump(),
            "available_capital": request.available_capital,
        },
        selected_business=SelectedBusiness(**request.selected_business.model_dump()),
    )

    updated_state = await run_market_intelligence(
        case_state,
        radius_meters=request.radius_meters,
        supply_chain_radius_meters=request.supply_chain_radius_meters,
        commodity=request.commodity,
        unit=request.unit,
        base_reference_price=request.base_reference_price,
        district_population=request.district_population,
        state_population=request.state_population,
    )

    return updated_state.model_dump(mode="json")
