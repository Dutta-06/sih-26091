from __future__ import annotations

import pytest

from src.agents.competitor_agent import CompetitorAgent
from src.agents.pricing_agent import PricingAgent
from src.agents.supply_chain_agent import SupplyChainAgent
from src.graph import run_market_intelligence
from src.schemas import CompetitorAgentOutput, Confidence, PricingAgentOutput, SupplyChainAgentOutput
from src.state_store import InMemoryCaseStateStore


@pytest.mark.asyncio
async def test_graph_fans_out_and_merges_into_case_state(base_case_state, monkeypatch):
    async def fake_competitor_run(self, case_state, **kwargs):
        return CompetitorAgentOutput(competitor_count=2, confidence=Confidence.REAL_DATA)

    async def fake_pricing_run(self, case_state, **kwargs):
        return PricingAgentOutput(
            representative_price=50.0,
            data_source="fake",
            pricing_basis="real_commodity_price",
            is_estimated=False,
            confidence=Confidence.REAL_DATA,
        )

    async def fake_supply_chain_run(self, case_state, **kwargs):
        return SupplyChainAgentOutput(confidence=Confidence.REAL_DATA)

    monkeypatch.setattr(CompetitorAgent, "run", fake_competitor_run)
    monkeypatch.setattr(PricingAgent, "run", fake_pricing_run)
    monkeypatch.setattr(SupplyChainAgent, "run", fake_supply_chain_run)

    store = InMemoryCaseStateStore()
    result = await run_market_intelligence(base_case_state, store=store)

    assert result.market_intelligence.competitor.competitor_count == 2
    assert result.market_intelligence.pricing.representative_price == 50.0
    assert result.market_intelligence.supply_chain.confidence == Confidence.REAL_DATA

    persisted = await store.get(base_case_state.case_id)
    assert persisted is not None
    assert persisted.market_intelligence.competitor.competitor_count == 2
