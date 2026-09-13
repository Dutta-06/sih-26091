"""Schemas and data models for Module 2 Financial Interpretation.

Defines Pydantic models for:
1. Market intelligence snapshots (Module 1 inputs / fixtures).
2. Computed debt-serviceability ratios.
3. Strongly-typed LLM financial analyst commentary.
"""

from __future__ import annotations

from typing import Literal
from pydantic import AliasChoices, BaseModel, Field


class PricingSnapshot(BaseModel):
    """Pricing analysis snapshot from Module 1 Pricing Agent."""

    commodity_or_product: str = "general_goods"
    price_min: float | None = None
    price_max: float | None = None
    representative_price: float | None = None
    unit: str = "unit"
    is_estimated: bool = True
    confidence: str = "estimated"


class MarketReachSnapshot(BaseModel):
    """Market reach snapshot from Module 1 Market Reach Agent."""

    population_within_radius: int = 25000
    radius_km: float = 5.0
    estimated_monthly_customer_reach: int = 650
    confidence: str = "estimated"


class CompetitorSnapshot(BaseModel):
    """Competitor snapshot from Module 1 Competitor Agent."""

    competitor_count: int = 3
    saturation_level: str = "medium"
    density_per_10k: float | None = 1.2
    confidence: str = "estimated"


class SeasonalRiskSnapshot(BaseModel):
    """Seasonal demand and risk patterns from Module 1 Risk Agent."""

    sector: str = "general"
    trough_months: list[str] = Field(
        default_factory=lambda: ["July", "August", "September"],
        description="Months with lowest seasonal demand/revenue.",
    )
    peak_months: list[str] = Field(
        default_factory=lambda: ["October", "November", "December"],
        description="Months with highest seasonal demand/revenue.",
    )
    seasonal_curve_multipliers: list[float] = Field(
        default_factory=lambda: [1.05, 1.0, 0.95, 0.85, 0.80, 0.75, 0.70, 0.85, 1.10, 1.25, 1.20, 1.15],
        description="12-month relative demand indices (1.0 = average month, <1.0 = low season).",
    )
    trough_revenue_drop_pct: float = Field(
        default=30.0,
        description="Estimated peak-to-trough drop in monthly revenues.",
    )
    cogs_inflation_shock_pct: float = Field(
        default=15.0,
        description="Plausible input cost/raw material inflation surge.",
    )
    confidence: str = "estimated"


class OperatingEstimates(BaseModel):
    """Projected operating economics informed by Module 1 market analysis."""

    estimated_monthly_revenue: float
    estimated_monthly_cogs: float  # Cost of goods sold / raw materials
    estimated_monthly_opex: float  # Operating expenses (rent, utilities, transport)
    estimated_monthly_operating_surplus: float  # Revenue - COGS - Opex (EBITDA proxy)


class Module1IntelligenceSnapshot(BaseModel):
    """Aggregated Module 1 market intelligence feed for financial reasoning."""

    business_category: str
    location: str
    pricing: PricingSnapshot = Field(default_factory=PricingSnapshot)
    market_reach: MarketReachSnapshot = Field(default_factory=MarketReachSnapshot)
    competitor: CompetitorSnapshot = Field(default_factory=CompetitorSnapshot)
    risk: SeasonalRiskSnapshot = Field(default_factory=SeasonalRiskSnapshot)
    operating_estimates: OperatingEstimates | None = None

    @classmethod
    def create_default_fixture(
        cls,
        business_category: str = "dairy",
        location: str = "Nashik, Maharashtra",
        project_cost: float = 1_000_000,
    ) -> Module1IntelligenceSnapshot:
        """Create realistic baseline operating economics scaled to project size."""
        # Baseline rule: Monthly gross revenue ~ 18-25% of project cost for micro-enterprises
        monthly_rev = round(project_cost * 0.22, 2)
        monthly_cogs = round(monthly_rev * 0.55, 2)
        monthly_opex = round(monthly_rev * 0.18, 2)
        monthly_surplus = round(monthly_rev - monthly_cogs - monthly_opex, 2)

        return cls(
            business_category=business_category,
            location=location,
            pricing=PricingSnapshot(
                commodity_or_product=business_category,
                price_min=45.0,
                price_max=60.0,
                representative_price=52.0,
                unit="litre/kg/unit",
                is_estimated=True,
                confidence="estimated",
            ),
            market_reach=MarketReachSnapshot(
                population_within_radius=35000,
                radius_km=7.0,
                estimated_monthly_customer_reach=850,
                confidence="estimated",
            ),
            competitor=CompetitorSnapshot(
                competitor_count=4,
                saturation_level="medium",
                density_per_10k=1.14,
                confidence="estimated",
            ),
            operating_estimates=OperatingEstimates(
                estimated_monthly_revenue=monthly_rev,
                estimated_monthly_cogs=monthly_cogs,
                estimated_monthly_opex=monthly_opex,
                estimated_monthly_operating_surplus=monthly_surplus,
            ),
        )


