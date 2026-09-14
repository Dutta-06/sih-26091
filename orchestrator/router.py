"""Conversational intent routing and slot filling (TDD 4.1-4.3, TECHNICAL_SETUP 4).

Reads: the user message, the current CaseState
Writes: entrepreneur_profile slots, session_meta (requested_stage, pending_slot, last_intent, language, grievance text)
Tech: keyword/regex intent classification with English, Hindi (Devanagari) and Hinglish cues so Hindi works
offline; other Indic languages go through orchestrator.language (IndicTrans2) when enabled.

``route_conversational_turn`` returns ``(state, reply, run_graph)``; the caller invokes the graph when
``run_graph`` is True, entering at ``session_meta.requested_stage``.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal, Optional

from common.reference import load_catalog
from module1_feasibility.profiling_agent import extract_profile_from_slots
from orchestrator import language
from orchestrator.state import CaseState, SessionMeta

Intent = Literal["new_case", "provide_info", "continue", "jump_application", "jump_monitoring",
                 "raise_grievance", "inquire_scheme", "consent_monitoring"]

SLOT_ORDER = ["location", "capital", "activity"]
PROMPTS = {
    "location": "Which village, block or district will the business be in?",
    "capital": "How much of your own money (margin capital) can you invest? For example: Rs 50,000 or 1 lakh.",
    "activity": "What business would you like to start (for example tailoring, dairy, kirana store)? You can also tell me why.",
}

_CUES: dict[str, list[str]] = {
    "raise_grievance": ["complaint", "grievance", "problem with", "not working", "broken", "breakdown", "delay in",
                        "delayed", "unable to repay", "can't repay", "cannot repay", "prices crashed", "price crash",
                        "शिकायत", "समस्या", "खराब", "shikayat", "samasya", "kharab"],
    "consent_monitoring": ["i consent", "i agree to monitoring", "allow monitoring", "consent to monitoring",
                           "you can read my sms", "सहमति", "sahmati"],
    "jump_monitoring": ["monitoring", "health score", "how is my business doing", "my transactions", "business health"],
    "jump_application": ["application status", "my application", "apply now", "loan application", "documents needed",
                         "fill the form", "आवेदन", "aavedan"],
    "inquire_scheme": ["scheme", "subsidy", "guideline", "interest rate", "eligibility", "moratorium", "योजना", "yojana"],
    "new_case": ["new case", "start over", "restart", "start again", "नया केस", "फिर से शुरू"],
}

def match_activity(text: Optional[str]) -> Optional[dict[str, Any]]:
    """Catalog match on whole words (so 'been' is not beekeeping and 'hotel' is not an oil mill)."""
    if not text:
        return None
    lowered, best = text.lower(), (0, None)
    for activity in load_catalog().values():
        for kw in [*activity["keywords"], activity["category"].lower()]:
            kw = kw.lower()
            if len(kw) > best[0] and re.search(r"(?<!\w)" + re.escape(kw) + r"(?:s|es)?(?!\w)", lowered):
                best = (len(kw), activity)
    return best[1]


_DEV_DIGITS =str.maketrans("०१२३४५६७८९", "0123456789")
_NUM = r"(\d+(?:[.,]\d+)*)"


def _num(raw: str) -> float:
    return float(raw.replace(",", ""))


def extract_capital(text: str, expecting: bool = False) -> Optional[float]:
    t = text.translate(_DEV_DIGITS).lower()
    for pattern, mult in [
        (_NUM + r"\s*(?:crore|cr\b|करोड़|करोड)", 10_000_000),
        (_NUM + r"\s*(?:lakhs?|lacs?|lac\b|lakh|लाख)", 100_000),
        (_NUM + r"\s*(?:thousand|hazaa?r|hajar|हज़ार|हजार|k\b)", 1_000),
    ]:
        m = re.search(pattern, t)
        if m:
            return _num(m.group(1)) * mult
    m = re.search(r"(?:₹|rs\.?|inr|rupees?)\s*" + _NUM, t) or re.search(_NUM + r"\s*(?:rupees?|rs\b|₹|रुपये|रुपए|rupaye)", t)
    if m:
        return _num(m.group(1))
    for raw in re.findall(r"\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?", t):
        value = _num(raw)
        if value >= 5_000 or (expecting and value > 0):
            return value
    return None


_STOP = {"and", "with", "for", "to", "because", "i", "have", "want", "rupees", "rs", "my", "the", "a", "start",
         "business", "since", "as", "but", "so", "who", "where", "lakh", "capital", "invest", "least", "all", "home",
         "present", "once", "time", "this", "that", "our", "it", "which", "what", "first", "last", "one", "am", "is"}


def _clean_location(candidate: str) -> Optional[str]:
    words, out = re.split(r"\s+", candidate.strip(" ,.")), []
    for w in words:
        if w.lower().strip(",") in _STOP or re.search(r"\d", w):
            break
        out.append(w)
    loc = " ".join(out).strip(" ,.")
    if not loc or match_activity(loc) or loc.lower() in {"india", "village", "town", "city"}:
        return None
    return loc


def extract_location(text: str) -> Optional[str]:
    for m in re.finditer(r"\b(?:in|near|at|from)\s+([A-Za-z][A-Za-z ,.-]{1,60})", text, re.IGNORECASE):
        loc = _clean_location(m.group(1))
        if loc:
            return loc
    m = re.search(r"([A-Za-z][A-Za-z-]+(?:,?\s+[A-Za-z][A-Za-z-]+)?)\s+mein\b", text, re.IGNORECASE)
    if m and (loc := _clean_location(m.group(1).split()[-1])):
        return loc
    for m in re.finditer(r"([ऀ-ॿ]+)\s+में", text):
        if not match_activity(m.group(1)) and m.group(1) not in {"गांव", "गाँव", "शहर", "जिले", "व्यवसाय", "धंधे"}:
            return m.group(1)
    return None


def extract_reason(text: str) -> Optional[str]:
    m = re.search(r"(?:\bbecause\b|\bsince\b|\bkyunki\b|\bkyonki\b|क्योंकि)\s*(.+?)(?:[.!?।]|$)", text, re.IGNORECASE)
    return m.group(1).strip(" ,") if m and m.group(1).strip() else None


def extract_slots_from_text(message: str, pending_slot: Optional[str] = None) -> dict[str, Any]:
    slots: dict[str, Any] = {}
    capital = extract_capital(message, expecting=pending_slot == "capital")
    if capital is not None:
        slots["available_capital"] = capital
    activity = match_activity(message)
    if activity:
        slots["business_preference"] = activity["category"]
    elif pending_slot == "activity" and message.strip() and capital is None:
        slots["business_preference"] = message.strip()
    location = extract_location(message)
    if location is None and pending_slot == "location" and capital is None and activity is None:
        location = _clean_location(message) or None
    if location:
        slots["location_query"] = location
    reason = extract_reason(message)
    if reason:
        slots["preference_reason"] = reason
    return slots


def parse_intent(message: str, state: Optional[CaseState] = None) -> Intent:
    text = message.lower()
    hits = {intent for intent, cues in _CUES.items() if any(c in text for c in cues)}
    for intent in ("raise_grievance", "consent_monitoring", "new_case"):
        if intent in hits:
            return intent  # type: ignore[return-value]
    pending = state.session_meta.pending_slot if state else None
    slots = extract_slots_from_text(message, pending)
    profile_incomplete = state is None or missing_slot(state) is not None
    if slots and (profile_incomplete or pending):
        return "provide_info"
    for intent in ("jump_monitoring", "jump_application", "inquire_scheme"):
        if intent in hits:
            return intent  # type: ignore[return-value]
    if state and state.application_status and state.application_status.next_required_field:
        return "continue"  # the message answers the pending application field
    return "provide_info" if slots else "continue"


def missing_slot(state: CaseState) -> Optional[str]:
    p = state.entrepreneur_profile
    if p is None or not p.location_query:
        return "location"
    if p.available_capital <= 0:
        return "capital"
    if not p.business_preference:
        return "activity"
    return None


_DERIVED_FIELDS = ["business_shortlist", "market_reach_intel", "opportunity_intel", "risk_intel", "competitor_intel",
                   "pricing_intel", "supply_chain_intel", "market_intelligence", "feasibility_record",
                   "financial_plan", "application_status"]


def _reset_assessment(state: CaseState) -> None:
    for name in _DERIVED_FIELDS:
        setattr(state, name, [] if name == "business_shortlist" else None)


def _apply_slots(state: CaseState, slots: dict[str, Any]) -> bool:
    """Merge slots into the profile; returns True if an assessment-relevant slot changed."""
    p = state.entrepreneur_profile
    current = {
        "location_query": p.location_query if p else "",
        "available_capital": p.available_capital if p else 0.0,
        "business_preference": p.business_preference if p else None,
        "preference_reason": p.preference_reason if p else None,
    }
    merged = {**current, **slots}
    changed = any(merged[k] != current[k] for k in ("location_query", "available_capital", "business_preference"))
    if p is None or changed:
        new = extract_profile_from_slots(merged["location_query"], merged["available_capital"],
                                         merged["business_preference"], preference_reason=merged["preference_reason"])
        if p is not None:  # keep everything else the user told us before
            new = p.model_copy(update={**new.model_dump(include={"location_query", "available_capital",
                                                                  "business_preference", "preference_reason"}),
                                       "location": new.location if new.location_query != p.location_query else p.location})
        state.entrepreneur_profile = new
    elif merged["preference_reason"] != current["preference_reason"]:
        state.entrepreneur_profile = p.model_copy(update={"preference_reason": merged["preference_reason"]})
    return changed


def _application_prompt(state: CaseState) -> Optional[str]:
    app = state.application_status
    if app and app.next_required_field:
        return app.next_required_prompt or f"Please provide: {app.next_required_field.replace('_', ' ')}."
    return None


def _respond(state: CaseState, reply: str, run_graph: bool) -> tuple[CaseState, str, bool]:
    lang = state.session_meta.language_code
    return state, language.from_english(reply, lang) if lang != "en" else reply, run_graph


def route_conversational_turn(message: str, current_state: Optional[CaseState] = None) -> tuple[CaseState, str, bool]:
    lang = language.detect_language(message)
    english, status = language.to_english(message, lang)
    intent = parse_intent(message, current_state)
    if intent == "continue" and english != message:
        intent = parse_intent(english, current_state)

    if current_state is None or intent == "new_case":
        sid = current_state.session_meta.session_id if current_state else f"session_{uuid.uuid4().hex[:8]}"
        state = CaseState(session_meta=SessionMeta(session_id=sid))
    else:
        state = current_state.model_copy(deep=True)
    meta = state.session_meta
    meta.user_turns += 1
    meta.last_intent = intent
    meta.language_code, meta.translation_status = lang, status
    meta.requested_stage = None

    if intent == "raise_grievance":
        meta.pending_grievance_text = english
        meta.requested_stage = "grievance"
        return _respond(state, "I have logged your issue and will route it for support.", True)

    if intent == "consent_monitoring":
        meta.consent_sms_monitoring = True
        return _respond(state, "Thank you. Monitoring consent recorded. Only structured amounts and dates from your "
                               "transaction notifications will be kept; the message text is discarded.", False)

    if intent == "jump_monitoring":
        if not meta.consent_sms_monitoring:
            return _respond(state, "Monitoring needs your consent to read transaction notifications. Reply 'I consent' to allow it.", False)
        if not meta.pending_transactions:
            return _respond(state, "Monitoring is on. Share your recent transaction notifications to update the health score.", False)
        meta.requested_stage = "monitoring"
        return _respond(state, "Updating your business health check.", True)

    if intent == "inquire_scheme":
        meta.requested_stage = "scheme_inquiry"
        return _respond(state, "Here is how the scheme applies to your case.", True)

    if intent == "jump_application":
        plan = state.financial_plan
        if not plan or plan.eligibility_status != "eligible":
            reason = plan.ineligibility_reason if plan else "the feasibility and financial assessment is not complete yet"
            return _respond(state, f"The application cannot start yet: {reason}.", False)
        meta.requested_stage = "application"
        return _respond(state, "Resuming your loan application.", True)

    pending_field = _application_prompt(state)
    if intent == "continue" and pending_field and state.application_status:
        field = state.application_status.next_required_field
        try:
            from module2_financial.documentation_agent import record_field

            accepted, msg = record_field(state, field, english.strip())
        except Exception as exc:
            return _respond(state, f"Could not record {field}: {exc}", False)
        if not accepted:
            return _respond(state, msg, False)
        meta.requested_stage = "application"
        return _respond(state, msg, True)

    slots = extract_slots_from_text(message, meta.pending_slot)
    if english != message:
        slots = {**extract_slots_from_text(english, meta.pending_slot), **slots}
    changed = _apply_slots(state, slots) if slots else False
    if changed:
        _reset_assessment(state)

    slot = missing_slot(state)
    if slot:
        meta.pending_slot = slot
        ack = ""
        if slots.get("location_query"):
            ack = f"Location noted: {slots['location_query']}. "
        elif slots.get("available_capital"):
            ack = f"Capital noted: Rs {slots['available_capital']:,.0f}. "
        return _respond(state, ack + PROMPTS[slot], False)

    meta.pending_slot = None
    p = state.entrepreneur_profile
    if changed or state.feasibility_record is None:
        meta.requested_stage = "profiling"
        meta.current_stage = "feasibility_assessment"
        reason = f" (reason: {p.preference_reason})" if p.preference_reason else ""
        return _respond(state, f"Assessing {p.business_preference}{reason} in {p.location_query} with "
                               f"Rs {p.available_capital:,.0f} of your own capital.", True)
    if pending_field:
        return _respond(state, pending_field, False)
    return _respond(state, "Your case is saved. You can ask about the scheme, your application, monitoring, "
                           "or report a problem.", False)
