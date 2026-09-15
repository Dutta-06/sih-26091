"""Discovery ranking and adversarial review rules (pure, offline)."""

from __future__ import annotations

import pytest

import module1_feasibility.adversarial_review as review
import module1_feasibility.discovery_agent as discovery
from common.reference import get_activity
from module1_feasibility.profiling_agent import extract_profile_from_slots, identify_constraints
from orchestrator.state import (
    BusinessCandidate,
    CaseState,
    CompetitorIntelligence,
    FeasibilityRecord,
    MarketIntelligence,
    RejectionEntry,
    RiskFlag,
    RiskIntelligence,
    SessionMeta,
)


@pytest.fixture(autouse=True)
def neutral_prior(monkeypatch):
    monkeypatch.setattr(discovery, "_category_prior", lambda cid, district: None)


def _state(capital: float, pref: str | None, history: list[RejectionEntry] | None = None) -> CaseState:
    return CaseState(
        session_meta=SessionMeta(session_id="d"),
        entrepreneur_profile=extract_profile_from_slots("Bhadohi", capital, pref),
        feasibility_record=FeasibilityRecord(rejection_history=history or []) if history else None,
    )


def _preview(dscr, seasonal=None, eligible=True):
    return {"project_cost": 100_000, "eligible": eligible, "quarterly_installment": 10_000,
            "quarterly_surplus": 10_000 * (dscr or 0), "base_dscr": dscr, "min_seasonal_dscr": seasonal}


def test_user_preference_assessed_first():
    shortlist = discovery.run(_state(12_000, "Tailoring"))["business_shortlist"]
    assert shortlist[0].catalog_id == "tailoring" and shortlist[0].is_user_preference
    assert shortlist[0].source_confidence == "estimated"
    assert [c.rank for c in shortlist] == list(range(1, len(shortlist) + 1))


def test_capital_infeasible_activities_excluded():
    shortlist = discovery.run(_state(12_000, "dairy"))["business_shortlist"]  # supports Rs 1.2L; dairy needs 1.5L
    ids = {c.catalog_id for c in shortlist}
    assert "dairy_farming" not in ids and "mustard_oil_mill" not in ids
    assert all(c.min_project_cost <= 120_000 for c in shortlist)
    assert any("Dairy" in c for c in identify_constraints(extract_profile_from_slots("x", 12_000, "dairy")))


def test_rejection_excludes_and_prefers_adjacent():
    history = [RejectionEntry(category="Tailoring and Garment Stitching Unit", catalog_id="tailoring",
                              verdict="not_recommended", reasons=["R3"])]
    shortlist = discovery.run(_state(50_000, "tailoring", history))["business_shortlist"]
    assert "tailoring" not in {c.catalog_id for c in shortlist}
    top = shortlist[0]
    assert top.catalog_id in get_activity("tailoring")["adjacent"] or top.sector == "textiles_apparel"
    assert top.adjacent_to == "Tailoring and Garment Stitching Unit" and not top.is_user_preference


def test_score_candidate_components_and_prior():
    profile = extract_profile_from_slots("x", 100_000, "dairy")
    profile.assets = ["cattle shed", "borewell water"]
    score, parts = discovery.score_candidate(profile, get_activity("dairy_farming"))
    assert parts["preference_match"] == 1.0 and parts["infrastructure_fit"] == 1.0 and score > 0
    assert parts["outcome_prior_available"] == 0.0
    boosted, parts2 = discovery.score_candidate(profile, get_activity("dairy_farming"), prior=1.1)
    assert boosted > score and parts2["outcome_prior"] == 1.1
    none_score, none_parts = discovery.score_candidate(extract_profile_from_slots("x", 1_000, None), get_activity("dairy_farming"))
    assert none_score == 0.0 and none_parts["capital_feasible"] == 0.0


def test_nothing_affordable_gives_empty_shortlist():
    assert discovery.run(_state(1_000, "tea"))["business_shortlist"] == []