class DebtServiceMetrics(BaseModel):
    """Deterministic financial safety metrics computed prior to LLM interpretation."""

    monthly_emi: float = Field(description="Scheduled monthly loan repayment (post-moratorium).")
    monthly_moratorium_interest: float = Field(description="Monthly interest payable during moratorium.")
    projected_monthly_operating_surplus: float = Field(
        description="Projected monthly net cash inflow before debt service."
    )
    dscr: float = Field(
        description="Debt Service Coverage Ratio (Monthly Operating Surplus / Monthly EMI)."
    )
    margin_of_safety_pct: float = Field(
        description="Percentage drop in operating surplus the business can absorb before EMI default."
    )
    working_capital_runway_months: float = Field(
        description="Number of months of full EMI covered by allocated working capital."
    )
    serviceability_status: Literal["comfortable", "adequate", "tight", "insufficient"] = Field(
        description="Categorical debt service safety tier."
    )


class FinancialAnalystCommentary(BaseModel):
    """Section 6.2 Financial Interpretation Structured Output Schema.

    Explains the deterministic numbers in plain language, evaluates whether projected
    operating surplus is sufficient to service the repayment schedule, and highlights
    margin of safety without altering deterministic figures.
    """

    executive_summary: str = Field(
        validation_alias=AliasChoices("executive_summary", "description", "summary", "overview", "executiveSummary"),
        description="Plain-language overview of the funding package, scheme fit, and overall viability."
    )
    repayment_serviceability_assessment: str = Field(
        validation_alias=AliasChoices("repayment_serviceability_assessment", "serviceability_assessment", "repayment_assessment", "repaymentServiceabilityAssessment"),
        description="Detailed evaluation of whether projected operating surplus comfortably services the EMI schedule."
    )
    margin_of_safety_analysis: str = Field(
        validation_alias=AliasChoices("margin_of_safety_analysis", "margin_of_safety", "marginOfSafetyAnalysis"),
        description="Explanation of safety margins and business resilience against revenue dips or cost inflation."
    )
    working_capital_adequacy: str = Field(
        validation_alias=AliasChoices("working_capital_adequacy", "working_capital_analysis", "workingCapitalAdequacy"),
        description="Assessment of allocated working capital and liquidity buffer during initial and low seasons."
    )
    key_risks: list[str] = Field(
        validation_alias=AliasChoices("key_risks", "risks", "keyRisks"),
        description="Top 3 financial and operational risks identified from market & repayment data."
    )
    actionable_recommendations: list[str] = Field(
        validation_alias=AliasChoices("actionable_recommendations", "recommendations", "actionableRecommendations"),
        description="Specific, actionable advice for the entrepreneur and credit underwriting officer."
    )
    confidence_tag: str = Field(
        default="estimated",
        validation_alias=AliasChoices("confidence_tag", "confidence", "confidenceTag"),
        description="Data confidence label reflecting underlying market intelligence."
    )


class ScenarioRunDetail(BaseModel):
    """Outcome of one specific stress-test scenario."""

    name: str = Field(description="Scenario name (e.g., 'Baseline', 'Severe Monsoon Trough', 'Input Cost Surge').")
    description: str
    revenue_multiplier: float
    cogs_multiplier: float
    lowest_monthly_dscr: float
    min_cash_balance: float
    months_in_deficit: int
    is_viable: bool
    summary_observation: str


class StressTestResult(BaseModel):
    """Section 6.3 Scenario and Stress Testing Output Schema.

    Evaluates whether loan repayment remains feasible under seasonal downside
    and cost shock scenarios, tracking liquidity buffers across the repayment schedule.
    """

    baseline_dscr: float = Field(description="DSCR under average/normal operating conditions.")
    trough_dscr: float = Field(description="DSCR during the lowest seasonal demand month.")
    min_cash_reserve: float = Field(description="Lowest cumulative cash balance recorded during loan tenure.")
    months_with_cash_deficit: int = Field(description="Total months where cash flow is insufficient to cover EMI.")
    max_liquidity_shortfall: float = Field(description="Maximum cash shortfall in any single month (0.0 if solvent).")
    break_even_revenue_drop_pct: float = Field(
        description="Maximum tolerable revenue drop percentage before operating surplus fails to cover EMI."
    )
    stress_verdict: Literal["resilient", "vulnerable", "critical_risk"] = Field(
        description="Overall stress-test resilience classification."
    )
    scenario_runs: list[ScenarioRunDetail] = Field(
        default_factory=list,
        description="Detailed comparative outcomes across multiple stress scenarios.",
    )
    risk_mitigation_strategies: list[str] = Field(
        default_factory=list,
        description="Actionable buffer and inventory recommendations to navigate low seasons.",
    )
    llm_stress_interpretation: str | None = Field(
        default=None,
        description="Plain-language interpretation from the LLM on downside resilience.",
    )
    confidence_tag: str = Field(
        default="estimated",
        description="Confidence tag reflecting underlying risk model assumptions.",
    )

