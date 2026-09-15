"""Business Discovery Agent (Module 1, TDD 5.2 and 5.5).

Reads: state.entrepreneur_profile, state.feasibility_record.rejection_history
Writes: state.business_shortlist (ranked; top entry is the activity assessed next)
Tech: pure rule-based multi-factor scoring over the business catalog (capital fit, stated preference,
adjacency to a rejected option, infrastructure fit) times an outcome-learning prior.

First pass: the user's stated activity, if affordable, is assessed first. After a rejection the
rejected activities are excluded and alternatives adjacent to them (same sector or listed in the
catalog ``adjacent`` field) are preferred (TDD 5.5).
"""

from __future__ import annotations

from typing import Any, Optional

from common.reference import load_catalog, match_activity
from module1_feasibility.profiling_agent import affordable_project_cost
from orchestrator.state import BusinessCandidate, CaseState, EntrepreneurProfile, OutcomeLearningStatus

WEIGHTS = {"capital_fit": 0.35, "preference_match": 0.25, "adjacency": 0.20, "infrastructure_fit": 0.20}
PRIOR_BOUNDS = (0.8, 1.2)

INFRA_CUES: dict[str, list[str]] = {
    "three_phase_power": ["three phase", "three-phase", "3 phase", "3-phase", "industrial power"],
    "pond": ["pond", "talab", "tank", "तालाब"],
    "shop_premises": ["shop", "dukan", "premises", "market space", "दुकान"],
    "shed": ["shed", "cattle shed", "land", "plot", "courtyard", "zameen", "जमीन"],
    "water": ["water", "well", "borewell", "tubewell", "handpump", "pani", "पानी"],
    "electricity": ["electricity", "power connection", "bijli", "three phase", "बिजली"],
    "roadside_premises": ["roadside", "main road", "highway", "bus stand", "market"],
    "flowering_crops_nearby": ["orchard", "mustard field", "sunflower", "litchi", "crops", "farm"],
}


def infrastructure_fit(profile: EntrepreneurProfile, activity: dict[str, Any]) -> float:
    """1.0 per need evidenced in assets/premises text, 0.5 per need not mentioned (unknown = neutral)."""
    needs = activity.get("infrastructure_needs") or []
    if not needs:
        return 1.0
    text = " ".join([*profile.assets, profile.land_or_premises or ""]).lower()
    matched = sum(1 for need in needs if any(cue in text for cue in INFRA_CUES.get(need, [need.replace("_", " ")])))
    return round((matched + 0.5 * (len(needs) - matched)) / len(needs), 3)


def _prior_value(prior: Any) -> tuple[float, bool, bool]:
    """(bounded multiplier, prior available, synthetic dominant)."""
    if isinstance(prior, OutcomeLearningStatus) and prior.category_prior is not None:
        lo, hi = PRIOR_BOUNDS
        return max(lo, min(hi, prior.category_prior)), True, prior.is_synthetic_dominant
    if isinstance(prior, (int, float)):
        return max(PRIOR_BOUNDS[0], min(PRIOR_BOUNDS[1], float(prior))), True, False
    return 1.0, False, False


def score_candidate(
    profile: EntrepreneurProfile,
    activity: dict[str, Any],
    *,
    rejected_sectors: set[str] | frozenset[str] = frozenset(),
    rejected_ids: set[str] | frozenset[str] = frozenset(),
    prior: Any = None,
) -> tuple[float, dict[str, float]]:
    """Deterministic 0-100 score and its components. Capital-infeasible activities score 0."""
    affordable = affordable_project_cost(profile.available_capital)
    min_cost = float(activity.get("min_project_cost") or 0)
    feasible = affordable > 0 and min_cost <= affordable
    capital_fit = (1.0 - 0.5 * min_cost / affordable) if feasible else 0.0

    preferred = match_activity(profile.business_preference)
    if preferred and preferred["id"] == activity["id"]:
        preference = 1.0
    elif preferred and preferred.get("sector") == activity.get("sector"):
        preference = 0.5
    else:
        preference = 0.0

    adjacency = 0.0
    if activity["id"] not in rejected_ids and (rejected_ids or rejected_sectors):
        adjacent_lists = {a for rid in rejected_ids for a in (load_catalog().get(rid, {}).get("adjacent") or [])}
        if activity["id"] in adjacent_lists:
            adjacency = 1.0
        elif activity.get("sector") in rejected_sectors:
            adjacency = 0.7

    infra = infrastructure_fit(profile, activity)
    multiplier, prior_available, synthetic = _prior_value(prior)
    base = (WEIGHTS["capital_fit"] * capital_fit + WEIGHTS["preference_match"] * preference
            + WEIGHTS["adjacency"] * adjacency + WEIGHTS["infrastructure_fit"] * infra)
    score = round(100 * base * multiplier, 2) if feasible else 0.0
    breakdown = {
        "capital_fit": round(capital_fit, 3),
        "capital_feasible": 1.0 if feasible else 0.0,
        "preference_match": preference,
        "adjacency": adjacency,
        "infrastructure_fit": infra,
        "outcome_prior": multiplier,
        "outcome_prior_available": 1.0 if prior_available else 0.0,
        "outcome_prior_synthetic_dominant": 1.0 if synthetic else 0.0,
    }
    return score, breakdown


