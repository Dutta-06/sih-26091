"""Operating model, financial analyst and scenario digital twin (TDD 6.2-6.3)."""

import math

import pytest

from common.reference import get_activity
from module2_financial import financial_analyst_agent, scenario_digital_twin
from module2_financial.financial_engine import build_financial_plan
from module2_financial.operating_model import (
    break_even_revenue_drop_pct,
    build_operating_projection,
    coverage_band,
    preview_debt_service,
    quarter_factors,
    quarterly_dscr_profile,
)
from orchestrator.state import (
    BusinessCandidate,
    CaseState,
    MarketIntelligence,
    MarketReachIntelligence,
    OperatingProjection,
    PricingIntelligence,
    RiskIntelligence,
    SessionMeta,
)

DAIRY = get_activity("dairy_farming")


def _state(capital=100_000.0, catalog_id="dairy_farming", **extra) -> CaseState:
    return CaseState(
        session_meta=SessionMeta(session_id="t"),
        business_shortlist=[BusinessCandidate(category=catalog_id, catalog_id=catalog_id)],
        financial_plan=build_financial_plan(capital),
        **extra,
    )


def _projection(quarterly_surplus: float, annual_revenue: float = 400_000.0) -> OperatingProjection:
    return OperatingProjection(annual_revenue=annual_revenue, operating_margin=quarterly_surplus * 4 / annual_revenue if annual_revenue else 0.0,
                               annual_operating_surplus=quarterly_surplus * 4, quarterly_operating_surplus=quarterly_surplus)


# --- operating model --------------------------------------------------------

def test_projection_base_and_basis_without_module1_inputs():
    p = build_operating_projection(1_000_000.0, DAIRY)
    assert p.annual_revenue == 1_000_000.0 * DAIRY["annual_revenue_to_project_cost"]
    assert p.annual_operating_surplus == round(p.annual_revenue * DAIRY["operating_margin"], 2)
    assert p.quarterly_operating_surplus == round(p.annual_operating_surplus / 4, 2)
    assert p.source_confidence == "estimated"
    assert any("catalog planning assumption" in b for b in p.basis)
    assert any("No pricing adjustment" in b for b in p.basis)
    assert any("No market-reach adjustment" in b for b in p.basis)


def test_projection_pricing_and_reach_adjustments_are_bounded_and_recorded():
    midpoint = (DAIRY["reference_price"]["low"] + DAIRY["reference_price"]["high"]) / 2
    base = build_operating_projection(1_000_000.0, DAIRY).annual_revenue
    pricing = PricingIntelligence(optimal_target_price=midpoint * 1.1, source_confidence="real")
    p = build_operating_projection(1_000_000.0, DAIRY, pricing=pricing)
    assert p.annual_revenue == pytest.approx(base * 1.1, abs=0.01)
    assert any("Pricing adjustment x1.100" in b and "real" in b for b in p.basis)
    assert p.source_confidence == "estimated"  # base is still a catalog assumption

    high = build_operating_projection(1_000_000.0, DAIRY, pricing=PricingIntelligence(optimal_target_price=midpoint * 5))
    assert high.annual_revenue == pytest.approx(base * 1.2, abs=0.01)

    thin = build_operating_projection(1_000_000.0, DAIRY, market_reach=MarketReachIntelligence(consumer_base_estimate=100))
    assert thin.annual_revenue == pytest.approx(base * 0.85, abs=0.01)
    assert any("Market-reach adjustment x0.850" in b for b in thin.basis)


def test_projection_requires_catalog_economics():
    with pytest.raises(ValueError):
        build_operating_projection(100_000.0, {})


def test_quarterly_dscr_profile_uses_calendar_quarters_and_normalised_index():
    index = [2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0]  # mean 1.0
    assert quarter_factors(index) == [2.0, 1.0, 1.0, 0.0]
    assert quarterly_dscr_profile(_projection(1_000.0), 500.0, index) == [4.0, 2.0, 2.0, 0.0]
    doubled = [v * 2 for v in index]
    assert quarter_factors(doubled) == quarter_factors(index)
    with pytest.raises(ValueError):
        quarter_factors([1.0] * 11)


