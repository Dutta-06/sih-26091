"""Outcome Learning Loop (Module 3, TDD 7.5 / TECHNICAL_SETUP 7.6).

Reads: state.grievance_log, state.monitoring_record, cross-case outcome store (real + synthetic records)
Writes: outcome store (real records, is_synthetic=False), state.grievance_log (outcome tracking),
        state.outcome_learning (OutcomeLearningStatus with visible synthetic status)
Tech: weighted improvement rate shrunk toward neutral -> bounded category prior for discovery ranking

category_prior formula:
    weight per record = (1.0 if real else SYNTHETIC_WEIGHT) * (DISTRICT_BONUS if same district else 1.0)
    rate       = (sum(w * improved) + PRIOR_STRENGTH * 0.5) / (sum(w) + PRIOR_STRENGTH)
    multiplier = clamp(1 + 0.2 * (rate - 0.5), 0.9, 1.1)
"""

from __future__ import annotations

from typing import Any, Optional

from module3_monitoring._case import catalog_id, district
from module3_monitoring.grievance_engine import route, track_outcomes
from orchestrator import stores
from orchestrator.state import CaseState, OutcomeLearningStatus

SYNTHETIC_WEIGHT = 0.3
DISTRICT_BONUS = 2.0
PRIOR_STRENGTH = 10.0
PRIOR_BOUNDS = (0.9, 1.1)


def _ensure_seed() -> None:
    from synthetic_data.seed_outcomes import insert, load_or_generate
    insert(load_or_generate()["records"])


def category_prior(catalog_id: str, district: Optional[str]) -> OutcomeLearningStatus:
    records = stores.outcome_records(catalog_id) if catalog_id else []
    if catalog_id and not records:
        _ensure_seed()
        records = stores.outcome_records(catalog_id)
    records = [r for r in records if r["improved"] is not None]
    real = [r for r in records if not r["is_synthetic"]]
    synthetic = [r for r in records if r["is_synthetic"]]
    if not records:
        return OutcomeLearningStatus(
            real_records=0, synthetic_records=0, is_synthetic_dominant=False, category_prior=1.0,
            status_note="No outcome records (real or synthetic) for this activity; neutral prior 1.0 applied.")

    def weight(r: dict[str, Any]) -> float:
        same = district and r["district"] and r["district"].lower() == district.lower()
        return (SYNTHETIC_WEIGHT if r["is_synthetic"] else 1.0) * (DISTRICT_BONUS if same else 1.0)

    total = sum(weight(r) for r in records)
    rate = (sum(weight(r) * r["improved"] for r in records) + PRIOR_STRENGTH * 0.5) / (total + PRIOR_STRENGTH)
    multiplier = round(max(PRIOR_BOUNDS[0], min(PRIOR_BOUNDS[1], 1 + 0.2 * (rate - 0.5))), 3)
    synth_w = sum(weight(r) for r in synthetic)
    dominant = synth_w >= total - synth_w
    label = ("synthetic seed dominant, indicative only" if dominant
             else "mostly genuine outcome records")
    return OutcomeLearningStatus(
        real_records=len(real), synthetic_records=len(synthetic), is_synthetic_dominant=dominant,
        category_prior=multiplier,
        status_note=(f"Based on {len(real)} real and {len(synthetic)} synthetic outcome records "
                     f"(synthetic weighted {SYNTHETIC_WEIGHT}) - {label}. Weighted improvement rate "
                     f"{rate:.0%}, prior multiplier {multiplier}."))


def run(state: CaseState) -> dict[str, Any]:
    log, changed = track_outcomes(list(state.grievance_log), list(state.monitoring_record))
    cid, dist = catalog_id(state), district(state)
    if cid:
        existing = {r["session_id"] for r in stores.outcome_records(cid) if not r["is_synthetic"]}
        for entry in log:
            key = f"{state.session_meta.session_id}:{entry.ticket_id}"
            if entry.outcome_improved is None or key in existing:
                continue
            _, intervention, _ = route(entry.issue_type, None)
            stores.add_outcome_record(cid, dist, intervention, entry.health_score_at_logging,
                                      entry.health_score_after, is_synthetic=False, session_id=key)
    update: dict[str, Any] = {"outcome_learning": category_prior(cid, dist) if cid else OutcomeLearningStatus(
        is_synthetic_dominant=False, category_prior=1.0,
        status_note="No activity selected for this case; outcome learning not applied.")}
    if changed:
        update["grievance_log"] = log
    return update
