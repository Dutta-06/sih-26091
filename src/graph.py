"""
LangGraph wiring for the Module 1 local-intelligence fan-out (TDD Section
4.2: "Parallel local intelligence gathering: for the selected activity,
run market reach, opportunity, risk, competitor, pricing, and supply chain
analysis concurrently" and Section 3.1/3.3 diagrams).

This build only implements three of the six local-intelligence agents
(Competitor, Pricing, Supply Chain). The graph is built so the other three
(Market Reach, Opportunity, Risk) can be added as additional parallel
branches from the same entry point without restructuring anything here —
each agent writes to its own key in market_intelligence and the merge node
already treats market_intelligence as an extensible object
(MarketIntelligence.model_config = extra="allow").

Graph shape:

    START --> competitor_node   \
          --> pricing_node       >--> merge_node --> END
          --> supply_chain_node /

The three agent nodes have no edges between them, so LangGraph schedules
them in the same superstep (i.e. concurrently); merge_node has incoming
edges from all three and therefore only runs once all three have produced
output, giving the fan-out/fan-in shape TDD Section 4.2 and Figure 3
describe.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.competitor_agent import CompetitorAgent
from src.agents.pricing_agent import PricingAgent
from src.agents.supply_chain_agent import SupplyChainAgent
from src.config import settings
from src.schemas import CaseState, CompetitorAgentOutput, PricingAgentOutput, SupplyChainAgentOutput
from src.state_store import CaseStateStore, InMemoryCaseStateStore


class MarketIntelligenceGraphState(TypedDict, total=False):
    # Input
    case_state_json: dict[str, Any]
    radius_meters: int
    supply_chain_radius_meters: int
    commodity: str | None
    unit: str | None
    base_reference_price: float | None
    district_population: float | None
    state_population: float | None

    # Fan-out outputs (each node writes only its own key -> no concurrent-
    # write conflicts on a shared key)
    competitor_result: dict[str, Any]
    pricing_result: dict[str, Any]
    supply_chain_result: dict[str, Any]

    # Fan-in output
    case_state_json_out: dict[str, Any]


def _load_case_state(state: MarketIntelligenceGraphState) -> CaseState:
    return CaseState.model_validate(state["case_state_json"])


async def _competitor_node(state: MarketIntelligenceGraphState) -> dict[str, Any]:
    case_state = _load_case_state(state)
    agent = CompetitorAgent()
    result = await agent.run(
        case_state,
        radius_meters=state.get("radius_meters") or settings.competitor_search_radius_meters,
        district_population=state.get("district_population"),
        state_population=state.get("state_population"),
    )
    return {"competitor_result": result.model_dump(mode="json")}


async def _pricing_node(state: MarketIntelligenceGraphState) -> dict[str, Any]:
    case_state = _load_case_state(state)
    agent = PricingAgent()
    result = await agent.run(
        case_state,
        commodity=state.get("commodity"),
        unit=state.get("unit"),
        base_reference_price=state.get("base_reference_price"),
    )
    return {"pricing_result": result.model_dump(mode="json")}


async def _supply_chain_node(state: MarketIntelligenceGraphState) -> dict[str, Any]:
    case_state = _load_case_state(state)
    agent = SupplyChainAgent()
    result = await agent.run(
        case_state,
        radius_meters=state.get("supply_chain_radius_meters") or settings.supply_chain_search_radius_meters,
    )
    return {"supply_chain_result": result.model_dump(mode="json")}


def build_market_intelligence_graph(store: CaseStateStore | None = None):
    """Builds and compiles the fan-out/fan-in graph. `store` defaults to an
    in-memory placeholder (see src/state_store.py) — pass a real
    CaseStateStore implementation in production."""

    case_state_store = store or InMemoryCaseStateStore()

    async def _merge_node(state: MarketIntelligenceGraphState) -> dict[str, Any]:
        case_state = _load_case_state(state)
        case_state.market_intelligence.competitor = CompetitorAgentOutput.model_validate(
            state["competitor_result"]
        )
        case_state.market_intelligence.pricing = PricingAgentOutput.model_validate(state["pricing_result"])
        case_state.market_intelligence.supply_chain = SupplyChainAgentOutput.model_validate(
            state["supply_chain_result"]
        )
        await case_state_store.save(case_state)
        return {"case_state_json_out": case_state.model_dump(mode="json")}

    graph = StateGraph(MarketIntelligenceGraphState)
    graph.add_node("competitor", _competitor_node)
    graph.add_node("pricing", _pricing_node)
    graph.add_node("supply_chain", _supply_chain_node)
    graph.add_node("merge", _merge_node)

    graph.add_edge(START, "competitor")
    graph.add_edge(START, "pricing")
    graph.add_edge(START, "supply_chain")

    graph.add_edge("competitor", "merge")
    graph.add_edge("pricing", "merge")
    graph.add_edge("supply_chain", "merge")

    graph.add_edge("merge", END)

    return graph.compile()


async def run_market_intelligence(
    case_state: CaseState,
    store: CaseStateStore | None = None,
    **kwargs: Any,
) -> CaseState:
    """Convenience entry point: runs the compiled graph for one case and
    returns the updated CaseState."""
    compiled = build_market_intelligence_graph(store)
    result = await compiled.ainvoke({"case_state_json": case_state.model_dump(mode="json"), **kwargs})
    return CaseState.model_validate(result["case_state_json_out"])
