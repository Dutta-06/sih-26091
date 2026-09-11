from __future__ import annotations

import pytest

from src.agents.competitor_agent import CompetitorAgent
from src.agents.pricing_agent import PricingAgent
from src.agents.supply_chain_agent import SupplyChainAgent
from src.config import settings
from src.schemas import Confidence


class _ExplodingAdapter:
    """Stands in for any real adapter (Udyam / Overpass / commodity price /
    purchasing power / routing). Any attribute access returns an async
    function that raises — so if a mock-mode agent ever touches it, the
    test fails loudly instead of silently degrading to a live call."""

    name = "should-not-be-called-in-mock-mode"

    def __getattr__(self, item):
        async def _boom(*args, **kwargs):
            raise AssertionError(
                f"External adapter method '{item}' was called while DATA_MODE=mock — "
                "mock mode must never touch a real adapter."
            )

        return _boom


# --- DATA_MODE default -----------------------------------------------------

def test_data_mode_defaults_to_mock():
    assert settings.data_mode == "mock"


# --- Competitor Agent --------------------------------------------------------

@pytest.mark.asyncio
async def test_competitor_agent_mock_mode_never_touches_real_adapters(base_case_state):
    # base_case_state (tests/conftest.py) is Rampur/Sadar/Meerut, selected
    # business "Grocery" / sector "grocery" -> mock category "grocery",
    # which has businesses seeded in Rampur within the default 5km radius.
    agent = CompetitorAgent(
        udyam_adapter=_ExplodingAdapter(), overpass_adapter=_ExplodingAdapter(), data_mode="mock",
    )
    result = await agent.run(base_case_state, district_population=500000, state_population=20000000)

    assert result.competitor_count is not None
    assert result.competitor_count > 0
    assert result.confidence == Confidence.ESTIMATED  # mock, never REAL_DATA
    assert any("mock database" in lim.lower() for lim in result.limitations)


@pytest.mark.asyncio
async def test_competitor_agent_mock_mode_insufficient_for_unmapped_sector(base_case_state):
    base_case_state.selected_business.sector = "unmapped_sector"
    agent = CompetitorAgent(
        udyam_adapter=_ExplodingAdapter(), overpass_adapter=_ExplodingAdapter(), data_mode="mock",
    )
    result = await agent.run(base_case_state)

    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert result.competitor_count is None
    assert any("never falls back to a live adapter" in lim for lim in result.limitations)


# --- Pricing Agent ------------------------------------------------------------

@pytest.mark.asyncio
async def test_pricing_agent_mock_mode_never_touches_real_adapters(base_case_state):
    agent = PricingAgent(
        commodity_price_adapter=_ExplodingAdapter(), purchasing_power_adapter=_ExplodingAdapter(), data_mode="mock",
    )
    result = await agent.run(base_case_state, commodity="milk", unit="litre")

    assert result.confidence == Confidence.ESTIMATED  # mock, never REAL_DATA
    assert result.is_estimated is True
    assert result.representative_price is not None
    assert result.data_source == "Mock Database (data/mock.db)"


@pytest.mark.asyncio
async def test_pricing_agent_mock_mode_insufficient_without_commodity(base_case_state):
    agent = PricingAgent(
        commodity_price_adapter=_ExplodingAdapter(), purchasing_power_adapter=_ExplodingAdapter(), data_mode="mock",
    )
    result = await agent.run(base_case_state)  # no commodity supplied

    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert result.representative_price is None


@pytest.mark.asyncio
async def test_pricing_agent_mock_mode_insufficient_for_unknown_product(base_case_state):
    agent = PricingAgent(
        commodity_price_adapter=_ExplodingAdapter(), purchasing_power_adapter=_ExplodingAdapter(), data_mode="mock",
    )
    result = await agent.run(base_case_state, commodity="unobtainium")

    assert result.confidence == Confidence.INSUFFICIENT_DATA


# --- Supply Chain Agent --------------------------------------------------------

@pytest.mark.asyncio
async def test_supply_chain_agent_mock_mode_never_touches_real_adapters(base_case_state):
    agent = SupplyChainAgent(
        overpass_adapter=_ExplodingAdapter(), routing_adapter=_ExplodingAdapter(), data_mode="mock",
    )
    result = await agent.run(base_case_state)

    assert result.confidence != Confidence.REAL_DATA
    assert len(result.suppliers) > 0  # Rampur has grocery_wholesale suppliers in mock db
    assert len(result.distribution_points) > 0
    assert len(result.route_risks) > 0
    # Route risk must be the documented Haversine proxy, never a real OSRM call.
    assert any("Haversine" in lim for lim in result.limitations)


@pytest.mark.asyncio
async def test_supply_chain_agent_mock_mode_missing_coordinates(base_case_state):
    base_case_state.entrepreneur_profile["location"]["latitude"] = None
    base_case_state.entrepreneur_profile["location"]["longitude"] = None
    agent = SupplyChainAgent(
        overpass_adapter=_ExplodingAdapter(), routing_adapter=_ExplodingAdapter(), data_mode="mock",
    )
    result = await agent.run(base_case_state)

    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert result.suppliers == []


# --- Graph end-to-end (mock mode) -----------------------------------------------

@pytest.mark.asyncio
async def test_graph_runs_end_to_end_in_mock_mode(base_case_state):
    from src.graph import run_market_intelligence

    updated = await run_market_intelligence(base_case_state, commodity="milk", unit="litre")

    assert updated.market_intelligence.competitor is not None
    assert updated.market_intelligence.pricing is not None
    assert updated.market_intelligence.supply_chain is not None
    assert updated.market_intelligence.competitor.confidence != Confidence.REAL_DATA
    assert updated.market_intelligence.pricing.confidence != Confidence.REAL_DATA
    assert updated.market_intelligence.supply_chain.confidence != Confidence.REAL_DATA


# --- FastAPI /analyze end-to-end (mock mode) --------------------------------------

def test_analyze_endpoint_end_to_end_mock_mode():
    from fastapi.testclient import TestClient

    from src.api import app

    client = TestClient(app)
    payload = {
        "case_id": "case-mock-001",
        "location": {
            "village": "Rampur", "block": "Sadar", "district": "Meerut", "state": "Uttar Pradesh",
            "latitude": 28.9845, "longitude": 77.7064,
        },
        "available_capital": 150000,
        "selected_business": {"name": "Grocery", "sector": "grocery"},
        "commodity": "milk",
        "unit": "litre",
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["market_intelligence"]["competitor"]["confidence"] != "REAL_DATA"
    assert body["market_intelligence"]["pricing"]["confidence"] != "REAL_DATA"
    assert body["market_intelligence"]["supply_chain"] is not None


def test_health_endpoint_reports_data_mode():
    from fastapi.testclient import TestClient

    from src.api import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["data_mode"] == "mock"
