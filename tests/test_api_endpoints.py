"""FastAPI endpoints with fake agents (offline)."""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient

from orchestrator import persistence, stores
from orchestrator.app import app
from tests.test_graph_flow import install_fakes

client = TestClient(app)


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    return install_fakes(monkeypatch)


def _start(message="I have Rs 12000 and want to start tailoring in Bhadohi because I know stitching") -> dict:
    r = client.post("/session", json={"message": message})
    assert r.status_code == 200, r.text
    return r.json()


def test_health_reports_real_node_count():
    data = client.get("/health").json()
    assert data["status"] == "healthy" and data["nodes"] == 23


def test_conversation_runs_and_persists():
    first = client.post("/session", json={"message": "Namaste"}).json()
    assert not first["ran_graph"]
    sid = first["session_id"]
    client.post("/session", json={"session_id": sid, "message": "Bhadohi, Uttar Pradesh"})
    client.post("/session", json={"session_id": sid, "message": "12000"})
    data = client.post("/session", json={"session_id": sid, "message": "tailoring"}).json()
    assert data["ran_graph"] and "Recommended: Tailoring" in data["reply"]
    assert "Application status: documents pending" in data["reply"]
    assert persistence.load_case(sid).feasibility_record.verdict == "viable"
    assert client.get(f"/state/{sid}").status_code == 200
    assert client.get("/state/missing").status_code == 404


def test_above_fifty_lakh_is_handled():
    data = _start("I have 6 lakh rupees for dairy in Bhadohi")
    assert "Not eligible for the scheme" in data["reply"]
    r = client.post("/pipeline/run", json={"available_capital": 6_000_000, "location": "Bhadohi", "business_category": "dairy"})
    assert r.status_code == 200 and "Not eligible" in r.json()["summary"]


def test_agent_failure_returns_422(monkeypatch):
    def boom(state):
        raise RuntimeError("connector exploded")

    monkeypatch.setattr(sys.modules["module2_financial.financial_engine"], "run", boom)
    r = client.post("/session", json={"message": "I have 1 lakh rupees for tailoring in Bhadohi"})
    assert r.status_code == 422 and "connector exploded" in r.json()["detail"]


def test_application_event_transitions_and_launch():
    sid = _start()["session_id"]
    r = client.post(f"/application/{sid}/field", json={"field": "full_name", "value": "Sunita Devi"})
    assert r.status_code == 200 and r.json()["accepted"]
    assert client.post(f"/application/{sid}/event", json={"event": "sanction"}).status_code == 409  # illegal from pending
    for event in ("submit", "start_verification", "sanction"):
        r = client.post(f"/application/{sid}/event", json={"event": event})
        assert r.status_code == 200, r.text
    assert r.json()["state"]["launch_roadmap"] == []  # sanctioned but not disbursed -> still paused
    r = client.post(f"/application/{sid}/event", json={"event": "disburse", "amount": 108000})
    assert r.json()["disbursement_status"] == "disbursed" and r.json()["state"]["launch_roadmap"]


def test_notifications_require_consent_and_discard_raw_text():
    sid = _start()["session_id"]
    raw = "Rs 1500 credited to A/c XX1234 by UPI ref 99887766 SECRETMARKER"
    assert client.post(f"/monitoring/{sid}/notifications", json={"messages": [raw]}).status_code == 403
    assert client.post(f"/monitoring/{sid}/consent", json={"consent": True}).status_code == 200
    r = client.post(f"/monitoring/{sid}/notifications", json={"messages": [raw]})
    assert r.status_code == 200 and r.json()["transactions_parsed"] == 1
    assert r.json()["state"]["monitoring_record"][0]["transactions_parsed"] == 1
    saved = persistence.load_case(sid).model_dump_json()
    assert "SECRETMARKER" not in saved and "XX1234" not in saved


def test_grievance_endpoint():
    sid = _start()["session_id"]
    r = client.post(f"/grievance/{sid}", json={"text": "Supplier delayed thread delivery"})
    assert r.status_code == 200 and r.json()["grievance"]["description"] == "Supplier delayed thread delivery"


def test_feedback_and_survey_stored():
    body = {"district": "Bhadohi", "topic": "demand", "observation": "Uniform orders peak in June", "catalog_id": "tailoring", "rating": 4}
    assert client.post("/feedback", json=body).json()["kind"] == "funded_entrepreneur"
    assert client.post("/survey", json={**body, "rating": None}).json()["kind"] == "resident_survey"
    kinds = {row["kind"] for row in stores.local_feedback("Bhadohi", "tailoring")}
    assert kinds == {"funded_entrepreneur", "resident_survey"}


def test_map_geojson_and_view():
    sid = _start()["session_id"]
    fc = client.get(f"/map/{sid}").json()
    assert fc["type"] == "FeatureCollection"
    assert all(f["properties"].get("confidence") for f in fc["features"])  # fake geocoder has no coordinates
    html = client.get(f"/map/{sid}/view")
    assert html.status_code == 200 and "leaflet" in html.text and sid in html.text


def test_map_includes_located_entrepreneur():
    from orchestrator.app import build_geojson
    from orchestrator.state import CaseState, LocationDetails, MarketReachIntelligence, SessionMeta
    from module1_feasibility.profiling_agent import extract_profile_from_slots

    state = CaseState(session_meta=SessionMeta(session_id="map"),
                      entrepreneur_profile=extract_profile_from_slots("Bhadohi", 10_000, None),
                      market_reach_intel=MarketReachIntelligence(radius_km=8))
    state.entrepreneur_profile.location = LocationDetails(latitude=25.4, longitude=82.57, resolution_method="lgd_table")
    feature = build_geojson(state)["features"][0]
    assert feature["geometry"]["coordinates"] == [82.57, 25.4] and feature["properties"]["radius_km"] == 8


def test_voice_unavailable_returns_501():
    sid = _start()["session_id"]
    r = client.post(f"/session/{sid}/voice", files={"audio": ("a.wav", b"RIFF0000", "audio/wav")})
    assert r.status_code == 501
