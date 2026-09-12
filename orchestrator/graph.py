"""Master LangGraph StateGraph Orchestration Definition.

Implements the multi-agent control flow defined in Technical Setup Section 2 & 4
and Technical Design Document Figure 2 & Figure 3:
- Fan-out to 6 parallel Module 1 intelligence agents
- Fan-in to SWOT Synthesis
- Adversarial Review red-team pass with conditional rejection loop back to Business Discovery
- Deterministic Module 2 Financial Engine -> Financial Analyst -> Stress Test -> Policy -> Documentation -> Tracker
- Module 3 Post-disbursement Lifecycle: Procurement -> Roadmap -> Monitoring -> Health Score -> Grievance -> Outcome Loop.
"""

from __future__ import annotations

import sys
from typing import Any
from langgraph.graph import END, StateGraph

from orchestrator.state import CaseState
from orchestrator.persistence import get_checkpointer

# Import Module 1 agents
import module1_feasibility.profiling_agent as profiling_agent
import module1_feasibility.discovery_agent as discovery_agent
import module1_feasibility.market_reach_agent as market_reach_agent
import module1_feasibility.opportunity_agent as opportunity_agent
import module1_feasibility.risk_agent as risk_agent
import module1_feasibility.competitor_agent as competitor_agent
import module1_feasibility.pricing_agent as pricing_agent
import module1_feasibility.supply_chain_agent as supply_chain_agent
import module1_feasibility.swot_synthesis as swot_synthesis
import module1_feasibility.adversarial_review as adversarial_review

# Import Module 2 nodes
import module2_financial.financial_engine as financial_engine
import module2_financial.financial_analyst_agent as financial_analyst_agent
import module2_financial.scenario_digital_twin as scenario_digital_twin
import module2_financial.policy_scheme_agent as policy_scheme_agent
import module2_financial.documentation_agent as documentation_agent
import module2_financial.application_tracker as application_tracker

# Import Module 3 nodes
import module3_monitoring.procurement_coordinator as procurement_coordinator
import module3_monitoring.launch_copilot as launch_copilot
import module3_monitoring.ongoing_monitoring_agent as ongoing_monitoring_agent
import module3_monitoring.health_score_agent as health_score_agent
import module3_monitoring.grievance_engine as grievance_engine
import module3_monitoring.outcome_learning_loop as outcome_learning_loop


def route_adversarial_verdict(state: CaseState) -> str:
    """Conditional Edge:
    - If adversarial review outputs 'not_recommended' or 'marginal', loop back to 'discovery_agent'
      with the candidate added to rejection history.
    - If 'viable', advance to Module 2 'financial_engine'.
    """
    verdict = "viable"
    if state.feasibility_record:
        verdict = state.feasibility_record.verdict

    if verdict in ("not_recommended", "marginal"):
        return "discovery_agent"
    return "financial_engine"


def build_graph(with_checkpointer: bool = True):
    """Assembles the compiled StateGraph across all 3 modules."""
    workflow = StateGraph(CaseState)

    # ---------------------------------------------------------
    # Register Module 1 Nodes
    # ---------------------------------------------------------
    workflow.add_node("profiling_agent", profiling_agent.run)
    workflow.add_node("discovery_agent", discovery_agent.run)

    # 6 Parallel Local Intelligence Nodes
    workflow.add_node("market_reach_agent", market_reach_agent.run)
    workflow.add_node("opportunity_agent", opportunity_agent.run)
    workflow.add_node("risk_agent", risk_agent.run)
    workflow.add_node("competitor_agent", competitor_agent.run)
    workflow.add_node("pricing_agent", pricing_agent.run)
    workflow.add_node("supply_chain_agent", supply_chain_agent.run)

    workflow.add_node("swot_synthesis", swot_synthesis.run)
    workflow.add_node("adversarial_review", adversarial_review.run)

    # ---------------------------------------------------------
    # Register Module 2 Nodes
    # ---------------------------------------------------------
    workflow.add_node("financial_engine", financial_engine.run)
    workflow.add_node("financial_analyst", financial_analyst_agent.run)
    workflow.add_node("scenario_digital_twin", scenario_digital_twin.run)
    workflow.add_node("policy_scheme", policy_scheme_agent.run)
    workflow.add_node("documentation", documentation_agent.run)
    workflow.add_node("application_tracker", application_tracker.run)

    # ---------------------------------------------------------
    # Register Module 3 Nodes
    # ---------------------------------------------------------
    workflow.add_node("procurement_coordinator", procurement_coordinator.run)
    workflow.add_node("launch_copilot", launch_copilot.run)
    workflow.add_node("ongoing_monitoring", ongoing_monitoring_agent.run)
    workflow.add_node("health_score", health_score_agent.run)
    workflow.add_node("grievance_engine", grievance_engine.run)
    workflow.add_node("outcome_learning_loop", outcome_learning_loop.run)

    # ---------------------------------------------------------
    # Edges & Parallel Fan-Out / Fan-In
    # ---------------------------------------------------------
    workflow.set_entry_point("profiling_agent")
    workflow.add_edge("profiling_agent", "discovery_agent")

    # 1 -> 6 Fan-Out from discovery_agent to the 6 parallel local intelligence agents
    workflow.add_edge("discovery_agent", "market_reach_agent")
    workflow.add_edge("discovery_agent", "opportunity_agent")
    workflow.add_edge("discovery_agent", "risk_agent")
    workflow.add_edge("discovery_agent", "competitor_agent")
    workflow.add_edge("discovery_agent", "pricing_agent")
    workflow.add_edge("discovery_agent", "supply_chain_agent")

    # 6 -> 1 Fan-In from all 6 agents to swot_synthesis
    workflow.add_edge("market_reach_agent", "swot_synthesis")
    workflow.add_edge("opportunity_agent", "swot_synthesis")
    workflow.add_edge("risk_agent", "swot_synthesis")
    workflow.add_edge("competitor_agent", "swot_synthesis")
    workflow.add_edge("pricing_agent", "swot_synthesis")
    workflow.add_edge("supply_chain_agent", "swot_synthesis")

    # Synthesis -> Adversarial Review
    workflow.add_edge("swot_synthesis", "adversarial_review")

    # Conditional Branch on Adversarial Verdict
    workflow.add_conditional_edges(
        "adversarial_review",
        route_adversarial_verdict,
        {
            "discovery_agent": "discovery_agent",
            "financial_engine": "financial_engine",
        },
    )

    # Module 2 Flow
    workflow.add_edge("financial_engine", "financial_analyst")
    workflow.add_edge("financial_analyst", "scenario_digital_twin")
    workflow.add_edge("scenario_digital_twin", "policy_scheme")
    workflow.add_edge("policy_scheme", "documentation")
    workflow.add_edge("documentation", "application_tracker")

    # Module 3 Flow
    workflow.add_edge("application_tracker", "procurement_coordinator")
    workflow.add_edge("procurement_coordinator", "launch_copilot")
    workflow.add_edge("launch_copilot", "ongoing_monitoring")
    workflow.add_edge("ongoing_monitoring", "health_score")
    workflow.add_edge("health_score", "grievance_engine")
    workflow.add_edge("grievance_engine", "outcome_learning_loop")
    workflow.add_edge("outcome_learning_loop", END)

    checkpointer = get_checkpointer() if with_checkpointer else None
    return workflow.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        print("Compiling LangGraph StateGraph across Modules 1, 2, and 3...")
        app = build_graph(with_checkpointer=True)
        print("LangGraph StateGraph compiled successfully!")
        print(f"Total Nodes: {len(app.get_graph().nodes)}")
        sys.exit(0)
