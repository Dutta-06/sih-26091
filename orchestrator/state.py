"""Canonical Shared Case State Schema.

Implements Technical Design Document Section 9 (State and Data Model) and
TECHNICAL_SETUP.md Section 3. Every agent in Modules 1, 2, and 3 reads from and
writes to this single case object.

Conventions
-----------
* Every intelligence output carries ``source_confidence: "real" | "estimated"``
  (TDD Section 2, confidence-labeled outputs). A figure is "real" only when it was
  read from an actual open data source during this run; fixtures, heuristics,
  catalog assumptions and fallbacks are "estimated". Gaps are recorded in
  ``limitations`` instead of being silently filled with plausible numbers.
* The six parallel Module 1 agents write to independent flat fields
  (``market_reach_intel`` ... ``supply_chain_intel``) so that concurrent LangGraph
  writes never collide; ``swot_synthesis`` fans them in to ``market_intelligence``.
* Raw transaction notification (SMS) text is never stored here (TDD Section 7.3);
  only parsed, structured ``TransactionRecord`` values are.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["real", "estimated"]
Level = Literal["low", "medium", "high"]
SaturationLevel = Literal["low", "medium", "high", "unknown"]
Verdict = Literal["viable", "marginal", "not_recommended"]


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class DataSourceRef(_Model):
    """One data source consulted by an agent, with its own confidence label."""

    name: str
    source_confidence: Confidence = "estimated"
    detail: str = ""


class IntelBase(_Model):
    source_confidence: Confidence = "estimated"
    data_source_detail: str = ""
    sources: list[DataSourceRef] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=utc_now_iso)


# ---------------------------------------------------------------------------
# TDD 5.1 & 5.2: Entrepreneur Profile & Business Discovery Shortlist
# ---------------------------------------------------------------------------

class LocationDetails(_Model):
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
    resolution_method: Literal[
        "nominatim", "lgd_table", "census_table", "state_centroid", "unresolved"
    ] = "unresolved"
    source_confidence: Confidence = "estimated"
    candidates_considered: int = 0
    notes: list[str] = Field(default_factory=list)


class EntrepreneurProfile(_Model):
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
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    documents_available: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)  # early constraint identification (5.1)


class BusinessCandidate(_Model):
    category: str
    catalog_id: str = ""
    sector: str = ""
    nic_code: Optional[str] = None
    commodity: Optional[str] = None  # Agmarknet commodity name, if agri-linked
    rationale: str = ""
    rank: int = 1
    feasibility_score: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    indicative_setup_cost: float = 0.0
    min_project_cost: float = 0.0
    infrastructure_readiness: str = "moderate"
    is_user_preference: bool = False
    adjacent_to: Optional[str] = None  # set when proposed as an alternative to a rejected option
    source_confidence: Confidence = "estimated"


# ---------------------------------------------------------------------------
# TDD 5.3: Hyper-Local Market Intelligence (6 parallel agents)
# ---------------------------------------------------------------------------

class DistributionPoint(_Model):
    name: str
    type: str  # "mandi", "weekly_haat", "retail_cluster", "transport_hub", ...
    distance_km: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source_confidence: Confidence = "estimated"


class MarketReachIntelligence(IntelBase):
    population_within_radius: Optional[int] = None
    radius_km: float = 10.0
    consumer_base_estimate: Optional[int] = None
    households_estimate: Optional[int] = None
    population_data_year: Optional[int] = None
    distribution_points: list[DistributionPoint] = Field(default_factory=list)
    nearby_mandis: list[str] = Field(default_factory=list)


class SubNiche(_Model):
    name: str
    description: str = ""
    evidence: list[str] = Field(default_factory=list)
    source_document: Optional[str] = None
    relevance_score: float = 0.0
    saturation_level: SaturationLevel = "unknown"
    saturation_score: Optional[float] = None  # 0 (unserved) .. 1 (saturated)
    saturation_basis: str = ""
    source_confidence: Confidence = "estimated"


class OpportunityIntelligence(IntelBase):
    sector_niche: str = ""
    sub_niches: list[SubNiche] = Field(default_factory=list)
    unserved_demand_niches: list[str] = Field(default_factory=list)
    saturation_level: SaturationLevel = "unknown"
    saturation_score: Optional[float] = None
    supporting_evidence: list[str] = Field(default_factory=list)
    local_feedback_evidence: list[str] = Field(default_factory=list)  # TDD 5.6


class RiskFlag(_Model):
    risk_id: str = ""
    category: Literal["route", "seasonal", "structural", "local_feedback"]
    title: str
    severity: Level = "medium"
    description: str = ""
    mitigation: str = ""
    source_confidence: Confidence = "estimated"


class RiskIntelligence(IntelBase):
    overall_severity: Level = "medium"
    road_distance_to_hub_km: Optional[float] = None
    route_distance_method: Literal["osrm", "haversine_estimate", "unavailable"] = "unavailable"
    supply_route_risk: Level = "medium"
    seasonal_demand_variation: Level = "medium"
    seasonal_index: list[float] = Field(default_factory=list)  # 12 monthly factors, mean 1.0
    seasonal_basis: str = ""
    low_season_months: list[str] = Field(default_factory=list)
    single_buyer_dependency_risk: Level = "medium"
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    mitigation_strategies: list[str] = Field(default_factory=list)


class CompetitorEntry(_Model):
    name: str
    distance_km: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: str = ""


class TierAttempt(_Model):
    tier: Literal["udyam", "overpass", "web_search"]
    status: Literal["used", "no_data", "unavailable", "skipped", "error"]
    detail: str = ""


class CompetitorIntelligence(IntelBase):
    estimated_competitor_count: Optional[int] = None
    density_per_10k_population: Optional[float] = None
    benchmark_district_avg_density: Optional[float] = None
    benchmark_state_avg_density: Optional[float] = None
    z_score_vs_district: Optional[float] = None
    z_score_vs_state: Optional[float] = None
    saturation_level: SaturationLevel = "unknown"
    identified_competitors: list[CompetitorEntry] = Field(default_factory=list)
    fallback_tier_used: Literal["udyam", "overpass", "web_search", "none"] = "none"
    tiers_attempted: list[TierAttempt] = Field(default_factory=list)


class PricePoint(_Model):
    label: str
    value: float
    unit: str = ""
    source_confidence: Confidence = "estimated"
    source: str = ""


class MonthlyPrice(_Model):
    month: str  # "YYYY-MM"
    modal_price: float


class PricingIntelligence(IntelBase):
    recommended_price_unit: str = ""
    min_market_price: Optional[float] = None
    max_market_price: Optional[float] = None
    optimal_target_price: Optional[float] = None
    price_points: list[PricePoint] = Field(default_factory=list)
    regional_purchasing_power_proxy: Optional[Level] = None
    purchasing_power_index: Optional[float] = None  # 1.0 = national reference
    price_source_type: Literal["direct_market_data", "purchasing_power_proxy", "unavailable"] = "unavailable"
    monthly_price_history: list[MonthlyPrice] = Field(default_factory=list)


class SupplyNode(_Model):
    name: str
    role: Literal["input_supplier", "enterprise", "processor", "logistics", "buyer"]
    distance_km: Optional[float] = None
    source_confidence: Confidence = "estimated"


class SupplyEdge(_Model):
    source: str
    target: str
    transport_mode: str = ""
    lead_time_days: Optional[float] = None
    reliability: Optional[float] = None


class SupplyChainIntelligence(IntelBase):
    raw_material_availability: Literal["locally_available", "regionally_available", "scarce", "unknown"] = "unknown"
    nodes: list[SupplyNode] = Field(default_factory=list)
    edges: list[SupplyEdge] = Field(default_factory=list)
    major_suppliers: list[str] = Field(default_factory=list)
    transport_modes: list[str] = Field(default_factory=list)
    lead_time_days: Optional[float] = None
    single_points_of_failure: list[str] = Field(default_factory=list)
    critical_vulnerabilities: list[str] = Field(default_factory=list)
    alternate_sources: list[str] = Field(default_factory=list)


class MarketIntelligence(_Model):
    """The unified 6-agent fan-in object (TDD Section 9)."""

    market_reach: MarketReachIntelligence = Field(default_factory=MarketReachIntelligence)
    opportunity: OpportunityIntelligence = Field(default_factory=OpportunityIntelligence)
    risk: RiskIntelligence = Field(default_factory=RiskIntelligence)
    competitor: CompetitorIntelligence = Field(default_factory=CompetitorIntelligence)
    pricing: PricingIntelligence = Field(default_factory=PricingIntelligence)
    supply_chain: SupplyChainIntelligence = Field(default_factory=SupplyChainIntelligence)
    missing_branches: list[str] = Field(default_factory=list)

    def confidence_summary(self) -> dict[str, Confidence]:
        return {
            name: getattr(self, name).source_confidence
            for name in ("market_reach", "opportunity", "risk", "competitor", "pricing", "supply_chain")
        }


# ---------------------------------------------------------------------------
# TDD 5.4 & 5.5: SWOT Synthesis, Adversarial Review, Alternative Path
# ---------------------------------------------------------------------------

class SWOTAnalysis(_Model):
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    budget_scaling_notes: str = ""
    grounding_sources: list[str] = Field(default_factory=list)


class RejectionEntry(_Model):
    category: str
    catalog_id: str = ""
    verdict: Verdict
    reasons: list[str] = Field(default_factory=list)
    attempt_number: int = 1
    logged_at: str = Field(default_factory=utc_now_iso)


class FeasibilityRecord(_Model):
    selected_category: str = ""
    selected_catalog_id: str = ""
    preference_reason_context: str = ""
    swot: SWOTAnalysis = Field(default_factory=SWOTAnalysis)
    verdict: Verdict = "marginal"
    verdict_reasoning: str = ""
    adversarial_critique: list[str] = Field(default_factory=list)
    rejection_history: list[RejectionEntry] = Field(default_factory=list)
    attempt_number: int = 1
    alternatives_exhausted: bool = False
    timestamp: str = Field(default_factory=utc_now_iso)

    def rejected_catalog_ids(self) -> set[str]:
        return {r.catalog_id for r in self.rejection_history if r.catalog_id}


# ---------------------------------------------------------------------------
# TDD 6: Module 2 — Financial Structuring and Funding Preparation
# ---------------------------------------------------------------------------

class SchemeTier(_Model):
    name: Literal["micro_finance", "term_loan"]
    display_name: str
    max_project_cost: float
    max_loan_amount: float
    interest_rate: float  # annual decimal e.g. 0.065 or 0.08
    tenure_years: int
    moratorium_months: int


class QuarterlyRepaymentInstallment(_Model):
    quarter_number: int
    is_moratorium: bool
    opening_balance: float
    interest_payment: float
    principal_payment: float
    total_installment: float
    closing_balance: float


class OperatingProjection(_Model):
    """Indicative operating model used by the analyst and stress test (estimated)."""

    annual_revenue: float
    operating_margin: float
    annual_operating_surplus: float
    quarterly_operating_surplus: float
    basis: list[str] = Field(default_factory=list)
    source_confidence: Confidence = "estimated"


class StressTestResult(_Model):
    scenario_name: str = "Low-season downside"
    revenue_drop_percentage: float = 0.0
    seasonal_basis: str = ""
    stressed_quarterly_surplus: float = 0.0
    quarterly_installment_due: float = 0.0
    debt_service_coverage_ratio: float = 0.0  # minimum quarterly DSCR over the stressed year
    quarterly_dscr: list[float] = Field(default_factory=list)
    deficit_quarters: int = 0
    is_sustainable: bool = False
    buffer_recommendation: str = ""
    source_confidence: Confidence = "estimated"


class FinancialPlan(_Model):
    """Deterministic core outputs annotated by financial reasoning agents."""

    eligibility_status: Literal["eligible", "outside_scheme_range", "invalid_input"] = "eligible"
    ineligibility_reason: Optional[str] = None

    available_margin_capital: float = 0.0
    computed_project_cost: float = 0.0
    maximum_loan_eligibility: float = 0.0
    margin_percentage: float = 10.0
    loan_percentage: float = 90.0
    loan_cap_applied: bool = False

    scheme_tier: Optional[SchemeTier] = None
    working_capital_requirement: float = 0.0
    capital_expenditure_allocation: float = 0.0

    repayment_schedule: list[QuarterlyRepaymentInstallment] = Field(default_factory=list)
    regular_quarterly_installment: float = 0.0
    total_interest_payable: float = 0.0
    total_repayment_amount: float = 0.0

    # Reasoning periphery (never alters the figures above)
    operating_projection: Optional[OperatingProjection] = None
    base_debt_service_coverage_ratio: Optional[float] = None
    analyst_commentary: str = ""
    analyst_commentary_source: Literal["llm", "deterministic_template", ""] = ""
    stress_test_result: Optional[StressTestResult] = None
    scenarios: list[StressTestResult] = Field(default_factory=list)
    policy_explanation: str = ""
    policy_sources: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    process_steps: list[str] = Field(default_factory=list)


DocumentState = Literal["complete", "pending", "missing"]
DisbursementStatus = Literal[
    "not_applied",
    "documents_pending",
    "submitted",
    "under_verification",
    "sanctioned",
    "disbursed",
    "rejected",
]


class FormPackage(_Model):
    form_id: str
    title: str
    fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


class StatusTransition(_Model):
    from_status: DisbursementStatus
    to_status: DisbursementStatus
    reason: str = ""
    actor: str = "system"
    at: str = Field(default_factory=utc_now_iso)


class ApplicationStatus(_Model):
    form_data: dict[str, Any] = Field(default_factory=dict)
    forms: list[FormPackage] = Field(default_factory=list)
    checklist: dict[str, DocumentState] = Field(default_factory=dict)
    next_required_field: Optional[str] = None  # asked conversationally, one at a time
    next_required_prompt: Optional[str] = None
    disbursement_status: DisbursementStatus = "not_applied"
    status_history: list[StatusTransition] = Field(default_factory=list)
    sanctioned_amount: Optional[float] = None
    disbursement_date: Optional[str] = None
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# TDD 7: Module 3 — Launch & Post-Disbursement Monitoring
# ---------------------------------------------------------------------------

class ProcurementRecommendation(_Model):
    cluster_id: str
    district: str
    business_category: str
    pooled_items: list[str] = Field(default_factory=list)
    enrolled_peer_count: int = 0
    status: Literal["open", "ready_to_order", "insufficient_peers"] = "open"
    notes: list[str] = Field(default_factory=list)


class LaunchMilestone(_Model):
    phase_number: int
    title: str
    target_week: int
    tasks: list[str]
    theme: Literal["supplier_discovery", "licensing", "inventory", "customer_acquisition", "operations"] = "operations"
    completed: bool = False


class TransactionRecord(_Model):
    """Structured fields parsed from a consented notification; raw text is discarded."""

    occurred_at: str
    direction: Literal["credit", "debit"]
    amount: float
    channel: Literal["upi", "neft_imps", "cash_deposit", "card", "atm", "other"] = "other"
    is_loan_repayment: bool = False


class HealthSnapshot(_Model):
    timestamp: str = Field(default_factory=utc_now_iso)
    period_label: str = ""
    period_days: Optional[int] = None
    transactions_parsed: int = 0
    credit_transaction_count: int = 0
    reported_revenue: float = 0.0
    projected_baseline_revenue: float = 0.0
    reported_expenses: float = 0.0
    operating_surplus: float = 0.0
    installment_due: float = 0.0
    loan_installment_status: Literal["paid", "grace_period", "overdue", "not_due", "unknown"] = "unknown"
    health_score: Optional[float] = None  # 0-100
    health_band: Optional[Literal["healthy", "watch", "at_risk"]] = None
    early_warning_flag: bool = False
    warning_reason: Optional[str] = None
    intervention_type: Optional[
        Literal["pricing_adjustment", "supply_chain_change", "mentor_outreach", "repayment_counselling"]
    ] = None
    suggested_intervention: Optional[str] = None
    approximate_creditworthiness_index: Optional[float] = None  # 0-100, NOT a credit score
    creditworthiness_label: str = "Approximate indicator derived from consented transaction notifications; not a formal credit score."
    coverage_note: str = "Covers only notifications received on the entrepreneur's device; coverage is approximate."
    is_consent_verified: bool = False
    limitations: list[str] = Field(default_factory=list)


class GrievanceEntry(_Model):
    ticket_id: str
    issue_type: Literal["supply_delay", "pricing_collapse", "machinery_breakdown", "loan_repayment_stress", "other"]
    description: str
    status: Literal["open", "mentor_assigned", "in_progress", "resolved"] = "open"
    assigned_mentor: Optional[str] = None
    intervention_suggested: Optional[str] = None
    resolution_notes: Optional[str] = None
    case_context: dict[str, Any] = Field(default_factory=dict)
    health_score_at_logging: Optional[float] = None
    health_score_after: Optional[float] = None
    outcome_improved: Optional[bool] = None
    logged_at: str = Field(default_factory=utc_now_iso)


class OutcomeLearningStatus(_Model):
    real_records: int = 0
    synthetic_records: int = 0
    is_synthetic_dominant: bool = True
    category_prior: Optional[float] = None  # multiplier applied by discovery ranking
    status_note: str = ""


# ---------------------------------------------------------------------------
# Session Meta and Master Case State
# ---------------------------------------------------------------------------

EntryStage = Literal["profiling", "application", "launch", "monitoring", "grievance", "scheme_inquiry"]


class SessionMeta(_Model):
    session_id: str
    current_stage: str = "profiling"
    requested_stage: Optional[EntryStage] = None  # set by the router; read by the graph entry node
    last_intent: Optional[str] = None
    language_code: str = "en"
    translation_status: Literal["not_needed", "translated", "unavailable"] = "not_needed"
    consent_sms_monitoring: bool = False
    pending_slot: Optional[str] = None
    pending_grievance_text: Optional[str] = None
    pending_transactions: list[TransactionRecord] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    user_turns: int = 0


class CaseState(_Model):
    """The master typed state container persisting across the entire lifecycle."""

    entrepreneur_profile: Optional[EntrepreneurProfile] = None
    business_shortlist: list[BusinessCandidate] = Field(default_factory=list)

    # 6 parallel local intelligence write targets (fanned in by swot_synthesis)
    market_reach_intel: Optional[MarketReachIntelligence] = None
    opportunity_intel: Optional[OpportunityIntelligence] = None
    risk_intel: Optional[RiskIntelligence] = None
    competitor_intel: Optional[CompetitorIntelligence] = None
    pricing_intel: Optional[PricingIntelligence] = None
    supply_chain_intel: Optional[SupplyChainIntelligence] = None

    market_intelligence: Optional[MarketIntelligence] = None
    feasibility_record: Optional[FeasibilityRecord] = None
    financial_plan: Optional[FinancialPlan] = None
    application_status: Optional[ApplicationStatus] = None
    procurement_recommendation: Optional[ProcurementRecommendation] = None
    launch_roadmap: list[LaunchMilestone] = Field(default_factory=list)
    monitoring_record: list[HealthSnapshot] = Field(default_factory=list)
    grievance_log: list[GrievanceEntry] = Field(default_factory=list)
    outcome_learning: Optional[OutcomeLearningStatus] = None
    scheme_reference: Optional[str] = None  # plain-language scheme rules for inquiries made before a plan exists
    session_meta: SessionMeta

    def selected_candidate(self) -> Optional[BusinessCandidate]:
        """The activity currently under assessment: top of the (re-ranked) shortlist."""
        return self.business_shortlist[0] if self.business_shortlist else None
