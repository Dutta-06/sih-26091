"""Health Score and Early Warning Agent (Module 3, TDD 7.4).

Reads: state.monitoring_record, state.financial_plan (operating margin of the original plan), catalog activity,
       pricing intelligence; thresholds from settings.health_score_thresholds_path
Writes: state.monitoring_record[-1] (health_score, health_band, early_warning_flag, warning_reason,
        intervention_type, suggested_intervention)
Tech: rule-based scoring of actuals against the original plan; all thresholds and weights are configuration

Components (each 0..1, missing ones dropped and weights renormalised):
    revenue_vs_plan  = reported_revenue / projected_baseline_revenue / revenue_ratio_full_score
    surplus_coverage = (operating_surplus / installment_due) / coverage_full_score
    repayment        = repayment_scores[loan_installment_status]
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from config.settings import settings
from module3_monitoring._case import activity, intel
from orchestrator.state import CaseState, HealthSnapshot


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def thresholds() -> dict[str, Any]:
    return _load(str(settings.health_score_thresholds_path))


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _weeks(snap: HealthSnapshot) -> float:
    try:
        days = int(snap.period_label.rsplit("(", 1)[1].split()[0])
    except (IndexError, ValueError):
        days = 7
    return max(1.0, days / 7)


def _planned_expense_ratio(state: CaseState, act: dict[str, Any]) -> Optional[float]:
    proj = state.financial_plan.operating_projection if state.financial_plan else None
    margin = proj.operating_margin if proj else act.get("operating_margin")
    return 1 - margin if margin is not None else None


def _suggestion(kind: str, state: CaseState, act: dict[str, Any], m: dict[str, Any]) -> str:
    inputs = ", ".join(act.get("key_inputs", [])[:2]) or "main inputs"
    buyers = ", ".join(act.get("buyers", [])[:2]) or "existing buyers"
    category = act.get("category", "the enterprise")
    if kind == "pricing_adjustment":
        pricing = intel(state, "pricing")
        target = getattr(pricing, "optimal_target_price", None)
        ref = act.get("reference_price") or {}
        anchor = (f"the pricing analysis target of Rs {target:,.0f} ({pricing.source_confidence})" if target
                  else f"the catalog reference range Rs {ref.get('low')}-{ref.get('high')} (estimated)" if ref
                  else "prevailing local prices")
        return (f"Revenue is {m['ratio']:.0%} of the plan baseline while transaction volume looks normal: review the "
                f"price per {act.get('price_unit', 'unit')} against {anchor}, and check realisations from {buyers}.")
    if kind == "supply_chain_change":
        return (f"Expenses are {m['expense_ratio']:.0%} of revenue against about {m['planned_expense_ratio']:.0%} "
                f"in the plan: compare quotes for {inputs}, consider an alternate source or pooled purchase "
                f"through the procurement cluster.")
    if kind == "repayment_counselling":
        cov = f"surplus covers {m['coverage']:.2f}x the installment due" if m.get("coverage") is not None else \
            f"installment status is {m['status']}"
        return (f"For this {category} unit the {cov}: meet the SCA / bank loan officer early to discuss "
                f"the repayment date or restructuring before it becomes overdue.")
    return (f"The signal is unclear or has stayed at risk: request a mentor review of {category} operations, "
            f"covering input costs ({inputs}) and offtake to {buyers}.")


def run(state: CaseState) -> dict[str, Any]:
    if not state.monitoring_record:
        return {}
    cfg = thresholds()
    records = list(state.monitoring_record)
    snap = records[-1].model_copy()
    act = activity(state) or {}

    ratio = snap.reported_revenue / snap.projected_baseline_revenue if snap.projected_baseline_revenue > 0 else None
    coverage = snap.operating_surplus / snap.installment_due if snap.installment_due > 0 else None
    components = {
        "revenue_vs_plan": None if ratio is None else _clamp(ratio / cfg["revenue_ratio_full_score"]),
        "surplus_coverage": None if coverage is None else _clamp(coverage / cfg["coverage_full_score"]),
        "repayment": cfg["repayment_scores"].get(snap.loan_installment_status),
    }
    if snap.loan_installment_status == "unknown" and ratio is None and coverage is None:
        components["repayment"] = None  # nothing measured against the plan: no score rather than a guess
    used = {k: v for k, v in components.items() if v is not None}
    if not used:
        snap.health_score, snap.health_band = None, None
        snap.early_warning_flag = False
        snap.warning_reason = "Not enough plan data (baseline revenue / installment) to score this period."
        records[-1] = snap
        return {"monitoring_record": records}

    total_w = sum(cfg["weights"][k] for k in used)
    snap.health_score = round(100 * sum(cfg["weights"][k] * v for k, v in used.items()) / total_w, 1)
    bands = cfg["bands"]
    snap.health_band = ("healthy" if snap.health_score >= bands["healthy_min_score"]
                        else "watch" if snap.health_score >= bands["watch_min_score"] else "at_risk")

    reasons = []
    if snap.health_band == "at_risk":
        reasons.append(f"health score {snap.health_score:.0f} is in the at-risk band")
    if ratio is not None and ratio < cfg["revenue_ratio_floor"]:
        reasons.append(f"revenue is {ratio:.0%} of the plan baseline (floor {cfg['revenue_ratio_floor']:.0%})")
    snap.early_warning_flag = bool(reasons)
    snap.warning_reason = "; ".join(reasons).capitalize() if reasons else None

    expense_ratio = snap.reported_expenses / snap.reported_revenue if snap.reported_revenue > 0 else None
    planned_er = _planned_expense_ratio(state, act)
    prev = [r for r in records[:-1] if r.health_band is not None]
    volume = snap.transactions_parsed / _weeks(snap)
    normal_volume = (volume >= cfg["normal_volume_vs_previous_ratio"] * prev[-1].transactions_parsed / _weeks(prev[-1])
                     if prev else volume >= cfg["normal_volume_min_transactions_per_week"])
    persistent = snap.health_band == "at_risk" and len(prev) >= cfg["persistent_at_risk_snapshots"] - 1 and all(
        r.health_band == "at_risk" for r in prev[-(cfg["persistent_at_risk_snapshots"] - 1):])

    kind = None
    if snap.early_warning_flag or snap.health_band == "watch":
        if snap.loan_installment_status == "overdue" or (coverage is not None and coverage < 1):
            kind = "repayment_counselling"
        elif (expense_ratio is not None and planned_er is not None
              and expense_ratio > planned_er + cfg["expense_ratio_spike_margin"]) and not persistent:
            kind = "supply_chain_change"
        elif ratio is not None and ratio < cfg["revenue_shortfall_ratio"] and normal_volume and not persistent:
            kind = "pricing_adjustment"
        else:
            kind = "mentor_outreach"
    snap.intervention_type = kind
    snap.suggested_intervention = _suggestion(kind, state, act, {
        "ratio": ratio, "coverage": coverage, "status": snap.loan_installment_status,
        "expense_ratio": expense_ratio, "planned_expense_ratio": planned_er,
    }) if kind else None
    records[-1] = snap
    return {"monitoring_record": records}
