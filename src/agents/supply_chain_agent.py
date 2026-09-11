"""
Supply Chain Agent (TDD Section 5.3, "Risk analysis" supply-chain
dimension, and Section 8: "Road distance and routing" -> "Supply chain and
accessibility risk"):

Identifies nearby suppliers and distribution points via OSM Overpass,
evaluates route distance/duration/accessibility to each via the routing
adapter, and flags structural supply-chain vulnerabilities such as single-
supplier dependency, consistent with TDD Section 5.3's "curated taxonomy
of structural business risks."
"""

from __future__ import annotations

import logging

from src.adapters.overpass_adapter import OverpassAdapter
from src.adapters.routing_adapter import RoutingAdapter
from src.config import settings
from src.mockdb import queries as mockdb_queries
from src.mockdb import schema as mockdb_schema
from src.schemas import CaseState, Confidence, RouteRisk, SourceRecord, SupplierRecord, SupplyChainAgentOutput

logger = logging.getLogger(__name__)

MOCK_SOURCE_NAME = "Mock Database (data/mock.db)"

# Maps a case's business sector to the `category` column used in the mock
# database's `suppliers` table (src/mockdb/seed_data.py::_SUPPLIER_PROFILES).
_SECTOR_TO_MOCK_SUPPLIER_CATEGORY: dict[str, str] = {
    "grocery": "grocery_wholesale",
    "kirana": "grocery_wholesale",
    "dairy": "dairy_input",
    "tailoring": "fabric_wholesale",
    "bakery": "bakery_supplies",
    "hardware": "hardware_trade",
    "agro_input": "agro_wholesale",
}

# Mock-mode route-risk proxy: DATA_MODE=mock never calls the RoutingAdapter
# (OSRM), so route distance/duration is approximated from the mock
# database's straight-line (Haversine) distance at this assumed average
# rural road speed. This is a documented modeling choice, not a claim of
# real routing — surfaced in every mock route_risk's limitations.
_ASSUMED_RURAL_ROAD_SPEED_KMPH = 30.0


# Sector -> OSM tags for likely suppliers/wholesalers of raw materials.
# Same caveat as the Competitor Agent's mapping: this is a query-shaping
# heuristic, not a fabricated data source.
_SECTOR_TO_SUPPLIER_TAGS: dict[str, list[tuple[str, str]]] = {
    "grocery": [("shop", "wholesale"), ("shop", "trade")],
    "kirana": [("shop", "wholesale"), ("shop", "trade")],
    "tailoring": [("shop", "fabric"), ("shop", "wholesale")],
    "dairy": [("shop", "farm"), ("shop", "wholesale")],
    "bakery": [("shop", "wholesale"), ("shop", "trade")],
    "hardware": [("shop", "trade"), ("shop", "wholesale")],
    "electronics_repair": [("shop", "wholesale"), ("shop", "trade")],
    "beauty_salon": [("shop", "wholesale"), ("shop", "trade")],
    "restaurant": [("shop", "wholesale"), ("shop", "farm")],
    "agro_input": [("shop", "agrarian"), ("shop", "wholesale")],
}

_DISTRIBUTION_TAGS: list[tuple[str, str]] = [("amenity", "marketplace"), ("shop", "supermarket")]

_LONG_ROUTE_KM_THRESHOLD = 20.0


