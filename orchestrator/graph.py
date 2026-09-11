"""
LangGraph wiring for this two-agent build (TECHNICAL_SETUP.md Section 4).

Only Market Reach Agent and Opportunity Agent are registered here (see
IMPLEMENTATION_PLAN.md Section 2 for full scope). In the original six-agent
design (Figure 3) these two run in parallel with Risk, Competitor, Pricing,
and Supply Chain, fanning into a shared synthesis node. This build runs them
sequentially instead, because the Opportunity Agent's saturation proxy here
reuses the Market Reach Agent's POI/population output (IMPLEMENTATION_PLAN.md
Section 4) -- a real dependency that doesn't exist in the original design,
where saturation comes from the Competitor Agent instead.

When the Competitor and Pricing agents are added later, market_reach and
opportunity can move back onto parallel branches fanning into a shared
synthesis node, matching the original design exactly; opportunity_agent.py
already prefers `state.market_intelligence.competitor` the moment it's
populated, so no agent code changes would be needed, only this graph's edges.

IMPLEMENTATION NOTE on the `def run(state) -> CaseState` node contract from
TECHNICAL_SETUP.md Section 1: with a Pydantic model as the graph's state
schema, this installed LangGraph version (0.2.x) only merges fields that
pydantic considers "explicitly set" on the object a node returns -- it does
not diff nested in-place mutations against the schema's defaults. Both
agents therefore explicitly reassign the top-level field they changed
(e.g. `state.market_intelligence = market_intelligence`) rather than only
mutating a nested attribute, so the update is actually picked up. Any new
node added to this graph following the same file-per-agent convention needs
to follow the same reassignment pattern for the same reason.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from module1_feasibility import market_reach_agent, opportunity_agent
from orchestrator.state import CaseState


def build_graph():
    graph = StateGraph(CaseState)
    graph.add_node("market_reach", market_reach_agent.run)
    graph.add_node("opportunity", opportunity_agent.run)

    graph.add_edge(START, "market_reach")
    graph.add_edge("market_reach", "opportunity")
    graph.add_edge("opportunity", END)

    return graph.compile()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Compile (and optionally dry-run) the agent graph")
    parser.add_argument(
        "--dry-run", action="store_true", help="Compile the graph and print its nodes without running it"
    )
    args = parser.parse_args()

    compiled = build_graph()
    if args.dry_run:
        print("Graph compiled successfully.")
        print("Nodes:", list(compiled.get_graph().nodes))
        return
    print("Graph compiled successfully. Use run_pipeline.py to execute it against a sample case.")


if __name__ == "__main__":
    main()