def _category_prior(catalog_id: str, district: Optional[str]) -> Any:
    try:
        from module3_monitoring.outcome_learning_loop import category_prior

        return category_prior(catalog_id, district)
    except Exception:
        return None


def feasible_unrejected(profile: EntrepreneurProfile, rejected_ids: set[str]) -> list[dict[str, Any]]:
    affordable = affordable_project_cost(profile.available_capital)
    return [a for a in load_catalog().values()
            if a["id"] not in rejected_ids and affordable > 0 and a["min_project_cost"] <= affordable]


def _rationale(activity: dict[str, Any], parts: dict[str, float], affordable: float, adjacent_to: Optional[str],
               is_pref: bool) -> str:
    bits = [f"Minimum project Rs {activity['min_project_cost']:,.0f} within the Rs {affordable:,.0f} the stated capital supports"]
    if is_pref:
        bits.append("matches the stated preference")
    if adjacent_to:
        bits.append(f"proposed as an alternative adjacent to rejected '{adjacent_to}'")
    if parts["infrastructure_fit"] < 1.0:
        bits.append(f"infrastructure needs ({', '.join(activity.get('infrastructure_needs') or [])}) not confirmed in profile")
    if not parts["outcome_prior_available"]:
        bits.append("no outcome-learning prior available (neutral)")
    return "; ".join(bits) + ". Catalog economics are planning estimates."


def _adjacent_source(activity: dict[str, Any], history: list, catalog: dict[str, dict[str, Any]]) -> Optional[str]:
    """Most recent rejected activity this one is adjacent to (catalog list first, then same sector)."""
    rejected = [catalog[r.catalog_id] for r in reversed(history) if r.catalog_id in catalog]
    for rej in rejected:
        if activity["id"] in (rej.get("adjacent") or []):
            return rej["category"]
    return next((rej["category"] for rej in rejected if rej.get("sector") == activity.get("sector")), None)


def run(state: CaseState) -> dict[str, Any]:
    profile = state.entrepreneur_profile
    if profile is None or profile.available_capital <= 0:
        return {"business_shortlist": []}
    history = state.feasibility_record.rejection_history if state.feasibility_record else []
    rejected_ids = {r.catalog_id for r in history if r.catalog_id}
    catalog = load_catalog()
    rejected_sectors = {catalog[r]["sector"] for r in rejected_ids if r in catalog}
    affordable = affordable_project_cost(profile.available_capital)
    preferred = match_activity(profile.business_preference)
    district = profile.location.district

    scored = []
    for activity in feasible_unrejected(profile, rejected_ids):
        score, parts = score_candidate(profile, activity, rejected_sectors=rejected_sectors,
                                       rejected_ids=rejected_ids, prior=_category_prior(activity["id"], district))
        is_pref = bool(preferred and preferred["id"] == activity["id"])
        # First pass: assess what the user asked for. After a rejection: prefer adjacency, then score.
        key = (is_pref and not history, parts["adjacency"] if history else 0.0, score)
        scored.append((key, activity, score, parts, is_pref))
    scored.sort(key=lambda x: x[0], reverse=True)

    shortlist = []
    for rank, (_, activity, score, parts, is_pref) in enumerate(scored, start=1):
        adjacent_to = _adjacent_source(activity, history, catalog) if parts["adjacency"] > 0 else None
        infra = parts["infrastructure_fit"]
        shortlist.append(BusinessCandidate(
            category=activity["category"],
            catalog_id=activity["id"],
            sector=activity.get("sector", ""),
            nic_code=activity.get("nic_class"),
            commodity=activity.get("commodity"),
            rationale=_rationale(activity, parts, affordable, adjacent_to, is_pref),
            rank=rank,
            feasibility_score=score,
            score_breakdown=parts,
            indicative_setup_cost=affordable,
            min_project_cost=float(activity["min_project_cost"]),
            infrastructure_readiness="high" if infra >= 0.9 else "moderate" if infra >= 0.6 else "low",
            is_user_preference=is_pref,
            adjacent_to=adjacent_to,
            source_confidence="estimated",
        ))
    return {"business_shortlist": shortlist}
