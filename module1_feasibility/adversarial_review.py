"""Adversarial (Red-Team) Review (Module 1, TDD 5.4-5.5, TECHNICAL_SETUP 5.10).

Reads: state.feasibility_record (swot, selected activity), state.market_intelligence, state.entrepreneur_profile
Writes: state.feasibility_record (verdict, verdict_reasoning, adversarial_critique, rejection_history,
attempt_number, alternatives_exhausted)
Tech: deterministic red-team rules looking only for reasons the business would fail; coverage figures from
module2_financial.operating_model.preview_debt_service; optional common.llm.explain rephrases the reasoning.

Rules (each emits a critique with the numbers):
  not_recommended  R1 catalog minimum project cost > project the capital supports
                   R2 base DSCR < 1.0 (catalog economics cannot service the loan)
                   R3 competitor saturation high AND z-score vs district > 2
  marginal         M1 base DSCR < 1.25   M2 saturation high (competitor or cross-checked sub-niche)
                   M3 two or more high-severity non-seasonal risk flags
                   M4 weakest seasonal-quarter DSCR < 0.8 (seasonality is judged here, not in M3)
Estimated (low-confidence) inputs never reject on their own; they are counted in a critique.
Outside the scheme range (> Rs 50L project) is not a business rejection; the financial engine reports it.
"""

from __future__ import annotations

from typing import Any, Optional

from common.llm import explain
from common.reference import get_activity
from config.settings import settings
from module1_feasibility.discovery_agent import feasible_unrejected
from module1_feasibility.profiling_agent import affordable_project_cost
from orchestrator.state import CaseState, FeasibilityRecord, MarketIntelligence, RejectionEntry, Verdict

DSCR_REJECT = 1.0
DSCR_MARGINAL = 1.25
SEASONAL_DSCR_MARGINAL = 0.8
Z_REJECT = 2.0
SEASONAL_RISK_IDS = {"seasonal_demand_variation", "working_capital_strain", "festival_season_concentration"}


def _preview(capital: float, activity: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        from module2_financial.operating_model import preview_debt_service

        return preview_debt_service(capital, activity)
    except Exception:
        return None


def evaluate(capital: float, activity: dict[str, Any], mi: Optional[MarketIntelligence],
             preview: Optional[dict[str, Any]]) -> tuple[Verdict, list[str], list[str]]:
    """Returns (verdict, failure reasons driving the verdict, all critique lines)."""
    reject, marginal, notes = [], [], []
    affordable = affordable_project_cost(capital)
    if activity["min_project_cost"] > affordable:
        reject.append(f"R1: {activity['category']} needs at least Rs {activity['min_project_cost']:,.0f}; "
                      f"capital Rs {capital:,.0f} supports Rs {affordable:,.0f}.")

    if preview is None:
        notes.append("Debt-service preview unavailable; coverage rules not applied.")
    elif not preview.get("eligible"):
        notes.append(f"Project Rs {preview.get('project_cost', 0):,.0f} is outside the scheme range; coverage rules not applied.")
    else:
        dscr, seasonal = preview.get("base_dscr"), preview.get("min_seasonal_dscr")
        basis = (f"quarterly surplus Rs {preview.get('quarterly_surplus') or 0:,.0f} vs installment "
                 f"Rs {preview.get('quarterly_installment') or 0:,.0f}, catalog estimates")
        if dscr is not None and dscr < DSCR_REJECT:
            reject.append(f"R2: base DSCR {dscr:.2f} < {DSCR_REJECT} ({basis}).")
        elif dscr is not None and dscr < DSCR_MARGINAL:
            marginal.append(f"M1: base DSCR {dscr:.2f} < {DSCR_MARGINAL} ({basis}).")
        if seasonal is not None and seasonal < SEASONAL_DSCR_MARGINAL:
            marginal.append(f"M4: weakest seasonal quarter DSCR {seasonal:.2f} < {SEASONAL_DSCR_MARGINAL}.")

    if mi is not None:
        comp, z = mi.competitor, mi.competitor.z_score_vs_district
        if comp.saturation_level == "high" and z is not None and z > Z_REJECT:
            reject.append(f"R3: competitor saturation high, z-score {z:+.2f} vs district > {Z_REJECT} ({comp.source_confidence}).")
        elif comp.saturation_level == "high":
            marginal.append(f"M2: competitor saturation high ({comp.estimated_competitor_count} nearby, {comp.source_confidence}).")
        saturated = [n.name for n in mi.opportunity.sub_niches if n.saturation_level == "high"]
        if saturated and len(saturated) == len(mi.opportunity.sub_niches) and comp.saturation_level != "high":
            marginal.append(f"M2: all identified sub-niches saturated ({', '.join(saturated[:3])}).")
        # Seasonal cash-flow risk is already tested quantitatively by M4, so it is not counted twice here.
        highs = [f.title for f in mi.risk.risk_flags
                 if f.severity == "high" and f.category != "seasonal" and f.risk_id not in SEASONAL_RISK_IDS]
        if len(highs) >= 2:
            marginal.append(f"M3: {len(highs)} high-severity non-seasonal risks ({'; '.join(highs[:3])}, {mi.risk.source_confidence}).")
        estimated = sum(1 for c in mi.confidence_summary().values() if c == "estimated")
        if estimated:
            notes.append(f"{estimated} of 6 analyses are estimates; verify locally before committing capital.")
        if mi.missing_branches:
            notes.append(f"Missing analyses: {', '.join(mi.missing_branches)}.")
    else:
        notes.append("Market intelligence missing; only capital and coverage rules applied.")

    verdict: Verdict = "not_recommended" if reject else "marginal" if marginal else "viable"
    reasons = reject + marginal
    return verdict, reasons, reasons + notes


def run(state: CaseState) -> dict[str, Any]:
    record = (state.feasibility_record or FeasibilityRecord()).model_copy(deep=True)
    candidate = state.selected_candidate()
    profile = state.entrepreneur_profile
    activity = get_activity(candidate.catalog_id) if candidate and candidate.catalog_id else None
    if candidate is None or activity is None or profile is None:
        record.verdict = "not_recommended"
        record.alternatives_exhausted = True
        record.verdict_reasoning = "No affordable, unrejected activity is left to assess."
        record.adversarial_critique = [record.verdict_reasoning]
        return {"feasibility_record": record}

    capital = profile.available_capital
    verdict, reasons, critique = evaluate(capital, activity, state.market_intelligence, _preview(capital, activity))
    fallback = (f"{candidate.category}: {verdict.replace('_', ' ')}. "
                + (" ".join(reasons) if reasons else "No red-team rule triggered at the current estimates."))
    text, _ = explain(
        "You are a red-team credit reviewer. Restate only the given reasons the business may fail; add no numbers.",
        fallback, fallback)
    record.verdict, record.verdict_reasoning, record.adversarial_critique = verdict, text, critique
    record.selected_category, record.selected_catalog_id = candidate.category, candidate.catalog_id

    if verdict != "viable":
        record.rejection_history.append(RejectionEntry(
            category=candidate.category, catalog_id=candidate.catalog_id, verdict=verdict,
            reasons=reasons, attempt_number=record.attempt_number))
        record.attempt_number += 1
        remaining = feasible_unrejected(profile, record.rejected_catalog_ids())
        record.alternatives_exhausted = record.attempt_number > settings.max_feasibility_attempts or not remaining
    return {"feasibility_record": record}
