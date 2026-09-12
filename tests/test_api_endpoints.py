"""Integration tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
from orchestrator.app import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["nodes"] == 24


def test_pipeline_direct_run_endpoint():
    payload = {
        "available_capital": 100000.0,
        "location": "Bhadohi, Bhadohi, Uttar Pradesh",
        "business_category": "Dairy Farming",
    }
    response = client.post("/pipeline/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["financial_plan"]["computed_project_cost"] == 1000000.0
    assert data["financial_plan"]["maximum_loan_eligibility"] == 900000.0
    assert data["financial_plan"]["scheme_tier"]["name"] == "term_loan"
    assert data["feasibility"]["verdict"] == "viable"
    assert len(data["launch_roadmap"]) > 0


def test_session_conversational_endpoint():
    payload = {
        "message": "I have 1 lakh rupees in Bhadohi and want to start a Dairy unit",
    }
    response = client.post("/session", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_complete"] is True
    assert "Feasible Project Cost" in data["reply"]
