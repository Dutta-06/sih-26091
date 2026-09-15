"""Module 3 tests: monitoring, health scoring, grievances, outcome learning, procurement, launch roadmap."""

import datetime as dt
import json
import uuid

import pytest

from config.settings import settings
from data_connectors.sms_parser import parse_notifications
from module3_monitoring import (grievance_engine, health_score_agent, launch_copilot, ongoing_monitoring_agent,
                                outcome_learning_loop, procurement_coordinator)
from orchestrator import stores
from orchestrator.state import (ApplicationStatus, BusinessCandidate, CaseState, CompetitorIntelligence,
                                EntrepreneurProfile, FinancialPlan, GrievanceEntry, HealthSnapshot, LocationDetails,
                                OperatingProjection, QuarterlyRepaymentInstallment, SchemeTier, SessionMeta)
from synthetic_data import seed_outcomes

MESSAGES = [
    "Rs.6,000.00 credited to A/c XX0001 on 03-08-26 by UPI ref 000011112222. Avl Bal Rs.18,300.50",
    "Rs.5,500 credited to A/c XX0001 on 10-08-26 by UPI ref 000011113333.",
    "Rs.6,200 credited to A/c XX0001 on 17-08-26 by UPI from DAIRY COOP.",
    "Rs.6,100 credited to A/c XX0001 on 24-08-26 by UPI ref 000011114444.",
    "INR 9,000 debited from A/c no. XX0001 on 05/08/2026 NEFT to FEED SUPPLIER.",
    "Your a/c XX0001 is debited for Rs 3,000 on 20-Aug-2026 towards Loan EMI. NACH ref 99990000",
]


def make_state(catalog_id="dairy_farming", district="Varanasi", consent=True, moratorium_quarter=False):
    schedule = [QuarterlyRepaymentInstallment(quarter_number=q, is_moratorium=moratorium_quarter and q == 1,
                                              opening_balance=180000, interest_payment=3600, principal_payment=5400,
                                              total_installment=9000, closing_balance=174600) for q in (1, 2, 3)]
    return CaseState(
        entrepreneur_profile=EntrepreneurProfile(location_query=district or "",
                                                 location=LocationDetails(district=district, state="Uttar Pradesh")),
        business_shortlist=[BusinessCandidate(category="Dairy", catalog_id=catalog_id)],
        financial_plan=FinancialPlan(
            computed_project_cost=200000, working_capital_requirement=40000, capital_expenditure_allocation=160000,
            scheme_tier=SchemeTier(name="term_loan", display_name="Term Loan", max_project_cost=5e6,
                                   max_loan_amount=4.5e6, interest_rate=0.08, tenure_years=7, moratorium_months=6),
            repayment_schedule=schedule, regular_quarterly_installment=9000,
            operating_projection=OperatingProjection(annual_revenue=300000, operating_margin=0.3,
                                                     annual_operating_surplus=90000, quarterly_operating_surplus=22500)),
        application_status=ApplicationStatus(disbursement_status="disbursed", disbursement_date="2026-07-25"),
        session_meta=SessionMeta(session_id=f"s-{uuid.uuid4().hex[:8]}", consent_sms_monitoring=consent,
                                 current_stage="monitoring"),
    )


def apply(state, update):
    return state.model_copy(update=update)


# --- 7.3 monitoring -----------------------------------------------------------

def test_consent_gate(monkeypatch):
    txns = parse_notifications(MESSAGES)
    state = make_state(consent=False)
    state.session_meta.pending_transactions = txns
    assert ongoing_monitoring_agent.run(state) == {}
    state = make_state(consent=True)
    state.session_meta.pending_transactions = txns
    monkeypatch.setattr(settings, "sms_monitoring_enabled", False)
    assert ongoing_monitoring_agent.run(state) == {}


