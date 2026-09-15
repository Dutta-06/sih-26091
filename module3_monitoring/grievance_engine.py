"""Grievance Engine (Module 3, TDD 7.5).

Reads: state.session_meta.pending_grievance_text, case context (activity, district, stage, latest health snapshot,
       disbursement status), state.monitoring_record (for outcome tracking)
Writes: state.grievance_log, state.session_meta (pending_grievance_text cleared)
Tech: keyword classifier (English + Hindi/Hinglish cues), ticket with static routing table to mentor ROLES
      (never named people), outcome tracking against later health snapshots
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from module3_monitoring._case import activity, catalog_id, district, parse_ts
from orchestrator.state import CaseState, GrievanceEntry, HealthSnapshot

_KEYWORDS: dict[str, list[str]] = {
    "loan_repayment_stress": ["emi", "loan", "installment", "instalment", "repay", "repayment", "kist", "kisht",
                              "karz", "karza", "qarz", "udhaar", "bank notice", "किस्त", "कर्ज", "लोन"],
    "machinery_breakdown": ["machine", "machinery", "broken", "breakdown", "repair", "motor", "not working",
                            "kharab", "kharaab", "toot", "tuta", "band pad", "खराब", "मशीन", "टूट"],
    "pricing_collapse": ["price", "prices", "rate", "rates", "bhav", "daam", "dam", "keemat", "sasta",
                         "no buyers", "not selling", "nahi bik", "mandi rate", "भाव", "दाम", "कीमत"],
    "supply_delay": ["delay", "delayed", "late", "not delivered", "shortage", "supply", "supplier", "stock",
                     "raw material", "feed", "chara", "maal", "der", "deri", "nahi aaya", "nahi mila",
                     "देरी", "चारा", "माल"],
}

# issue_type -> (mentor role, intervention type, suggested intervention). Sector-specific roles override defaults.
ROUTING: dict[str, dict[str, Any]] = {
    "supply_delay": {"role": "DIC / MSME facilitation desk", "intervention": "supply_chain_change",
                     "action": "Identify an alternate source for the delayed input and consider pooled purchase.",
                     "sector_roles": {"animal_husbandry": "District livestock extension officer",
                                      "fisheries": "District fisheries extension officer"}},
    "pricing_collapse": {"role": "DIC / MSME facilitation desk", "intervention": "pricing_adjustment",
                         "action": "Review selling price and buyer mix against current local market rates.",
                         "sector_roles": {"agri_allied":"Block agriculture extension officer (ATMA)"}},
    "machinery_breakdown": {"role": "DIC / MSME facilitation desk", "intervention": "mentor_outreach",
                            "action": "Arrange inspection and repair quote; check warranty or asset insurance claim.",
                            "sector_roles": {"animal_husbandry": "District livestock extension officer"}},
    "loan_repayment_stress": {"role": "SCA loan officer", "intervention": "repayment_counselling",
                              "action": "Discuss repayment date or restructuring with the lender before default."},
    "other": {"role": "Block-level enterprise mentor (SCA field staff)", "intervention": "mentor_outreach",
              "action": "Mentor to call back and clarify the issue."},
}


def _count(text: str, kw: str) -> int:
    if not kw.isascii():
        return text.count(kw)
    return len(re.findall(rf"\b{re.escape(kw)}\b", text))


def classify_issue(text: str) -> str:
    lowered = (text or "").lower()
    scores = {issue: sum(_count(lowered, kw) for kw in kws) for issue, kws in _KEYWORDS.items()}
    best = max(scores, key=lambda k: scores[k])  # dict order breaks ties
    return best if scores[best] > 0 else "other"


def route(issue_type: str, sector: Optional[str]) -> tuple[str, str, str]:
    entry = ROUTING.get(issue_type, ROUTING["other"])
    role = entry.get("sector_roles", {}).get(sector or "", entry["role"])
    return role, entry["intervention"], entry["action"]


def track_outcomes(log: list[GrievanceEntry], records: list[HealthSnapshot]) -> tuple[list[GrievanceEntry], bool]:
    """Fill health_score_after / outcome_improved from the newest scored snapshot taken after each ticket."""
    changed, out = False, []
    for entry in log:
        logged = parse_ts(entry.logged_at)
        later = [s for s in records if s.health_score is not None and logged
                 and (ts := parse_ts(s.timestamp)) and ts > logged]
        if entry.health_score_at_logging is not None and later and later[-1].health_score != entry.health_score_after:
            after = later[-1].health_score
            entry = entry.model_copy(update={"health_score_after": after,
                                             "outcome_improved": after > entry.health_score_at_logging})
            changed = True
        out.append(entry)
    return out, changed


def run(state: CaseState) -> dict[str, Any]:
    log, changed = track_outcomes(list(state.grievance_log), list(state.monitoring_record))
    text = (state.session_meta.pending_grievance_text or "").strip()
    update: dict[str, Any] = {}
    if text:
        act = activity(state) or {}
        issue = classify_issue(text)
        role, _, action = route(issue, act.get("sector"))
        latest = next((s for s in reversed(state.monitoring_record) if s.health_score is not None), None)
        app = state.application_status
        log.append(GrievanceEntry(
            ticket_id=f"TKT-{uuid.uuid4().hex[:10].upper()}",
            issue_type=issue,
            description=text,
            status="mentor_assigned",
            assigned_mentor=role,
            intervention_suggested=(latest.suggested_intervention if latest and latest.suggested_intervention
                                    and issue == "other" else action),
            case_context={
                "catalog_id": catalog_id(state) or None,
                "category": act.get("category"),
                "district": district(state),
                "stage": state.session_meta.current_stage,
                "latest_health_score": latest.health_score if latest else None,
                "latest_health_band": latest.health_band if latest else None,
                "disbursement_status": app.disbursement_status if app else None,
            },
            health_score_at_logging=latest.health_score if latest else None,
        ))
        update["session_meta"] = state.session_meta.model_copy(update={"pending_grievance_text": None})
        changed = True
    if changed:
        update["grievance_log"] = log
    return update
