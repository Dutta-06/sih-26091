"""
Shared case state (TECHNICAL_SETUP.md Section 3 / design doc Section 9).

This implements the FULL state shape described in the design document and
Technical Setup doc so it stays drop-in compatible with the other four
Module 1 agents and Modules 2-3 if/when they're built later. Only the
fields the Market Reach Agent and Opportunity Agent actually read or write
are populated by this repository today; everything else is present as an
Optional/empty placeholder.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, Field

# "real" = sourced from live/verified data; "estimated" = inferred, stale,
# or proxied. Every agent output must carry this tag (design doc Section 2:
# "Confidence-labeled outputs").
Confidence = Literal["real", "estimated"]


# ---------------------------------------------------------------------------
# Entrepreneur profile / business shortlist (Section 5.1-5.2 -- not built by
# this repository; included so market_reach_agent / opportunity_agent have a
# real input contract to read from).
# ---------------------------------------------------------------------------


class EntrepreneurProfile(BaseModel):
    location_query: str  # free-text village/block/district as stated by the user
    available_capital: Optional[float] = None
    skills: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    business_preference: Optional[str] = None
    preference_reason: Optional[str] = None


class BusinessCandidate(BaseModel):
    category: str
    rationale: Optional[str] = None
    rank: Optional[int] = None


# ---------------------------------------------------------------------------
# Market intelligence (Section 5.3 -- the six-agent fan-in). Only
# market_reach and opportunity are implemented; the rest are typed as plain
# dicts so a future Risk/Competitor/Pricing/Supply Chain agent can populate
# them without a schema migration blocking this build.
# ---------------------------------------------------------------------------


class POI(BaseModel):
    name: str
    type: str
    lat: float
    lon: float


class MarketReachOutput(BaseModel):
    population_within_radius: int
    population_data_year: int = 2011
    radius_km: float
    distribution_points: list[POI] = Field(default_factory=list)
    resolved_lat: float
    resolved_lon: float
    lgd_code: Optional[str] = None
    source_confidence: Confidence = "estimated"
    notes: Optional[str] = None


class SubNiche(BaseModel):
    name: str
    saturation: Literal["low", "medium", "high"]
    saturation_basis: str  # "competitor_agent" | "poi_density_proxy" | "no_signal_default"
    rationale: str
    source_confidence: Confidence = "estimated"


class OpportunityOutput(BaseModel):
    sub_niches: list[SubNiche] = Field(default_factory=list)
    source_confidence: Confidence = "estimated"


class MarketIntelligence(BaseModel):
    market_reach: Optional[MarketReachOutput] = None
    opportunity: Optional[OpportunityOutput] = None
    # Not implemented in this repository -- placeholders for future agents,
    # per TECHNICAL_SETUP.md Sections 5.5-5.8 and IMPLEMENTATION_PLAN.md
    # Section 1. opportunity_agent.py checks `competitor` and prefers it
    # over its own POI-density proxy the moment it's populated.
    risk: Optional[dict] = None
    competitor: Optional[dict] = None
    pricing: Optional[dict] = None
    supply_chain: Optional[dict] = None


# ---------------------------------------------------------------------------
# Everything below Module 1's local-intelligence stage is out of scope for
# this build (see IMPLEMENTATION_PLAN.md Section 2) and is included only as
# an untyped placeholder so CaseState matches the full design's shape.
# ---------------------------------------------------------------------------


class FeasibilityRecord(BaseModel):
    swot: Optional[dict] = None
    verdict: Optional[str] = None
    rejection_history: list[dict] = Field(default_factory=list)


class FinancialPlan(BaseModel):
    project_cost: Optional[float] = None
    loan_eligibility: Optional[float] = None
    scheme_tier: Optional[str] = None
    repayment_schedule: Optional[list[dict]] = None
    stress_test_result: Optional[dict] = None
    analyst_commentary: Optional[str] = None
    policy_explanation: Optional[str] = None


class ApplicationStatus(BaseModel):
    form_data: Optional[dict] = None
    checklist: Optional[dict] = None
    disbursement_status: Optional[str] = None


class HealthSnapshot(BaseModel):
    timestamp: dt.datetime
    health_score: Optional[float] = None
    early_warning_flag: bool = False


class GrievanceEntry(BaseModel):
    issue_type: str
    status: str
    assigned_mentor: Optional[str] = None
    resolution: Optional[str] = None


class SessionMeta(BaseModel):
    session_id: str
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    last_updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class CaseState(BaseModel):
    entrepreneur_profile: Optional[EntrepreneurProfile] = None
    business_shortlist: list[BusinessCandidate] = Field(default_factory=list)

    # Addition not named explicitly in the design doc: Figure 3 shows the
    # ranked shortlist feeding straight into the six local-intelligence
    # agents "for the selected activity," which implies a selection step
    # happens upstream (in discovery/orchestration). We surface that
    # selection explicitly here since market_reach_agent and
    # opportunity_agent both need to know which single category to evaluate.
    selected_business_category: Optional[str] = None

    market_intelligence: MarketIntelligence = Field(default_factory=MarketIntelligence)
    feasibility_record: Optional[FeasibilityRecord] = None
    financial_plan: Optional[FinancialPlan] = None
    application_status: Optional[ApplicationStatus] = None
    monitoring_record: list[HealthSnapshot] = Field(default_factory=list)
    grievance_log: list[GrievanceEntry] = Field(default_factory=list)
    session_meta: SessionMeta
