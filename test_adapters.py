from __future__ import annotations

import pytest

from src.adapters.commodity_price_adapter import CommodityPriceAdapter
from src.adapters.overpass_adapter import OverpassAdapter
from src.adapters.purchasing_power_adapter import PurchasingPowerAdapter
from src.adapters.routing_adapter import RoutingAdapter
from src.adapters.udyam_adapter import UdyamAdapter
from src.config import Settings
from src.schemas import Confidence


@pytest.mark.asyncio
async def test_udyam_adapter_insufficient_when_dataset_path_missing():
    adapter = UdyamAdapter(dataset_path=None)
    result = await adapter.count_registered_enterprises(district="Meerut", ncs_code="123")
    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert "UDYAM_DATASET_PATH" in result.limitations[0]


@pytest.mark.asyncio
async def test_udyam_adapter_insufficient_when_file_not_found(tmp_path):
    adapter = UdyamAdapter(dataset_path=str(tmp_path / "does_not_exist.csv"))
    result = await adapter.count_registered_enterprises(district="Meerut", ncs_code=None)
    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert "not found" in result.limitations[0].lower()


@pytest.mark.asyncio
async def test_udyam_adapter_real_data_from_csv(tmp_path):
    csv_path = tmp_path / "udyam.csv"
    csv_path.write_text("District,NIC_Code\nMeerut,123\nMeerut,123\nGhaziabad,123\n")
    adapter = UdyamAdapter(dataset_path=str(csv_path))
    result = await adapter.count_registered_enterprises(district="Meerut", ncs_code="123")
    assert result.confidence == Confidence.REAL_DATA
    assert result.data == 2


@pytest.mark.asyncio
async def test_commodity_price_adapter_insufficient_when_api_key_missing(monkeypatch):
    # Settings is a frozen dataclass (by design, so nothing mutates config
    # mid-run); rebind the module-level `settings` name to a fresh instance
    # instead of mutating fields on the shared singleton.
    fake_settings = Settings(data_gov_in_api_key=None, commodity_price_resource_id="some-id")
    monkeypatch.setattr("src.adapters.commodity_price_adapter.settings", fake_settings)
    adapter = CommodityPriceAdapter()
    result = await adapter.get_price_range(commodity="wheat", district="Meerut", state="UP")
    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert "DATA_GOV_IN_API_KEY" in result.limitations[0]


@pytest.mark.asyncio
async def test_purchasing_power_adapter_insufficient_when_dataset_missing():
    adapter = PurchasingPowerAdapter(dataset_path=None)
    result = await adapter.get_asset_index(district="Meerut")
    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert "SECC_DATASET_PATH" in result.limitations[0]


@pytest.mark.asyncio
async def test_purchasing_power_adapter_insufficient_when_district_not_in_file(tmp_path):
    csv_path = tmp_path / "secc.csv"
    csv_path.write_text("District,AssetIndex\nGhaziabad,0.5\n")
    adapter = PurchasingPowerAdapter(dataset_path=str(csv_path))
    result = await adapter.get_asset_index(district="Meerut")
    assert result.confidence == Confidence.INSUFFICIENT_DATA
    assert "No SECC record" in result.limitations[0]


@pytest.mark.asyncio
async def test_overpass_adapter_insufficient_when_coordinates_missing():
    adapter = OverpassAdapter()
    result = await adapter.query_nearby(latitude=None, longitude=None, radius_meters=5000, osm_tags=[("shop", "grocery")])
    assert result.confidence == Confidence.INSUFFICIENT_DATA


@pytest.mark.asyncio
async def test_routing_adapter_insufficient_when_endpoints_missing():
    adapter = RoutingAdapter()
    result = await adapter.route(origin=None, destination=(28.98, 77.70))
    assert result.confidence == Confidence.INSUFFICIENT_DATA