def test_snapshot_from_transactions_and_raw_text_not_stored():
    state = make_state()
    state.session_meta.pending_transactions = parse_notifications(MESSAGES)
    state = apply(state, ongoing_monitoring_agent.run(state))
    snap = state.monitoring_record[-1]
    assert snap.reported_revenue == 23800 and snap.reported_expenses == 9000
    assert snap.loan_installment_status == "paid" and snap.is_consent_verified
    assert snap.projected_baseline_revenue > 0 and snap.transactions_parsed == 6
    assert 0 <= snap.approximate_creditworthiness_index <= 100
    assert "not a formal credit score" in snap.creditworthiness_label
    assert state.session_meta.pending_transactions == []
    dumped = state.model_dump_json()
    for fragment in ("FEED SUPPLIER", "DAIRY COOP", "XX0001", "NACH ref", "Avl Bal"):
        assert fragment not in dumped


def test_moratorium_quarter_not_due_and_no_transactions_no_snapshot():
    state = make_state(moratorium_quarter=True)
    assert ongoing_monitoring_agent.run(state) == {}
    state.session_meta.pending_transactions = parse_notifications(MESSAGES[:4])
    snap = ongoing_monitoring_agent.run(state)["monitoring_record"][-1]
    assert snap.loan_installment_status == "not_due"


# --- 7.4 health score -----------------------------------------------------------

def scored(state, **snap):
    snap.setdefault("period_label", "2026-08-01 to 2026-08-28 (28 days)")
    state.monitoring_record = [HealthSnapshot(**snap)]
    return health_score_agent.run(state)["monitoring_record"][-1]


HEALTHY = dict(reported_revenue=24000, projected_baseline_revenue=23000, reported_expenses=15000,
               operating_surplus=9000, installment_due=2800, loan_installment_status="paid", transactions_parsed=20)


def test_health_bands_from_config(tmp_path, monkeypatch):
    state = make_state()
    snap = scored(state, **HEALTHY)
    assert snap.health_band == "healthy" and not snap.early_warning_flag and snap.intervention_type is None
    cfg = health_score_agent.thresholds() | {"bands": {"healthy_min_score": 101, "watch_min_score": 101}}
    path = tmp_path / "thresholds.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setattr(settings, "health_score_thresholds_path", path)
    snap = scored(state, **HEALTHY)
    assert snap.health_band == "at_risk" and snap.early_warning_flag and snap.intervention_type


def test_intervention_rules():
    state = make_state()
    pricing = scored(state, **HEALTHY | dict(reported_revenue=13000, reported_expenses=8000, operating_surplus=5000))
    assert pricing.early_warning_flag and pricing.intervention_type == "pricing_adjustment"
    assert "litre" in pricing.suggested_intervention
    supply = scored(state, **HEALTHY | dict(reported_revenue=15000, reported_expenses=13500, operating_surplus=1500,
                                            installment_due=1000))
    assert supply.intervention_type == "supply_chain_change" and "fodder" in supply.suggested_intervention.lower()
    overdue = scored(state, **HEALTHY | dict(loan_installment_status="overdue", reported_revenue=14000,
                                             reported_expenses=12500, operating_surplus=1500))
    assert overdue.intervention_type == "repayment_counselling"
    unclear = scored(state, **HEALTHY | dict(reported_revenue=13000, reported_expenses=8000, operating_surplus=5000,
                                             transactions_parsed=2))
    assert unclear.intervention_type == "mentor_outreach"


def test_no_plan_data_means_no_score():
    state = make_state()
    snap = scored(state, reported_revenue=1000, transactions_parsed=3)
    assert snap.health_score is None and not snap.early_warning_flag


# --- 7.5 grievances and outcomes --------------------------------------------------

@pytest.mark.parametrize("text,issue", [
    ("Feed supplier delivery is late by two weeks", "supply_delay"),
    ("chara nahi aaya is hafte", "supply_delay"),
    ("Milk bhav gir gaya, no buyers", "pricing_collapse"),
    ("Chaff cutter machine kharab ho gayi", "machinery_breakdown"),
    ("EMI ki kist bharne mein dikkat hai", "loan_repayment_stress"),
    ("मेरी किस्त नहीं भर पा रहा", "loan_repayment_stress"),
    ("Need help with something", "other"),
])
def test_classify_issue(text, issue):
    assert grievance_engine.classify_issue(text) == issue