def test_negative_dscr_not_clamped_and_zero_installment_is_infinite():
    assert quarterly_dscr_profile(_projection(-250.0), 500.0, [1.0] * 12) == [-0.5] * 4
    assert all(math.isinf(v) for v in quarterly_dscr_profile(_projection(100.0), 0.0, [1.0] * 12))


def test_break_even_revenue_drop():
    assert break_even_revenue_drop_pct(_projection(1_500.0, 40_000.0), 1_000.0) == 5.0  # 500 / 10,000 quarterly revenue
    assert break_even_revenue_drop_pct(_projection(500.0, 40_000.0), 1_000.0) == -5.0
    assert break_even_revenue_drop_pct(_projection(0.0, 0.0), 1_000.0) is None


def test_coverage_bands():
    assert [coverage_band(v) for v in (-0.2, 0.99, 1.0, 1.24, 1.25, 3.0)] == [
        "does not cover", "does not cover", "thin", "thin", "comfortable", "comfortable"]


def test_preview_debt_service_contract():
    preview = preview_debt_service(100_000.0, DAIRY)
    assert set(preview) == {"project_cost", "eligible", "quarterly_installment", "quarterly_surplus", "base_dscr", "min_seasonal_dscr"}
    assert preview["eligible"] is True and preview["project_cost"] == 1_000_000.0
    assert preview["base_dscr"] == round(preview["quarterly_surplus"] / preview["quarterly_installment"], 2)
    assert preview["min_seasonal_dscr"] < preview["base_dscr"]

    outside = preview_debt_service(600_000.0, DAIRY)
    assert outside["eligible"] is False and outside["base_dscr"] is None and outside["quarterly_installment"] is None


# --- financial analyst ------------------------------------------------------

@pytest.mark.parametrize("margin, band_phrase", [(0.24, "comfortably"), (0.20, "only thinly"), (0.10, "does not cover")])
def test_analyst_commentary_wording_matches_dscr(monkeypatch, margin, band_phrase):
    activity = dict(DAIRY, operating_margin=margin)
    monkeypatch.setattr(financial_analyst_agent, "case_activity", lambda state: activity)
    plan = financial_analyst_agent.run(_state())["financial_plan"]
    ratio = plan.base_debt_service_coverage_ratio
    assert ratio == round(plan.operating_projection.quarterly_operating_surplus / plan.regular_quarterly_installment, 2)
    assert f"{ratio:.2f}x" in plan.analyst_commentary
    assert band_phrase in plan.analyst_commentary
    assert plan.analyst_commentary_source == "deterministic_template"
    assert "estimates" in plan.analyst_commentary
    if ratio < 1.0:
        assert "no margin of safety" in plan.analyst_commentary
    else:
        assert "Margin of safety" in plan.analyst_commentary


def test_analyst_zero_surplus_does_not_crash(monkeypatch):
    monkeypatch.setattr(financial_analyst_agent, "case_activity", lambda state: dict(DAIRY, operating_margin=0.0))
    plan = financial_analyst_agent.run(_state())["financial_plan"]
    assert plan.base_debt_service_coverage_ratio == 0.0
    assert "does not cover" in plan.analyst_commentary


def test_analyst_never_changes_engine_figures_and_uses_llm_when_available(monkeypatch):
    state = _state()
    before = state.financial_plan.model_dump(exclude={"operating_projection", "base_debt_service_coverage_ratio",
                                                      "analyst_commentary", "analyst_commentary_source"})
    monkeypatch.setattr(financial_analyst_agent, "explain", lambda system, prompt, fallback: ("rephrased", "llm"))
    plan = financial_analyst_agent.run(state)["financial_plan"]
    assert plan.analyst_commentary == "rephrased" and plan.analyst_commentary_source == "llm"
    assert plan.model_dump(exclude={"operating_projection", "base_debt_service_coverage_ratio",
                                    "analyst_commentary", "analyst_commentary_source"}) == before
    assert state.financial_plan.analyst_commentary == ""  # input state not mutated


def test_analyst_reads_pricing_from_market_intelligence():
    midpoint = (DAIRY["reference_price"]["low"] + DAIRY["reference_price"]["high"]) / 2
    mi = MarketIntelligence(pricing=PricingIntelligence(optimal_target_price=midpoint * 0.9))
    plan = financial_analyst_agent.run(_state(market_intelligence=mi))["financial_plan"]
    assert any("Pricing adjustment x0.900" in b for b in plan.operating_projection.basis)


