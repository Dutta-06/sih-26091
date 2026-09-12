"""Intent Routing and Slot-Filling Layer (Section 4).

Classifies user conversational turns, identifies missing required fields
(location, available capital, business category), and directs the session flow.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal
from orchestrator.state import CaseState, SessionMeta
from module1_feasibility.profiling_agent import extract_profile_from_slots


def parse_intent(message: str) -> Literal["new_case", "provide_info", "inquire_scheme", "raise_grievance", "continue"]:
    """Classifies user turn intent based on keyword patterns."""
    text = message.lower()
    if any(k in text for k in ["complaint", "issue", "problem", "broken", "delay", "not working"]):
        return "raise_grievance"
    if any(k in text for k in ["rule", "guideline", "subsidy", "eligibility criteria", "scheme explain"]):
        return "inquire_scheme"
    if any(k in text for k in ["start", "new", "apply", "plan", "business", "rupees", "lakh", "capital"]):
        return "new_case"
    return "provide_info"


def extract_slots_from_text(message: str) -> dict[str, Any]:
    """Extracts capital, location, and business category preferences from natural language."""
    slots: dict[str, Any] = {}

    # 1. Extract capital (e.g. 1 lakh, 100000, 50,000, 1.4 lakh)
    capital = None
    lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|lacs|lakhs)", message, re.IGNORECASE)
    if lakh_match:
        capital = float(lakh_match.group(1)) * 100_000.0
    else:
        num_matches = re.findall(r"(?:₹|Rs\.?|INR)?\s*(\d{1,3}(?:,\d{3})+|\d+)", message)
        for raw_num in num_matches:
            val = float(raw_num.replace(",", ""))
            if val >= 5_000:  # meaningful capital amount
                capital = val
                break

    if capital is not None:
        slots["available_capital"] = capital

    # 2. Extract location using strict word boundaries (avoid matching 'at' in 'capital')
    loc_match = re.search(r"\b(?:in|near|at|from)\b\s+([A-Za-z\s,]+?)(?:\s+and\b|\s+with\b|\.|$)", message, re.IGNORECASE)
    if loc_match:
        loc_candidate = loc_match.group(1).strip()
        # Clean up any trailing prepositions
        loc_candidate = re.sub(r"\s+(?:for|to|and|with)$", "", loc_candidate, flags=re.IGNORECASE).strip()
        if loc_candidate and loc_candidate.lower() not in ["capital", "dairy", "farming", "business", "india"]:
            slots["location_query"] = loc_candidate

    # 3. Extract business category (dairy, poultry, mustard oil, retail, tailoring, grocery)
    text = message.lower()
    for cat in [
        "dairy farming",
        "dairy",
        "poultry",
        "mustard oil",
        "retail",
        "tailoring",
        "textiles",
        "grocery",
        "fisheries",
        "flour mill",
    ]:
        if cat in text:
            slots["business_preference"] = cat.title()
            break

    return slots


def route_conversational_turn(message: str, current_state: CaseState | None = None) -> tuple[CaseState, str]:
    """Processes a conversational turn, fills missing slots, and returns updated state + assistant response."""
    intent = parse_intent(message)
    slots = extract_slots_from_text(message)

    if current_state is None:
        session_id = f"session_{str(uuid.uuid4())[:8]}"
        session_meta = SessionMeta(session_id=session_id)
        current_state = CaseState(session_meta=session_meta)

    current_state.session_meta.user_turns += 1

    # Update profile slots
    existing_profile = current_state.entrepreneur_profile
    loc = slots.get("location_query") or (existing_profile.location_query if existing_profile else "")
    capital = slots.get("available_capital") or (existing_profile.available_capital if existing_profile else 0.0)
    pref = slots.get("business_preference") or (existing_profile.business_preference if existing_profile else None)

    # Check for missing required slots conversationally
    if not loc or loc == "Not specified":
        current_state.entrepreneur_profile = extract_profile_from_slots(
            location_query="Not specified",
            available_capital=capital,
            business_preference=pref,
        )
        return (
            current_state,
            "Namaste! To provide an accurate hyper-local feasibility study and scheme calculation, "
            "could you please share your village, block, or district location?",
        )

    if capital <= 0:
        current_state.entrepreneur_profile = extract_profile_from_slots(
            location_query=loc,
            available_capital=0.0,
            business_preference=pref,
        )
        return (
            current_state,
            f"Thank you. Location registered as '{loc}'. "
            "How much margin money (self-capital) do you have available to invest (e.g. Rs. 1,00,000)?",
        )

    if not pref:
        current_state.entrepreneur_profile = extract_profile_from_slots(
            location_query=loc,
            available_capital=capital,
            business_preference=None,
        )
        return (
            current_state,
            f"Understood: Rs. {capital:,.0f} available in '{loc}'. "
            "What type of business are you planning to start (e.g., Dairy, Mustard Oil Mini-Mill, Retail Seed Depot)?",
        )

    # All core slots filled -> ready for graph orchestration
    current_state.entrepreneur_profile = extract_profile_from_slots(
        location_query=loc,
        available_capital=capital,
        business_preference=pref,
    )
    current_state.session_meta.current_stage = "feasibility_assessment"

    response = (
        f"All required details captured:\n"
        f"• Location: {loc}\n"
        f"• Available Margin Capital: Rs. {capital:,.2f} (10% contribution)\n"
        f"• Proposed Activity: {pref}\n\n"
        f"Launching hyper-local feasibility and financial structuring pipeline..."
    )
    return current_state, response