def test_grievance_ticket_routing_and_no_fabrication():
    state = make_state()
    assert grievance_engine.run(state) == {}
    state.monitoring_record = [HealthSnapshot(health_score=48.0, health_band="at_risk")]
    state.session_meta.pending_grievance_text = "Feed supply delayed again"
    state = apply(state, grievance_engine.run(state))
    ticket = state.grievance_log[-1]
    assert ticket.issue_type == "supply_delay"
    assert ticket.assigned_mentor == "District livestock extension officer"
    assert ticket.health_score_at_logging == 48.0 and ticket.case_context["district"] == "Varanasi"
    assert ticket.case_context["disbursement_status"] == "disbursed" and ticket.intervention_suggested
    assert state.session_meta.pending_grievance_text is None
    assert len(state.grievance_log) == 1


def test_outcome_tracking_and_real_record_written_once():
    state = make_state(catalog_id="tailoring")
    logged = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    state.grievance_log = [GrievanceEntry(ticket_id="TKT-TEST1", issue_type="pricing_collapse", description="x",
                                          health_score_at_logging=42.0, logged_at=logged.isoformat())]
    state.monitoring_record = [HealthSnapshot(health_score=61.0, health_band="watch")]
    state = apply(state, outcome_learning_loop.run(state))
    assert state.grievance_log[0].health_score_after == 61.0 and state.grievance_log[0].outcome_improved is True
    outcome_learning_loop.run(state)
    real = [r for r in stores.outcome_records("tailoring") if not r["is_synthetic"]]
    assert len(real) == 1 and real[0]["intervention_type"] == "pricing_adjustment" and real[0]["improved"] == 1
    assert state.outcome_learning.real_records == 1


def test_synthetic_seed_tagging_prior_bounds_and_note():
    data = seed_outcomes.generate()
    assert data == seed_outcomes.generate() and all(r["is_synthetic"] is True for r in data["records"])
    status = outcome_learning_loop.category_prior("beekeeping", None)
    assert status.synthetic_records > 0 and status.real_records == 0 and status.is_synthetic_dominant
    assert 0.9 <= status.category_prior <= 1.1
    assert "0 real" in status.status_note and "synthetic" in status.status_note
    before = len(stores.outcome_records())
    seed_outcomes.insert(data["records"])
    assert len(stores.outcome_records()) == before  # idempotent
    for _ in range(40):
        stores.add_outcome_record("beekeeping", "Varanasi", "mentor_outreach", 40, 70, is_synthetic=False)
    strong = outcome_learning_loop.category_prior("beekeeping", "Varanasi")
    assert strong.category_prior <= 1.1 and not strong.is_synthetic_dominant and strong.real_records == 40
    assert outcome_learning_loop.category_prior("unknown_activity", None).category_prior == 1.0


# --- 7.1 procurement / 7.2 launch --------------------------------------------------

def test_procurement_insufficient_then_ready():
    district = f"District-{uuid.uuid4().hex[:6]}"
    state = make_state(district=district)
    state.competitor_intel = CompetitorIntelligence(estimated_competitor_count=7, density_per_10k_population=2.5)
    rec = procurement_coordinator.run(state)["procurement_recommendation"]
    assert rec.status == "insufficient_peers" and rec.enrolled_peer_count == 1
    assert any("potential peer pool" in n for n in rec.notes)
    for sid in ("peer-a", "peer-b"):
        stores.join_procurement_cluster(district, "dairy_farming", sid, ["Cattle feed concentrate"])
    rec = procurement_coordinator.run(state)["procurement_recommendation"]
    assert rec.status == "ready_to_order" and rec.enrolled_peer_count == 3
    assert rec.pooled_items == ["Cattle feed concentrate"]
    assert procurement_coordinator.run(make_state(district=None)) == {}


def test_launch_roadmap_derived_from_catalog():
    state = make_state(catalog_id="mustard_oil_mill")
    roadmap = launch_copilot.run(state)["launch_roadmap"]
    assert [m.theme for m in roadmap] == ["licensing", "supplier_discovery", "inventory",
                                          "customer_acquisition", "operations"]
    assert not any(m.completed for m in roadmap)
    text = json.dumps([m.model_dump() for m in roadmap])
    assert "Electricity load sanction" in text and "Mustard seed" in text and "Oil wholesalers" in text
    assert "40,000" in text and "dairy" not in text.lower()
    assert max(m.target_week for m in roadmap) <= 6 * 4.33
    assert launch_copilot.run(make_state(catalog_id="")) == {}