def test_analyst_degrades_without_activity_and_skips_ineligible():
    state = _state(catalog_id="unknown_activity")
    plan = financial_analyst_agent.run(state)["financial_plan"]
    assert plan.base_debt_service_coverage_ratio is None and "not assessed" in plan.analyst_commentary
    assert financial_analyst_agent.run(_state(capital=600_000.0)) == {}
    assert financial_analyst_agent.run(CaseState(session_meta=SessionMeta(session_id="t"))) == {}


# --- scenario digital twin ----------------------------------------------------

def test_seasonal_fallback_is_labeled_and_risk_index_preferred():
    plan = scenario_digital_twin.run(_state())["financial_plan"]
    assert plan.stress_test_result.seasonal_basis.startswith("Catalog seasonal profile")
    assert len(plan.scenarios) == 4 and plan.stress_test_result == plan.scenarios[0]

    index = [1.0] * 12
    risk = RiskIntelligence(seasonal_index=index, seasonal_basis="Agmarknet decomposition", source_confidence="real")
    plan = scenario_digital_twin.run(_state(risk_intel=risk))["financial_plan"]
    assert plan.stress_test_result.seasonal_basis.startswith("Risk analysis seasonal index (real)")
    mi = MarketIntelligence(risk=RiskIntelligence(seasonal_index=[0.5] * 6 + [1.5] * 6))
    plan = scenario_digital_twin.run(_state(market_intelligence=mi, risk_intel=risk))["financial_plan"]
    assert plan.stress_test_result.quarterly_dscr[0] < plan.stress_test_result.quarterly_dscr[3]


def test_stress_buffer_computed_from_actual_shortfall():
    state = _state()
    installment = state.financial_plan.regular_quarterly_installment
    projection = _projection(installment, annual_revenue=installment * 16)  # base DSCR exactly 1.0
    state.financial_plan = state.financial_plan.model_copy(update={"operating_projection": projection})
    index = [0.7] * 3 + [0.9] * 3 + [1.1] * 3 + [1.3] * 3
    state.risk_intel = RiskIntelligence(seasonal_index=index)
    result = scenario_digital_twin.run(state)["financial_plan"].stress_test_result

    assert result.quarterly_dscr == [0.7, 0.9, 1.1, 1.3]
    assert result.deficit_quarters == 2 and result.is_sustainable is False
    shortfall = round(installment * 0.3, 2) + round(installment * 0.1, 2)
    buffer = math.ceil(shortfall / 1000) * 1000
    assert f"Rs {buffer:,.0f}" in result.buffer_recommendation
    assert result.buffer_recommendation.startswith("Not sustainable")
    assert "resilient" not in result.buffer_recommendation.lower()
    assert result.debt_service_coverage_ratio == 0.7
    assert result.stressed_quarterly_surplus == round(installment * 0.7, 2)


def test_every_scenario_wording_matches_numbers():
    plan = scenario_digital_twin.run(_state())["financial_plan"]
    names = [s.scenario_name for s in plan.scenarios]
    assert "price fall" in names[1] and "input-cost" in names[2] and names[3].startswith("Break-even")
    for s in plan.scenarios:
        assert s.is_sustainable == (s.debt_service_coverage_ratio >= 1.0) == (s.deficit_quarters == 0)
        assert s.is_sustainable == (not s.buffer_recommendation.startswith("Not sustainable"))
        assert s.debt_service_coverage_ratio == min(s.quarterly_dscr)
        assert s.source_confidence == "estimated"
    assert plan.scenarios[3].debt_service_coverage_ratio == 1.0


def test_twin_negative_surplus_not_clamped_and_skips_without_plan():
    state = _state()
    state.financial_plan = state.financial_plan.model_copy(update={"operating_projection": _projection(-1_000.0)})
    result = scenario_digital_twin.run(state)["financial_plan"].stress_test_result
    assert result.debt_service_coverage_ratio < 0 and result.deficit_quarters == 4
    assert scenario_digital_twin.run(_state(capital=600_000.0)) == {}
    assert scenario_digital_twin.run(_state(catalog_id="unknown_activity")) == {}
