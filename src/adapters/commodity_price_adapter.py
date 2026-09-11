"""
Government commodity price open data API adapter (TDD Section 8:
"Government commodity price open data API" -> "Real agricultural pricing
and seasonal patterns").

BLOCKING GAP, documented rather than guessed: the TDD names the source
category but not the concrete dataset/resource id. The realistic match is
data.gov.in's Agmarknet "Variety-wise Daily Market Prices" API family,
which requires (a) a registered api-key and (b) a specific resource id per
dataset/commodity. Neither is fabricated here — both must be supplied via
DATA_GOV_IN_API_KEY and COMMODITY_PRICE_RESOURCE_ID. Without them this
adapter returns INSUFFICIENT_DATA and the Pricing Agent falls back to the
purchasing-power-proxy estimate path, exactly as TDD Section 5.3 specifies
("for categories without direct data, estimates ... explicitly labels
which figures are real and which are estimated").
"""

from __future__ import annotations

import httpx

from src.adapters.base import Adapter, AdapterResult
from src.config import settings
from src.schemas import Confidence


class CommodityPriceAdapter(Adapter):
    name = "Government commodity price open data API"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def get_price_range(
        self,
        commodity: str,
        district: str | None,
        state: str | None,
    ) -> AdapterResult[dict]:
        if not settings.data_gov_in_api_key or not settings.commodity_price_resource_id:
            missing = []
            if not settings.data_gov_in_api_key:
                missing.append("DATA_GOV_IN_API_KEY")
            if not settings.commodity_price_resource_id:
                missing.append("COMMODITY_PRICE_RESOURCE_ID")
            return AdapterResult.insufficient(
                self.name,
                f"Missing required configuration for the commodity price API: {', '.join(missing)}. "
                "The TDD names this source category but not a specific dataset/resource id.",
            )

        url = f"{settings.data_gov_in_base_url}/{settings.commodity_price_resource_id}"
        params = {
            "api-key": settings.data_gov_in_api_key,
            "format": "json",
            "filters[commodity]": commodity,
        }
        if district:
            params["filters[district]"] = district
        if state:
            params["filters[state]"] = state

        client = await self._get_client()
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return AdapterResult.insufficient(
                self.name, f"Commodity price API request failed: {exc.__class__.__name__}: {exc}"
            )

        try:
            payload = response.json()
        except ValueError:
            return AdapterResult.insufficient(self.name, "Commodity price API returned a non-JSON response.")

        records = payload.get("records", [])
        if not records:
            return AdapterResult.insufficient(
                self.name, f"No price records returned for '{commodity}' in the given location."
            )

        prices = []
        for rec in records:
            for key in ("modal_price", "Modal_Price", "modal_x0020_price"):
                if key in rec:
                    try:
                        prices.append(float(rec[key]))
                    except (TypeError, ValueError):
                        pass
                    break

        if not prices:
            return AdapterResult.insufficient(
                self.name, "Price records returned but no parseable modal price field found."
            )

        return AdapterResult(
            data={
                "price_min": min(prices),
                "price_max": max(prices),
                "representative_price": sum(prices) / len(prices),
                "sample_size": len(prices),
            },
            confidence=Confidence.REAL_DATA,
            source=self.name,
        )
