from module2_financial import documentation_agent as doc
from module2_financial.financial_engine import build_financial_plan
from orchestrator.state import (BusinessCandidate, CaseState, EntrepreneurProfile, FeasibilityRecord, LocationDetails,
                                SessionMeta)


def make_state(**profile_kw):
    loc = LocationDetails(district="Bhadohi", state="Uttar Pradesh", village="Gopiganj")
    profile = EntrepreneurProfile(location_query="Gopiganj", location=loc, **profile_kw)
    return CaseState(
        entrepreneur_profile=profile,
        session_meta=SessionMeta(session_id="d"),
        business_shortlist=[BusinessCandidate(category="Dairy Farming (Milch Animals)", catalog_id="dairy_farming",
                                              nic_code="0141")],
        feasibility_record=FeasibilityRecord(selected_category="Dairy Farming (Milch Animals)"),
        financial_plan=build_financial_plan(100_000, "Dairy Farming (Milch Animals)"),
    )


def _form(status, form_id):
    return next(f for f in status.forms if f.form_id == form_id)


def test_autofill_from_case_paths():
    state = make_state(full_name="Sita Devi")
    status = doc.run(state)["application_status"]
    loan = _form(status, "loan_application")
    plan = state.financial_plan
    assert loan.fields["applicant_name"] == "Sita Devi"
    assert loan.fields["project_cost"] == plan.computed_project_cost
    assert loan.fields["loan_amount_requested"] == plan.maximum_loan_eligibility
    assert loan.fields["scheme"] == plan.scheme_tier.display_name
    udyam = _form(status, "udyam_registration")
    assert udyam.fields["nic_code"] == "0141" and udyam.fields["district"] == "Bhadohi"
    assert "aadhaar_number" in udyam.missing_fields
    assert "applicant_name" not in udyam.missing_fields


def test_one_missing_field_at_a_time():
    state = make_state()
    status = doc.run(state)["application_status"]
    assert status.next_required_field == "full_name"
    assert "full name" in status.next_required_prompt
    assert doc.record_field(state, "full_name", "Sita Devi")[0]
    state.application_status = doc.run(state)["application_status"]
    assert state.application_status.next_required_field == "aadhaar_number"


def test_aadhaar_and_account_masked_and_validated():
    state = make_state(full_name="Sita Devi")
    ok, msg = doc.record_field(state, "aadhaar_number", "1234 5678 9012")
    assert not ok and "12 digits" in msg
    ok, _ = doc.record_field(state, "aadhaar_number", "2345 6789 0123")
    assert ok
    data = state.application_status.form_data
    assert data["aadhaar_number"] == "XXXX-XXXX-0123" and data["aadhaar_verified_format"] is True
    assert "234567890123" not in str(state.model_dump())
    assert doc.record_field(state, "bank_account_number", "12345678901234")[0]
    assert data["bank_account_number"] == "XXXXXXXXXX1234"
    assert not doc.record_field(state, "ifsc_code", "SBIN123")[0]
    assert doc.record_field(state, "ifsc_code", "sbin0001234")[0] and data["ifsc_code"] == "SBIN0001234"
    assert not doc.record_field(state, "pan_number", "ABC123")[0]
    assert doc.record_field(state, "pan_number", "abcde1234f")[0]
    assert not doc.record_field(state, "phone_number", "12345")[0]
    assert doc.record_field(state, "phone_number", "+91 98765 43210")[0]
    assert state.entrepreneur_profile.phone_number == "9876543210"
    assert not doc.record_field(state, "unknown_field", "x")[0]


def test_checklist_evidence_rules():
    state = make_state(documents_available=["Aadhaar card", "Bank passbook"], social_category="SC")
    doc.record_field(state, "documents_in_progress", "caste certificate")
    status = doc.run(state)["application_status"]
    c = status.checklist
    assert c["identity_proof"] == "complete"
    assert c["bank_passbook"] == "complete"
    assert c["caste_or_category_certificate"] == "pending"
    assert c["project_quotation"] == "missing"
    assert c["udyam_certificate"] == "missing"
    # a validated Aadhaar number format is not a document copy
    doc.record_field(state, "aadhaar_number", "234567890123")
    assert doc.run(make_state())["application_status"].checklist["identity_proof"] == "missing"


def test_udyam_number_implies_certificate_and_general_skips_caste():
    state = make_state(social_category="General")
    assert doc.record_field(state, "udyam_registration_number", "UDYAM-UP-12-0001234")[0]
    c = doc.run(state)["application_status"].checklist
    assert c["udyam_certificate"] == "complete"
    assert "caste_or_category_certificate" not in c


def test_scheme_required_documents_added():
    state = make_state()
    state.financial_plan.required_documents = ["Aadhaar card", "Two passport size photographs"]
    c = doc.run(state)["application_status"].checklist
    assert c["two_passport_size_photographs"] == "missing"
    assert "aadhaar_card" not in c


def test_run_degrades_without_upstream():
    state = CaseState(session_meta=SessionMeta(session_id="e"))
    status = doc.run(state)["application_status"]
    assert all(s == "missing" for s in status.checklist.values())
    assert status.next_required_field == "full_name"
