"""
Pydantic schemas for the Hyper-Local Business Advisory platform.

Covers:
  - Confidence labeling (TDD Section 2, "Confidence-labeled outputs")
  - The three agent output contracts this build implements:
        Competitor Agent, Pricing Agent, Supply Chain Agent
    (TDD Section 5.3)
  - The relevant slice of the shared case state object (TDD Section 9)

Only the fields required to support the three agents implemented in this
build are modeled in full. Sections owned by agents not yet built
(market_reach, opportunity, risk, feasibility_record, financial_plan,
application_status, monitoring_record, grievance_log) are represented as
loosely-typed placeholders so this module does not invent behavior for
components outside scope, while still keeping the case state object shape
consistent with Section 9 for when those agents are added later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class Confidence(str, Enum):
    """Per TDD Section 2: every agent output is tagged so downstream
    consumers can distinguish verified findings from inference."""

    REAL_DATA = "REAL_DATA"
    ESTIMATED = "ESTIMATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class SaturationLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------


class SourceRecord(BaseModel):
    """One data source consulted while producing an output."""

    model_config = ConfigDict(extra="forbid")

    name: str
    detail: Optional[str] = None
    confidence: Confidence


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")

    village: Optional[str] = None
    block: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_code: Optional[str] = None  # from Local Government Directory


class SelectedBusiness(BaseModel):
    """The business activity the three agents run against. Produced by the
    (not-yet-built) Business Discovery and Ranking stage."""

    model_config = ConfigDict(extra="forbid")

    name: str
    sector: Optional[str] = None
    ncs_code: Optional[str] = None  # National Industrial Classification ref


# ---------------------------------------------------------------------------
# Competitor Agent
# ---------------------------------------------------------------------------


class NearbyCompetitor(BaseModel):
    """One identified competitor record. Only populated when the
    underlying source returns individual entities (e.g. Overpass); an
    aggregate count-only source (e.g. a bulk Udyam extract queried by
    count) cannot populate this without fabricating records, and will
    leave it empty with a limitation explaining why."""

    model_config = ConfigDict(extra="forbid")

    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = None


class CompetitorAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competitor_count: Optional[int] = None
    nearby_competitors: list[NearbyCompetitor] = Field(default_factory=list)
    density_score: Optional[float] = None  # competitors per unit population
    saturation_level: SaturationLevel = SaturationLevel.UNKNOWN
    geographic_distribution: Optional[str] = None  # e.g. "clustered", "dispersed"
    benchmark_district_density: Optional[float] = None
    benchmark_state_density: Optional[float] = None
    sources: list[SourceRecord] = Field(default_factory=list)
    confidence: Confidence
    limitations: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Pricing Agent
# ---------------------------------------------------------------------------


class PriceRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float
    max: float


class PurchasingPowerContext(BaseModel):
    """Surfaced explicitly so downstream consumers can see the proxy input
    that shaped an ESTIMATED price, rather than only the resulting number."""

    model_config = ConfigDict(extra="forbid")

    district: Optional[str] = None
    asset_index: Optional[float] = None  # normalized 0-1 SECC-derived proxy


class PricingAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_min: Optional[float] = None
    price_max: Optional[float] = None
    representative_price: Optional[float] = None
    currency: str = "INR"
    unit: Optional[str] = None
    pricing_basis: str  # "real_commodity_price" | "purchasing_power_proxy_estimate" | "insufficient_data"
    purchasing_power_context: Optional[PurchasingPowerContext] = None
    recommended_price_range: Optional[PriceRange] = None
    data_source: str
    is_estimated: bool
    confidence: Confidence
    limitations: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Supply Chain Agent
# ---------------------------------------------------------------------------


class SupplierRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = None


class RouteRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: str
    distance_km: Optional[float] = None
    duration_minutes: Optional[float] = None
    accessibility_flag: Optional[str] = None  # e.g. "no_direct_route"


class NearestSupplier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: Optional[str] = None
    distance_km: Optional[float] = None
    duration_minutes: Optional[float] = None


class SupplyChainAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suppliers: list[SupplierRecord] = Field(default_factory=list)
    distribution_points: list[SupplierRecord] = Field(default_factory=list)
    nearest_relevant_supplier_market: Optional[NearestSupplier] = None
    route_risks: list[RouteRisk] = Field(default_factory=list)
    supply_availability_accessibility: str = "unknown"  # "accessible" | "limited" | "unavailable" | "unknown"
    supplier_concentration_flag: Optional[str] = None  # e.g. "single_supplier_dependency"
    dependency_risks: list[str] = Field(default_factory=list)
    vulnerability_summary: list[str] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(default_factory=list)
    confidence: Confidence
    limitations: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Market intelligence section (Section 9: "Market intelligence")
# ---------------------------------------------------------------------------


class MarketIntelligence(BaseModel):
    """Fan-in target for the six Module 1 local intelligence agents.
    Only competitor / pricing / supply_chain are populated by this build;
    market_reach / opportunity / risk are left as None placeholders for the
    agents that own them (out of scope here)."""

    model_config = ConfigDict(extra="allow")  # allow other agents to attach later

    market_reach: Optional[dict[str, Any]] = None
    opportunity: Optional[dict[str, Any]] = None
    risk: Optional[dict[str, Any]] = None
    competitor: Optional[CompetitorAgentOutput] = None
    pricing: Optional[PricingAgentOutput] = None
    supply_chain: Optional[SupplyChainAgentOutput] = None


# ---------------------------------------------------------------------------
# Shared case state (Section 9)
# ---------------------------------------------------------------------------


class CaseState(BaseModel):
    """The single structured case object shared across all agents
    (TDD Section 9). Sections not touched by this build are typed loosely
    (dict/list) rather than modeled, since inventing their shape would be
    outside the scope of the Competitor / Pricing / Supply Chain agents."""

    model_config = ConfigDict(extra="allow")

    case_id: str
    entrepreneur_profile: dict[str, Any] = Field(default_factory=dict)
    business_shortlist: list[dict[str, Any]] = Field(default_factory=list)
    selected_business: Optional[SelectedBusiness] = None
    market_intelligence: MarketIntelligence = Field(default_factory=MarketIntelligence)
    feasibility_record: dict[str, Any] = Field(default_factory=dict)
    financial_plan: dict[str, Any] = Field(default_factory=dict)
    application_status: dict[str, Any] = Field(default_factory=dict)
    monitoring_record: dict[str, Any] = Field(default_factory=dict)
    grievance_log: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: str = Field(default_factory=_utcnow)
