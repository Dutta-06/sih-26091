"""
Market Reach Agent (design doc Section 5.3 / Figure 3; TECHNICAL_SETUP.md
Section 5.3).

Reads:  state.entrepreneur_profile.location_query
Writes: state.market_intelligence.market_reach

Tech: Nominatim geocoding, LGD code disambiguation, spatial nearest-neighbor
query (KD-tree) over the Census 2011 population grid, Overpass QL for
nearby markets/distribution points.
"""
from __future__ import annotations

import logging

from config.settings import settings
from data_connectors import census, geocoding, overpass
from orchestrator.state import CaseState, MarketReachOutput, POI

logger = logging.getLogger(__name__)


def run(state: CaseState) -> CaseState:
    if state.entrepreneur_profile is None:
        raise ValueError("market_reach_agent requires state.entrepreneur_profile to be set")

    location_query = state.entrepreneur_profile.location_query
    geo = geocoding.geocode_location(location_query)

    radius_km = settings.market_reach_radius_km
    pop = census.population_within_radius(geo.lat, geo.lon, radius_km)
    pois = overpass.query_pois(geo.lat, geo.lon, radius_m=int(radius_km * 1000))

    distribution_points = [
        POI(name=p.name, type=p.poi_type, lat=p.lat, lon=p.lon) for p in pois
    ]

    # Census 2011 is always at least "estimated" (stale data), per the
    # design doc's confidence-labeling principle (Section 2) -- so the
    # combined output can never be labeled "real" even when geocoding was.
    output = MarketReachOutput(
        population_within_radius=pop.population_within_radius,
        population_data_year=pop.data_year,
        radius_km=radius_km,
        distribution_points=distribution_points,
        resolved_lat=geo.lat,
        resolved_lon=geo.lon,
        lgd_code=geo.lgd_code,
        source_confidence="estimated",
        notes=(
            "Population figure is based on Census 2011 village-level data "
            f"({'SAMPLE fixture, not real census data' if pop.is_sample_data else 'configured dataset'}) "
            "and should be treated as an estimate, not a current count. "
            f"Location resolved with {geo.raw_candidates} candidate match(es); "
            f"{'disambiguated via LGD code' if geo.lgd_code else 'no LGD match found'}."
        ),
    )

    # Reassign (not just mutate-in-place): LangGraph's pydantic state
    # merging only picks up fields pydantic considers "explicitly set" on
    # the returned model, which in-place mutation of a nested default
    # object does not trigger. See orchestrator/graph.py for details.
    market_intelligence = state.market_intelligence
    market_intelligence.market_reach = output
    state.market_intelligence = market_intelligence

    logger.info(
        "market_reach_agent: resolved %r -> (%.4f, %.4f); population=%d within %.1fkm; %d POIs",
        location_query,
        geo.lat,
        geo.lon,
        output.population_within_radius,
        radius_km,
        len(distribution_points),
    )
    return state
