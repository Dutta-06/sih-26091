"""
Competitor Agent (TDD Section 5.3, "Competitor mapping"):

    "Estimates the density of existing similar enterprises using a tiered
    fallback approach across multiple data sources, normalizes the result
    by local population, and benchmarks it against district and state
    averages."

Tiered fallback, per the architecture diagram's tech note ("tiered fallback
chain (Udyam query, then Overpass/Places, then web-search extraction)"):
    1. Udyam Registration bulk dataset (REAL_DATA if a match is found)
    2. OpenStreetMap Overpass (REAL_DATA, counts nearby same-category POIs)
    3. Web-search extraction — NOT implemented in this build. No web-search
       provider is wired into this codebase, and fabricating a scraper
       against an unspecified provider would violate the "never invent
       APIs" instruction. This tier is a documented gap: it returns
       INSUFFICIENT_DATA with an explicit note instead of pretending to
       work.

Population normalization only happens when population data is present in
the case state (written by the Market Reach agent — out of scope for this
build). District/state benchmark normalization requires district/state
population figures which also come from outside this agent's scope; if
absent, benchmarks are left unset with a limitation note rather than
guessed.
"""

from __future__ import annotations

import logging

from src.adapters.overpass_adapter import OverpassAdapter
from src.adapters.udyam_adapter import UdyamAdapter
from src.config import settings
from src.mockdb import queries as mockdb_queries
from src.mockdb import schema as mockdb_schema
from src.schemas import CaseState, CompetitorAgentOutput, Confidence, SaturationLevel, SourceRecord

logger = logging.getLogger(__name__)

MOCK_SOURCE_NAME = "Mock Database (data/mock.db)"

# Maps a case's business sector to the `category` column used in the mock
# database's `businesses` table (src/mockdb/seed_data.py::CATEGORY_PROFILES).
# Sectors with no entry here have no mock coverage; per DATA_MODE=mock's
# "never fall back to a live adapter" rule, those return INSUFFICIENT_DATA
# rather than querying Overpass/Udyam.
_SECTOR_TO_MOCK_CATEGORY: dict[str, str] = {
    "grocery": "grocery",
    "kirana": "grocery",
    "dairy": "dairy",
    "tailoring": "tailoring",
    "bakery": "bakery",
    "hardware": "hardware",
    "agro_input": "agro_input",
}


# Conservative sector -> OSM shop/amenity tag heuristic. This is an
# engineering mapping decision (how to query OSM for "similar enterprises"),
# not a fabricated data source — Overpass itself remains the real API.
# Sectors not present here are simply unsupported by the Overpass fallback
# tier and the agent will report INSUFFICIENT_DATA for that tier.
_SECTOR_TO_OSM_TAGS: dict[str, list[tuple[str, str]]] = {
    "grocery": [("shop", "convenience"), ("shop", "grocery")],
    "kirana": [("shop", "convenience"), ("shop", "grocery")],
    "tailoring": [("shop", "tailor")],
    "dairy": [("shop", "dairy")],
    "bakery": [("shop", "bakery")],
    "hardware": [("shop", "hardware"), ("shop", "doityourself")],
    "electronics_repair": [("shop", "electronics"), ("craft", "electronics_repair")],
    "beauty_salon": [("shop", "hairdresser"), ("shop", "beauty")],
    "restaurant": [("amenity", "restaurant"), ("amenity", "fast_food")],
    "agro_input": [("shop", "agrarian")],
}

_SATURATION_THRESHOLDS = {
    # competitors per 10,000 population
    "low_max": 3.0,
    "medium_max": 8.0,
}


def _saturation_from_density(density_per_10k: float | None) -> SaturationLevel:
    if density_per_10k is None:
        return SaturationLevel.UNKNOWN
    if density_per_10k <= _SATURATION_THRESHOLDS["low_max"]:
        return SaturationLevel.LOW
    if density_per_10k <= _SATURATION_THRESHOLDS["medium_max"]:
        return SaturationLevel.MEDIUM
    return SaturationLevel.HIGH


