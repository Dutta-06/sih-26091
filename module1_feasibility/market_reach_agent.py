"""Market Reach Agent (TDD 5.3; TECHNICAL_SETUP §5.3).

Reads: state.entrepreneur_profile.location (resolved by profiling via data_connectors.geocoding.resolve_location)
Writes: state.market_reach_intel
Tech: Census 2011 village KD-tree radius query (state-density fallback), OSM Overpass (nwr) for markets,
      transport hubs and retail clusters, haversine distances.

Documented planning assumptions (always "estimated"):
* ``CATCHMENT_SHARE`` - share of residents within the radius treated as the reachable consumer base of a
  single village micro-enterprise.
* ``HOUSEHOLD_SIZE`` - persons per household, approximately the Census 2011 all-India average (~4.8).
"""

from __future__ import annotations

import logging
from typing import Any

from common.net import DataUnavailable
from common.reference import haversine_km
from config.settings import settings
from data_connectors import census, overpass
from orchestrator.state import CaseState, DataSourceRef, DistributionPoint, MarketReachIntelligence

logger = logging.getLogger(__name__)

CATCHMENT_SHARE = 0.30
HOUSEHOLD_SIZE = 4.8
MAX_POINTS = 25

DISTRIBUTION_TAGS: list[tuple[str, str]] = [
    ("amenity", "marketplace"),
    ("amenity", "bus_station"),
    ("public_transport", "station"),
    ("shop", "wholesale"),
    ("shop", "supermarket"),
    ("shop", "general"),
    ("landuse", "retail"),
]


def _point_type(tags: dict[str, str]) -> str:
    if tags.get("amenity") == "marketplace":
        return "marketplace"
    if tags.get("amenity") == "bus_station" or tags.get("public_transport") == "station":
        return "transport_hub"
    if tags.get("shop") == "wholesale":
        return "wholesale"
    return "retail_cluster"


def run(state: CaseState) -> dict[str, Any]:
    radius_km = settings.market_reach_radius_km
    intel = MarketReachIntelligence(radius_km=radius_km)
    loc = state.entrepreneur_profile.location if state.entrepreneur_profile else None

    if loc is None or loc.latitude is None or loc.longitude is None:
        intel.limitations.append("Location was not resolved to coordinates, so population, consumer base and "
                                 "nearby markets could not be estimated.")
        intel.data_source_detail = "No resolved location"
        return {"market_reach_intel": intel}

    coarse = loc.resolution_method == "state_centroid"
    intel.sources.append(DataSourceRef(name=f"Location ({loc.resolution_method})",
                                       source_confidence=loc.source_confidence, detail="; ".join(loc.notes)))

    # --- Population -----------------------------------------------------------
    if coarse:
        population, pop_conf, basis, limits = census.state_density_estimate(radius_km, loc.state)
        limits = ["Location is only a district/state centroid, so the village-level census lookup was skipped.",
                  *limits]
    else:
        population, pop_conf, basis, limits = census.population_within_radius(
            loc.latitude, loc.longitude, radius_km, loc.state)
    intel.limitations.extend(limits)
    intel.sources.append(DataSourceRef(name="Census 2011 population", source_confidence=pop_conf, detail=basis))
    if population is not None:
        intel.population_within_radius = population
        intel.population_data_year = census.DATA_YEAR
        intel.consumer_base_estimate = int(round(population * CATCHMENT_SHARE))
        intel.households_estimate = int(round(population / HOUSEHOLD_SIZE))

    # --- Distribution points ----------------------------------------------------
    pois_conf = "estimated"
    if coarse:
        intel.limitations.append("Nearby markets were not queried around a district/state centroid because "
                                 "distances would not describe the entrepreneur's locality.")
    else:
        try:
            pois = overpass.query_pois(loc.latitude, loc.longitude, int(radius_km * 1000), DISTRIBUTION_TAGS)
            pois_conf = "real"
            points = []
            for p in pois:
                kind = _point_type(p.get("tags") or {})
                points.append(DistributionPoint(
                    name=p.get("name") or f"Unnamed {kind.replace('_', ' ')} (OSM {p.get('osm_type', 'feature')})",
                    type=kind,
                    distance_km=round(haversine_km(loc.latitude, loc.longitude, p["lat"], p["lon"]), 2),
                    latitude=p["lat"], longitude=p["lon"], source_confidence="real",
                ))
            points.sort(key=lambda d: d.distance_km)
            intel.distribution_points = points[:MAX_POINTS]
            intel.nearby_mandis = [d.name for d in intel.distribution_points if d.type == "marketplace"]
            intel.sources.append(DataSourceRef(name="OpenStreetMap Overpass", source_confidence="real",
                                               detail=f"{len(pois)} features within {radius_km:g} km"))
            if not pois:
                intel.limitations.append("No markets, transport hubs or retail features are mapped in OSM within "
                                         "the radius; rural OSM coverage is sparse, so this is not proof of absence.")
            elif loc.source_confidence != "real":
                intel.limitations.append("Distances are measured from estimated coordinates.")
        except DataUnavailable as exc:
            intel.limitations.append(f"Nearby markets unavailable ({exc}).")
            intel.sources.append(DataSourceRef(name="OpenStreetMap Overpass", source_confidence="estimated",
                                               detail=str(exc)))

    intel.source_confidence = (
        "real" if population is not None and pop_conf == "real" and loc.source_confidence == "real" and not coarse
        else "estimated"
    )
    parts = [basis]
    if population is not None:
        parts.append(f"consumer base = population × {CATCHMENT_SHARE:.0%} assumed catchment share; "
                     f"households = population ÷ {HOUSEHOLD_SIZE} (approx. Census 2011 household size) - both estimated")
    if pois_conf == "real":
        parts.append(f"{len(intel.distribution_points)} distribution points from OSM Overpass")
    intel.data_source_detail = "; ".join(parts)
    logger.info("market_reach: population=%s (%s), %d distribution points",
                population, pop_conf, len(intel.distribution_points))
    return {"market_reach_intel": intel}
