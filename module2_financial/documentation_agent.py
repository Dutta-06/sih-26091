"""Documentation & Form Auto-fill Agent (Module 2, Section 6.5).

Reads: state.entrepreneur_profile, state.financial_plan
Writes: state.application_status.form_data
Tech: Template auto-fill mapping profile and financial state into standard scheme application packages.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import ApplicationStatus, CaseState


def run(state: CaseState) -> dict[str, Any]:
    profile = state.entrepreneur_profile
    plan = state.financial_plan

    loc = profile.location if profile else None
    form_data = {
        "applicant_name": "Beneficiary Entrepreneur",
        "location": {
            "village": loc.village if loc else "Bhadohi",
            "block": loc.block if loc else "Bhadohi",
            "district": loc.district if loc else "Bhadohi",
            "state": loc.state if loc else "Uttar Pradesh",
        },
        "enterprise_category": profile.business_preference if profile else "Dairy Farming",
        "project_cost": plan.computed_project_cost if plan else 1_000_000.0,
        "beneficiary_margin_contribution": plan.available_margin_capital if plan else 100_000.0,
        "loan_amount_requested": plan.maximum_loan_eligibility if plan else 900_000.0,
        "scheme_applied": plan.scheme_tier.display_name if plan else "Term Loan Scheme",
        "moratorium_requested_months": plan.scheme_tier.moratorium_months if plan else 6,
        "tenure_years": plan.scheme_tier.tenure_years if plan else 7,
        "udyam_draft_status": "Ready for biometric / OTP signing",
    }

    app_status = state.application_status or ApplicationStatus()
    app_status.form_data = form_data
    app_status.checklist = {
        "identity_proof_aadhaar": "complete",
        "caste_category_certificate": "complete",
        "bank_passbook_copy": "complete",
        "project_quotation_estimate": "complete",
        "land_possession_noc": "pending",
    }
    app_status.disbursement_status = "documents_pending"

    return {"application_status": app_status}
