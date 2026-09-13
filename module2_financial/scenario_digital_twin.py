"""Scenario and Stress Testing Agent (TDD Section 6.3 / "Digital Twin").

Tests the deterministic financial plan against seasonal demand patterns, raw material cost
shocks, and lean-season troughs to evaluate whether loan repayment remains feasible under
downside conditions rather than only under an average-case assumption.

Reads:  state.financial_plan, state.market_intelligence.risk
Writes: state.financial_plan.stress_test_result

Key principles:
1. Simulates month-by-month cumulative cash flow trajectory over the full loan repayment schedule.
2. Ingests seasonal revenue curves from Module 1 Risk Agent (Agmarknet / market signals).
3. Evaluates working capital buffer adequacy during lean seasons.
4. Categorizes stress resilience ("resilient", "vulnerable", "critical_risk").
5. Synthesizes risk mitigation strategies using local LLM (Ollama llama3.2).
6. Writes directly to `state.financial_plan.stress_test_result` without altering deterministic figures.
"""

from __future__ import annotations

from dataclasses import is_dataclass, replace
import logging
from typing import Any

from pydantic import AliasChoices, BaseModel, Field

from module2_financial.financial_engine import (
    ApplicantProfile,
    FinancialPlan,
    LoanEligibility,
)
from module2_financial.llm_client import LLMClient, get_llm_client
from module2_financial.schemas import (
    Module1IntelligenceSnapshot,
    ScenarioRunDetail,
    SeasonalRiskSnapshot,
    StressTestResult,
)

logger = logging.getLogger(__name__)


class LLMStressInterpretation(BaseModel):
    """Structured LLM output for scenario stress interpretation."""

    interpretation: str = Field(
        validation_alias=AliasChoices("interpretation", "description", "summary", "text", "analysis", "executive_summary"),
        description="Comprehensive, plain-language evaluation of downside scenario resilience."
    )


STRESS_INTERPRETATION_SYSTEM_PROMPT = """You are a Micro-Enterprise Risk and Scenario Analysis Specialist.
Your task is to interpret the results of a multi-scenario financial stress simulation (digital twin)
conducted on a rural/semi-urban micro-enterprise loan structure.

Analyze the downside resilience:
1. Explain how the business performs during the seasonal trough and cost shock scenarios.
2. Highlight whether the working capital reserve is sufficient to absorb cash deficits during lean months.
3. Provide 2-3 specific, pragmatic recommendations for navigating low-season cash flow gaps.

Keep the interpretation concise, grounded in the simulation numbers, and direct.
"""


def simulate_scenario(
    plan: FinancialPlan,
    base_revenue: float,
    base_cogs: float,
    base_opex: float,
    scenario_name: str,
    description: str,
    seasonal_multipliers: list[float],
    revenue_shock_pct: float = 0.0,
    cogs_multiplier: float = 1.0,
) -> ScenarioRunDetail:
    """Simulate month-by-month cash flow and debt service over the loan schedule."""
    repayments = plan.repayment_schedule
    if not repayments:
        return ScenarioRunDetail(
            name=scenario_name,
            description=description,
            revenue_multiplier=round(1.0 - (revenue_shock_pct / 100), 2),
            cogs_multiplier=cogs_multiplier,
            lowest_monthly_dscr=0.0,
            min_cash_balance=0.0,
            months_in_deficit=0,
            is_viable=False,
            summary_observation="No repayment schedule available.",
        )

    # Initial liquidity starts with the allocated working capital reserve
    cash_balance = float(plan.working_capital_requirement)
    min_cash_balance = cash_balance
    lowest_dscr = 999.0
    months_in_deficit = 0

    rev_factor = 1.0 - (revenue_shock_pct / 100.0)

    for installment in repayments:
        month_idx = (installment.installment_number - 1) % len(seasonal_multipliers)
        seasonal_idx = seasonal_multipliers[month_idx]

        # Monthly economics
        monthly_rev = round(base_revenue * rev_factor * seasonal_idx, 2)
        monthly_cogs = round(base_cogs * cogs_multiplier, 2)
        monthly_opex = base_opex
        monthly_surplus = round(monthly_rev - monthly_cogs - monthly_opex, 2)

        # DSCR for this month
        if installment.payment > 0:
            monthly_dscr = round(monthly_surplus / installment.payment, 2)
            if monthly_dscr < lowest_dscr:
                lowest_dscr = monthly_dscr

        # Net cash flow after servicing installment
        net_cash = monthly_surplus - installment.payment
        cash_balance = round(cash_balance + net_cash, 2)

        if cash_balance < min_cash_balance:
            min_cash_balance = cash_balance

        if cash_balance < 0:
            months_in_deficit += 1

    is_viable = months_in_deficit == 0 and lowest_dscr >= 1.0

    if is_viable:
        obs = f"Solvent throughout tenure; lowest monthly DSCR is {lowest_dscr}x with ₹{min_cash_balance:,.2f} min cash buffer."
    elif min_cash_balance < 0:
        obs = f"Incurred liquidity deficit of ₹{abs(min_cash_balance):,.2f} across {months_in_deficit} month(s)."
    else:
        obs = f"Tight debt servicing with trough DSCR of {lowest_dscr}x."

    return ScenarioRunDetail(
        name=scenario_name,
        description=description,
        revenue_multiplier=round(rev_factor, 2),
        cogs_multiplier=cogs_multiplier,
        lowest_monthly_dscr=round(max(0.0, lowest_dscr), 2),
        min_cash_balance=round(min_cash_balance, 2),
        months_in_deficit=months_in_deficit,
        is_viable=is_viable,
        summary_observation=obs,
    )


