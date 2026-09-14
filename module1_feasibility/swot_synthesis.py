"""SWOT Synthesis (Module 1, TDD 5.4, TECHNICAL_SETUP 5.9).

Reads: the six parallel intel fields (market_reach_intel ... supply_chain_intel), entrepreneur_profile,
selected candidate, feasibility_record (rejection history carried across loop-backs)
Writes: state.market_intelligence, state.feasibility_record (swot, selected activity, preference context)
Tech: deterministic fan-in; every SWOT bullet is generated from an actual value (bullets whose data is
missing are skipped) and carries its confidence label; opportunity sub-niche saturation is cross-checked
against competitor density; budget scaling notes computed from capital vs catalog minimum cost.
"""

from __future__ import annotations

from typing import Any, Optional

from common.reference import get_activity
from module1_feasibility.profiling_agent import affordable_project_cost
from orchestrator.state import (
    CaseState,
    CompetitorIntelligence,
    FeasibilityRecord,
    MarketIntelligence,
    SubNiche,
    SWOTAnalysis,
)

BRANCHES = {
    "market_reach": "market_reach_intel",
    "opportunity": "opportunity_intel",
    "risk": "risk_intel",
    "competitor": "competitor_intel",
    "pricing": "pricing_intel",
    "supply_chain": "supply_chain_intel",
}


def _tag(conf: str) -> str:
    return f"({conf})"


def _classify(density: float, benchmark: float) -> Optional[str]:
    try:
        from module1_feasibility.opportunity_agent import classify_saturation

        result = classify_saturation(density, benchmark)
    except Exception:
        return None
    level = result[0] if isinstance(result, tuple) else result
    return level if level in ("low", "medium", "high", "unknown") else None


def cross_check_saturation(niches: list[SubNiche], competitor: CompetitorIntelligence) -> tuple[list[SubNiche], list[str]]:
    """Re-grade sub-niche saturation against observed competitor density; returns (niches, notes)."""
    density, benchmark = competitor.density_per_10k_population, competitor.benchmark_district_avg_density
    if density is None:
        return niches, ["Sub-niche saturation not cross-checked: competitor density unknown."]
    observed = _classify(density, benchmark) if benchmark else None
    observed = observed or (competitor.saturation_level if competitor.saturation_level != "unknown" else None)
    if observed is None:
        return niches, ["Sub-niche saturation not cross-checked: no density benchmark."]
    notes, out = [], []
    for niche in niches:
        if niche.saturation_level != observed:
            notes.append(f"Sub-niche '{niche.name}': corpus saturation {niche.saturation_level} vs competitor density "
                         f"{density:.2f}/10k -> {observed} {_tag(competitor.source_confidence)}.")
            niche = niche.model_copy(update={
                "saturation_level": observed,
                "saturation_basis": (niche.saturation_basis + " | " if niche.saturation_basis else "")
                + f"cross-checked against competitor density {density:.2f}/10k (benchmark {benchmark})",
                "source_confidence": "estimated" if "estimated" in (niche.source_confidence, competitor.source_confidence) else "real",
            })
        out.append(niche)
    return out, notes


