"""
Open-source routing engine adapter (TDD Section 8: "Open-source routing
engine over open map data" -> "Supply chain and accessibility risk";
architecture diagram tech note names OSRM specifically).

Uses the public OSRM demo server (router.project-osrm.org) by default —
real, documented, keyless. This is explicitly NOT a production-grade
dependency: OSRM's own project documentation states the demo server is
rate-limited and offered for evaluation only, with no uptime guarantee.
That caveat is surfaced in every result's `limitations` when the default
is in use. Production deployments must set OSRM_BASE_URL to a self-hosted
OSRM instance over their own map extract.
"""

from __future__ import annotations

import httpx

from src.adapters.base import Adapter, AdapterResult
from src.config import settings
from src.schemas import Confidence


class RoutingAdapter(Adapter):
    name = "Open-source routing engine (OSRM)"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> AdapterResult[dict]:
        if origin is None or destination is None:
            return AdapterResult.insufficient(self.name, "Origin or destination coordinates missing.")

        o_lon, o_lat = origin[1], origin[0]
        d_lon, d_lat = destination[1], destination[0]
        url = f"{settings.osrm_base_url}/route/v1/driving/{o_lon},{o_lat};{d_lon},{d_lat}"

        client = await self._get_client()
        try:
            response = await client.get(url, params={"overview": "false"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return AdapterResult.insufficient(
                self.name, f"Routing request failed: {exc.__class__.__name__}: {exc}"
            )

        try:
            payload = response.json()
        except ValueError:
            return AdapterResult.insufficient(self.name, "Routing API returned a non-JSON response.")

        routes = payload.get("routes", [])
        if payload.get("code") != "Ok" or not routes:
            return AdapterResult.insufficient(
                self.name, f"No route found between the two points (code={payload.get('code')})."
            )

        best = routes[0]
        limitations = []
        if settings.osrm_is_public_demo:
            limitations.append(
                "Using the public OSRM demo server (rate-limited, no uptime guarantee per OSRM's own "
                "documentation). Set OSRM_BASE_URL to a self-hosted instance for production use."
            )

        return AdapterResult(
            data={
                "distance_km": round(best["distance"] / 1000, 2),
                "duration_minutes": round(best["duration"] / 60, 1),
            },
            confidence=Confidence.REAL_DATA,
            source=self.name,
            limitations=limitations,
        )
