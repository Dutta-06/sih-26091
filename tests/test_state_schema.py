"""Unit tests for CaseState schema and Conversational Router."""

from orchestrator.state import (
    CaseState,
    Confidence,
    EntrepreneurProfile,
    MarketReachIntelligence,
    SessionMeta,
)
from orchestrator.router import extract_slots_from_text, route_conversational_turn


def test_confidence_tagging():
    """Verify confidence tags are strictly enforced as 'real' or 'estimated'."""
    reach = MarketReachIntelligence(
        population_within_radius=50_000,
        source_confidence="real",
    )
    assert reach.source_confidence == "real"

    reach_est = MarketReachIntelligence(
        population_within_radius=50_000,
        source_confidence="estimated",
    )
    assert reach_est.source_confidence == "estimated"


def test_slot_extraction_various_prompts():
    """Verify natural language extraction for capital, location, and business category."""
    # Test lakh format
    slots1 = extract_slots_from_text("I have 1.5 lakh rupees in Bhadohi and want to do dairy")
    assert slots1.get("available_capital") == 150_000.0
    assert slots1.get("business_preference") == "Dairy"
    assert "Bhadohi" in slots1.get("location_query", "")

    # Test numerical format
    slots2 = extract_slots_from_text("I have 100000 available capital in Varanasi for poultry")
    assert slots2.get("available_capital") == 100_000.0
    assert slots2.get("business_preference") == "Poultry"
    assert "Varanasi" in slots2.get("location_query", "")


def test_conversational_slot_filling_flow():
    """Verify conversational slot filling asks for missing fields step-by-step."""
    # Turn 1: empty message -> asks for location
    state1, reply1 = route_conversational_turn("Hello, I want to start a business")
    assert "location" in reply1.lower()

    # Turn 2: provides location -> asks for capital
    state2, reply2 = route_conversational_turn("I am in Jaunpur, Uttar Pradesh", state1)
    assert "margin money" in reply2.lower()

    # Turn 3: provides capital -> asks for category
    state3, reply3 = route_conversational_turn("I have 1 lakh rupees", state2)
    assert "what type of business" in reply3.lower()

    # Turn 4: provides category -> launches pipeline
    state4, reply4 = route_conversational_turn("Dairy farming", state3)
    assert "launching" in reply4.lower()
    assert state4.entrepreneur_profile.available_capital == 100_000.0
    assert state4.entrepreneur_profile.business_preference == "Dairy Farming"
