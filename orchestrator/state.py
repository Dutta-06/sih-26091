"""Canonical Shared Case State Schema.

Adheres strictly to TECHNICAL_SETUP.md Section 3 and Technical Design Document Section 9.
Every agent in Modules 1, 2, and 3 reads from and writes to instances of this state.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

# Core Principle: Confidence-labeled outputs (TDD Section 2)
Confidence = Literal["real", "estimated"]


# ---------------------------------------------------------------------------
# Section 5.1 & 5.2: Entrepreneur Profile & Business Discovery Shortlist
# ---------------------------------------------------------------------------

class LocationDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw_query: str = ""
    village: Optional[str] = None
    gram_panchayat: Optional[str] = None
    block: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    lgd_code: Optional[str] = None  # Local Government Directory code


class EntrepreneurProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    location_query: str
    location: LocationDetails = Field(default_factory=LocationDetails)
    available_capital: float = 0.0
    skills: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    land_or_premises: Optional[str] = None
    business_preference: Optional[str] = None
    preference_reason: Optional[str] = None
    social_category: Optional[str] = None
    is_woman_owned: bool = False
    is_shg_member: bool = False


class BusinessCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str
    rationale: str = ""
    rank: int = 1
    feasibility_score: float = 0.0
    indicative_setup_cost: float = 0.0
    infrastructure_readiness: str = "moderate"


# ---------------------------------------------------------------------------
# Section 5.3: Market Intelligence (6 Parallel Agents Fan-In)
# ---------------------------------------------------------------------------

class DistributionPoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    type: str  # e.g., "mandi", "weekly_haat", "retail_cluster", "transport_hub"
    distance_km: float
    coordinates: Optional[tuple[float, float]] = None


class MarketReachIntelligence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    population_within_radius: int = 0
    radius_km: float = 10.0
    consumer_base_estimate: int = 0
    distribution_points: list[DistributionPoint] = Field(default_factory=list)
    nearby_mandis: list[str] = Field(default_factory=list)
    source_confidence: Confidence = "estimated"
    data_source_detail: str = "Census 2011 + Nominatim / Overpass POI"


class OpportunityIntelligence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sector_niche: str = ""
    unserved_demand_niches: list[str] = Field(default_factory=list)
    saturation_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    saturation_score: float = 0.5  # 0 (completely unserved) to 1.0 (heavily saturated)
    supporting_evidence: list[str] = Field(default_factory=list)
    source_confidence: Confidence = "estimated"
    data_source_detail: str = "NABARD/KVIC Model Project Reports"


class RiskIntelligence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    road_distance_to_hub_km: float = 0.0
    supply_route_risk: str = "low"
    seasonal_demand_variation: str = "moderate"
    low_season_months: list[str] = Field(default_factory=list)
    single_buyer_dependency_risk: str = "medium"
    risk_flags: list[str] = Field(default_factory=list)
    mitigation_strategies: list[str] = Field(default_factory=list)
    source_confidence: Confidence = "estimated"
    data_source_detail: str = "OSRM Routing + Agmarknet Price History + Risk Taxonomy"


class CompetitorIntelligence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    estimated_competitor_count: int = 0
    density_per_10k_population: float = 0.0
    benchmark_district_avg_density: float = 0.0
    z_score_vs_district: float = 0.0
    identified_competitors: list[str] = Field(default_factory=list)
    fallback_tier_used: str = "udyam"  # "udyam" | "overpass" | "web_search"
    source_confidence: Confidence = "estimated"
    data_source_detail: str = "Udyam Registration Open Data"


class PricingIntelligence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recommended_price_unit: str = ""
    min_market_price: float = 0.0
    max_market_price: float = 0.0
    optimal_target_price: float = 0.0
    regional_purchasing_power_proxy: str = "medium"  # derived from SECC
    price_source_type: Literal["direct_market_data", "purchasing_power_proxy"] = "purchasing_power_proxy"
    source_confidence: Confidence = "estimated"
    data_source_detail: str = "SECC 2011 Asset Index Proxy / Agmarknet"


class SupplyChainIntelligence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw_material_availability: str = "locally_available"
    major_suppliers: list[str] = Field(default_factory=list)
    transport_modes: list[str] = Field(default_factory=list)
    lead_time_days: int = 3
    critical_vulnerabilities: list[str] = Field(default_factory=list)
    alternate_sources: list[str] = Field(default_factory=list)
    source_confidence: Confidence = "estimated"
    data_source_detail: str = "Supply Graph Traversal (NetworkX)"


class MarketIntelligence(BaseModel):
    """The unified 6-agent fan-in object."""
    model_config = ConfigDict(extra="ignore")

    market_reach: MarketReachIntelligence = Field(default_factory=MarketReachIntelligence)
    opportunity: OpportunityIntelligence = Field(default_factory=OpportunityIntelligence)
    risk: RiskIntelligence = Field(default_factory=RiskIntelligence)
    competitor: CompetitorIntelligence = Field(default_factory=CompetitorIntelligence)
    pricing: PricingIntelligence = Field(default_factory=PricingIntelligence)
    supply_chain: SupplyChainIntelligence = Field(default_factory=SupplyChainIntelligence)


# ---------------------------------------------------------------------------
# Section 5.4 & 5.5: SWOT Synthesis & Adversarial Feasibility Record
# ---------------------------------------------------------------------------

class SWOTAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    budget_scaling_notes: str = ""


class FeasibilityRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    selected_category: str = ""
    swot: SWOTAnalysis = Field(default_factory=SWOTAnalysis)
    verdict: Literal["viable", "marginal", "not_recommended"] = "viable"
    verdict_reasoning: str = ""
    rejection_history: list[str] = Field(default_factory=list)
    adversarial_critique: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Section 6: Module 2 — Financial Structuring and Funding Preparation
# ---------------------------------------------------------------------------

class SchemeTier(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Literal["micro_finance", "term_loan"]
    display_name: str
    max_project_cost: float
    max_loan_amount: float
    interest_rate: float  # annual decimal e.g. 0.065 or 0.08
    tenure_years: int
    moratorium_months: int


class QuarterlyRepaymentInstallment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    quarter_number: int
    is_moratorium: bool
    opening_balance: float
    interest_payment: float
    principal_payment: float
    total_installment: float
    closing_balance: float


class StressTestResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scenario_name: str = "Seasonal Low-Demand Downside"
    revenue_drop_percentage: float = 25.0
    stressed_quarterly_surplus: float = 0.0
    quarterly_installment_due: float = 0.0
    debt_service_coverage_ratio: float = 1.2
    is_sustainable: bool = True
    buffer_recommendation: str = ""


class FinancialPlan(BaseModel):
    """Deterministic core outputs annotated by financial reasoning agents."""
    model_config = ConfigDict(extra="ignore")

    available_margin_capital: float = 0.0
    computed_project_cost: float = 0.0
    maximum_loan_eligibility: float = 0.0
    margin_percentage: float = 10.0
    loan_percentage: float = 90.0

    scheme_tier: SchemeTier
    working_capital_requirement: float = 0.0
    capital_expenditure_allocation: float = 0.0

    repayment_schedule: list[QuarterlyRepaymentInstallment] = Field(default_factory=list)
    total_interest_payable: float = 0.0
    total_repayment_amount: float = 0.0

    analyst_commentary: str = ""
    stress_test_result: Optional[StressTestResult] = None
    policy_explanation: str = ""


class ApplicationStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    form_data: dict[str, Any] = Field(default_factory=dict)
    checklist: dict[str, Literal["complete", "pending", "missing"]] = Field(
        default_factory=lambda: {
            "identity_proof": "pending",
            "address_proof": "pending",
            "quotation_machinery": "pending",
            "caste_certificate": "pending",
            "bank_account_details": "pending",
        }
    )
    disbursement_status: Literal[
        "not_applied", "documents_pending", "under_verification", "sanctioned", "disbursed"
    ] = "not_applied"
    sanctioned_amount: Optional[float] = None
    disbursement_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Section 7: Module 3 — Launch & Post-Disbursement Monitoring
# ---------------------------------------------------------------------------

class LaunchMilestone(BaseModel):
    model_config = ConfigDict(extra="ignore")

    phase_number: int
    title: str
    target_week: int
    tasks: list[str]
    completed: bool = False


class HealthSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    reported_revenue: float = 0.0
    projected_baseline_revenue: float = 0.0
    reported_expenses: float = 0.0
    operating_surplus: float = 0.0
    loan_installment_status: Literal["paid", "grace_period", "overdue"] = "paid"
    health_score: float = 85.0  # 0-100 scale
    early_warning_flag: bool = False
    warning_reason: Optional[str] = None
    approximate_creditworthiness_index: float = 720.0  # labeled approximate
    suggested_intervention: Optional[str] = None
    is_consent_verified: bool = True


class GrievanceEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket_id: str
    issue_type: Literal["supply_delay", "pricing_collapse", "machinery_breakdown", "loan_repayment_stress", "other"]
    description: str
    status: Literal["open", "mentor_assigned", "in_progress", "resolved"] = "open"
    assigned_mentor: Optional[str] = None
    resolution_notes: Optional[str] = None
    logged_at: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Session Meta and Master Case State
# ---------------------------------------------------------------------------

class SessionMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    current_stage: str = "profiling"
    language_code: str = "en"  # "en", "hi", "mr", "ta", etc.
    consent_sms_monitoring: bool = False
    created_at: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    user_turns: int = 0


class CaseState(BaseModel):
    """The master typed state container persisting across the entire lifecycle."""
    model_config = ConfigDict(extra="ignore")

    entrepreneur_profile: Optional[EntrepreneurProfile] = None
    business_shortlist: list[BusinessCandidate] = Field(default_factory=list)

    # 6 Parallel Local Intelligence sub-fields (independent parallel write targets)
    market_reach_intel: Optional[MarketReachIntelligence] = None
    opportunity_intel: Optional[OpportunityIntelligence] = None
    risk_intel: Optional[RiskIntelligence] = None
    competitor_intel: Optional[CompetitorIntelligence] = None
    pricing_intel: Optional[PricingIntelligence] = None
    supply_chain_intel: Optional[SupplyChainIntelligence] = None

    # Unified 6-agent fan-in object
    market_intelligence: Optional[MarketIntelligence] = None
    feasibility_record: Optional[FeasibilityRecord] = None
    financial_plan: Optional[FinancialPlan] = None
    application_status: Optional[ApplicationStatus] = None
    monitoring_record: list[HealthSnapshot] = Field(default_factory=list)
    grievance_log: list[GrievanceEntry] = Field(default_factory=list)
    launch_roadmap: list[LaunchMilestone] = Field(default_factory=list)
    session_meta: SessionMeta