def run_stress_test_suite(
    plan: FinancialPlan,
    operating_estimates: Any,
    seasonal_risk: SeasonalRiskSnapshot,
) -> StressTestResult:
    """Run full stress simulation across baseline, seasonal troughs, and cost shocks."""
    base_rev = operating_estimates.estimated_monthly_revenue
    base_cogs = operating_estimates.estimated_monthly_cogs
    base_opex = operating_estimates.estimated_monthly_opex
    base_surplus = operating_estimates.estimated_monthly_operating_surplus

    regular_repayments = [
        item for item in plan.repayment_schedule if item.period_type == "repayment"
    ]
    monthly_emi = regular_repayments[0].payment if regular_repayments else 0.0

    # 1. Baseline Average Case
    flat_curve = [1.0] * 12
    baseline_run = simulate_scenario(
        plan, base_rev, base_cogs, base_opex,
        scenario_name="Baseline (Average Conditions)",
        description="Normal business conditions with average demand and stable input costs.",
        seasonal_multipliers=flat_curve,
        revenue_shock_pct=0.0,
        cogs_multiplier=1.0,
    )

    # 2. Seasonal Demand Curve Trough (from Risk Agent)
    seasonal_run = simulate_scenario(
        plan, base_rev, base_cogs, base_opex,
        scenario_name="Seasonal Demand Cycle",
        description=f"Reflects 12-month demand cycle with peak drop of {seasonal_risk.trough_revenue_drop_pct:.0f}% in trough months ({', '.join(seasonal_risk.trough_months)}).",
        seasonal_multipliers=seasonal_risk.seasonal_curve_multipliers,
        revenue_shock_pct=0.0,
        cogs_multiplier=1.0,
    )

    # 3. Input Cost Surge (+15% raw materials)
    cogs_shock_mult = 1.0 + (seasonal_risk.cogs_inflation_shock_pct / 100.0)
    cost_surge_run = simulate_scenario(
        plan, base_rev, base_cogs, base_opex,
        scenario_name="Raw Material Inflation Shock",
        description=f"Input costs / COGS surge by {seasonal_risk.cogs_inflation_shock_pct:.0f}% due to supply chain tightening.",
        seasonal_multipliers=flat_curve,
        revenue_shock_pct=0.0,
        cogs_multiplier=cogs_shock_mult,
    )

    # 4. Severe Compound Shock (Trough Season + 15% Cost Surge)
    compound_run = simulate_scenario(
        plan, base_rev, base_cogs, base_opex,
        scenario_name="Compound Stress (Lean Season + Cost Surge)",
        description="Simultaneous occurrence of lean seasonal demand and elevated raw material costs.",
        seasonal_multipliers=seasonal_risk.seasonal_curve_multipliers,
        revenue_shock_pct=10.0,
        cogs_multiplier=cogs_shock_mult,
    )

    scenario_runs = [baseline_run, seasonal_run, cost_surge_run, compound_run]

    # Calculate break-even revenue drop percentage
    # Surplus = Rev - COGS - Opex = EMI  => Rev = COGS + Opex + EMI
    break_even_rev = base_cogs + base_opex + monthly_emi
    if base_rev > break_even_rev:
        break_even_drop_pct = round(((base_rev - break_even_rev) / base_rev) * 100, 1)
    else:
        break_even_drop_pct = 0.0

    # Determine overall verdict
    trough_dscr = seasonal_run.lowest_monthly_dscr
    min_cash = min(r.min_cash_balance for r in scenario_runs)
    total_deficit_months = sum(r.months_in_deficit for r in scenario_runs)
    max_shortfall = max(0.0, abs(min(0.0, min_cash)))

    if total_deficit_months == 0 and trough_dscr >= 1.25:
        stress_verdict = "resilient"
    elif min_cash >= 0 and trough_dscr >= 0.95:
        stress_verdict = "vulnerable"
    else:
        stress_verdict = "critical_risk"

    # Actionable mitigation strategies
    strategies = [
        f"Maintain an operating liquidity reserve equal to at least ₹{monthly_emi * 3:,.2f} (3 months of EMI) prior to entering {', '.join(seasonal_risk.trough_months)}.",
        "Negotiate supplier credit terms with delayed settlement windows during low-demand months.",
        "Explore flexible repayment alignment (e.g. balloon/seasonal moratorium) if available under the scheme.",
    ]

    return StressTestResult(
        baseline_dscr=baseline_run.lowest_monthly_dscr,
        trough_dscr=trough_dscr,
        min_cash_reserve=round(min_cash, 2),
        months_with_cash_deficit=total_deficit_months,
        max_liquidity_shortfall=round(max_shortfall, 2),
        break_even_revenue_drop_pct=break_even_drop_pct,
        stress_verdict=stress_verdict,
        scenario_runs=scenario_runs,
        risk_mitigation_strategies=strategies,
        confidence_tag="estimated",
    )


