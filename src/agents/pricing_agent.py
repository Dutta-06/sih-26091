"""
Pricing Agent (TDD Section 5.3, "Pricing analysis"):

    "For categories with direct market price data, uses real recorded
    prices; for categories without direct data, estimates a representative
    local price range using a purchasing-power proxy, and explicitly labels
    which figures are real and which are estimated."

Two-tier flow:
    1. Government commodity price API — only for commodities the API
       actually covers (agricultural commodities). REAL_DATA.
    2. Purchasing-power proxy (SECC asset index) — a representative price
       range is derived from a base reference price for the category
       scaled by the local asset index. ESTIMATED, never presented as a
       real price.

If neither tier has usable data, the agent returns INSUFFICIENT_DATA
rather than inventing numbers. This agent never fabricates a market price.
"""

from __future__ import annotations

import logging

from src.adapters.commodity_price_adapter import CommodityPriceAdapter
from src.adapters.purchasing_power_adapter import PurchasingPowerAdapter
from src.config import settings
from src.mockdb import queries as mockdb_queries
from src.mockdb import schema as mockdb_schema
from src.schemas import CaseState, Confidence, PricingAgentOutput

logger = logging.getLogger(__name__)

MOCK_SOURCE_NAME = "Mock Database (data/mock.db)"