class SupplyChainAgent:
    def __init__(
        self,
        overpass_adapter: OverpassAdapter | None = None,
        routing_adapter: RoutingAdapter | None = None,
        data_mode: str | None = None,
    ) -> None:
        self.overpass_adapter = overpass_adapter or OverpassAdapter()
        self.routing_adapter = routing_adapter or RoutingAdapter()
        self.data_mode = (data_mode or settings.data_mode).strip().lower()

    async def run(
        self,
        case_state: CaseState,
        radius_meters: int = 15000,
        max_route_checks: int = 3,
    ) -> SupplyChainAgentOutput:
        if self.data_mode == "mock":
            return await self._run_mock(case_state, radius_meters, max_route_checks)
        return await self._run_real(case_state, radius_meters, max_route_checks)

    # ------------------------------------------------------------------
    # Mock tier: reads exclusively from data/mock.db via src/mockdb/*.
    # NEVER calls self.overpass_adapter / self.routing_adapter.
    # ------------------------------------------------------------------
    async def _run_mock(
        self,
        case_state: CaseState,
        radius_meters: int,
        max_route_checks: int,
    ) -> SupplyChainAgentOutput:
        logger.info("[MOCK] Supply Chain Agent → mock.db")

        selected = case_state.selected_business
        location = case_state.entrepreneur_profile.get("location", {})
        latitude = location.get("latitude")
        longitude = location.get("longitude")

        if latitude is None or longitude is None:
            return SupplyChainAgentOutput(
                confidence=Confidence.INSUFFICIENT_DATA,
                limitations=["Entrepreneur location coordinates not available in case state."],
            )

        sector_key = (selected.sector or selected.name).lower().replace(" ", "_") if selected else None
        supplier_category = _SECTOR_TO_MOCK_SUPPLIER_CATEGORY.get(sector_key) if sector_key else None

        limitations: list[str] = []
        suppliers: list[SupplierRecord] = []
        radius_km = radius_meters / 1000

        conn = mockdb_schema.connect(settings.mock_db_path)
        try:
            if supplier_category:
                sup_result = mockdb_queries.find_suppliers(
                    conn, category=supplier_category, latitude=latitude, longitude=longitude, radius_km=radius_km,
                )
                for s in sup_result["suppliers"]:
                    suppliers.append(
                        SupplierRecord(
                            name=s["supplier_name"], category=supplier_category,
                            latitude=s["latitude"], longitude=s["longitude"], distance_km=s["distance_km"],
                        )
                    )
                if not suppliers:
                    limitations.append(
                        "Mock database: no suppliers found for this category within the search radius."
                    )
            else:
                limitations.append(
                    f"Mock tier: no mock-database supplier-category mapping for sector '{sector_key}'; "
                    "supplier lookup skipped."
                )

            market_result = mockdb_queries.find_markets(
                conn, latitude=latitude, longitude=longitude, radius_km=radius_km,
            )
        finally:
            conn.close()

        distribution_points: list[SupplierRecord] = [
            SupplierRecord(
                name=m["market_name"], category="distribution_point",
                latitude=m["latitude"], longitude=m["longitude"], distance_km=m["distance_km"],
            )
            for m in market_result["markets"]
        ]
        if not distribution_points:
            limitations.append("Mock database: no markets found within the search radius.")

        # --- Route risk: straight-line Haversine proxy from mock coordinates.
        # DATA_MODE=mock NEVER calls the RoutingAdapter/OSRM. ---
        route_risks: list[RouteRisk] = []
        candidates = (suppliers + distribution_points)[:max_route_checks]
        for candidate in candidates:
            if candidate.distance_km is None:
                route_risks.append(RouteRisk(to=candidate.name, accessibility_flag="coordinates_unavailable"))
                continue
            distance_km = candidate.distance_km
            duration_minutes = round((distance_km / _ASSUMED_RURAL_ROAD_SPEED_KMPH) * 60, 1)
            flag = "long_supply_route" if distance_km > _LONG_ROUTE_KM_THRESHOLD else None
            route_risks.append(
                RouteRisk(to=candidate.name, distance_km=distance_km, duration_minutes=duration_minutes, accessibility_flag=flag)
            )
        if candidates:
            limitations.append(
                "Route distance/duration is a straight-line (Haversine) proxy computed from mock "
                f"database coordinates at an assumed {_ASSUMED_RURAL_ROAD_SPEED_KMPH:.0f} km/h rural "
                "road speed — NOT real road routing. DATA_MODE=mock never calls the RoutingAdapter/OSRM."
            )

        supplier_concentration_flag = None
        if supplier_category:
            if len(suppliers) == 0:
                supplier_concentration_flag = "no_suppliers_found_in_radius"
            elif len(suppliers) == 1:
                supplier_concentration_flag = "single_supplier_dependency"

        vulnerability_summary: list[str] = []
        if supplier_concentration_flag == "single_supplier_dependency":
            vulnerability_summary.append(
                "Only one identifiable supplier was found within the search radius (mock database), "
                "indicating a potential single-supplier dependency risk."
            )
        elif supplier_concentration_flag == "no_suppliers_found_in_radius":
            vulnerability_summary.append(
                "No suppliers matching this business category were found within the search radius in "
                "the mock database."
            )
        for rr in route_risks:
            if rr.accessibility_flag == "long_supply_route":
                vulnerability_summary.append(
                    f"Straight-line distance to '{rr.to}' is {rr.distance_km} km (~{rr.duration_minutes} "
                    f"min at assumed rural speed), above the {_LONG_ROUTE_KM_THRESHOLD} km accessibility threshold."
                )
            elif rr.accessibility_flag == "no_direct_route":
                vulnerability_summary.append(f"No routable path could be found to '{rr.to}'.")

        overall_confidence = Confidence.ESTIMATED if (suppliers or distribution_points) else Confidence.INSUFFICIENT_DATA

        return SupplyChainAgentOutput(
            suppliers=suppliers,
            distribution_points=distribution_points,
            route_risks=route_risks,
            supplier_concentration_flag=supplier_concentration_flag,
            vulnerability_summary=vulnerability_summary,
            sources=[SourceRecord(name=MOCK_SOURCE_NAME, confidence=overall_confidence, detail="suppliers_and_markets")],
            confidence=overall_confidence,
            limitations=limitations,
        )

    # ------------------------------------------------------------------
    # Real tier: unchanged Overpass + OSRM logic, exactly as before this
    # change.
    # ------------------------------------------------------------------
    async def _run_real(
        self,
        case_state: CaseState,
        radius_meters: int = 15000,
        max_route_checks: int = 3,
    ) -> SupplyChainAgentOutput:
        selected = case_state.selected_business
        location = case_state.entrepreneur_profile.get("location", {})
        latitude = location.get("latitude")
        longitude = location.get("longitude")

        sources: list[SourceRecord] = []
        limitations: list[str] = []

        if latitude is None or longitude is None:
            return SupplyChainAgentOutput(
                confidence=Confidence.INSUFFICIENT_DATA,
                limitations=["Entrepreneur location coordinates not available in case state."],
            )

        sector_key = (selected.sector or selected.name).lower().replace(" ", "_") if selected else None
        supplier_tags = _SECTOR_TO_SUPPLIER_TAGS.get(sector_key) if sector_key else None

        suppliers: list[SupplierRecord] = []
        overall_confidence = Confidence.INSUFFICIENT_DATA

        if supplier_tags:
            supplier_result = await self.overpass_adapter.query_nearby(latitude, longitude, radius_meters, supplier_tags)
            sources.append(SourceRecord(name=self.overpass_adapter.name, confidence=supplier_result.confidence, detail="suppliers"))
            if supplier_result.confidence == Confidence.REAL_DATA:
                overall_confidence = Confidence.REAL_DATA
                for el in supplier_result.data:
                    suppliers.append(
                        SupplierRecord(
                            name=el.get("name") or "Unnamed supplier",
                            category=sector_key,
                            latitude=el.get("latitude"),
                            longitude=el.get("longitude"),
                        )
                    )
            else:
                limitations.extend(f"Supplier lookup: {m}" for m in supplier_result.limitations)
        else:
            limitations.append("No OSM tag mapping available for this business sector; supplier lookup skipped.")

        # --- Distribution points ---
        distribution_points: list[SupplierRecord] = []
        dist_result = await self.overpass_adapter.query_nearby(latitude, longitude, radius_meters, _DISTRIBUTION_TAGS)
        sources.append(SourceRecord(name=self.overpass_adapter.name, confidence=dist_result.confidence, detail="distribution_points"))
        if dist_result.confidence == Confidence.REAL_DATA:
            overall_confidence = Confidence.REAL_DATA if overall_confidence != Confidence.REAL_DATA else overall_confidence
            for el in dist_result.data:
                distribution_points.append(
                    SupplierRecord(
                        name=el.get("name") or "Unnamed market",
                        category="distribution_point",
                        latitude=el.get("latitude"),
                        longitude=el.get("longitude"),
                    )
                )
        else:
            limitations.extend(f"Distribution point lookup: {m}" for m in dist_result.limitations)

        # --- Route risk for the nearest few points found ---
        route_risks: list[RouteRisk] = []
        candidates = (suppliers + distribution_points)[:max_route_checks]
        sources.append(SourceRecord(name=self.routing_adapter.name, confidence=Confidence.REAL_DATA if candidates else Confidence.INSUFFICIENT_DATA))
        for candidate in candidates:
            if candidate.latitude is None or candidate.longitude is None:
                route_risks.append(RouteRisk(to=candidate.name, accessibility_flag="coordinates_unavailable"))
                continue
            route_result = await self.routing_adapter.route(
                origin=(latitude, longitude), destination=(candidate.latitude, candidate.longitude)
            )
            if route_result.confidence == Confidence.REAL_DATA:
                distance_km = route_result.data["distance_km"]
                flag = "long_supply_route" if distance_km > _LONG_ROUTE_KM_THRESHOLD else None
                route_risks.append(
                    RouteRisk(
                        to=candidate.name,
                        distance_km=distance_km,
                        duration_minutes=route_result.data["duration_minutes"],
                        accessibility_flag=flag,
                    )
                )
                limitations.extend(route_result.limitations)
            else:
                route_risks.append(RouteRisk(to=candidate.name, accessibility_flag="no_direct_route"))
                limitations.extend(f"Routing to {candidate.name}: {m}" for m in route_result.limitations)

        # --- Concentration flag ---
        supplier_concentration_flag = None
        if supplier_tags:
            if len(suppliers) == 0:
                supplier_concentration_flag = "no_suppliers_found_in_radius"
            elif len(suppliers) == 1:
                supplier_concentration_flag = "single_supplier_dependency"

        vulnerability_summary: list[str] = []
        if supplier_concentration_flag == "single_supplier_dependency":
            vulnerability_summary.append(
                "Only one identifiable supplier was found within the search radius, indicating a "
                "potential single-supplier dependency risk."
            )
        elif supplier_concentration_flag == "no_suppliers_found_in_radius":
            vulnerability_summary.append(
                "No suppliers matching this business category were found within the search radius via "
                "OSM data; this may reflect sparse OSM coverage rather than an actual absence of suppliers."
            )
        for rr in route_risks:
            if rr.accessibility_flag == "long_supply_route":
                vulnerability_summary.append(
                    f"Route to '{rr.to}' is {rr.distance_km} km (~{rr.duration_minutes} min), "
                    f"above the {_LONG_ROUTE_KM_THRESHOLD} km accessibility threshold."
                )
            elif rr.accessibility_flag == "no_direct_route":
                vulnerability_summary.append(f"No routable path could be found to '{rr.to}'.")

        return SupplyChainAgentOutput(
            suppliers=suppliers,
            distribution_points=distribution_points,
            route_risks=route_risks,
            supplier_concentration_flag=supplier_concentration_flag,
            vulnerability_summary=vulnerability_summary,
            sources=sources,
            confidence=overall_confidence,
            limitations=limitations,
        )
