"""Risk Agent (Module 1, TDD 5.3 / TECHNICAL_SETUP.md 5.5).

Reads: state.business_shortlist (selected candidate), state.entrepreneur_profile.location,
       state.market_reach_intel (distribution points from an earlier pass, if any),
       orchestrator.stores.local_feedback (TDD 5.6)
Writes: state.risk_intel
Tech: OSRM road distance to the nearest hub (haversine x 1.3 labeled fallback); classical
      multiplicative seasonal decomposition of Agmarknet monthly prices (catalog seasonal
      profile fallback); TF-IDF retrieval over the curated risk taxonomy plus deterministic
      severity rules keyed on catalog attributes.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from common.net import DataUnavailable
from common.reference import MONTHS, get_activity, haversine_km, load_state_reference, low_season_months
from config.settings import settings
from data_connectors import osrm
from orchestrator import stores
from orchestrator.state import CaseState, DataSourceRef, Level, MonthlyPrice, RiskFlag, RiskIntelligence
from rag.vector_store import retrieve

try:  # worker B's connector; patched in tests
    from data_connectors import agmarknet
except ImportError:  # pragma: no cover
    agmarknet = None
try:  # worker A's connector; patched in tests
    from data_connectors import overpass
except ImportError:  # pragma: no cover
    overpass = None

ROAD_FACTOR = 1.3  # straight-line to road distance, a rough planning factor
HUB_SEARCH_RADIUS_M = 30_000
MAX_HUB_KM = 150.0  # beyond this the "nearest" reference hub is not meaningful
PRECISE_METHODS = {"nominatim", "lgd_table", "census_table"}
_RANK = {"low": 0, "medium": 1, "high": 2}


# --- Route -------------------------------------------------------------------

def _is_coarse(loc) -> bool:
    if loc is None or loc.latitude is None or loc.longitude is None:
        return True
    if loc.resolution_method not in PRECISE_METHODS:
        return True
    ref = load_state_reference()
    centroids = list(ref["districts"].values()) + list(ref["states"].values())
    return any(abs(loc.latitude - c["lat"]) < 0.01 and abs(loc.longitude - c["lon"]) < 0.01 for c in centroids)


def _find_hub(state: CaseState, lat: float, lon: float, limitations: list[str]) -> Optional[dict[str, Any]]:
    """Nearest market hub: known distribution point > OSM marketplace > reference district HQ."""
    points = [p for p in (state.market_reach_intel.distribution_points if state.market_reach_intel else [])
              if p.latitude is not None and p.longitude is not None]
    if points:
        p = min(points, key=lambda p: haversine_km(lat, lon, p.latitude, p.longitude))
        return {"name": p.name, "lat": p.latitude, "lon": p.longitude, "kind": p.type}
    if overpass is not None:
        try:
            pois = overpass.query_pois(lat, lon, HUB_SEARCH_RADIUS_M, [("amenity", "marketplace")])
            pois = [p for p in pois if p.get("lat") is not None and p.get("lon") is not None]
            if pois:
                p = min(pois, key=lambda p: haversine_km(lat, lon, p["lat"], p["lon"]))
                return {"name": p.get("name") or "OSM marketplace", "lat": p["lat"], "lon": p["lon"], "kind": "marketplace"}
        except DataUnavailable as exc:
            limitations.append(f"Marketplace search unavailable ({exc}); used district headquarters as hub.")
        except Exception as exc:  # connector contract not yet met / malformed response
            limitations.append(f"Marketplace search failed ({type(exc).__name__}); used district headquarters as hub.")
    districts = load_state_reference()["districts"]
    if not districts:
        return None
    name, info = min(districts.items(), key=lambda kv: haversine_km(lat, lon, kv[1]["lat"], kv[1]["lon"]))
    if haversine_km(lat, lon, info["lat"], info["lon"]) > MAX_HUB_KM:
        return None
    return {"name": f"{name} district headquarters", "lat": info["lat"], "lon": info["lon"], "kind": "district_hq"}


def _route_band(km: float, perishable: bool) -> Level:
    low, medium = (10.0, 25.0) if perishable else (15.0, 40.0)
    return "low" if km <= low else "medium" if km <= medium else "high"


def analyse_route(state: CaseState, activity: dict[str, Any]) -> dict[str, Any]:
    profile = state.entrepreneur_profile
    loc = profile.location if profile else None
    limitations: list[str] = []
    out = {"km": None, "method": "unavailable", "risk": "medium", "confidence": "estimated",
           "limitations": limitations, "flag": None, "detail": ""}
    if _is_coarse(loc):
        limitations.append("Entrepreneur location is unresolved or only a district/state centroid, so road "
                           "distance to the nearest market hub is unknown; supply-route risk left at 'medium'.")
        out["detail"] = "route distance unavailable (no precise location)"
        return out
    hub = _find_hub(state, loc.latitude, loc.longitude, limitations)
    if hub is None:
        limitations.append("No market hub with known coordinates within range; road distance unknown, "
                           "supply-route risk left at 'medium'.")
        out["detail"] = "route distance unavailable (no hub)"
        return out
    try:
        km = osrm.road_distance_km(loc.latitude, loc.longitude, hub["lat"], hub["lon"])
        method = "osrm"
    except DataUnavailable as exc:
        km = haversine_km(loc.latitude, loc.longitude, hub["lat"], hub["lon"]) * ROAD_FACTOR
        method = "haversine_estimate"
        limitations.append(f"OSRM unavailable ({exc}); distance is straight-line x {ROAD_FACTOR} (estimate).")
    perishable = bool(activity.get("perishable"))
    risk = _route_band(km, perishable)
    real = method == "osrm" and loc.source_confidence == "real"
    if hub["kind"] == "district_hq":
        limitations.append("Hub is the district headquarters town from reference coordinates, not a verified market.")
    out.update(km=round(km, 1), method=method, risk=risk, confidence="real" if real else "estimated",
               detail=f"{km:.1f} km to {hub['name']} ({method})")
    out["flag"] = RiskFlag(
        category="route", title="Supply-route distance", severity=risk, source_confidence=out["confidence"],
        description=f"Nearest market hub ({hub['name']}) is about {km:.1f} km by road"
                    f"{' (estimated from straight-line distance)' if method != 'osrm' else ''}."
                    f"{' Product is perishable, so distance bands are tighter.' if perishable else ''}",
        mitigation="Plan fixed transport days or pooled transport with nearby producers." if risk != "low" else "",
    )
    return out


# --- Seasonality -------------------------------------------------------------

def seasonal_decomposition(prices: list[MonthlyPrice]) -> Optional[list[float]]:
    """12 multiplicative monthly factors (Jan..Dec, mean 1.0) from >= 24 months of prices."""
    if len(prices) < 24:
        return None
    s = pd.Series({pd.Period(p.month, "M"): float(p.modal_price) for p in prices if p.modal_price > 0}).sort_index()
    if len(s) < 24:
        return None
    s = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M")).interpolate(limit=2).dropna()
    if len(s) < 24:
        return None
    try:  # optional dependency
        from statsmodels.tsa.seasonal import seasonal_decompose

        seasonal = seasonal_decompose(s.set_axis(s.index.to_timestamp()), model="multiplicative", period=12).seasonal
        factors = seasonal.groupby(seasonal.index.month).mean()
    except ImportError:
        trend = s.rolling(12, center=True).mean().rolling(2).mean().shift(-1)  # centred 2x12 moving average
        ratio = (s / trend).dropna()
        factors = ratio.groupby(ratio.index.month).mean()
    if len(factors) < 12:
        return None
    arr = np.array([factors[m] for m in range(1, 13)], dtype=float)
    return [round(float(v), 4) for v in arr / arr.mean()]


def _variation(index: list[float]) -> Level:
    """Peak-to-trough swing relative to the average month (index mean is 1.0)."""
    amplitude = max(index) - min(index)
    return "low" if amplitude < 0.25 else "medium" if amplitude < 0.5 else "high"


def analyse_seasonality(state: CaseState, activity: dict[str, Any], commodity: Optional[str]) -> dict[str, Any]:
    limitations: list[str] = []
    loc = state.entrepreneur_profile.location if state.entrepreneur_profile else None
    index, confidence, basis = None, "estimated", ""
    if commodity and agmarknet is not None:
        try:
            prices = agmarknet.fetch_monthly_prices(commodity, loc.state if loc else None, loc.district if loc else None, months=36)
            index = seasonal_decomposition(prices)
            if index:
                confidence = "real"
                basis = (f"Agmarknet modal prices for {commodity}, {len(prices)} months, classical multiplicative "
                         "decomposition (price seasonality used as a proxy for revenue seasonality)")
            else:
                limitations.append(f"Only {len(prices)} usable months of {commodity} prices (need 24); used catalog profile.")
        except DataUnavailable as exc:
            limitations.append(f"Agmarknet price history unavailable ({exc}); used catalog seasonal profile.")
        except Exception as exc:  # malformed data must not break the fan-out
            limitations.append(f"Agmarknet price analysis failed ({type(exc).__name__}); used catalog seasonal profile.")
    elif not commodity:
        limitations.append("Activity has no Agmarknet commodity; seasonal pattern from catalog profile.")
    if index is None:
        profile = activity.get("seasonal_profile") or []
        if len(profile) == 12:
            mean = sum(profile) / 12
            index = [round(v / mean, 4) for v in profile]
            basis = "catalog seasonal profile (indicative planning assumption)"
        else:
            limitations.append("No seasonal pattern available; seasonal variation left at 'medium'.")
            return {"index": [], "basis": "unavailable", "variation": "medium", "confidence": "estimated",
                    "low": [], "limitations": limitations, "flag": None}
    variation, low = _variation(index), low_season_months(index)
    flag = RiskFlag(
        risk_id="seasonal_demand_variation", category="seasonal", title="Seasonal demand variation", severity=variation, source_confidence=confidence,
        description=f"Peak-to-trough swing of {100 * (max(index) - min(index)):.0f}% of average; weakest months: "
                    f"{', '.join(low) or 'none below 92% of average'} (basis: {basis}).",
        mitigation="Build a cash buffer during peak months to cover instalments in low months." if variation != "low" else "",
    )
    return {"index": index, "basis": basis, "variation": variation, "confidence": confidence, "low": low,
            "limitations": limitations, "flag": flag}


# --- Structural (taxonomy) ---------------------------------------------------

@lru_cache(maxsize=None)
def _taxonomy_entry(risk_id: str) -> dict[str, str]:
    path = Path(settings.risk_taxonomy_path) / f"{risk_id}.md"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    grab = lambda key: (m.group(1).strip() if (m := re.search(rf"^{key}:\s*(.+)$", text, re.M)) else "")
    title = text.splitlines()[0].lstrip("# ").strip()
    return {"title": title, "pattern": grab("Pattern"), "mitigation": grab("Mitigation")}


CONCENTRATED_BUYERS = ("exporter", "master weaver", "cooperative", "processor", "wholesaler")
CREDIT_BUYERS = ("wholesaler", "retailer", "retail", "exporter", "processor", "cooperative", "kirana", "master weaver", "bakeries")


def structural_rules(activity: dict[str, Any], route: dict[str, Any], seasonal: dict[str, Any]) -> list[tuple[str, Level, str]]:
    """Deterministic (risk_id, severity, reason) triggers from catalog attributes."""
    buyers = [b.lower() for b in activity.get("buyers", [])]
    infra = activity.get("infrastructure_needs", [])
    sector = activity.get("sector", "")
    rules: list[tuple[str, Level, str]] = []
    if len(buyers) <= 1:
        rules.append(("single_buyer_dependency", "high", f"Only {len(buyers)} typical buyer channel listed."))
    elif len(buyers) == 2:
        concentrated = any(k in b for b in buyers for k in CONCENTRATED_BUYERS)
        rules.append(("single_buyer_dependency", "high" if concentrated else "medium",
                      f"Only two buyer channels ({', '.join(activity['buyers'])})."))
    if activity.get("perishable"):
        far = route["km"] is not None and route["km"] > 25
        rules.append(("perishability_cold_chain", "high" if far else "medium",
                      "Perishable product" + (f" with the hub {route['km']} km away." if far else
                                              "; distance to market not confirmed." if route["km"] is None else ".")))
    inputs = " ".join(activity.get("key_inputs", [])).lower()
    if activity.get("commodity") or re.search(r"feed|fodder|seed|grain|oil", inputs):
        rules.append(("input_price_volatility", "medium", "Main inputs are agricultural commodities or feed."))
    if "three_phase_power" in infra:
        rules.append(("power_reliability", "high", "Machinery needs a three-phase power connection."))
    elif "electricity" in infra:
        rules.append(("power_reliability", "low", "Operations depend on grid electricity."))
    if any(k in b for b in buyers for k in CREDIT_BUYERS):
        rules.append(("credit_receivables", "medium", "Sales to traders/retailers usually involve credit periods."))
    extra_licences = [l for l in activity.get("licences", []) if "udyam" not in l.lower()]
    if extra_licences:
        rules.append(("regulatory_licensing", "medium", f"Needs: {'; '.join(extra_licences)}."))
    if sector in {"animal_husbandry", "fisheries"}:
        rules.append(("climate_disease_livestock_fisheries", "high" if sector == "fisheries" else "medium",
                      "Live animals/stock exposed to disease and weather losses."))
    index = seasonal["index"]
    if index and max(index) >= 1.2:
        peak = [MONTHS[i] for i, v in enumerate(index) if v >= 1.15]
        rules.append(("festival_season_concentration", "medium", f"Demand concentrated in {', '.join(peak)}."))
    if len(seasonal["low"]) >= 3 or seasonal["variation"] == "high":
        rules.append(("working_capital_strain", "high" if len(seasonal["low"]) >= 5 else "medium",
                      f"{len(seasonal['low'])} low-season months to finance."))
    return rules


PROFILE_MATCH_SCORE = 0.12


def analyse_structural(activity: dict[str, Any], route: dict, seasonal: dict,
                       profile_text: str = "") -> tuple[list[RiskFlag], dict[str, Level], list[str]]:
    """Rule-triggered taxonomy entries, plus entries retrieved from the entrepreneur's own statements."""
    limitations: list[str] = []
    triggered = {rid: (sev, reason) for rid, sev, reason in structural_rules(activity, route, seasonal)}
    if profile_text.strip():
        for chunk in retrieve("risk_taxonomy", profile_text, top_k=3, min_score=PROFILE_MATCH_SCORE):
            rid = Path(chunk.source).stem
            if rid not in triggered:
                triggered[rid] = ("medium", f"Matches the entrepreneur's stated situation: \"{profile_text.strip()[:120]}\".")
    if not retrieve("risk_taxonomy", activity.get("category", "business risk"), top_k=1, min_score=0.0):
        limitations.append("Risk taxonomy knowledge base is empty or missing; structural flags use rule text only.")
    flags: list[RiskFlag] = []
    for risk_id, (severity, reason) in triggered.items():
        entry = _taxonomy_entry(risk_id)
        flags.append(RiskFlag(
            risk_id=risk_id, category="structural", title=entry.get("title") or risk_id.replace("_", " ").capitalize(),
            severity=severity, source_confidence="estimated",
            description=f"{reason} {entry.get('pattern', '')}".strip(), mitigation=entry.get("mitigation", ""),
        ))
    return flags, {rid: sev for rid, (sev, _) in triggered.items()}, limitations


