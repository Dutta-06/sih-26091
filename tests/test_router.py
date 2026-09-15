"""Conversational router: intents, one-at-a-time slot filling, Hindi cues, language detection."""

from __future__ import annotations

from orchestrator.language import detect_language, from_english, to_english
from orchestrator.router import extract_capital, extract_slots_from_text, parse_intent, route_conversational_turn
from orchestrator.state import ApplicationStatus, CaseState, FinancialPlan, SessionMeta


def test_slot_filling_order_one_at_a_time():
    state, reply, run = route_conversational_turn("Hello, I want to start a business")
    assert state.session_meta.pending_slot == "location" and not run and "village" in reply.lower()
    state, reply, run = route_conversational_turn("Jaunpur, Uttar Pradesh", state)
    assert state.entrepreneur_profile.location_query == "Jaunpur, Uttar Pradesh"
    assert state.session_meta.pending_slot == "capital" and not run
    state, reply, run = route_conversational_turn("12000", state)
    assert state.entrepreneur_profile.available_capital == 12_000
    assert state.session_meta.pending_slot == "activity" and not run
    state, reply, run = route_conversational_turn("Tailoring, because I learnt stitching from my mother", state)
    assert run and state.session_meta.requested_stage == "profiling" and state.session_meta.pending_slot is None
    p = state.entrepreneur_profile
    assert p.business_preference == "Tailoring and Garment Stitching Unit"
    assert p.preference_reason == "I learnt stitching from my mother"
    assert p.skills == [] and p.assets == []  # nothing invented


def test_single_message_fills_all_slots():
    state, _, run = route_conversational_turn("I have 1 lakh rupees and want to start a dairy business near Bhadohi")
    p = state.entrepreneur_profile
    assert run and p.available_capital == 100_000 and p.location_query == "Bhadohi" and "Dairy" in p.business_preference


def test_hindi_cues_offline():
    msg = "मेरे पास 1 लाख रुपये हैं और मैं भदोही में डेयरी शुरू करना चाहता हूँ क्योंकि मेरे पास भैंसें हैं"
    state, reply, run = route_conversational_turn(msg)
    p = state.entrepreneur_profile
    assert run and p.available_capital == 100_000 and p.location_query == "भदोही"
    assert "Dairy" in p.business_preference and p.preference_reason.startswith("मेरे पास भैंसें")
    assert state.session_meta.language_code == "hi"
    assert state.session_meta.translation_status == "unavailable"  # models disabled in tests
    assert extract_slots_from_text("Bhadohi mein 50 hazaar se silai")["available_capital"] == 50_000
    assert extract_capital("२ लाख") == 200_000


def test_capital_parsing_variants():
    assert extract_capital("Rs 12,000") == 12_000
    assert extract_capital("1.5 lakh") == 150_000
    assert extract_capital("within 10 km") is None
    assert extract_capital("5", expecting=True) == 5


def test_word_boundary_activity_matching():
    assert "business_preference" not in extract_slots_from_text("I have been at the hotel")


def test_intents():
    assert parse_intent("My sewing machine is broken, I want to file a complaint") == "raise_grievance"
    assert parse_intent("I consent to monitoring") == "consent_monitoring"
    assert parse_intent("start over please") == "new_case"
    state = CaseState(session_meta=SessionMeta(session_id="s"))
    state, _, _ = route_conversational_turn("I have 1 lakh for dairy in Bhadohi", state)
    assert parse_intent("What is the interest rate under the scheme?", state) == "inquire_scheme"
    assert parse_intent("show my application status", state) == "jump_application"
    assert parse_intent("how is my business doing, health score?", state) == "jump_monitoring"
    assert parse_intent("I have 2 lakh now", state) == "provide_info"
    assert parse_intent("ok", state) == "continue"


def test_grievance_and_jump_routing():
    state, _, _ = route_conversational_turn("I have 1 lakh for dairy in Bhadohi")
    s2, _, run = route_conversational_turn("Complaint: milk prices crashed", state)
    assert run and s2.session_meta.requested_stage == "grievance" and "crashed" in s2.session_meta.pending_grievance_text

    s3, reply, run = route_conversational_turn("show my application status", state)
    assert not run and "cannot start" in reply
    state.financial_plan = FinancialPlan()
    s4, _, run = route_conversational_turn("show my application status", state)
    assert run and s4.session_meta.requested_stage == "application"

    s5, reply, run = route_conversational_turn("health score please", state)
    assert not run and "consent" in reply.lower()
    s6, _, run = route_conversational_turn("I consent", state)
    assert not run and s6.session_meta.consent_sms_monitoring


def test_changed_slot_resets_assessment():
    state, _, _ = route_conversational_turn("I have 1 lakh for dairy in Bhadohi")
    state.financial_plan = FinancialPlan()
    s2, _, run = route_conversational_turn("Actually I have 2 lakh", state)
    assert run and s2.financial_plan is None and s2.entrepreneur_profile.available_capital == 200_000
    assert s2.entrepreneur_profile.location_query == "Bhadohi"


def test_pending_application_field_is_recorded(monkeypatch):
    import sys
    import types

    mod = types.ModuleType("module2_financial.documentation_agent")
    mod.record_field = lambda st, f, v: (True, f"Recorded {f}={v}")
    monkeypatch.setitem(sys.modules, "module2_financial.documentation_agent", mod)
    state, _, _ = route_conversational_turn("I have 1 lakh for dairy in Bhadohi")
    state.financial_plan = FinancialPlan()
    state.application_status = ApplicationStatus(next_required_field="full_name", next_required_prompt="Your full name?")
    from orchestrator.state import FeasibilityRecord
    state.feasibility_record = FeasibilityRecord(verdict="viable")
    s2, reply, run = route_conversational_turn("Sunita Devi", state)
    assert run and s2.session_meta.requested_stage == "application" and "Sunita Devi" in reply


def test_language_detection_and_passthrough():
    assert detect_language("नमस्ते") == "hi"
    assert detect_language("வணக்கம்") == "ta"
    assert detect_language("নমস্কার") == "bn"
    assert detect_language("hello") == "en"
    assert to_english("नमस्ते", "hi") == ("नमस्ते", "unavailable")
    assert to_english("hi", "en") == ("hi", "not_needed")
    assert from_english("hello", "hi") == "hello"
