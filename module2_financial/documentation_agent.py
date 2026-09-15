"""Documentation Agent (Module 2, TDD 6.5 / TECHNICAL_SETUP.md 6.5).

Reads: state.entrepreneur_profile, state.financial_plan, state.feasibility_record, state.business_shortlist,
       state.application_status.form_data (fields collected conversationally)
Writes: state.application_status.forms, .form_data, .checklist, .next_required_field, .next_required_prompt
Tech: form templates (Udyam registration, KYC, loan application) as field maps keyed to CaseState paths;
      auto-fill from the case, one-missing-field-at-a-time prompting, deterministic regex validation.
      Prompts are English; translation is handled by the multilingual layer (orchestrator.language).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from orchestrator.state import ApplicationStatus, CaseState, FormPackage


# --- Validation ----------------------------------------------------------------

def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _v_text(value: str) -> tuple[bool, Any]:
    text = " ".join(value.split())
    return (True, text) if len(text) >= 2 else (False, "This field cannot be blank.")


def _v_phone(value: str) -> tuple[bool, Any]:
    d = _digits(value)
    d = d[2:] if len(d) == 12 and d.startswith("91") else d
    return (True, d) if re.fullmatch(r"[6-9]\d{9}", d) else (False, "Please give a valid 10-digit Indian mobile number.")


def _v_aadhaar(value: str) -> tuple[bool, Any]:
    d = _digits(value)
    return (True, d) if re.fullmatch(r"[2-9]\d{11}", d) else (False, "Aadhaar number must be 12 digits (not starting with 0 or 1).")


def _v_pan(value: str) -> tuple[bool, Any]:
    p = value.replace(" ", "").upper()
    return (True, p) if re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", p) else (False, "PAN must look like ABCDE1234F.")


def _v_ifsc(value: str) -> tuple[bool, Any]:
    code = value.replace(" ", "").upper()
    return (True, code) if re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", code) else (False, "IFSC must be 11 characters, like SBIN0001234.")


def _v_account(value: str) -> tuple[bool, Any]:
    d = _digits(value)
    return (True, d) if 9 <= len(d) <= 18 else (False, "Bank account number must have 9 to 18 digits.")


def _v_pincode(value: str) -> tuple[bool, Any]:
    d = _digits(value)
    return (True, d) if re.fullmatch(r"[1-9]\d{5}", d) else (False, "PIN code must be 6 digits.")


def _v_money(value: str) -> tuple[bool, Any]:
    try:
        amount = float(value.replace(",", "").replace("₹", "").replace("Rs", "").strip())
    except ValueError:
        return False, "Please give the amount as a number."
    return (True, amount) if amount >= 0 else (False, "Amount cannot be negative.")


def _v_udyam(value: str) -> tuple[bool, Any]:
    code = value.replace(" ", "").upper()
    return (True, code) if re.fullmatch(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}", code) else (False, "Udyam number must look like UDYAM-UP-00-0000000.")


def mask_aadhaar(digits: str) -> str:
    return f"XXXX-XXXX-{digits[-4:]}"


def mask_account(digits: str) -> str:
    return "X" * (len(digits) - 4) + digits[-4:]


@dataclass(frozen=True)
class Collectable:
    validator: Callable[[str], tuple[bool, Any]]
    prompt: str
    target: str  # "profile.<attr>", "location.<attr>" or "form"


COLLECTABLE: dict[str, Collectable] = {
    "full_name": Collectable(_v_text, "What is your full name, as written on your Aadhaar card?", "profile.full_name"),
    "phone_number": Collectable(_v_phone, "What is your 10-digit mobile number?", "profile.phone_number"),
    "aadhaar_number": Collectable(_v_aadhaar, "Please tell me your 12-digit Aadhaar number.", "form"),
    "pan_number": Collectable(_v_pan, "What is your PAN number?", "form"),
    "bank_account_number": Collectable(_v_account, "What is your bank account number?", "form"),
    "ifsc_code": Collectable(_v_ifsc, "What is the IFSC code of your bank branch?", "form"),
    "enterprise_name": Collectable(_v_text, "What name do you want to give your enterprise?", "form"),
    "residential_address": Collectable(_v_text, "What is your full residential address?", "form"),
    "pincode": Collectable(_v_pincode, "What is the 6-digit PIN code of your address?", "location.pincode"),
    "social_category": Collectable(_v_text, "Which social category do you belong to (General, SC, ST, OBC, minority)?", "profile.social_category"),
    "land_or_premises": Collectable(_v_text, "Where will the business run - your own land, rented premises, or home?", "profile.land_or_premises"),
    "udyam_registration_number": Collectable(_v_udyam, "If you already have Udyam registration, what is the Udyam number?", "form"),
}


# --- Templates -------------------------------------------------------------------

@dataclass(frozen=True)
class Field:
    key: str
    paths: tuple[str, ...]  # CaseState paths, or "form_data.<key>"; first non-empty wins
    required: bool = True
    collect: Optional[str] = None  # COLLECTABLE key to ask when empty


F = Field
TEMPLATES: dict[str, tuple[str, list[Field]]] = {
    "udyam_registration": ("Udyam Registration", [
        F("applicant_name", ("entrepreneur_profile.full_name",), collect="full_name"),
        F("aadhaar_number", ("form_data.aadhaar_number",), collect="aadhaar_number"),
        F("mobile_number", ("entrepreneur_profile.phone_number",), collect="phone_number"),
        F("social_category", ("entrepreneur_profile.social_category",), collect="social_category"),
        F("is_woman_owned", ("entrepreneur_profile.is_woman_owned",)),
        F("enterprise_name", ("form_data.enterprise_name",), collect="enterprise_name"),
        F("major_activity", ("feasibility_record.selected_category", "business_shortlist[0].category")),
        F("nic_code", ("business_shortlist[0].nic_code",)),
        F("district", ("entrepreneur_profile.location.district",)),
        F("state", ("entrepreneur_profile.location.state",)),
        F("pincode", ("entrepreneur_profile.location.pincode",), collect="pincode"),
        F("investment_in_plant_and_machinery", ("financial_plan.capital_expenditure_allocation",)),
        F("pan_number", ("form_data.pan_number",), required=False, collect="pan_number"),
        F("bank_account_number", ("form_data.bank_account_number",), collect="bank_account_number"),
        F("ifsc_code", ("form_data.ifsc_code",), collect="ifsc_code"),
    ]),
    "kyc": ("KYC (Know Your Customer)", [
        F("applicant_name", ("entrepreneur_profile.full_name",), collect="full_name"),
        F("aadhaar_number", ("form_data.aadhaar_number",), collect="aadhaar_number"),
        F("pan_number", ("form_data.pan_number",), required=False, collect="pan_number"),
        F("mobile_number", ("entrepreneur_profile.phone_number",), collect="phone_number"),
        F("residential_address", ("form_data.residential_address",), collect="residential_address"),
        F("village", ("entrepreneur_profile.location.village",), required=False),
        F("district", ("entrepreneur_profile.location.district",)),
        F("state", ("entrepreneur_profile.location.state",)),
        F("pincode", ("entrepreneur_profile.location.pincode",), collect="pincode"),
    ]),
    "loan_application": ("Loan Application", [
        F("applicant_name", ("entrepreneur_profile.full_name",), collect="full_name"),
        F("business_activity", ("feasibility_record.selected_category", "business_shortlist[0].category")),
        F("scheme", ("financial_plan.scheme_tier.display_name",)),
        F("project_cost", ("financial_plan.computed_project_cost",)),
        F("margin_contribution", ("financial_plan.available_margin_capital",)),
        F("loan_amount_requested", ("financial_plan.maximum_loan_eligibility",)),
        F("working_capital", ("financial_plan.working_capital_requirement",)),
        F("tenure_years", ("financial_plan.scheme_tier.tenure_years",)),
        F("moratorium_months", ("financial_plan.scheme_tier.moratorium_months",)),
        F("business_premises", ("entrepreneur_profile.land_or_premises",), collect="land_or_premises"),
        F("udyam_registration_number", ("form_data.udyam_registration_number",), required=False,
          collect="udyam_registration_number"),
        F("bank_account_number", ("form_data.bank_account_number",), collect="bank_account_number"),
        F("ifsc_code", ("form_data.ifsc_code",), collect="ifsc_code"),
    ]),
}

BASE_DOCUMENTS: dict[str, tuple[str, ...]] = {
    "identity_proof": ("aadhaar", "identity", "voter id", "voter card"),
    "address_proof": ("address", "ration card", "electricity bill", "domicile"),
    "caste_or_category_certificate": ("caste", "category certificate", "sc certificate", "st certificate", "obc"),
    "bank_passbook": ("passbook", "bank statement", "cancelled cheque", "bank account"),
    "project_quotation": ("quotation", "estimate", "proforma", "project report"),
    "land_or_premises_proof": ("land", "khatauni", "lease", "rent agreement", "premises", "noc"),
    "udyam_certificate": ("udyam",),
}
NO_CATEGORY_CERT = {"general", "gen", "unreserved", "none"}


def _read_path(state: CaseState, path: str) -> Any:
    if path.startswith("form_data."):
        return (state.application_status.form_data if state.application_status else {}).get(path[10:])
    obj: Any = state
    for part in path.split("."):
        m = re.fullmatch(r"(\w+)(?:\[(\d+)\])?", part)
        obj = getattr(obj, m.group(1), None) if obj is not None else None
        if m.group(2) is not None:
            obj = obj[int(m.group(2))] if isinstance(obj, list) and len(obj) > int(m.group(2)) else None
    return obj


def _first_value(state: CaseState, paths: tuple[str, ...]) -> Any:
    """First non-empty value; booleans count as present, zero amounts (unset plan figures) do not."""
    for path in paths:
        value = _read_path(state, path)
        if isinstance(value, bool) or (value not in (None, "", []) and value != 0):
            return value
    return None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def build_checklist(state: CaseState, form_data: dict[str, Any]) -> dict[str, str]:
    profile = state.entrepreneur_profile
    available = [d.lower() for d in (profile.documents_available if profile else [])]
    in_progress = [d.lower() for d in form_data.get("documents_in_progress", [])]
    docs = dict(BASE_DOCUMENTS)
    if profile and (profile.social_category or "").strip().lower() in NO_CATEGORY_CERT:
        docs.pop("caste_or_category_certificate")
    plan = state.financial_plan
    for name in (plan.required_documents if plan else []):
        lowered = name.lower()
        if not any(a in lowered for aliases in docs.values() for a in aliases):
            docs[_slug(name)] = (lowered,)
    checklist: dict[str, str] = {}
    for key, aliases in docs.items():
        terms = aliases + (key.replace("_", " "),)
        matches = lambda entries: any(t in e or e == key for e in entries for t in terms)
        if matches(available) or (key == "udyam_certificate" and form_data.get("udyam_registration_number")):
            checklist[key] = "complete"
        elif matches(in_progress):
            checklist[key] = "pending"
        else:
            checklist[key] = "missing"
    return checklist


def run(state: CaseState) -> dict[str, Any]:
    status = (state.application_status or ApplicationStatus()).model_copy(deep=True)
    working = state.model_copy(update={"application_status": status})
    forms, next_field = [], None
    for form_id, (title, fields) in TEMPLATES.items():
        package = FormPackage(form_id=form_id, title=title)
        for f in fields:
            value = _first_value(working, f.paths)
            package.fields[f.key] = value
            if value is None and f.required:
                package.missing_fields.append(f.key)
                if next_field is None and f.collect:
                    next_field = f.collect
        forms.append(package)
    status.forms = forms
    status.checklist = build_checklist(state, status.form_data)
    status.next_required_field = next_field
    status.next_required_prompt = COLLECTABLE[next_field].prompt if next_field else None
    if next_field is None:  # form fields done: ask about the first document not yet discussed, one at a time
        declined = set(status.form_data.get("documents_not_available", []))
        doc = next((k for k, v in status.checklist.items() if v == "missing" and k not in declined), None)
        if doc:
            status.next_required_field = f"{DOCUMENT_FIELD_PREFIX}{doc}"
            status.next_required_prompt = (f"Do you have your {doc.replace('_', ' ')}? Reply 'yes' if you have it, "
                                           "'applied' if you are getting it, or 'no'.")
    return {"application_status": status}


DOCUMENT_FIELD_PREFIX = "document:"
_YES = re.compile(r"^\s*(yes|y|have|haan|ha|हाँ|हां|available|ready)\b", re.I)
_APPLIED = re.compile(r"(applied|in progress|getting|pending|बनवा|apply)", re.I)
_NO = re.compile(r"^\s*(no|n|nahi|nahin|नहीं|not)\b", re.I)


def _record_document_answer(state: CaseState, doc: str, value: str) -> tuple[bool, str]:
    label = doc.replace("_", " ")
    form_data = state.application_status.form_data
    if _APPLIED.search(value):
        return record_field(state, "documents_in_progress", label)
    if _YES.match(value):
        return record_field(state, "documents_available", label)
    if _NO.match(value):
        declined = form_data.setdefault("documents_not_available", [])
        if doc not in declined:
            declined.append(doc)
        return True, f"Noted that you do not have the {label} yet; it stays on the checklist as missing."
    return False, f"Please reply 'yes', 'applied' or 'no' for the {label}."


def record_field(state: CaseState, field: str, value: str) -> tuple[bool, str]:
    """Validate one conversational answer and store it on the case (mutates ``state``)."""
    if state.application_status is None:
        state.application_status = ApplicationStatus()
    form_data = state.application_status.form_data
    value = "" if value is None else str(value).strip()
    if field.startswith(DOCUMENT_FIELD_PREFIX):
        return _record_document_answer(state, field[len(DOCUMENT_FIELD_PREFIX):], value)
    if field in {"documents_in_progress", "documents_available"}:
        items = [v.strip() for v in re.split(r"[,;]", value) if v.strip()]
        if not items:
            return False, "Please name the document."
        if field == "documents_available":
            if state.entrepreneur_profile is None:
                return False, "Profile not started yet; cannot record documents."
            target = state.entrepreneur_profile.documents_available
        else:
            target = form_data.setdefault("documents_in_progress", [])
        target.extend(i for i in items if i not in target)
        return True, f"Noted: {', '.join(items)}."
    spec = COLLECTABLE.get(field)
    if spec is None:
        return False, f"'{field}' is not a field I can record."
    ok, result = spec.validator(value)
    if not ok:
        return False, result
    if field == "aadhaar_number":
        form_data.update(aadhaar_number=mask_aadhaar(result), aadhaar_verified_format=True)
        return True, "Aadhaar number format verified; only the last 4 digits are stored."
    if field == "bank_account_number":
        form_data["bank_account_number"] = mask_account(result)
        return True, "Bank account number recorded (masked)."
    kind, _, attr = spec.target.partition(".")
    if kind == "form":
        form_data[field] = result
    else:
        profile = state.entrepreneur_profile
        if profile is None:
            return False, "Profile not started yet; please complete profiling first."
        setattr(profile.location if kind == "location" else profile, attr, result)
    return True, f"Recorded {field.replace('_', ' ')}."