class ScenarioDigitalTwinAgent:
    """Agent implementing Section 6.3 Scenario and Stress Testing."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or get_llm_client()

    def stress_test(
        self,
        plan: FinancialPlan,
        profile: ApplicantProfile | None = None,
        market_intelligence: Module1IntelligenceSnapshot | None = None,
    ) -> StressTestResult:
        """Run multi-scenario digital twin simulation and synthesize qualitative risk verdict."""
        if plan.loan_eligibility != LoanEligibility.ELIGIBLE or not plan.scheme_tier:
            return StressTestResult(
                baseline_dscr=0.0,
                trough_dscr=0.0,
                min_cash_reserve=0.0,
                months_with_cash_deficit=0,
                max_liquidity_shortfall=0.0,
                break_even_revenue_drop_pct=0.0,
                stress_verdict="critical_risk",
                scenario_runs=[],
                risk_mitigation_strategies=["Application not eligible for loan disbursement."],
                llm_stress_interpretation="Loan plan ineligible under current parameters; stress testing skipped.",
                confidence_tag="verified",
            )

        if market_intelligence is None or market_intelligence.operating_estimates is None:
            cat = profile.business_category if profile else "dairy"
            loc = f"{profile.district}, {profile.state}" if profile else "Nashik, Maharashtra"
            market_intelligence = Module1IntelligenceSnapshot.create_default_fixture(
                business_category=cat,
                location=loc,
                project_cost=plan.project_cost,
            )

        # 1. Deterministic simulation engine
        stress_result = run_stress_test_suite(
            plan=plan,
            operating_estimates=market_intelligence.operating_estimates,
            seasonal_risk=market_intelligence.risk,
        )

        # 2. LLM Qualitative Synthesis (Ollama llama3.2)
        prompt = (
            f"Business: {profile.business_category if profile else 'General'} (Project Cost: ₹{plan.project_cost:,.2f})\n"
            f"Loan: ₹{plan.loan_amount:,.2f} ({plan.scheme_name.upper()} Scheme)\n"
            f"Working Capital Allocated: ₹{plan.working_capital_requirement:,.2f}\n"
            f"Simulation Results:\n"
            f"- Baseline DSCR: {stress_result.baseline_dscr}x\n"
            f"- Trough Season DSCR: {stress_result.trough_dscr}x\n"
            f"- Minimum Cash Buffer: ₹{stress_result.min_cash_reserve:,.2f}\n"
            f"- Total Deficit Months: {stress_result.months_with_cash_deficit}\n"
            f"- Break-Even Revenue Drop: {stress_result.break_even_revenue_drop_pct}%\n"
            f"- Verdict: {stress_result.stress_verdict.upper()}\n\n"
            f"Scenario Breakdown:\n"
            + "\n".join(f"  • {s.name}: Lowest DSCR={s.lowest_monthly_dscr}x, Min Cash=₹{s.min_cash_balance:,.2f} ({s.summary_observation})" for s in stress_result.scenario_runs)
            + "\n\nProvide an executive qualitative interpretation of this downside stress test."
        )

        try:
            res = self.llm_client.generate_structured(
                prompt=prompt,
                system_prompt=STRESS_INTERPRETATION_SYSTEM_PROMPT,
                schema=LLMStressInterpretation,
            )
            stress_result.llm_stress_interpretation = res.interpretation
        except Exception as err:
            logger.warning(f"LLM stress interpretation failed: {err}; using rule summary.")
            stress_result.llm_stress_interpretation = (
                f"Under seasonal stress testing, the business achieves a trough DSCR of {stress_result.trough_dscr}x "
                f"and maintains a minimum cash balance of ₹{stress_result.min_cash_reserve:,.2f}. "
                f"Stress verdict is classified as {stress_result.stress_verdict.upper()}."
            )

        return stress_result


def run(state: Any) -> Any:
    """LangGraph node execution function matching Section 6.3 contract.

    Reads:  state.financial_plan, state.market_intelligence.risk
    Writes: state.financial_plan.stress_test_result
    """
    if state.financial_plan is None:
        raise ValueError("ScenarioDigitalTwinAgent requires state.financial_plan to be computed first")

    profile = getattr(state, "applicant_profile", None) or getattr(state, "entrepreneur_profile", None)
    market_intelligence = getattr(state, "market_intelligence", None)
    market_snapshot: Module1IntelligenceSnapshot | None = None

    if market_intelligence is not None:
        if isinstance(market_intelligence, Module1IntelligenceSnapshot):
            market_snapshot = market_intelligence
        elif isinstance(market_intelligence, dict):
            market_snapshot = Module1IntelligenceSnapshot.model_validate(market_intelligence)

    agent = ScenarioDigitalTwinAgent()
    stress_result = agent.stress_test(
        plan=state.financial_plan,
        profile=profile,
        market_intelligence=market_snapshot,
    )

    # Attach stress_test_result to state.financial_plan without altering any deterministic figures
    if is_dataclass(state.financial_plan):
        new_plan = replace(state.financial_plan, stress_test_result=stress_result)
        if is_dataclass(state):
            return replace(state, financial_plan=new_plan)
        else:
            state.financial_plan = new_plan
            return state
    else:
        state.financial_plan.stress_test_result = stress_result
        return state


if __name__ == "__main__":
    from module2_financial.financial_engine import (
        FeasibilityVerdict,
        SchemeTerms,
        build_financial_plan,
    )

    print("=" * 70)
    print("Testing Section 6.3 Scenario / Digital Twin Agent")
    print("=" * 70)

    # 1. Sample applicant
    profile = ApplicantProfile(
        available_capital=100_000.0,
        state="Maharashtra",
        district="Nashik",
        business_category="agri_allied",
        is_new_business=True,
        is_woman_owned=True,
        has_udyam_registration=True,
    )

    # 2. Financial plan
    terms = SchemeTerms(
        margin_rate=0.10,
        working_capital_rate=0.20,
        interest_rate=0.08,
        tenure_years=7,
        moratorium_months=6,
    )
    plan = build_financial_plan(
        available_capital=profile.available_capital,
        feasibility_verdict=FeasibilityVerdict.RECOMMENDED,
        scheme="pmmy",
        applicant_profile=profile,
        scheme_terms=terms,
    )

    # 3. Run Scenario / Digital Twin
    agent = ScenarioDigitalTwinAgent()
    stress_result = agent.stress_test(plan=plan, profile=profile)

    print(f"\n[1] Stress Test Resilience Metrics:")
    print(f"  • Overall Verdict: {stress_result.stress_verdict.upper()}")
    print(f"  • Baseline DSCR: {stress_result.baseline_dscr}x")
    print(f"  • Trough Season DSCR: {stress_result.trough_dscr}x")
    print(f"  • Min Cumulative Cash Reserve: ₹{stress_result.min_cash_reserve:,.2f}")
    print(f"  • Months with Liquidity Deficit: {stress_result.months_with_cash_deficit}")
    print(f"  • Break-Even Revenue Drop Tolerance: {stress_result.break_even_revenue_drop_pct}%")

    print(f"\n[2] Scenario Breakdown:")
    for sc in stress_result.scenario_runs:
        print(f"  • {sc.name}:")
        print(f"      - Trough DSCR: {sc.lowest_monthly_dscr}x | Min Cash: ₹{sc.min_cash_balance:,.2f} | Viable: {sc.is_viable}")
        print(f"      - Note: {sc.summary_observation}")

    print(f"\n[3] LLM Qualitative Interpretation (Ollama llama3.2):")
    print(f"{stress_result.llm_stress_interpretation}")

    print(f"\n[4] Mitigation Strategies:")
    for i, strat in enumerate(stress_result.risk_mitigation_strategies, 1):
        print(f"  {i}. {strat}")
    print("\n" + "=" * 70)