def build_swot(mi: MarketIntelligence, capital: float, activity: Optional[dict[str, Any]]) -> SWOTAnalysis:
    s, w, o, t = [], [], [], []
    reach, opp, risk, comp, pricing, supply = mi.market_reach, mi.opportunity, mi.risk, mi.competitor, mi.pricing, mi.supply_chain

    if reach.consumer_base_estimate is not None:
        (s if reach.consumer_base_estimate >= 10_000 else w).append(
            f"Consumer base ~{reach.consumer_base_estimate:,} within {reach.radius_km:g} km {_tag(reach.source_confidence)}.")
    if reach.distribution_points:
        near = sorted((d for d in reach.distribution_points if d.distance_km is not None), key=lambda d: d.distance_km)
        detail = f"; nearest {near[0].name} at {near[0].distance_km:.1f} km" if near else ""
        s.append(f"{len(reach.distribution_points)} distribution points identified{detail} {_tag(reach.source_confidence)}.")

    if comp.estimated_competitor_count is not None:
        z = f", z-score {comp.z_score_vs_district:+.2f} vs district" if comp.z_score_vs_district is not None else ""
        line = f"{comp.estimated_competitor_count} similar enterprises nearby (saturation {comp.saturation_level}{z}) {_tag(comp.source_confidence)}."
        (t if comp.saturation_level == "high" else s if comp.saturation_level == "low" else w).append(line)

    for niche in opp.sub_niches[:3]:
        if niche.saturation_level in ("low", "medium"):
            o.append(f"Sub-niche '{niche.name}' with {niche.saturation_level} saturation {_tag(niche.source_confidence)}.")
        elif niche.saturation_level == "high":
            t.append(f"Sub-niche '{niche.name}' appears saturated {_tag(niche.source_confidence)}.")
    for niche in opp.unserved_demand_niches[:2]:
        o.append(f"Unserved demand: {niche} {_tag(opp.source_confidence)}.")
    o.extend(f"Local feedback: {e}" for e in opp.local_feedback_evidence[:2])

    if pricing.min_market_price is not None and pricing.max_market_price is not None:
        o.append(f"Market price band {pricing.min_market_price:,.0f}-{pricing.max_market_price:,.0f} "
                 f"{pricing.recommended_price_unit} ({pricing.price_source_type.replace('_', ' ')}) {_tag(pricing.source_confidence)}.")
    if pricing.regional_purchasing_power_proxy == "low":
        w.append(f"Low regional purchasing power {_tag(pricing.source_confidence)}.")

    if risk.low_season_months:
        t.append(f"Low-demand months {', '.join(risk.low_season_months)} ({risk.seasonal_demand_variation} seasonal variation) {_tag(risk.source_confidence)}.")
    if risk.road_distance_to_hub_km is not None:
        (t if risk.supply_route_risk == "high" else w if risk.supply_route_risk == "medium" else s).append(
            f"Road distance to hub {risk.road_distance_to_hub_km:.1f} km ({risk.route_distance_method}), route risk {risk.supply_route_risk} {_tag(risk.source_confidence)}.")
    t.extend(f"{f.title} [{f.severity}] {_tag(f.source_confidence)}." for f in risk.risk_flags if f.severity == "high")

    if supply.raw_material_availability != "unknown":
        (s if supply.raw_material_availability == "locally_available" else w).append(
            f"Raw materials {supply.raw_material_availability.replace('_', ' ')} {_tag(supply.source_confidence)}.")
    w.extend(f"Supply single point of failure: {p} {_tag(supply.source_confidence)}." for p in supply.single_points_of_failure[:2])

    affordable = affordable_project_cost(capital)
    if activity and affordable > 0:
        min_cost = activity["min_project_cost"]
        ratio = affordable / min_cost if min_cost else 0
        notes = (f"Capital Rs {capital:,.0f} supports a project of Rs {affordable:,.0f} (10% margin), "
                 f"{ratio:.1f}x the catalog minimum of Rs {min_cost:,.0f} for {activity['category']} (estimated planning figure).")
        if ratio < 1:
            notes += " Below the minimum viable scale."
        elif ratio < 1.5:
            notes += " Close to minimum scale: little room for cost overruns."
    else:
        notes = "Budget scaling not computed: capital or activity unknown."

    sources = sorted({f"{src.name} ({src.source_confidence})" for intel in (reach, opp, risk, comp, pricing, supply)
                      for src in intel.sources})
    return SWOTAnalysis(strengths=s, weaknesses=w, opportunities=o, threats=t,
                        budget_scaling_notes=notes, grounding_sources=sources)


def run(state: CaseState) -> dict[str, Any]:
    fields, missing = {}, []
    for branch, attr in BRANCHES.items():
        value = getattr(state, attr)
        if value is None:
            missing.append(branch)
        else:
            fields[branch] = value
    mi = MarketIntelligence(**fields, missing_branches=missing)
    niches, notes = cross_check_saturation(mi.opportunity.sub_niches, mi.competitor)
    mi.opportunity = mi.opportunity.model_copy(update={
        "sub_niches": niches, "limitations": [*mi.opportunity.limitations, *notes]})
    for branch in missing:
        getattr(mi, branch).limitations.append(f"{branch} analysis did not produce output in this run.")

    record = (state.feasibility_record or FeasibilityRecord()).model_copy(deep=True)
    profile = state.entrepreneur_profile
    candidate = state.selected_candidate()
    activity = get_activity(candidate.catalog_id) if candidate and candidate.catalog_id else None
    record.selected_category = candidate.category if candidate else ""
    record.selected_catalog_id = candidate.catalog_id if candidate else ""
    if profile and profile.preference_reason:
        pref = profile.business_preference or "the stated activity"
        suffix = "" if candidate and candidate.is_user_preference else f"; currently assessing {record.selected_category or 'no activity'} instead"
        record.preference_reason_context = f"User wants {pref} because: {profile.preference_reason}{suffix}."
    record.swot = build_swot(mi, profile.available_capital if profile else 0.0, activity) if candidate else SWOTAnalysis(
        budget_scaling_notes="No activity selected for assessment.")
    record.verdict_reasoning, record.adversarial_critique = "", []
    return {"market_intelligence": mi, "feasibility_record": record}
