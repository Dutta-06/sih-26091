"""Financial Analyst Agent (TDD Section 6.2 / "Financial Interpretation").

A reasoning stage separate from the deterministic engine that evaluates whether the
projected operating surplus for the business, informed by the pricing and market
analyses from Module 1, is sufficient to comfortably service the computed repayment
schedule.

Reads:  state.financial_plan, state.market_intelligence.pricing
Writes: state.financial_plan.analyst_commentary

Key principles:
1. Explains the numbers in plain language and highlights margin of safety.
2. Grounded in deterministic metrics (DSCR, margin of safety, runway) to prevent LLM math hallucination.
3. NEVER alters the deterministic financial figures from `financial_engine.py`.
4. Extensible: Accepts real Module 1 case state or clean baseline fixtures.
5. Pluggable LLM: Works with Gemini, OpenAI, Claude, Groq, Ollama, or Mock fallback.
"""

from __future__ import annotations

from dataclasses import is_dataclass, replace
import logging
from typing import Any

from module2_financial.llm_client import LLMClient, get_llm_client
from module2_financial.financial_engine import (
    ApplicantProfile,
    FinancialPlan,
    LoanEligibility,
)
from module2_financial.schemas import (
    CompetitorSnapshot,
    DebtServiceMetrics,
    FinancialAnalystCommentary,
    MarketReachSnapshot,
    Module1IntelligenceSnapshot,
    PricingSnapshot,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Micro-Enterprise Financial Analyst and Credit Underwriting Advisor.
Your role is to interpret the loan structure and repayment schedule produced by the deterministic Financial Engine.

Your core objectives:
1. Evaluate whether the projected operating surplus (informed by local pricing and market reach from Module 1) is sufficient to comfortably service the monthly EMI obligations.
2. Explain the financial plan and scheme terms in clear, accessible, plain language for the entrepreneur and credit officer.
3. Highlight the Margin of Safety (how much revenue drop or cost increase the business can absorb before debt stress).
4. Identify real operational/financial risks and provide 2-3 concrete, actionable recommendations.

CRITICAL CONSTRAINTS:
- NEVER modify or invent different financial numbers (e.g. project cost, loan amount, or EMI). The numbers provided are verified and final.
- Ground all qualitative assertions in the provided numbers and market signals.
"""


def compute_debt_service_metrics(
    plan: FinancialPlan,
    operating_surplus: float,
) -> DebtServiceMetrics:
    """Deterministically calculate debt service safety ratios before calling the LLM.

    This ensures the LLM is provided with mathematically exact metrics (DSCR, Margin of Safety)
    rather than estimating ratios itself.
    """
    # Extract post-moratorium regular EMI from repayment schedule
    regular_repayments = [
        item for item in plan.repayment_schedule if item.period_type == "repayment"
    ]
    moratorium_periods = [
        item for item in plan.repayment_schedule if item.period_type == "moratorium"
    ]

    monthly_emi = regular_repayments[0].payment if regular_repayments else 0.0
    monthly_moratorium_interest = moratorium_periods[0].payment if moratorium_periods else 0.0

    if monthly_emi > 0:
        dscr = round(operating_surplus / monthly_emi, 2)
        margin_of_safety_pct = round(
            max(0.0, ((operating_surplus - monthly_emi) / operating_surplus) * 100), 1
        )
        working_capital_runway = round(plan.working_capital_requirement / monthly_emi, 1)
    else:
        dscr = 99.0
        margin_of_safety_pct = 100.0
        working_capital_runway = 99.0

    # Categorize serviceability tier based on banking standards for micro-enterprises
    if dscr >= 1.75:
        serviceability_status = "comfortable"
    elif dscr >= 1.30:
        serviceability_status = "adequate"
    elif dscr >= 1.00:
        serviceability_status = "tight"
    else:
        serviceability_status = "insufficient"

    return DebtServiceMetrics(
        monthly_emi=monthly_emi,
        monthly_moratorium_interest=monthly_moratorium_interest,
        projected_monthly_operating_surplus=operating_surplus,
        dscr=dscr,
        margin_of_safety_pct=margin_of_safety_pct,
        working_capital_runway_months=working_capital_runway,
        serviceability_status=serviceability_status,
    )


def _build_analyst_prompt(
    profile: ApplicantProfile,
    plan: FinancialPlan,
    metrics: DebtServiceMetrics,
    market_intelligence: Module1IntelligenceSnapshot,
) -> str:
    """Format all deterministic figures and market signals into a structured LLM prompt."""
    tier = plan.scheme_tier
    rate_pct = f"{tier.rate * 100:.1f}%" if tier else "N/A"
    tenure_yrs = tier.tenure_years if tier else "N/A"
    moratorium_mos = tier.moratorium_months if tier else "N/A"

    prompt = f"""=== CASE DATA FOR FINANCIAL INTERPRETATION ===

1. APPLICANT & BUSINESS PROFILE:
- Business Category: {profile.business_category}
- Location: {profile.district}, {profile.state}
- Available Capital (Equity): ₹{profile.available_capital:,.2f}
- New Business: {profile.is_new_business}
- Woman Owned: {profile.is_woman_owned}
- Social Category: {profile.social_category or 'General'}

2. DETERMINISTIC FINANCIAL PLAN (Scheme: {plan.scheme_name.upper()}):
- Total Project Cost: ₹{plan.project_cost:,.2f}
- Capital Expenditure (Capex): ₹{plan.capital_expenditure:,.2f}
- Allocated Working Capital: ₹{plan.working_capital_requirement:,.2f}
- Loan Amount: ₹{plan.loan_amount:,.2f}
- Interest Rate: {rate_pct} per annum
- Loan Tenure: {tenure_yrs} years ({moratorium_mos} months moratorium)
- Monthly Repayment (EMI): ₹{metrics.monthly_emi:,.2f} (Moratorium Interest: ₹{metrics.monthly_moratorium_interest:,.2f}/mo)
- Eligibility Status: {plan.loan_eligibility.value}

3. MODULE 1 MARKET & OPERATING SIGNALS:
- Local Population within Reach: {market_intelligence.market_reach.population_within_radius:,} residents ({market_intelligence.market_reach.radius_km} km radius)
- Representative Commodity/Product Price: ₹{market_intelligence.pricing.representative_price} per {market_intelligence.pricing.unit}
- Competitor Density: {market_intelligence.competitor.competitor_count} local competitors ({market_intelligence.competitor.saturation_level} saturation)
- Projected Monthly Revenue: ₹{market_intelligence.operating_estimates.estimated_monthly_revenue:,.2f}
- Projected Monthly Expenses (COGS + Opex): ₹{(market_intelligence.operating_estimates.estimated_monthly_cogs + market_intelligence.operating_estimates.estimated_monthly_opex):,.2f}
- Projected Monthly Operating Surplus: ₹{metrics.projected_monthly_operating_surplus:,.2f}

4. DETERMINISTIC DEBT-SERVICE METRICS:
- Debt Service Coverage Ratio (DSCR): {metrics.dscr}x
- Margin of Safety: {metrics.margin_of_safety_pct}%
- Working Capital Loan Runway: {metrics.working_capital_runway_months} months
- Serviceability Rating: {metrics.serviceability_status.upper()}

Please produce a comprehensive financial interpretation in structured format.
"""
    return prompt


class FinancialAnalystAgent:
    """Agent implementing Section 6.2 Financial Interpretation."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or get_llm_client()

    def interpret(
        self,
        plan: FinancialPlan,
        profile: ApplicantProfile,
        market_intelligence: Module1IntelligenceSnapshot | None = None,
    ) -> FinancialAnalystCommentary:
        """Evaluate and annotate a deterministic financial plan with qualitative reasoning."""
        if plan.loan_eligibility != LoanEligibility.ELIGIBLE or not plan.scheme_tier:
            return FinancialAnalystCommentary(
                executive_summary="The applicant does not meet the eligibility thresholds for the selected scheme.",
                repayment_serviceability_assessment="Loan cannot be structured under current parameters.",
                margin_of_safety_analysis="No debt service scheduled.",
                working_capital_adequacy="N/A",
                key_risks=["Ineligibility under configured scheme rules."],
                actionable_recommendations=["Review scheme parameters or explore alternative credit schemes."],
                confidence_tag="verified",
            )

        # Use provided market intelligence or generate baseline realistic fixture
        if market_intelligence is None or market_intelligence.operating_estimates is None:
            market_intelligence = Module1IntelligenceSnapshot.create_default_fixture(
                business_category=profile.business_category,
                location=f"{profile.district}, {profile.state}",
                project_cost=plan.project_cost,
            )

        # 1. Deterministic ratios
        surplus = market_intelligence.operating_estimates.estimated_monthly_operating_surplus
        metrics = compute_debt_service_metrics(plan, surplus)

        # 2. Build grounded prompt
        prompt = _build_analyst_prompt(profile, plan, metrics, market_intelligence)

        # 3. Call structured LLM
        commentary = self.llm_client.generate_structured(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            schema=FinancialAnalystCommentary,
        )

        return commentary


def run(state: Any) -> Any:
    """LangGraph node execution function matching TECHNICAL_SETUP.md Section 6.2 contract.

    Reads:  state.financial_plan, state.market_intelligence.pricing
    Writes: state.financial_plan.analyst_commentary
    """
    if state.financial_plan is None:
        raise ValueError("FinancialAnalystAgent requires state.financial_plan to be computed first")

    # Extract profile and market intelligence (supports both Pydantic and Dataclass representations)
    profile = getattr(state, "applicant_profile", None) or getattr(state, "entrepreneur_profile", None)
    if profile is None:
        raise ValueError("FinancialAnalystAgent requires applicant/entrepreneur profile in state")

    market_intelligence = getattr(state, "market_intelligence", None)
    market_snapshot: Module1IntelligenceSnapshot | None = None
    if market_intelligence is not None:
        if isinstance(market_intelligence, Module1IntelligenceSnapshot):
            market_snapshot = market_intelligence
        elif isinstance(market_intelligence, dict):
            market_snapshot = Module1IntelligenceSnapshot.model_validate(market_intelligence)
        elif hasattr(market_intelligence, "pricing"):
            pricing_obj = getattr(market_intelligence, "pricing", None)
            market_reach_obj = getattr(market_intelligence, "market_reach", None)
            market_snapshot = Module1IntelligenceSnapshot(
                business_category=getattr(profile, "business_category", "general"),
                location=f"{getattr(profile, 'district', '')}, {getattr(profile, 'state', '')}",
                pricing=PricingSnapshot(
                    representative_price=getattr(pricing_obj, "representative_price", 50.0) if pricing_obj else 50.0,
                    unit=getattr(pricing_obj, "unit", "unit") if pricing_obj else "unit",
                    confidence=getattr(pricing_obj, "confidence", "estimated") if pricing_obj else "estimated",
                ),
                market_reach=MarketReachSnapshot(
                    population_within_radius=getattr(market_reach_obj, "population_within_radius", 25000) if market_reach_obj else 25000,
                ),
            )

    agent = FinancialAnalystAgent()
    commentary = agent.interpret(
        plan=state.financial_plan,
        profile=profile,
        market_intelligence=market_snapshot,
    )

    # Attach commentary to state.financial_plan without altering any deterministic figures
    if is_dataclass(state.financial_plan):
        new_plan = replace(state.financial_plan, analyst_commentary=commentary)
        if is_dataclass(state):
            return replace(state, financial_plan=new_plan)
        else:
            state.financial_plan = new_plan
            return state
    else:
        state.financial_plan.analyst_commentary = commentary
        return state


if __name__ == "__main__":
    from module2_financial.financial_engine import (
        FeasibilityVerdict,
        SchemeTerms,
        build_financial_plan,
    )

    print("=" * 70)
    print("Testing Section 6.2 Financial Analyst Agent")
    print("=" * 70)

    # 1. Create sample applicant profile
    profile = ApplicantProfile(
        available_capital=100_000.0,
        state="Maharashtra",
        district="Nashik",
        business_category="agri_allied",
        is_new_business=True,
        is_woman_owned=True,
        has_udyam_registration=True,
    )

    # 2. Define scheme terms (PMMY worked example)
    terms = SchemeTerms(
        margin_rate=0.10,
        working_capital_rate=0.20,
        interest_rate=0.08,
        tenure_years=7,
        moratorium_months=6,
    )

    # 3. Generate deterministic financial plan
    plan = build_financial_plan(
        available_capital=profile.available_capital,
        feasibility_verdict=FeasibilityVerdict.RECOMMENDED,
        scheme="pmmy",
        applicant_profile=profile,
        scheme_terms=terms,
    )

    print(f"\n[1] Deterministic Engine Output:")
    print(f"  • Scheme: {plan.scheme_name.upper()}")
    print(f"  • Total Project Cost: ₹{plan.project_cost:,.2f}")
    print(f"  • Loan Amount: ₹{plan.loan_amount:,.2f}")
    print(f"  • Capex: ₹{plan.capital_expenditure:,.2f} | Working Capital: ₹{plan.working_capital_requirement:,.2f}")
    print(f"  • Total Installments: {len(plan.repayment_schedule)}")

    # 4. Run Financial Analyst Agent (LLM Reasoning Layer)
    agent = FinancialAnalystAgent()
    commentary = agent.interpret(plan=plan, profile=profile)

    print(f"\n[2] Financial Interpretation (Section 6.2 Output):")
    print(f"\n--- Executive Summary ---\n{commentary.executive_summary}")
    print(f"\n--- Repayment Serviceability ---\n{commentary.repayment_serviceability_assessment}")
    print(f"\n--- Margin of Safety ---\n{commentary.margin_of_safety_analysis}")
    print(f"\n--- Working Capital Adequacy ---\n{commentary.working_capital_adequacy}")
    print(f"\n--- Key Risks ---")
    for i, risk in enumerate(commentary.key_risks, 1):
        print(f"  {i}. {risk}")
    print(f"\n--- Recommendations ---")
    for i, rec in enumerate(commentary.actionable_recommendations, 1):
        print(f"  {i}. {rec}")
    print("\n" + "=" * 70)