def test_micro_case_not_rejected_for_small_capital():
    verdict, reasons, _ = review.evaluate(12_000, get_activity("tailoring"), MarketIntelligence(), _preview(1.6, 1.3))
    assert verdict == "viable" and reasons == []


def test_micro_case_with_real_debt_service_preview():
    preview = review._preview(12_000, get_activity("tailoring"))
    if preview is None:
        pytest.skip("module2_financial.operating_model.preview_debt_service unavailable")
    verdict, reasons, _ = review.evaluate(12_000, get_activity("tailoring"), MarketIntelligence(), preview)
    assert not any(r.startswith("R1") for r in reasons)
    assert verdict != "not_recommended" or any(r.startswith("R2") for r in reasons)


@pytest.mark.parametrize("dscr,seasonal,mi,expected,rule", [
    (0.9, None, MarketIntelligence(), "not_recommended", "R2"),
    (1.1, None, MarketIntelligence(), "marginal", "M1"),
    (1.6, 0.7, MarketIntelligence(), "marginal", "M4"),
    (1.6, None, MarketIntelligence(competitor=CompetitorIntelligence(saturation_level="high", z_score_vs_district=2.5)), "not_recommended", "R3"),
    (1.6, None, MarketIntelligence(competitor=CompetitorIntelligence(saturation_level="high", z_score_vs_district=1.0)), "marginal", "M2"),
    (1.6, None, MarketIntelligence(risk=RiskIntelligence(overall_severity="high", risk_flags=[
        RiskFlag(risk_id="power_reliability", category="structural", title="Power reliability", severity="high"),
        RiskFlag(risk_id="single_buyer_dependency", category="structural", title="Single-buyer dependency", severity="high"),
    ])), "marginal", "M3"),
    # seasonal high-severity flags are judged by the seasonal DSCR rule (M4), not counted again in M3
    (1.6, None, MarketIntelligence(risk=RiskIntelligence(overall_severity="high", risk_flags=[
        RiskFlag(risk_id="seasonal_demand_variation", category="seasonal", title="Seasonal demand variation", severity="high"),
        RiskFlag(risk_id="working_capital_strain", category="structural", title="Working capital strain", severity="high"),
    ])), "viable", None),
])
def test_review_rules(dscr, seasonal, mi, expected, rule):
    verdict, reasons, critique = review.evaluate(100_000, get_activity("tailoring"), mi, _preview(dscr, seasonal))
    assert verdict == expected
    assert (not reasons) if rule is None else any(r.startswith(rule) for r in reasons)
    assert any("6 of 6 analyses are estimates" in c for c in critique)


def test_capital_rule_and_outside_range_not_rejected():
    verdict, reasons, _ = review.evaluate(10_000, get_activity("dairy_farming"), None, _preview(2.0))
    assert verdict == "not_recommended" and reasons[0].startswith("R1")
    verdict, _, critique = review.evaluate(600_000, get_activity("dairy_farming"), MarketIntelligence(), _preview(None, eligible=False))
    assert verdict == "viable" and any("outside the scheme range" in c for c in critique)


def test_rejection_recorded_and_exhaustion(monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(review, "_preview", lambda cap, act: _preview(0.5))
    state = _state(50_000, "tailoring")
    state.business_shortlist = [BusinessCandidate(category="Tailoring and Garment Stitching Unit", catalog_id="tailoring")]
    state.market_intelligence = MarketIntelligence()
    record = review.run(state)["feasibility_record"]
    assert record.rejection_history[0].catalog_id == "tailoring" and record.attempt_number == 2
    assert not record.alternatives_exhausted
    state.feasibility_record = record.model_copy(update={"attempt_number": settings.max_feasibility_attempts})
    record = review.run(state)["feasibility_record"]
    assert record.alternatives_exhausted


def test_review_with_no_candidate_marks_exhausted():
    record = review.run(_state(1_000, "tea"))["feasibility_record"]
    assert record.alternatives_exhausted and record.verdict == "not_recommended"
