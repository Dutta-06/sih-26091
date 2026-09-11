from __future__ import annotations

import pytest

from src.adapters.base import AdapterResult
from src.agents.supply_chain_agent import SupplyChainAgent
from src.schemas import Confidence


class FakeOverpassAdapter:
    name = "OpenStreetMap Overpass API"

    def __init__(self, responses: dict[str, AdapterResult]):
        # keyed by a marker in the tags list to distinguish supplier vs distribution queries
        self._responses = responses
        self.calls = []

    async def query_nearby(self, latitude, longitude, radius_meters, osm_tags):
        self.calls.append(osm_tags)
        if osm_tags == [("amenity", "marketplace"), ("shop", "supermarket")]:
            return self._responses["distribution"]
        return self._responses["supplier"]


class FakeRoutingAdapter:
    name = "Open-source routing engine (OSRM)"

    def __init__(self, result: AdapterResult):
        self._result = result
        self.calls = []

    async def route(self, origin, destination):
        self.calls.append((origin, destination))
        return self._result


@pytest.mark.asyncio
async def test_single_supplier_flags_dependency(base_case_state):
    supplier_data = [{"osm_id": 1, "osm_type": "node", "name": "Only Wholesaler", "tags": {}, "latitude": 28.99, "longitude": 77.71}]
    overpass = FakeOverpassAdapter(
        {
            "supplier": AdapterResult(data=supplier_data, confidence=Confidence.REAL_DATA, source="overpass"),
            "distribution": AdapterResult(data=[], confidence=Confidence.REAL_DATA, source="overpass"),
        }
    )
    routing = FakeRoutingAdapter(AdapterResult(data={"distance_km": 5.2, "duration_minutes": 12.0}, confidence=Confidence.REAL_DATA, source="osrm"))

    agent = SupplyChainAgent(overpass_adapter=overpass, routing_adapter=routing, data_mode="real")
    result = await agent.run(base_case_state)

    assert result.confidence == Confidence.REAL_DATA
    assert len(result.suppliers) == 1
    assert result.supplier_concentration_flag == "single_supplier_dependency"
    assert any("single-supplier dependency" in v for v in result.vulnerability_summary)
    assert len(result.route_risks) == 1
    assert result.route_risks[0].distance_km == 5.2


@pytest.mark.asyncio
async def test_long_route_flagged(base_case_state):
    supplier_data = [{"osm_id": 1, "osm_type": "node", "name": "Far Wholesaler", "tags": {}, "latitude": 29.5, "longitude": 78.5}]
    overpass = FakeOverpassAdapter(
        {
            "supplier": AdapterResult(data=supplier_data, confidence=Confidence.REAL_DATA, source="overpass"),
            "distribution": AdapterResult(data=[], confidence=Confidence.REAL_DATA, source="overpass"),
        }
    )
    routing = FakeRoutingAdapter(AdapterResult(data={"distance_km": 45.0, "duration_minutes": 70.0}, confidence=Confidence.REAL_DATA, source="osrm"))

    agent = SupplyChainAgent(overpass_adapter=overpass, routing_adapter=routing, data_mode="real")
    result = await agent.run(base_case_state)

    assert result.route_risks[0].accessibility_flag == "long_supply_route"
    assert any("above the" in v for v in result.vulnerability_summary)


@pytest.mark.asyncio
async def test_missing_coordinates_returns_insufficient_data(base_case_state):
    base_case_state.entrepreneur_profile["location"]["latitude"] = None
    base_case_state.entrepreneur_profile["location"]["longitude"] = None

    overpass = FakeOverpassAdapter(
        {
            "supplier": AdapterResult.insufficient("overpass", "unused"),
            "distribution": AdapterResult.insufficient("overpass", "unused"),
        }
    )
    routing = FakeRoutingAdapter(AdapterResult.insufficient("osrm", "unused"))

    agent = SupplyChainAgent(overpass_adapter=overpass, routing_adapter=routing, data_mode="real")
    result = await agent.run(base_case_state)

    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert result.suppliers == []
    assert "coordinates" in result.limitations[0].lower()


@pytest.mark.asyncio
async def test_no_suppliers_found_does_not_fabricate(base_case_state):
    overpass = FakeOverpassAdapter(
        {
            "supplier": AdapterResult(data=[], confidence=Confidence.REAL_DATA, source="overpass"),
            "distribution": AdapterResult(data=[], confidence=Confidence.REAL_DATA, source="overpass"),
        }
    )
    routing = FakeRoutingAdapter(AdapterResult.insufficient("osrm", "unused"))

    agent = SupplyChainAgent(overpass_adapter=overpass, routing_adapter=routing, data_mode="real")
    result = await agent.run(base_case_state)

    assert result.suppliers == []
    assert result.supplier_concentration_flag == "no_suppliers_found_in_radius"
    assert result.route_risks == []  # no candidates to route to
