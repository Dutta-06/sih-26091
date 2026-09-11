from __future__ import annotations

import pytest

from src.adapters.base import AdapterResult
from src.agents.pricing_agent import PricingAgent
from src.schemas import Confidence


class FakeCommodityAdapter:
    name = "Government commodity price open data API"

    def __init__(self, result: AdapterResult):
        self._result = result

    async def get_price_range(self, commodity, district, state):
        return self._result


class FakePurchasingPowerAdapter:
    name = "SECC asset data (purchasing-power proxy, bulk extract)"

    def __init__(self, result: AdapterResult):
        self._result = result

    async def get_asset_index(self, district):
        return self._result


@pytest.mark.asyncio
async def test_real_commodity_price_used_when_available(base_case_state):
    commodity_adapter = FakeCommodityAdapter(
        AdapterResult(
            data={"price_min": 18.0, "price_max": 24.0, "representative_price": 21.0, "sample_size": 5},
            confidence=Confidence.REAL_DATA,
            source="commodity api",
        )
    )
    pp_adapter = FakePurchasingPowerAdapter(AdapterResult.insufficient("secc", "should not be called"))

    agent = PricingAgent(commodity_price_adapter=commodity_adapter, purchasing_power_adapter=pp_adapter, data_mode="real")
    result = await agent.run(base_case_state, commodity="wheat", unit="kg")

    assert result.is_estimated is False
    assert result.confidence == Confidence.REAL_DATA
    assert result.price_min == 18.0
    assert result.representative_price == 21.0


@pytest.mark.asyncio
async def test_falls_back_to_estimate_when_commodity_api_unavailable(base_case_state):
    commodity_adapter = FakeCommodityAdapter(AdapterResult.insufficient("commodity api", "missing api key"))
    pp_adapter = FakePurchasingPowerAdapter(
        AdapterResult(data=0.6, confidence=Confidence.ESTIMATED, source="secc")
    )

    agent = PricingAgent(commodity_price_adapter=commodity_adapter, purchasing_power_adapter=pp_adapter, data_mode="real")
    result = await agent.run(base_case_state, commodity="handicrafts", base_reference_price=1000.0)

    assert result.is_estimated is True
    assert result.confidence == Confidence.ESTIMATED
    assert result.representative_price == pytest.approx(1000.0 * (0.8 + 0.4 * 0.6))
    assert result.price_min < result.representative_price < result.price_max
    assert any("ESTIMATED" in lim for lim in result.limitations)


@pytest.mark.asyncio
async def test_insufficient_data_when_no_base_reference_price(base_case_state):
    commodity_adapter = FakeCommodityAdapter(AdapterResult.insufficient("commodity api", "missing api key"))
    pp_adapter = FakePurchasingPowerAdapter(
        AdapterResult(data=0.5, confidence=Confidence.ESTIMATED, source="secc")
    )

    agent = PricingAgent(commodity_price_adapter=commodity_adapter, purchasing_power_adapter=pp_adapter, data_mode="real")
    result = await agent.run(base_case_state, commodity="handicrafts")  # no base_reference_price

    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert result.representative_price is None


@pytest.mark.asyncio
async def test_never_fabricates_price_when_all_tiers_fail(base_case_state):
    base_case_state.entrepreneur_profile["location"]["district"] = None
    commodity_adapter = FakeCommodityAdapter(AdapterResult.insufficient("commodity api", "missing api key"))
    pp_adapter = FakePurchasingPowerAdapter(AdapterResult.insufficient("secc", "no dataset configured"))

    agent = PricingAgent(commodity_price_adapter=commodity_adapter, purchasing_power_adapter=pp_adapter, data_mode="real")
    result = await agent.run(base_case_state, commodity="handicrafts", base_reference_price=1000.0)

    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert result.price_min is None
    assert result.price_max is None
