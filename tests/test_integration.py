"""Cross-module behaviour: real agents (no fakes) wired through the graph and API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from common.reference import lookup_district, lookup_state, match_activity
from data_connectors.geocoding import resolve_location
from module2_financial import documentation_agent
from orchestrator.app import app
from orchestrator.graph import build_graph, run_case
from orchestrator.router import route_conversational_turn

client = TestClient(app)


def _run(message: str):
    state, _, run_graph = route_conversational_turn(message)
    assert run_graph
    return run_case(build_graph(with_checkpointer=False), state)


def test_activity_matching_is_whole_word():
    assert match_activity("I have been saving for a tailoring unit")["id"] == "tailoring"
    assert match_activity("honey from bees")["id"] == "beekeeping"
    assert match_activity("I have been working in a hotel") is None


def test_regional_script_place_names_resolve():
    assert lookup_district("भदोही")[0] == "Bhadohi"
    assert lookup_state("उत्तर प्रदेश")[0] == "Uttar Pradesh"
    assert resolve_location("भदोही").district == "Bhadohi"


def test_micro_finance_case_keeps_the_stated_activity():
    final = _run("I have 12000 rupees and want to start tailoring in Mirzapur, Uttar Pradesh")
    assert final.feasibility_record.selected_category.startswith("Tailoring")
    assert final.feasibility_record.verdict == "viable"
    assert final.financial_plan.scheme_tier.name == "micro_finance"
    assert final.session_meta.current_stage == "application_documents_pending"
    assert not final.launch_roadmap  # Module 3 waits for disbursement


def test_every_module1_output_is_confidence_labeled_and_offline_is_estimated():
    final = _run("I have 1 lakh rupees and want to start a dairy farm in Bhadohi, Uttar Pradesh")
    labels = final.market_intelligence.confidence_summary()
    assert set(labels) == {"market_reach", "opportunity", "risk", "competitor", "pricing", "supply_chain"}
    assert set(labels.values()) == {"estimated"}  # offline: nothing may claim to be real data
    assert final.market_intelligence.competitor.estimated_competitor_count is None  # no fabricated competitors
    assert final.market_intelligence.risk.route_distance_method == "unavailable"


ANSWERS = {"full_name": "Asha Devi", "phone_number": "9876543210", "aadhaar_number": "234567890123",
           "bank_account_number": "123456789012", "ifsc_code": "SBIN0001234", "pincode": "231001",
           "pan_number": "ABCDE1234F"}


def test_documents_are_asked_one_at_a_time_after_form_fields():
    final = _run("I have 12000 rupees and want to start tailoring in Mirzapur, Uttar Pradesh")
    asked: list[str] = []
    for _ in range(40):
        final.application_status = documentation_agent.run(final)["application_status"]
        field = final.application_status.next_required_field
        if field is None:
            break
        assert field not in asked, f"asked twice: {field}"
        asked.append(field)
        if field.startswith(documentation_agent.DOCUMENT_FIELD_PREFIX):
            answer = "applied" if "caste" in field else "no" if "income" in field else "yes"
        else:
            answer = ANSWERS.get(field, "Sample answer")
        accepted, message = documentation_agent.record_field(final, field, answer)
        assert accepted, (field, message)
    fields = [f for f in asked if not f.startswith("document:")]
    docs = [f for f in asked if f.startswith("document:")]
    assert fields and docs and asked.index(docs[0]) > asked.index(fields[-1])  # documents after form fields
    checklist = final.application_status.checklist
    assert checklist["caste_or_category_certificate"] == "pending"
    assert checklist["income_certificate"] == "missing"  # "no" keeps it missing and it is not asked again
    assert checklist["identity_proof"] == "complete"
    assert final.application_status.form_data["aadhaar_number"] == "XXXX-XXXX-0123"


def test_above_scheme_ceiling_stops_before_feasibility():
    final = _run("I have 60 lakh rupees and want to start a flour mill in Gaya, Bihar")
    assert final.feasibility_record is None and final.financial_plan is None
    assert final.session_meta.current_stage == "not_eligible"


def test_scheme_question_before_any_plan_gets_rules_not_eligibility():
    reply = client.post("/session", json={"message": "What are the scheme rules and eligibility criteria?"}).json()["reply"]
    assert "Micro Finance Scheme" in reply and "Term Loan Scheme" in reply


def test_full_lifecycle_through_api():
    start = client.post("/session", json={"message": "I have 12000 rupees and want to start tailoring in Mirzapur, Uttar Pradesh"})
    assert start.status_code == 200, start.text
    sid = start.json()["session_id"]
    r = client.post(f"/application/{sid}/event", json={"event": "submit"})
    assert r.status_code == 409  # cannot submit before required documents are complete
    checklist = client.get(f"/state/{sid}").json()["application_status"]["checklist"]
    r = client.post(f"/application/{sid}/field", json={"field": "documents_available", "value": ", ".join(k.replace("_", " ") for k in checklist)})
    assert r.status_code == 200, r.text
    # all required documents complete -> the tracker submits automatically; officer events do the rest
    assert client.get(f"/state/{sid}").json()["application_status"]["disbursement_status"] == "submitted"
    for event in ("start_verification", "sanction", "disburse"):
        r = client.post(f"/application/{sid}/event", json={"event": event})
        assert r.status_code == 200, (event, r.text)
    state = client.get(f"/state/{sid}").json()
    assert state["application_status"]["disbursement_status"] == "disbursed"
    assert state["launch_roadmap"] and not any(m["completed"] for m in state["launch_roadmap"])

    assert client.post(f"/monitoring/{sid}/consent", json={"consent": True}).status_code == 200
    sms = ["Rs.2,500.00 credited to A/c XX1234 on 02-09-26 via UPI from RAMESH. Avl Bal Rs 10,000",
           "INR 900.00 debited from A/c XX1234 on 05-09-26 UPI to SUPPLIER"]
    r = client.post(f"/monitoring/{sid}/notifications", json={"messages": sms})
    assert r.status_code == 200, r.text
    state = client.get(f"/state/{sid}").json()
    assert state["monitoring_record"] and "RAMESH" not in str(state)

    r = client.post(f"/grievance/{sid}", json={"text": "Sewing machine is broken and repair is delayed"})
    assert r.status_code == 200, r.text
    state = client.get(f"/state/{sid}").json()
    assert state["grievance_log"][-1]["issue_type"] == "machinery_breakdown"
    assert state["outcome_learning"]["status_note"]
