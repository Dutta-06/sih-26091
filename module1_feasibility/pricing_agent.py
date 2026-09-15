"""Pricing Agent (TDD 5.3 "Pricing analysis"; TECHNICAL_SETUP.md 5.7).

Agri-linked categories (catalog/candidate ``commodity`` set) use real Agmarknet
modal prices from data.gov.in: min/max/target are the 25th/75th/50th percentiles
of the most recent 12 months of monthly modal prices ("real"). Otherwise, or when
that source is unavailable, a representative local range is estimated from the
catalog reference price scaled by a purchasing-power index: the SECC district asset
index when a dataset is loaded, else the state purchasing-power tier
(low 0.85 / medium 1.0 / high 1.15, a documented placeholder). Every price point
carries its own confidence label.

Reads: state.business_shortlist, state.entrepreneur_profile.location
Writes: state.pricing_intel
Tech: data.gov.in Agmarknet API (real prices), SECC asset-index / state-tier purchasing-power proxy (estimated).
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from common.net import DataUnavailable
from common.reference import get_activity, lookup_state
from data_connectors import agmarknet, secc
from orchestrator.state import CaseState, DataSourceRef, Level, LocationDetails, PricePoint, PricingIntelligence

STATE_TIER_INDEX: dict[str, float] = {"low": 0.85, "medium": 1.0, "high": 1.15}


def index_level(index: float) -> Level:
    return "low" if index < 0.925 else "medium" if index <= 1.075 else "high"


def real_price_intel(commodity: str, loc: LocationDetails) -> PricingIntelligence:
    """Direct market data path; raises ``DataUnavailable`` when no real prices exist."""
    history = agmarknet.fetch_monthly_prices(commodity, loc.state, loc.district, months=36)
    recent = np.array([p.modal_price for p in history[-12:]])
    low, mid, high = (round(float(np.percentile(recent, q)), 2) for q in (25, 50, 75))
    unit, src = agmarknet.PRICE_UNIT, f"Agmarknet ({commodity})"
    scope = f"{loc.district}, {loc.state}" if loc.district else (loc.state or "all markets")
    limitations = [] if len(history) >= 12 else [
        f"Only {len(history)} month(s) of Agmarknet history available; percentiles rest on a short window."]
    return PricingIntelligence(
        recommended_price_unit=unit,
        min_market_price=low, max_market_price=high, optimal_target_price=mid,
        price_points=[PricePoint(label=label, value=v, unit=unit, source_confidence="real", source=src)
                      for label, v in (("25th percentile modal price (12 mo)", low), ("Median modal price (12 mo)", mid),
                                       ("75th percentile modal price (12 mo)", high))],
        price_source_type="direct_market_data",
        monthly_price_history=history,
        source_confidence="real",
        data_source_detail=f"Agmarknet modal prices for {commodity}, {scope}: {len(history)} month(s), latest {history[-1].month}",
        sources=[DataSourceRef(name="Agmarknet via data.gov.in", source_confidence="real",
                               detail=f"{len(history)} monthly medians of modal price")],
        limitations=limitations + ["Mandi (wholesale) prices; farm-gate and retail prices differ."],
    )


def purchasing_power(loc: LocationDetails) -> tuple[Optional[float], Optional[DataSourceRef], list[str]]:
    """(index, source, limitations): SECC district index, else state tier, else None."""
    notes: list[str] = []
    try:
        raw, index = secc.purchasing_power_index(loc.district, loc.state)
        return index, DataSourceRef(name="SECC 2011 asset index", source_confidence="estimated",
                                    detail=f"{loc.district}: asset share {raw} -> index {index}"), notes
    except DataUnavailable as exc:
        notes.append(f"SECC asset index unavailable ({exc}).")
    found = lookup_state(loc.state)
    tier = found[1].get("purchasing_power") if found else None
    if tier in STATE_TIER_INDEX:
        notes.append(f"Purchasing power uses the coarse state tier for {found[0]} ('{tier}'), not district data.")
        return STATE_TIER_INDEX[tier], DataSourceRef(name="State purchasing-power tier (reference table)",
                                                     source_confidence="estimated",
                                                     detail=f"{found[0]}: {tier} -> {STATE_TIER_INDEX[tier]}"), notes
    notes.append("No state resolved for a purchasing-power adjustment.")
    return None, None, notes


def proxy_price_intel(activity: dict[str, Any], loc: LocationDetails, prior: list[str]) -> PricingIntelligence:
    ref = activity.get("reference_price") or {}
    unit = activity.get("price_unit", "")
    if ref.get("low") is None or ref.get("high") is None:
        return PricingIntelligence(
            recommended_price_unit=unit, price_source_type="unavailable",
            data_source_detail="No market data and no catalog reference price for this activity.",
            limitations=prior + ["No usable price data; price range not estimated."])
    index, source, notes = purchasing_power(loc)
    factor = index if index is not None else 1.0
    low, high = round(ref["low"] * factor, 2), round(ref["high"] * factor, 2)
    mid = round((low + high) / 2, 2)
    basis = f"catalog reference {ref['low']}-{ref['high']} x purchasing-power index {index}" if index is not None \
        else f"catalog reference {ref['low']}-{ref['high']} (no regional adjustment)"
    sources = [DataSourceRef(name="Business catalog reference price", source_confidence="estimated",
                             detail=f"{ref['low']}-{ref['high']} {unit} (planning assumption)")]
    if source:
        sources.append(source)
    return PricingIntelligence(
        recommended_price_unit=unit,
        min_market_price=low, max_market_price=high, optimal_target_price=mid,
        price_points=[PricePoint(label=label, value=v, unit=unit, source_confidence="estimated", source=basis)
                      for label, v in (("Estimated local low", low), ("Estimated target", mid), ("Estimated local high", high))],
        regional_purchasing_power_proxy=index_level(index) if index is not None else None,
        purchasing_power_index=index,
        price_source_type="purchasing_power_proxy",
        source_confidence="estimated",
        data_source_detail=f"Estimated range: {basis}",
        sources=sources,
        limitations=prior + notes + ["Price range is an estimate, not an observed local price; validate with nearby sellers."],
    )


def run(state: CaseState) -> dict[str, Any]:
    candidate = state.selected_candidate()
    activity = get_activity(candidate.catalog_id) if candidate and candidate.catalog_id else None
    profile = state.entrepreneur_profile
    loc = profile.location if profile else LocationDetails()
    if activity is None:
        return {"pricing_intel": PricingIntelligence(
            data_source_detail="No catalog activity selected.",
            limitations=["No catalog activity selected; pricing not assessed."])}

    commodity = (candidate.commodity if candidate else None) or activity.get("commodity")
    prior: list[str] = []
    if commodity:
        try:
            intel = real_price_intel(commodity, loc)
            if activity.get("price_unit") and activity["price_unit"] != intel.recommended_price_unit:
                intel.limitations.append(f"Agmarknet quotes {intel.recommended_price_unit}; the activity sells in "
                                         f"'{activity['price_unit']}', so convert before using as a selling price.")
            return {"pricing_intel": intel}
        except DataUnavailable as exc:
            prior.append(f"Direct market prices for {commodity} unavailable ({exc}); falling back to an estimate.")
    else:
        prior.append("Category has no Agmarknet commodity; direct market prices do not apply.")
    return {"pricing_intel": proxy_price_intel(activity, loc, prior)}