class CompetitorAgent:
    def __init__(
        self,
        udyam_adapter: UdyamAdapter | None = None,
        overpass_adapter: OverpassAdapter | None = None,
        data_mode: str | None = None,
    ) -> None:
        self.udyam_adapter = udyam_adapter or UdyamAdapter()
        self.overpass_adapter = overpass_adapter or OverpassAdapter()
        # Resolved once per agent instance, not per call, so a single run()
        # is never half-mock/half-real if settings change mid-process.
        self.data_mode = (data_mode or settings.data_mode).strip().lower()

    async def run(
        self,
        case_state: CaseState,
        radius_meters: int = 5000,
        district_population: float | None = None,
        state_population: float | None = None,
    ) -> CompetitorAgentOutput:
        if self.data_mode == "mock":
            return await self._run_mock(case_state, radius_meters, district_population, state_population)
        return await self._run_real(case_state, radius_meters, district_population, state_population)

    # ------------------------------------------------------------------
    # Mock tier: reads exclusively from data/mock.db via src/mockdb/*.
    # NEVER calls self.udyam_adapter / self.overpass_adapter.
    # ------------------------------------------------------------------
    async def _run_mock(
        self,
        case_state: CaseState,
        radius_meters: int,
        district_population: float | None,
        state_population: float | None,
    ) -> CompetitorAgentOutput:
        logger.info("[MOCK] Competitor Agent → mock.db")

        selected = case_state.selected_business
        location = case_state.entrepreneur_profile.get("location", {})
        district = location.get("district")
        block = location.get("block")
        village = location.get("village")
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        local_population = (case_state.market_intelligence.market_reach or {}).get("population")

        sector_key = (selected.sector or selected.name).lower().replace(" ", "_") if selected else None
        category = _SECTOR_TO_MOCK_CATEGORY.get(sector_key) if sector_key else None

        if not category:
            return CompetitorAgentOutput(
                confidence=Confidence.INSUFFICIENT_DATA,
                sources=[SourceRecord(name=MOCK_SOURCE_NAME, confidence=Confidence.INSUFFICIENT_DATA)],
                limitations=[
                    f"Mock tier: no mock-database category mapping for sector '{sector_key}'. "
                    "DATA_MODE=mock never falls back to a live adapter (Udyam/Overpass); "
                    "returning INSUFFICIENT_DATA instead.",
                ],
            )

        conn = mockdb_schema.connect(settings.mock_db_path)
        try:
            if latitude is not None and longitude is not None:
                result = mockdb_queries.find_businesses(
                    conn,
                    category=category,
                    latitude=latitude,
                    longitude=longitude,
                    radius_km=radius_meters / 1000,
                )
            else:
                result = mockdb_queries.find_businesses(
                    conn, category=category, village=village, block=block, district=district,
                )
        finally:
            conn.close()

        competitor_count = result["count"]
        limitations = [
            "Competitor count sourced from the local mock database (data/mock.db) — every matched "
            "record is marked data_status=MOCK_DATA / source=MOCK_DATABASE, not a live external source.",
        ]
        if competitor_count == 0:
            limitations.append("Mock database query returned zero matching businesses for the given category/location.")

        density_score: float | None = None
        if competitor_count is not None and local_population:
            density_score = round((competitor_count / local_population) * 10000, 3)
        else:
            limitations.append(
                "Local population not available in case state (owned by the Market Reach agent); "
                "competitor count could not be normalized into a density score."
            )

        benchmark_district = round((competitor_count / district_population) * 10000, 3) if district_population else None
        benchmark_state = round((competitor_count / state_population) * 10000, 3) if state_population else None
        if benchmark_district is None and benchmark_state is None:
            limitations.append("District/state population figures not supplied; benchmark comparison not computed.")

        return CompetitorAgentOutput(
            competitor_count=competitor_count,
            density_score=density_score,
            saturation_level=_saturation_from_density(density_score),
            benchmark_district_density=benchmark_district,
            benchmark_state_density=benchmark_state,
            sources=[SourceRecord(name=MOCK_SOURCE_NAME, confidence=Confidence.ESTIMATED)],
            confidence=Confidence.ESTIMATED,
            limitations=limitations,
        )

    # ------------------------------------------------------------------
    # Real tier: unchanged tiered Udyam -> Overpass -> (unimplemented
    # web-search) fallback chain, exactly as before this change.
    # ------------------------------------------------------------------
    async def _run_real(
        self,
        case_state: CaseState,
        radius_meters: int,
        district_population: float | None,
        state_population: float | None,
    ) -> CompetitorAgentOutput:
        selected = case_state.selected_business
        location = case_state.entrepreneur_profile.get("location", {})
        district = location.get("district")
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        local_population = (case_state.market_intelligence.market_reach or {}).get("population")

        sources: list[SourceRecord] = []
        limitations: list[str] = []
        competitor_count: int | None = None
        confidence = Confidence.INSUFFICIENT_DATA

        # --- Tier 1: Udyam bulk dataset ---
        ncs_code = selected.ncs_code if selected else None
        udyam_result = await self.udyam_adapter.count_registered_enterprises(district, ncs_code)
        sources.append(SourceRecord(name=self.udyam_adapter.name, confidence=udyam_result.confidence))
        if udyam_result.confidence == Confidence.REAL_DATA:
            competitor_count = udyam_result.data
            confidence = Confidence.REAL_DATA
        else:
            limitations.extend(f"Udyam tier: {msg}" for msg in udyam_result.limitations)

            # --- Tier 2: Overpass fallback ---
            sector_key = (selected.sector or selected.name).lower().replace(" ", "_") if selected else None
            osm_tags = _SECTOR_TO_OSM_TAGS.get(sector_key) if sector_key else None
            if osm_tags and latitude is not None and longitude is not None:
                overpass_result = await self.overpass_adapter.query_nearby(
                    latitude, longitude, radius_meters, osm_tags
                )
                sources.append(SourceRecord(name=self.overpass_adapter.name, confidence=overpass_result.confidence))
                if overpass_result.confidence == Confidence.REAL_DATA:
                    competitor_count = len(overpass_result.data)
                    confidence = Confidence.REAL_DATA
                    limitations.append(
                        "Competitor count sourced from OSM Overpass (Udyam tier unavailable); "
                        "OSM shop/amenity tagging coverage is uneven in rural areas and may undercount."
                    )
                else:
                    limitations.extend(f"Overpass tier: {msg}" for msg in overpass_result.limitations)
            else:
                limitations.append(
                    "Overpass tier: no OSM tag mapping available for this business sector, or coordinates missing."
                )

            # --- Tier 3: web-search extraction (not implemented) ---
            if competitor_count is None:
                limitations.append(
                    "Web-search extraction tier: not implemented in this build (no web-search provider "
                    "configured). Returning INSUFFICIENT_DATA rather than fabricating a result."
                )

        density_score: float | None = None
        if competitor_count is not None and local_population:
            density_score = round((competitor_count / local_population) * 10000, 3)
        elif competitor_count is not None:
            limitations.append(
                "Local population not available in case state (owned by the Market Reach agent); "
                "competitor count could not be normalized into a density score."
            )

        benchmark_district = None
        benchmark_state = None
        if competitor_count is not None and district_population:
            benchmark_district = round((competitor_count / district_population) * 10000, 3)
        if competitor_count is not None and state_population:
            benchmark_state = round((competitor_count / state_population) * 10000, 3)
        if benchmark_district is None and benchmark_state is None and competitor_count is not None:
            limitations.append(
                "District/state population figures not supplied; benchmark comparison not computed."
            )

        return CompetitorAgentOutput(
            competitor_count=competitor_count,
            density_score=density_score,
            saturation_level=_saturation_from_density(density_score),
            benchmark_district_density=benchmark_district,
            benchmark_state_density=benchmark_state,
            sources=sources,
            confidence=confidence,
            limitations=limitations,
        )