# --- Local feedback (TDD 5.6) ------------------------------------------------

def feedback_flags(district: Optional[str], catalog_id: str) -> tuple[list[RiskFlag], list[str]]:
    try:
        rows = stores.local_feedback(district, catalog_id)
    except Exception as exc:
        return [], [f"Local feedback store unreadable ({type(exc).__name__})."]
    flags = []
    for row in rows:
        rating = row.get("rating")
        severity: Level = "medium" if rating is None else "high" if rating <= 2 else "medium" if rating == 3 else "low"
        who = "previously funded entrepreneur" if row["kind"] == "funded_entrepreneur" else "local resident survey"
        flags.append(RiskFlag(category="local_feedback", title=f"Local feedback: {row['topic']}", severity=severity,
                              description=f"{who.capitalize()} reported: {row['observation']}"
                                          + (f" (rating {rating}/5)" if rating is not None else ""),
                              source_confidence="estimated"))
    return flags, []


# --- Node --------------------------------------------------------------------

def overall_severity(flags: list[RiskFlag]) -> Level:
    highs = sum(f.severity == "high" for f in flags)
    if highs >= 2:
        return "high"
    return "medium" if highs or any(f.severity == "medium" for f in flags) else "low"


def run(state: CaseState) -> dict[str, Any]:
    candidate = state.selected_candidate()
    activity = (get_activity(candidate.catalog_id) if candidate and candidate.catalog_id else None) or {}
    if not candidate:
        return {"risk_intel": RiskIntelligence(limitations=["No business candidate selected; risk not assessed."])}
    if not activity:
        activity = {"category": candidate.category, "sector": candidate.sector, "commodity": candidate.commodity}
    commodity = candidate.commodity or activity.get("commodity")

    route = analyse_route(state, activity)
    seasonal = analyse_seasonality(state, activity, commodity)
    profile = state.entrepreneur_profile
    profile_text = " ".join([*(profile.constraints if profile else []), (profile.preference_reason or "") if profile else ""])
    structural, severities, s_limits = analyse_structural(activity, route, seasonal, profile_text)
    district = profile.location.district if profile else None
    feedback, f_limits = feedback_flags(district, candidate.catalog_id)
    if not activity.get("id"):
        s_limits.append(f"'{candidate.category}' not in business catalog; structural rules limited.")

    flags = [f for f in (route["flag"], seasonal["flag"]) if f] + structural + feedback
    if route["flag"] is None:
        flags.insert(0, RiskFlag(category="route", title="Supply-route distance unknown", severity="medium",
                                 description=route["limitations"][-1], mitigation="Confirm the distance and transport "
                                 "options to the nearest market or collection point before committing."))
    flags.sort(key=lambda f: -_RANK[f.severity])
    single_buyer = severities.get("single_buyer_dependency", "low" if activity.get("id") else "medium")
    real = route["confidence"] == "real" and seasonal["confidence"] == "real"
    sources = [
        DataSourceRef(name={"osrm": "OSRM road routing", "haversine_estimate": "Haversine x 1.3 estimate",
                            "unavailable": "Route distance (unavailable)"}[route["method"]],
                      source_confidence=route["confidence"], detail=route["detail"]),
        DataSourceRef(name="Agmarknet seasonal decomposition" if seasonal["confidence"] == "real" else "Catalog seasonal profile",
                      source_confidence=seasonal["confidence"], detail=seasonal["basis"]),
        DataSourceRef(name="Curated risk taxonomy (data/risk_taxonomy)", source_confidence="estimated",
                      detail=f"{len(structural)} entries matched: {', '.join(severities) or 'none'}"),
        DataSourceRef(name="Local feedback and surveys store", source_confidence="estimated",
                      detail=f"{len(feedback)} observations for {district or 'unknown district'}"),
    ]
    intel = RiskIntelligence(
        source_confidence="real" if real else "estimated",
        data_source_detail="; ".join(f"{s.name}: {s.source_confidence}" for s in sources),
        sources=sources,
        limitations=route["limitations"] + seasonal["limitations"] + s_limits + f_limits,
        overall_severity=overall_severity(flags),
        road_distance_to_hub_km=route["km"],
        route_distance_method=route["method"],
        supply_route_risk=route["risk"],
        seasonal_demand_variation=seasonal["variation"],
        seasonal_index=seasonal["index"],
        seasonal_basis=seasonal["basis"],
        low_season_months=seasonal["low"],
        single_buyer_dependency_risk=single_buyer,
        risk_flags=flags,
        mitigation_strategies=list(dict.fromkeys(f.mitigation for f in flags if f.mitigation)),
    )
    return {"risk_intel": intel}