class PricingAgent:
    def __init__(
        self,
        commodity_price_adapter: CommodityPriceAdapter | None = None,
        purchasing_power_adapter: PurchasingPowerAdapter | None = None,
        data_mode: str | None = None,
    ) -> None:
        self.commodity_price_adapter = commodity_price_adapter or CommodityPriceAdapter()
        self.purchasing_power_adapter = purchasing_power_adapter or PurchasingPowerAdapter()
        self.data_mode = (data_mode or settings.data_mode).strip().lower()

    async def run(
        self,
        case_state: CaseState,
        commodity: str | None = None,
        unit: str | None = None,
        base_reference_price: float | None = None,
    ) -> PricingAgentOutput:
        if self.data_mode == "mock":
            return await self._run_mock(case_state, commodity=commodity, unit=unit)
        return await self._run_real(
            case_state, commodity=commodity, unit=unit, base_reference_price=base_reference_price
        )

    # ------------------------------------------------------------------
    # Mock tier: reads exclusively from data/mock.db's `prices` table via
    # src/mockdb/queries.py::find_prices. NEVER calls
    # self.commodity_price_adapter / self.purchasing_power_adapter.
    #
    # Note: the mock database (src/mockdb/schema.py) has no
    # purchasing-power/asset-index table — it models directly priced
    # products (milk, wheat, cattle_feed, ...) in `prices`, not a SECC-style
    # index to scale a reference price by. So there is only one mock tier
    # here (direct product price lookup), not the real agent's two tiers.
    # A commodity/product name is therefore required in mock mode; without
    # one this returns INSUFFICIENT_DATA rather than inventing an estimate
    # tier the mock database doesn't actually support.
    # ------------------------------------------------------------------
    async def _run_mock(
        self,
        case_state: CaseState,
        commodity: str | None,
        unit: str | None,
    ) -> PricingAgentOutput:
        logger.info("[MOCK] Pricing Agent → mock.db")

        location = case_state.entrepreneur_profile.get("location", {})
        district = location.get("district")

        if not commodity:
            return PricingAgentOutput(
                price_min=None, price_max=None, representative_price=None, unit=unit,
                data_source="none", is_estimated=True, confidence=Confidence.INSUFFICIENT_DATA,
                limitations=[
                    "Mock tier: no commodity/product name supplied. The mock database only models "
                    "directly priced products (data/mock.db::prices), not a purchasing-power/asset-"
                    "index proxy to scale a reference price by, so a product name is required. "
                    "DATA_MODE=mock never falls back to a live commodity price or SECC adapter.",
                ],
            )
        if not district:
            return PricingAgentOutput(
                price_min=None, price_max=None, representative_price=None, unit=unit,
                data_source="none", is_estimated=True, confidence=Confidence.INSUFFICIENT_DATA,
                limitations=["No district available in case state to look up mock price records."],
            )

        product = commodity.strip().lower().replace(" ", "_")
        conn = mockdb_schema.connect(settings.mock_db_path)
        try:
            result = mockdb_queries.find_prices(conn, product=product, district=district)
        finally:
            conn.close()

        if not result["records"]:
            return PricingAgentOutput(
                price_min=None, price_max=None, representative_price=None, unit=unit,
                data_source="none", is_estimated=True, confidence=Confidence.INSUFFICIENT_DATA,
                limitations=[
                    f"Mock tier: no mock price records for product '{product}' in district '{district}'. "
                    "DATA_MODE=mock never falls back to a live commodity price API.",
                ],
            )

        return PricingAgentOutput(
            price_min=result["min_price"],
            price_max=result["max_price"],
            representative_price=result["representative_price"],
            unit=unit or result["unit"],
            pricing_basis="mock_database",
            data_source=MOCK_SOURCE_NAME,
            is_estimated=True,
            confidence=Confidence.ESTIMATED,
            limitations=[
                f"Sourced from the local mock database (data/mock.db), {len(result['records'])} "
                f"record(s), most recent date {result['date']}. All rows are marked "
                "data_status=MOCK_DATA / source=MOCK_DATABASE — not a live government price feed.",
            ],
        )

    # ------------------------------------------------------------------
    # Real tier: unchanged two-tier commodity-price -> purchasing-power
    # flow, exactly as before this change.
    # ------------------------------------------------------------------
    async def _run_real(
        self,
        case_state: CaseState,
        commodity: str | None = None,
        unit: str | None = None,
        base_reference_price: float | None = None,
    ) -> PricingAgentOutput:
        """
        commodity: name to look up in the government commodity price API
            (only meaningful for categories that API actually covers —
            typically agricultural produce). Pass None to skip straight
            to the estimate tier for non-agricultural categories.
        base_reference_price: a known reference price for the category
            (e.g. a national or state average) that the purchasing-power
            asset index scales, required for the estimate tier to produce
            a range instead of just a raw index number. Must be supplied
            by the caller / case state — this agent will not invent one.
        """
        location = case_state.entrepreneur_profile.get("location", {})
        district = location.get("district")

        # --- Tier 1: real commodity price data ---
        if commodity:
            price_result = await self.commodity_price_adapter.get_price_range(
                commodity=commodity, district=district, state=location.get("state")
            )
            if price_result.confidence == Confidence.REAL_DATA:
                data = price_result.data
                return PricingAgentOutput(
                    price_min=data["price_min"],
                    price_max=data["price_max"],
                    representative_price=round(data["representative_price"], 2),
                    unit=unit,
                    data_source=self.commodity_price_adapter.name,
                    is_estimated=False,
                    confidence=Confidence.REAL_DATA,
                    limitations=[f"Sample size: {data.get('sample_size')} records."],
                )
            tier1_limitations = [f"Commodity price tier: {m}" for m in price_result.limitations]
        else:
            tier1_limitations = [
                "Commodity price tier skipped: no commodity name supplied (category is not "
                "a directly priced agricultural commodity)."
            ]

        # --- Tier 2: purchasing-power proxy estimate ---
        if not district:
            return PricingAgentOutput(
                price_min=None,
                price_max=None,
                representative_price=None,
                unit=unit,
                data_source="none",
                is_estimated=True,
                confidence=Confidence.INSUFFICIENT_DATA,
                limitations=tier1_limitations + ["No district available to look up the purchasing-power proxy."],
            )

        asset_result = await self.purchasing_power_adapter.get_asset_index(district)
        if asset_result.confidence != Confidence.ESTIMATED or asset_result.data is None:
            return PricingAgentOutput(
                price_min=None,
                price_max=None,
                representative_price=None,
                unit=unit,
                data_source="none",
                is_estimated=True,
                confidence=Confidence.INSUFFICIENT_DATA,
                limitations=tier1_limitations + [f"Purchasing-power tier: {m}" for m in asset_result.limitations],
            )

        if base_reference_price is None:
            return PricingAgentOutput(
                price_min=None,
                price_max=None,
                representative_price=None,
                unit=unit,
                data_source=self.purchasing_power_adapter.name,
                is_estimated=True,
                confidence=Confidence.INSUFFICIENT_DATA,
                limitations=tier1_limitations
                + [
                    "Asset index available but no base_reference_price supplied to scale it against; "
                    "cannot derive a price range from an index alone."
                ],
            )

        # Asset index assumed normalized 0-1; scale reference price +/-20%
        # around it. This scaling rule is an explicit, documented modeling
        # choice, not a claim of real observed prices.
        idx = max(0.0, min(1.0, asset_result.data))
        representative = round(base_reference_price * (0.8 + 0.4 * idx), 2)
        price_min = round(representative * 0.9, 2)
        price_max = round(representative * 1.1, 2)

        return PricingAgentOutput(
            price_min=price_min,
            price_max=price_max,
            representative_price=representative,
            unit=unit,
            pricing_basis="mock_database",
            data_source=self.purchasing_power_adapter.name,
            is_estimated=True,
            confidence=Confidence.ESTIMATED,
            limitations=tier1_limitations
            + [
                "Representative price is ESTIMATED: derived from a base reference price scaled by the "
                "local SECC purchasing-power asset index, not a directly observed market price.",
            ],
        )
