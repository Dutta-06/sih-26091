from __future__ import annotations

import pytest

from src.adapters.base import AdapterResult
from src.agents.competitor_agent import CompetitorAgent
from src.schemas import Confidence, SaturationLevel


class FakeUdyamAdapter:
    name = "Udyam Registration open dataset (bulk extract)"

    def __init__(self, result: AdapterResult):
        self._result = result

    async def count_registered_enterprises(self, district, ncs_code):
        return self._result


class FakeOverpassAdapter:
    name = "OpenStreetMap Overpass API"

    def __init__(self, result: AdapterResult):
        self._result = result

    async def query_nearby(self, latitude, longitude, radius_meters, osm_tags):
        return self._result


@pytest.mark.asyncio
async def test_udyam_hit_gives_real_data_and_density(base_case_state):
    base_case_state.market_intelligence.market_reach = {"population": 20000}
    udyam = FakeUdyamAdapter(AdapterResult(data=6, confidence=Confidence.REAL_DATA, source="Udyam"))
    overpass = FakeOverpassAdapter(AdapterResult.insufficient("Overpass", "should not be called"))

    agent = CompetitorAgent(udyam_adapter=udyam, overpass_adapter=overpass, data_mode="real")
    result = await agent.run(base_case_state, district_population=500000, state_population=20000000)

    assert result.competitor_count == 6
    assert result.confidence == Confidence.REAL_DATA
    assert result.density_score == pytest.approx((6 / 20000) * 10000)
    assert result.saturation_level == SaturationLevel.LOW
    assert result.benchmark_district_density is not None
    assert result.benchmark_state_density is not None


@pytest.mark.asyncio
async def test_falls_back_to_overpass_when_udyam_insufficient(base_case_state):
    udyam = FakeUdyamAdapter(AdapterResult.insufficient("Udyam", "no dataset configured"))
    overpass_data = [{"osm_id": i, "osm_type": "node", "name": f"Shop {i}", "tags": {}, "latitude": 1.0, "longitude": 1.0} for i in range(4)]
    overpass = FakeOverpassAdapter(AdapterResult(data=overpass_data, confidence=Confidence.REAL_DATA, source="Overpass"))

    agent = CompetitorAgent(udyam_adapter=udyam, overpass_adapter=overpass, data_mode="real")
    result = await agent.run(base_case_state)

    assert result.competitor_count == 4
    assert result.confidence == Confidence.REAL_DATA
    assert any("Udyam tier unavailable" in lim for lim in result.limitations)


@pytest.mark.asyncio
async def test_returns_insufficient_data_when_all_tiers_fail(base_case_state):
    base_case_state.selected_business.sector = "unmapped_sector"
    udyam = FakeUdyamAdapter(AdapterResult.insufficient("Udyam", "no dataset configured"))
    overpass = FakeOverpassAdapter(AdapterResult.insufficient("Overpass", "not reached"))

    agent = CompetitorAgent(udyam_adapter=udyam, overpass_adapter=overpass, data_mode="real")
    result = await agent.run(base_case_state)

    assert result.competitor_count is None
    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert result.saturation_level == SaturationLevel.UNKNOWN
    assert any("web-search extraction" in lim.lower() for lim in result.limitations)


@pytest.mark.asyncio
async def test_never_fabricates_population_when_missing(base_case_state):
    # No market_reach population set on purpose.
    udyam = FakeUdyamAdapter(AdapterResult(data=3, confidence=Confidence.REAL_DATA, source="Udyam"))
    overpass = FakeOverpassAdapter(AdapterResult.insufficient("Overpass", "should not be called"))

    agent = CompetitorAgent(udyam_adapter=udyam, overpass_adapter=overpass, data_mode="real")
    result = await agent.run(base_case_state)

    assert result.competitor_count == 3
    assert result.density_score is None
    assert any("not available in case state" in lim for lim in result.limitations)
