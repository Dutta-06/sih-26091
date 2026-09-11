"""
OpenStreetMap Overpass API adapter (TDD Section 8: "OpenStreetMap Overpass
API" -> "Nearby markets, shops, and infrastructure").

Used by:
  - Competitor Agent: as the fallback tier when Udyam data is unavailable
    (TDD architecture diagram: "tiered fallback chain (Udyam query, then
    Overpass/Places, then web-search extraction)").
  - Supply Chain Agent: suppliers, markets, and distribution points.

Endpoint is the standard public Overpass instance (overpass-api.de) — real,
documented, keyless. No credentials are required or invented.
"""

from __future__ import annotations

import httpx

from src.adapters.base import Adapter, AdapterResult
from src.config import settings
from src.schemas import Confidence


class OverpassAdapter(Adapter):
    name = "OpenStreetMap Overpass API"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=settings.overpass_timeout_seconds)
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    def build_nearby_query(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
        osm_tags: list[tuple[str, str]],
    ) -> str:
        """Builds an Overpass QL query for nodes/ways matching any of the
        given (key, value) tags within radius_meters of the point."""
        clauses = "\n".join(
            f'  node["{k}"="{v}"](around:{radius_meters},{latitude},{longitude});\n'
            f'  way["{k}"="{v}"](around:{radius_meters},{latitude},{longitude});'
            for k, v in osm_tags
        )
        return f"""
[out:json][timeout:{int(settings.overpass_timeout_seconds)}];
(
{clauses}
);
out center tags;
""".strip()

    async def query_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
        osm_tags: list[tuple[str, str]],
    ) -> AdapterResult[list[dict]]:
        if latitude is None or longitude is None:
            return AdapterResult.insufficient(self.name, "No coordinates provided for Overpass query.")

        query = self.build_nearby_query(latitude, longitude, radius_meters, osm_tags)
        client = await self._get_client()

        try:
            response = await client.post(settings.overpass_base_url, data={"data": query})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return AdapterResult.insufficient(
                self.name, f"Overpass API request failed: {exc.__class__.__name__}: {exc}"
            )

        try:
            payload = response.json()
        except ValueError:
            return AdapterResult.insufficient(self.name, "Overpass API returned a non-JSON response.")

        elements = payload.get("elements", [])
        if not elements:
            return AdapterResult(
                data=[],
                confidence=Confidence.REAL_DATA,
                source=self.name,
                limitations=["Overpass query returned zero matching elements in the given radius."],
            )

        parsed = []
        for el in elements:
            tags = el.get("tags", {})
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            parsed.append(
                {
                    "osm_id": el.get("id"),
                    "osm_type": el.get("type"),
                    "name": tags.get("name"),
                    "tags": tags,
                    "latitude": lat,
                    "longitude": lon,
                }
            )

        return AdapterResult(data=parsed, confidence=Confidence.REAL_DATA, source=self.name)
