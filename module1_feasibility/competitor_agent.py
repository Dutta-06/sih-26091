"""Competitor Mapping Agent (TDD 5.3 "Competitor mapping"; TECHNICAL_SETUP.md 5.6).

Estimates the density of similar enterprises with a tiered fallback chain, each
tier an independent, testable function returning a :class:`TierResult`:

1. ``tier_udyam``   -- Udyam Registration open dataset (NIC class + district/radius).
2. ``tier_overpass`` -- OpenStreetMap POIs matching the catalog ``osm_tags``.
3. ``tier_web_search`` -- not implemented; recorded as unavailable, never fabricated.

The first tier yielding a non-zero count is used (a zero from a partial registry or
sparse OSM coverage is "no_data", not "no competitors"). The count is normalised
per 10,000 residents within ``settings.market_reach_radius_km`` and compared with a
benchmark density (catalog ``typical_density_per_10k``, an estimate, until district
and state populations are available to normalise Udyam district/state counts).

z-score (Poisson approximation): expected = benchmark_density * population / 10,000;
z = (count - expected) / sqrt(expected). Left ``None`` when count, population or
benchmark is unknown. Saturation from density/benchmark ratio: <=0.75 low,
<=1.25 medium, else high; "unknown" when either is missing.

Reads: state.business_shortlist, state.entrepreneur_profile.location
Writes: state.competitor_intel
Tech: tiered fallback (Udyam CSV -> Overpass -> web search), Census radius population, Poisson z-score benchmarks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from common.net import DataUnavailable
from common.reference import get_activity, haversine_km
from config.settings import settings
from data_connectors import census, overpass, udyam
from orchestrator.state import (
    CaseState,
    CompetitorEntry,
    CompetitorIntelligence,
    DataSourceRef,
    LocationDetails,
    SaturationLevel,
    TierAttempt,
)

COARSE_RESOLUTION = {"state_centroid", "unresolved"}


@dataclass
class TierResult:
    attempt: TierAttempt
    count: Optional[int] = None
    scope: str = "radius"  # "radius" (normalisable by radius population) or "district"
    competitors: list[CompetitorEntry] = field(default_factory=list)
    district_count: Optional[int] = None
    state_count: Optional[int] = None


def usable_coordinates(loc: Optional[LocationDetails]) -> Optional[tuple[float, float]]:
    """Coordinates precise enough for a radius query (not a state centroid)."""
    if loc is None or loc.latitude is None or loc.longitude is None or loc.resolution_method in COARSE_RESOLUTION:
        return None
    return loc.latitude, loc.longitude


def tier_udyam(activity: dict[str, Any], loc: LocationDetails, radius_km: float) -> TierResult:
    coords = usable_coordinates(loc)
    try:
        m = udyam.find_enterprises(
            activity.get("nic_class", ""), loc.district, loc.state,
            lat=coords[0] if coords else None, lon=coords[1] if coords else None, radius_km=radius_km,
        )
    except DataUnavailable as exc:
        return TierResult(TierAttempt(tier="udyam", status="unavailable", detail=str(exc)))
    base = dict(district_count=m.district_count, state_count=m.state_count)
    if m.has_coordinates:
        count, scope = len(m.nearby), "radius"
    else:
        count, scope = m.district_count, "district"
    if not count:
        return TierResult(TierAttempt(tier="udyam", status="no_data",
                                      detail=f"{m.dataset}: no NIC {activity.get('nic_class')} registrations matched ({scope})"), **base)
    competitors = [CompetitorEntry(name=r["name"], distance_km=r["distance_km"], latitude=r["lat"], longitude=r["lon"],
                                   source="Udyam Registration") for r in m.nearby if r["name"]]
    detail = f"{m.dataset}: {count} registrations with NIC {activity.get('nic_class')} ({'within radius' if scope == 'radius' else 'district-wide'})"
    return TierResult(TierAttempt(tier="udyam", status="used", detail=detail), count=count, scope=scope,
                      competitors=competitors[:20], **base)


def tier_overpass(activity: dict[str, Any], loc: LocationDetails, radius_km: float) -> TierResult:
    tags = [tuple(t) for t in activity.get("osm_tags") or []]
    coords = usable_coordinates(loc)
    if not tags:
        return TierResult(TierAttempt(tier="overpass", status="skipped", detail="activity has no OSM tags"))
    if coords is None:
        return TierResult(TierAttempt(tier="overpass", status="skipped",
                                      detail="location not resolved below state level; a radius query would describe the wrong place"))
    try:
        pois = overpass.query_pois(coords[0], coords[1], int(radius_km * 1000), tags)
    except DataUnavailable as exc:
        return TierResult(TierAttempt(tier="overpass", status="unavailable", detail=str(exc)))
    except Exception as exc:  # connector bug / unexpected payload: degrade, don't crash the fan-out
        return TierResult(TierAttempt(tier="overpass", status="error", detail=f"{exc.__class__.__name__}: {exc}"))
    if not pois:
        return TierResult(TierAttempt(tier="overpass", status="no_data",
                                      detail=f"no OSM features tagged {tags} within {radius_km:g} km (OSM rural coverage is sparse)"))
    competitors = []
    for p in pois:
        if p.get("lat") is None or p.get("lon") is None:
            continue
        dist = round(haversine_km(coords[0], coords[1], p["lat"], p["lon"]), 2)
        if p.get("name"):
            competitors.append(CompetitorEntry(name=p["name"], distance_km=dist, latitude=p["lat"], longitude=p["lon"],
                                               source="OpenStreetMap"))
    competitors.sort(key=lambda c: c.distance_km or 0.0)
    return TierResult(TierAttempt(tier="overpass", status="used",
                                  detail=f"{len(pois)} OSM features tagged {tags} within {radius_km:g} km"),
                      count=len(pois), competitors=competitors[:20])


def tier_web_search(_activity: dict[str, Any], _loc: LocationDetails) -> TierResult:
    return TierResult(TierAttempt(tier="web_search", status="unavailable",
                                  detail="web-search extraction tier not implemented (no search provider configured)"))


def run_tiers(activity: dict[str, Any], loc: LocationDetails, radius_km: float) -> tuple[Optional[TierResult], list[TierResult]]:
    """Run tiers in order, stopping at the first that yields a count."""
    results: list[TierResult] = []
    for tier in (lambda: tier_udyam(activity, loc, radius_km), lambda: tier_overpass(activity, loc, radius_km),
                 lambda: tier_web_search(activity, loc)):
        result = tier()
        results.append(result)
        if result.attempt.status == "used":
            return result, results
    return None, results


def poisson_z(count: Optional[int], population: Optional[int], benchmark_density: Optional[float]) -> Optional[float]:
    if count is None or not population or not benchmark_density:
        return None
    expected = benchmark_density * population / 10_000
    return round((count - expected) / math.sqrt(expected), 2) if expected > 0 else None


def saturation_from_ratio(density: Optional[float], benchmark: Optional[float]) -> SaturationLevel:
    if density is None or not benchmark:
        return "unknown"
    ratio = density / benchmark
    return "low" if ratio <= 0.75 else "medium" if ratio <= 1.25 else "high"


def run(state: CaseState) -> dict[str, Any]:
    candidate = state.selected_candidate()
    activity = get_activity(candidate.catalog_id) if candidate and candidate.catalog_id else None
    profile = state.entrepreneur_profile
    loc = profile.location if profile else LocationDetails()
    radius_km = settings.market_reach_radius_km
    limitations: list[str] = []
    sources: list[DataSourceRef] = []

    if activity is None:
        return {"competitor_intel": CompetitorIntelligence(
            limitations=["No catalog activity selected; competitor density not assessed."],
            data_source_detail="No assessment performed.")}

    used, attempts = run_tiers(activity, loc, radius_km)
    for r in attempts:
        if r.attempt.status != "used":
            limitations.append(f"{r.attempt.tier} tier {r.attempt.status}: {r.attempt.detail}")
    count = used.count if used else None
    if used:
        sources.append(DataSourceRef(name={"udyam": "Udyam Registration dataset", "overpass": "OpenStreetMap Overpass",
                                           "web_search": "Web search"}[used.attempt.tier],
                                     source_confidence="real", detail=used.attempt.detail))
        if used.attempt.tier == "overpass":
            limitations.append("OSM counts only mapped, tagged businesses; informal enterprises are likely undercounted.")
        if used.attempt.tier == "udyam":
            limitations.append("Udyam covers registered enterprises only; informal competitors are not counted.")
    else:
        limitations.append("No competitor data source yielded a count; saturation is unknown, not low.")

    population, pop_conf = None, "estimated"
    coords = usable_coordinates(loc)
    if used and used.scope == "radius" and coords:
        try:
            population, pop_conf, basis, pop_lims = census.population_within_radius(coords[0], coords[1], radius_km, loc.state)
            sources.append(DataSourceRef(name="Census population within radius", source_confidence=pop_conf, detail=basis))
            limitations.extend(pop_lims)
        except Exception as exc:  # connector unavailable or failed: degrade with a limitation
            limitations.append(f"Population within {radius_km:g} km unavailable ({exc}).")
    elif used and used.scope == "district":
        limitations.append("Udyam extract has no coordinates, so the count is district-wide and cannot be "
                           "normalised by the radius population.")

    density = round(count / population * 10_000, 3) if count is not None and population else None
    if count is not None and density is None:
        limitations.append("Population for the counted area unknown; density, z-scores and saturation not computed.")

    benchmark = activity.get("typical_density_per_10k")
    district_bench = state_bench = None
    if benchmark:
        district_bench = state_bench = float(benchmark)
        sources.append(DataSourceRef(name="Business catalog typical density", source_confidence="estimated",
                                     detail=f"{benchmark} per 10k population (planning assumption)"))
        limitations.append("District/state benchmark densities are catalog planning assumptions, not measured averages.")
    if used and (used.district_count is not None or used.state_count is not None):
        limitations.append(f"Udyam counts for NIC {activity.get('nic_class')}: district={used.district_count}, "
                           f"state={used.state_count}; not normalised to densities (district/state population not loaded).")

    z_district = poisson_z(count, population, district_bench)
    z_state = poisson_z(count, population, state_bench)
    saturation = saturation_from_ratio(density, district_bench or state_bench)
    confidence = "real" if used and density is not None and pop_conf == "real" else "estimated"

    if used:
        detail = f"{used.attempt.tier} tier: {count} similar enterprises" + (
            f"; {density} per 10k vs benchmark {district_bench}" if density is not None else "")
    else:
        detail = "No tier produced data; competitor count unknown."

    intel = CompetitorIntelligence(
        estimated_competitor_count=count,
        density_per_10k_population=density,
        benchmark_district_avg_density=district_bench,
        benchmark_state_avg_density=state_bench,
        z_score_vs_district=z_district,
        z_score_vs_state=z_state,
        saturation_level=saturation,
        identified_competitors=used.competitors if used else [],
        fallback_tier_used=used.attempt.tier if used else "none",
        tiers_attempted=[r.attempt for r in attempts],
        source_confidence=confidence,
        data_source_detail=detail,
        sources=sources,
        limitations=limitations,
    )
    return {"competitor_intel": intel}
