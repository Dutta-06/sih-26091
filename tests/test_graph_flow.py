"""Automated Tests for Central LangGraph StateGraph Flow and Rejection Loop."""

from orchestrator.graph import build_graph, route_adversarial_verdict
from orchestrator.router import route_conversational_turn
from orchestrator.state import CaseState, FeasibilityRecord, SessionMeta
import module1_feasibility.adversarial_review as adversarial_review


def test_graph_compilation():
    """Verify graph compiles cleanly with checkpointer attached."""
    app = build_graph(with_checkpointer=True)
    assert app is not None
    graph_nodes = app.get_graph().nodes
    # Verify key nodes are registered
    assert "profiling_agent" in graph_nodes
    assert "discovery_agent" in graph_nodes
    assert "market_reach_agent" in graph_nodes
    assert "swot_synthesis" in graph_nodes
    assert "adversarial_review" in graph_nodes
    assert "financial_engine" in graph_nodes
    assert "ongoing_monitoring" in graph_nodes


def test_end_to_end_graph_execution():
    """Verify full end-to-end traversal from profiling through Module 3."""
    app = build_graph(with_checkpointer=True)
    msg = "I have 1 lakh rupees and want to start a Dairy unit near Bhadohi"
    state, _ = route_conversational_turn(msg)
    
    config = {"configurable": {"thread_id": "test_e2e_001"}}
    res = app.invoke(state, config=config)
    final_state = CaseState.model_validate(res) if isinstance(res, dict) else res

    # Verify Module 1 outputs
    assert final_state.feasibility_record is not None
    assert final_state.feasibility_record.verdict == "viable"
    assert final_state.market_intelligence is not None
    assert final_state.market_intelligence.market_reach.consumer_base_estimate > 0

    # Verify Module 2 outputs
    assert final_state.financial_plan is not None
    assert final_state.financial_plan.computed_project_cost == 1_000_000.0
    assert final_state.financial_plan.maximum_loan_eligibility == 900_000.0
    assert final_state.financial_plan.scheme_tier.name == "term_loan"
    assert len(final_state.financial_plan.repayment_schedule) == 28

    # Verify Module 3 outputs
    assert len(final_state.launch_roadmap) > 0
    assert final_state.application_status.disbursement_status == "sanctioned"


def test_adversarial_rejection_routing():
    """Verify that unviable choices trigger the rejection loop."""
    # Test adversarial evaluator logic directly
    verdict, reasoning, critiques = adversarial_review.evaluate_adversarial_critique(
        category="Saturated Tea Stall",
        available_capital=5_000.0,  # undercapitalized
        saturation_score=0.92,
        z_score_competition=2.8,
    )
    assert verdict == "not_recommended"
    assert "Insufficient Capital" in critiques[0]

    # Verify conditional edge routes to discovery_agent on rejection
    state = CaseState(
        session_meta=SessionMeta(session_id="test_rej_01"),
        feasibility_record=FeasibilityRecord(verdict="not_recommended"),
    )
    next_node = route_adversarial_verdict(state)
    assert next_node == "discovery_agent"

    # Verify conditional edge routes to financial_engine on viable verdict
    state.feasibility_record.verdict = "viable"
    next_node_viable = route_adversarial_verdict(state)
    assert next_node_viable == "financial_engine"
