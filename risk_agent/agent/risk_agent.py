"""
module1_feasibility/risk_agent.py

Deterministic Risk Agent for Module 1: Hyper-Local Market Intelligence.

Evaluates three independent risk dimensions:

1. Route / Supply-Chain Risk
   - OSRM road routing when available.
   - Haversine-based fallback when OSRM is unavailable.

2. Seasonal Price / Demand Risk
   - statsmodels seasonal_decompose when sufficient history exists.
   - coefficient-of-variation fallback for shorter histories.

3. Structural Business Risk
   - Retrieves relevant risk categories from a curated taxonomy.
   - Severity is assigned only by deterministic rules.
   - No LLM is used.

Reads:
    state.entrepreneur_profile
    state.business_shortlist
    state.market_intelligence.market_reach
    state.market_intelligence.pricing
    state.market_intelligence.competitor

Writes:
    state.market_intelligence.risk

The orchestration graph / fan-out / fan-in remains outside this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import os
import re
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from pydantic import BaseModel, Field
from statsmodels.tsa.seasonal import seasonal_decompose


# ============================================================
# 1. CONFIGURATION
# ============================================================

OSRM_BASE_URL = os.getenv(
    "OSRM_BASE_URL",
    "http://localhost:5000",
)

RISK_TAXONOMY_SOURCE_DIR = os.getenv(
    "RISK_TAXONOMY_SOURCE_DIR",
    "data/risk_taxonomy",
)


# ============================================================
# 2. ENUMS
# ============================================================

class Confidence(str, Enum):
    REAL = "real"
    ESTIMATED = "estimated"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================
# 3. STATE MODELS
# ============================================================

class Coordinates(BaseModel):
    lat: float
    lon: float


class RiskFlag(BaseModel):
    category: str
    severity: Severity
    description: str
    confidence: Confidence


class EntrepreneurProfile(BaseModel):
    """
    Input produced by the profiling agent.
    """

    location: Coordinates

    structural_context: Dict[str, str] = Field(
        default_factory=dict
    )


class BusinessCandidate(BaseModel):
    """
    Business selected by the discovery agent.
    """

    business_category: str
    selected: bool = False


class MarketReachRecord(BaseModel):
    """
    Output produced by the market-reach agent.
    """

    population_within_radius: Optional[int] = None

    distribution_points: List[Coordinates] = Field(
        default_factory=list
    )

    source_confidence: Literal[
        "real",
        "estimated",
    ] = "estimated"


class PricingRecord(BaseModel):
    """
    Output produced by the pricing agent.
    """

    commodity_price_series: List[float] = Field(
        default_factory=list
    )

    price_series_start: Optional[str] = None

    source_confidence: Literal[
        "real",
        "estimated",
    ] = "estimated"


class CompetitorRecord(BaseModel):
    """
    Output produced by the competitor agent.
    """

    market_saturation: Optional[str] = None

    source_confidence: Literal[
        "real",
        "estimated",
    ] = "estimated"


class RiskRecord(BaseModel):
    """
    Complete output of the Risk Agent.
    """

    overall_severity: Severity

    route_risk: RiskFlag

    seasonal_risk: RiskFlag

    structural_risk_flags: List[RiskFlag] = Field(
        default_factory=list
    )

    plain_language_summary: str

    raw_metrics: Dict[str, float] = Field(
        default_factory=dict
    )

    source_confidence: Literal[
        "real",
        "estimated",
    ] = "estimated"


class MarketIntelligence(BaseModel):
    """
    Shared Module 1 state.
    """

    market_reach: Optional[MarketReachRecord] = None

    pricing: Optional[PricingRecord] = None

    competitor: Optional[CompetitorRecord] = None

    risk: Optional[RiskRecord] = None

    opportunity: Optional[dict] = None

    supply_chain: Optional[dict] = None


class CaseState(BaseModel):
    """
    Minimal state required by the Risk Agent.

    In the actual project, replace this with:

        from orchestrator.state import CaseState
    """

    entrepreneur_profile: Optional[
        EntrepreneurProfile
    ] = None

    business_shortlist: List[
        BusinessCandidate
    ] = Field(default_factory=list)

    market_intelligence: Optional[
        MarketIntelligence
    ] = None


# ============================================================
# 4. RESULT / ANALYSIS DATA STRUCTURES
# ============================================================

@dataclass(frozen=True)
class RouteAnalysis:
    flag: RiskFlag
    distance_km: float
    confidence: Confidence


@dataclass(frozen=True)
class SeasonalAnalysis:
    flag: RiskFlag
    amplitude_ratio: float
    confidence: Confidence


@dataclass(frozen=True)
class RiskAnalysisResult:
    route: RouteAnalysis
    seasonal: SeasonalAnalysis
    structural_flags: tuple[RiskFlag, ...]
    overall_severity: Severity
    summary: str
    source_confidence: Literal[
        "real",
        "estimated",
    ]


# ============================================================
# 5. ROUTE RISK
# ============================================================

class RouteRiskAnalyzer:
    """
    Calculates supply-chain route risk.

    OSRM:
        Real road distance.

    Fallback:
        Haversine distance × 1.3.

    Thresholds:
        <= 15 km : LOW
        <= 40 km : MEDIUM
        > 40 km  : HIGH
    """

    LOW_KM = 15.0
    MEDIUM_KM = 40.0

    def __init__(
        self,
        base_url: str = OSRM_BASE_URL,
    ) -> None:
        self.base_url = base_url.rstrip("/")

    def _query_osrm(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> Optional[float]:

        url = (
            f"{self.base_url}/route/v1/driving/"
            f"{origin.lon},{origin.lat};"
            f"{destination.lon},{destination.lat}"
            f"?overview=false"
        )

        try:
            response = requests.get(
                url,
                timeout=6,
            )

            response.raise_for_status()

            data = response.json()

            routes = data.get("routes", [])

            if not routes:
                return None

            distance_meters = float(
                routes[0]["distance"]
            )

            return distance_meters / 1000.0

        except Exception:
            return None

    @staticmethod
    def _haversine_km(
        a: Coordinates,
        b: Coordinates,
    ) -> float:

        earth_radius_km = 6371.0

        dlat = math.radians(
            b.lat - a.lat
        )

        dlon = math.radians(
            b.lon - a.lon
        )

        value = (
            math.sin(dlat / 2) ** 2
            +
            math.cos(math.radians(a.lat))
            *
            math.cos(math.radians(b.lat))
            *
            math.sin(dlon / 2) ** 2
        )

        value = min(
            1.0,
            max(0.0, value),
        )

        return (
            2
            * earth_radius_km
            * math.asin(math.sqrt(value))
        )

    @classmethod
    def _severity(
        cls,
        distance_km: float,
    ) -> Severity:

        if distance_km <= cls.LOW_KM:
            return Severity.LOW

        if distance_km <= cls.MEDIUM_KM:
            return Severity.MEDIUM

        return Severity.HIGH

    def analyze(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> RouteAnalysis:

        distance_km = self._query_osrm(
            origin,
            destination,
        )

        if distance_km is not None:
            confidence = Confidence.REAL
            source_text = "OSRM road route"
        else:
            distance_km = (
                self._haversine_km(
                    origin,
                    destination,
                )
                * 1.3
            )

            confidence = Confidence.ESTIMATED
            source_text = "Haversine estimate"

        severity = self._severity(
            distance_km
        )

        flag = RiskFlag(
            category="supply_route_accessibility",
            severity=severity,
            description=(
                f"Nearest distribution point is "
                f"{distance_km:.1f} km away by road "
                f"({source_text})."
            ),
            confidence=confidence,
        )

        return RouteAnalysis(
            flag=flag,
            distance_km=distance_km,
            confidence=confidence,
        )


# ============================================================
# 6. SEASONAL PRICE RISK
# ============================================================

class SeasonalRiskAnalyzer:
    """
    Calculates seasonal price/demand variation.

    >= 24 observations:
        seasonal_decompose(period=12)

    < 24 observations:
        coefficient-of-variation estimate.

    Thresholds:
        < 8%  : LOW
        < 20% : MEDIUM
        >=20% : HIGH
    """

    LOW_AMPLITUDE = 0.08
    MEDIUM_AMPLITUDE = 0.20

    @classmethod
    def _severity(
        cls,
        amplitude_ratio: float,
    ) -> Severity:

        if amplitude_ratio < cls.LOW_AMPLITUDE:
            return Severity.LOW

        if amplitude_ratio < cls.MEDIUM_AMPLITUDE:
            return Severity.MEDIUM

        return Severity.HIGH

    @staticmethod
    def _clean_prices(
        prices: List[float],
    ) -> List[float]:

        clean = []

        for value in prices:

            try:
                value = float(value)

                if math.isfinite(value):
                    clean.append(value)

            except (TypeError, ValueError):
                continue

        return clean

    def analyze(
        self,
        prices: List[float],
        start_period: str,
    ) -> SeasonalAnalysis:

        clean_prices = self._clean_prices(
            prices
        )

        # ----------------------------------------------------
        # No data
        # ----------------------------------------------------

        if not clean_prices:

            flag = RiskFlag(
                category="seasonal_price_demand_variation",
                severity=Severity.LOW,
                description=(
                    "No commodity price history "
                    "was available for seasonal analysis."
                ),
                confidence=Confidence.ESTIMATED,
            )

            return SeasonalAnalysis(
                flag=flag,
                amplitude_ratio=0.0,
                confidence=Confidence.ESTIMATED,
            )

        # ----------------------------------------------------
        # Short history
        # ----------------------------------------------------

        if len(clean_prices) < 24:

            mean_price = float(
                np.mean(clean_prices)
            )

            std_price = float(
                np.std(clean_prices)
            )

            amplitude_ratio = (
                std_price
                / (abs(mean_price) + 1e-6)
            )

            confidence = Confidence.ESTIMATED

        # ----------------------------------------------------
        # Full seasonal decomposition
        # ----------------------------------------------------

        else:

            try:

                index = pd.period_range(
                    start=start_period,
                    periods=len(clean_prices),
                    freq="M",
                )

                series = pd.Series(
                    clean_prices,
                    index=index.to_timestamp(),
                )

                decomposition = seasonal_decompose(
                    series,
                    model="additive",
                    period=12,
                    extrapolate_trend=False,
                )

                seasonal_component = (
                    decomposition.seasonal
                )

                trend_component = (
                    decomposition.trend.dropna()
                )

                if trend_component.empty:
                    raise ValueError(
                        "Trend decomposition returned no values."
                    )

                seasonal_amplitude = float(
                    seasonal_component.max()
                    -
                    seasonal_component.min()
                )

                trend_mean = float(
                    trend_component.mean()
                )

                amplitude_ratio = (
                    seasonal_amplitude
                    / (abs(trend_mean) + 1e-6)
                )

                confidence = Confidence.REAL

            except Exception:

                mean_price = float(
                    np.mean(clean_prices)
                )

                std_price = float(
                    np.std(clean_prices)
                )

                amplitude_ratio = (
                    std_price
                    / (abs(mean_price) + 1e-6)
                )

                confidence = Confidence.ESTIMATED

        severity = self._severity(
            amplitude_ratio
        )

        flag = RiskFlag(
            category="seasonal_price_demand_variation",
            severity=severity,
            description=(
                f"Observed seasonal/price variation "
                f"is approximately "
                f"{amplitude_ratio * 100:.1f}% "
                f"relative to the underlying price level."
            ),
            confidence=confidence,
        )

        return SeasonalAnalysis(
            flag=flag,
            amplitude_ratio=amplitude_ratio,
            confidence=confidence,
        )


# ============================================================
# 7. RISK TAXONOMY
# ============================================================

@dataclass(frozen=True)
class RiskTaxonomyEntry:
    risk_id: str
    text: str


class RiskTaxonomy:

    DEFAULT_ENTRIES = (

        RiskTaxonomyEntry(
            "single_buyer_dependency",
            (
                "Business relies on one buyer or a very small "
                "number of buyers, creating buyer concentration risk."
            ),
        ),

        RiskTaxonomyEntry(
            "perishability_risk",
            (
                "Product is perishable and requires cold storage "
                "or rapid sale, creating spoilage risk."
            ),
        ),

        RiskTaxonomyEntry(
            "raw_material_dependency",
            (
                "Business depends heavily on a single supplier "
                "or raw material source."
            ),
        ),

        RiskTaxonomyEntry(
            "regulatory_licensing_risk",
            (
                "Business requires licenses, permits, or "
                "regulatory approvals."
            ),
        ),

        RiskTaxonomyEntry(
            "capital_intensity_risk",
            (
                "Business requires high upfront capital relative "
                "to expected early revenue."
            ),
        ),

        RiskTaxonomyEntry(
            "market_saturation_risk",
            (
                "Local market has a high density of competing "
                "businesses, limiting achievable market share."
            ),
        ),

        RiskTaxonomyEntry(
            "skill_dependency_risk",
            (
                "Business requires specialised skills that the "
                "entrepreneur may not yet possess."
            ),
        ),

        RiskTaxonomyEntry(
            "infrastructure_dependency_risk",
            (
                "Business depends on reliable electricity, water, "
                "internet, roads, or other infrastructure."
            ),
        ),
    )

    def __init__(
        self,
        source_dir: str = RISK_TAXONOMY_SOURCE_DIR,
    ) -> None:

        self.entries = self._load_entries(
            source_dir
        )

    def _load_entries(
        self,
        source_dir: str,
    ) -> tuple[RiskTaxonomyEntry, ...]:

        if not os.path.isdir(source_dir):
            return self.DEFAULT_ENTRIES

        loaded = []

        for filename in sorted(
            os.listdir(source_dir)
        ):

            path = os.path.join(
                source_dir,
                filename,
            )

            if not os.path.isfile(path):
                continue

            try:

                with open(
                    path,
                    "r",
                    encoding="utf-8",
                ) as file:

                    text = file.read().strip()

                if not text:
                    continue

                risk_id = os.path.splitext(
                    filename
                )[0]

                loaded.append(
                    RiskTaxonomyEntry(
                        risk_id=risk_id,
                        text=text,
                    )
                )

            except OSError:
                continue

        if loaded:
            return tuple(loaded)

        return self.DEFAULT_ENTRIES

    @staticmethod
    def _tokens(text: str) -> set[str]:
        """
        Tokenise normal words as well as identifiers such as:

            buyer_count
            cold-storage
            license_required
        """

        text = str(text).lower()

        tokens = re.findall(
            r"[a-z0-9]+",
            text,
        )

        return set(tokens)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[RiskTaxonomyEntry]:

        query_tokens = self._tokens(
            query
        )

        scored = []

        for entry in self.entries:

            entry_tokens = self._tokens(
                f"{entry.risk_id} {entry.text}"
            )

            overlap = len(
                query_tokens & entry_tokens
            )

            scored.append(
                (
                    overlap,
                    entry.risk_id,
                    entry,
                )
            )

        # Deterministic sorting:
        # higher overlap first, then risk_id.
        scored.sort(
            key=lambda item: (
                -item[0],
                item[1],
            )
        )

        return [
            entry
            for score, _, entry in scored[:top_k]
            if score > 0
        ]


# ============================================================
# 8. STRUCTURAL RISK ANALYZER
# ============================================================

class StructuralRiskAnalyzer:

    def __init__(
        self,
        taxonomy: Optional[RiskTaxonomy] = None,
    ) -> None:

        self.taxonomy = (
            taxonomy
            if taxonomy is not None
            else RiskTaxonomy()
        )

    @staticmethod
    def _normalise_context(
        context: Dict[str, str],
    ) -> Dict[str, str]:

        return {
            str(key).strip().lower():
            str(value).strip().lower()
            for key, value in context.items()
        }

    @staticmethod
    def _severity_for(
        risk_id: str,
        context: Dict[str, str],
    ) -> Optional[Severity]:

        context = (
            StructuralRiskAnalyzer
            ._normalise_context(context)
        )

        # ----------------------------------------------------
        # Buyer concentration
        # ----------------------------------------------------

        if risk_id == "single_buyer_dependency":

            buyer_count = context.get(
                "buyer_count"
            )

            if buyer_count is None:
                return None

            if buyer_count == "1":
                return Severity.HIGH

            try:

                count = int(
                    buyer_count
                )

                if count <= 3:
                    return Severity.MEDIUM

                return Severity.LOW

            except ValueError:
                return None

        # ----------------------------------------------------
        # Perishability
        # ----------------------------------------------------

        if risk_id == "perishability_risk":

            if context.get("perishable") != "yes":
                return None

            cold_storage = context.get(
                "cold_storage"
            )

            if cold_storage == "no":
                return Severity.HIGH

            if cold_storage == "yes":
                return Severity.MEDIUM

            return None

        # ----------------------------------------------------
        # Supplier dependency
        # ----------------------------------------------------

        if risk_id == "raw_material_dependency":

            if context.get(
                "single_supplier"
            ) == "yes":

                return Severity.HIGH

            return None

        # ----------------------------------------------------
        # Licensing
        # ----------------------------------------------------

        if risk_id == "regulatory_licensing_risk":

            value = context.get(
                "license_required"
            )

            if value is None:
                return None

            if value in {
                "no",
                "none",
                "false",
                "0",
            }:
                return None

            return Severity.MEDIUM

        # ----------------------------------------------------
        # Capital intensity
        # ----------------------------------------------------

        if risk_id == "capital_intensity_risk":

            mapping = {
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
            }

            return mapping.get(
                context.get(
                    "capital_intensity"
                )
            )

        # ----------------------------------------------------
        # Market saturation
        # ----------------------------------------------------

        if risk_id == "market_saturation_risk":

            mapping = {
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
            }

            return mapping.get(
                context.get(
                    "market_saturation"
                )
            )

        # ----------------------------------------------------
        # Skill dependency
        # ----------------------------------------------------

        if risk_id == "skill_dependency_risk":

            mapping = {
                "low": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "high": Severity.LOW,
            }

            return mapping.get(
                context.get(
                    "skill_experience"
                )
            )

        # ----------------------------------------------------
        # Infrastructure
        # ----------------------------------------------------

        if risk_id == "infrastructure_dependency_risk":

            mapping = {
                "poor": Severity.HIGH,
                "intermittent": Severity.MEDIUM,
                "reliable": Severity.LOW,
            }

            return mapping.get(
                context.get(
                    "infrastructure_reliability"
                )
            )

        return None

    def analyze(
        self,
        business_category: str,
        context: Dict[str, str],
    ) -> tuple[RiskFlag, ...]:

        query = (
            f"{business_category} "
            + " ".join(
                f"{key} {value}"
                for key, value in context.items()
            )
        )

        # Retrieve all possible relevant entries.
        # Since the taxonomy is deliberately small, this remains
        # deterministic and inexpensive.
        matches = self.taxonomy.retrieve(
            query,
            top_k=len(self.taxonomy.entries),
        )

        flags = []

        for match in matches:

            severity = self._severity_for(
                match.risk_id,
                context,
            )

            if severity is None:
                continue

            flags.append(
                RiskFlag(
                    category=match.risk_id,
                    severity=severity,
                    description=match.text,
                    confidence=Confidence.ESTIMATED,
                )
            )

        # Deterministic ordering.
        flags.sort(
            key=lambda flag: (
                {
                    Severity.HIGH: 0,
                    Severity.MEDIUM: 1,
                    Severity.LOW: 2,
                }[flag.severity],
                flag.category,
            )
        )

        return tuple(flags)


# ============================================================
# 9. INPUT EXTRACTION
# ============================================================

def _selected_business(
    state: CaseState,
) -> BusinessCandidate:

    if not state.business_shortlist:
        raise ValueError(
            "business_shortlist is empty."
        )

    for candidate in state.business_shortlist:

        if candidate.selected:
            return candidate

    return state.business_shortlist[0]


def _nearest_distribution_point(
    state: CaseState,
    origin: Coordinates,
) -> Coordinates:

    market = state.market_intelligence

    if (
        market is not None
        and market.market_reach is not None
        and market.market_reach.distribution_points
    ):

        points = (
            market
            .market_reach
            .distribution_points
        )

        return min(
            points,
            key=lambda point:
                (point.lat - origin.lat) ** 2
                +
                (point.lon - origin.lon) ** 2,
        )

    # No distribution point available.
    #
    # Do not invent a location.
    # Using origin gives a zero-distance estimate.

    return origin


def _price_history(
    state: CaseState,
) -> Tuple[List[float], str]:

    market = state.market_intelligence

    if (
        market is None
        or market.pricing is None
    ):

        return [], "2023-01"

    pricing = market.pricing

    return (
        pricing.commodity_price_series,
        pricing.price_series_start
        or "2023-01",
    )


def _structural_context(
    state: CaseState,
) -> Dict[str, str]:

    context: Dict[str, str] = {}

    if state.entrepreneur_profile:

        context.update(
            state
            .entrepreneur_profile
            .structural_context
        )

    market = state.market_intelligence

    if (
        market is not None
        and market.competitor is not None
        and market.competitor.market_saturation
    ):

        context.setdefault(
            "market_saturation",
            market.competitor.market_saturation,
        )

    return context


# ============================================================
# 10. OVERALL RISK
# ============================================================

def _overall_severity(
    route: Severity,
    seasonal: Severity,
    structural_flags: tuple[RiskFlag, ...],
) -> Severity:

    severities = [
        route,
        seasonal,
    ]

    severities.extend(
        flag.severity
        for flag in structural_flags
    )

    priority = {
        Severity.LOW: 0,
        Severity.MEDIUM: 1,
        Severity.HIGH: 2,
    }

    return max(
        severities,
        key=lambda value: priority[value],
    )


# ============================================================
# 11. VALIDATION
# ============================================================

class RiskValidator:

    @staticmethod
    def validate_route(
        flag: RiskFlag,
        distance_km: float,
    ) -> None:

        if distance_km <= RouteRiskAnalyzer.LOW_KM:

            expected = Severity.LOW

        elif (
            distance_km
            <= RouteRiskAnalyzer.MEDIUM_KM
        ):

            expected = Severity.MEDIUM

        else:

            expected = Severity.HIGH

        if flag.severity != expected:

            raise ValueError(
                "Route severity validation failed."
            )

    @staticmethod
    def validate_seasonal(
        flag: RiskFlag,
        amplitude_ratio: float,
    ) -> None:

        if (
            amplitude_ratio
            < SeasonalRiskAnalyzer.LOW_AMPLITUDE
        ):

            expected = Severity.LOW

        elif (
            amplitude_ratio
            < SeasonalRiskAnalyzer.MEDIUM_AMPLITUDE
        ):

            expected = Severity.MEDIUM

        else:

            expected = Severity.HIGH

        if flag.severity != expected:

            raise ValueError(
                "Seasonal severity validation failed."
            )

    @classmethod
    def validate(
        cls,
        result: RiskAnalysisResult,
    ) -> None:

        cls.validate_route(
            result.route.flag,
            result.route.distance_km,
        )

        cls.validate_seasonal(
            result.seasonal.flag,
            result.seasonal.amplitude_ratio,
        )

        for flag in result.structural_flags:

            if not isinstance(
                flag.severity,
                Severity,
            ):

                raise ValueError(
                    "Invalid structural severity."
                )

            if not isinstance(
                flag.confidence,
                Confidence,
            ):

                raise ValueError(
                    "Invalid structural confidence."
                )

        expected_overall = _overall_severity(
            result.route.flag.severity,
            result.seasonal.flag.severity,
            result.structural_flags,
        )

        if result.overall_severity != expected_overall:

            raise ValueError(
                "Overall severity validation failed."
            )


# ============================================================
# 12. SUMMARY
# ============================================================

def _build_summary(
    route_flag: RiskFlag,
    seasonal_flag: RiskFlag,
    structural_flags: tuple[RiskFlag, ...],
    overall: Severity,
) -> str:

    lines = [

        (
            f"Overall risk is {overall.value}."
        ),

        (
            f"Supply route risk is "
            f"{route_flag.severity.value}: "
            f"{route_flag.description}"
        ),

        (
            f"Seasonal price/demand risk is "
            f"{seasonal_flag.severity.value}: "
            f"{seasonal_flag.description}"
        ),
    ]

    if structural_flags:

        ordered = sorted(
            structural_flags,
            key=lambda flag: {
                Severity.HIGH: 0,
                Severity.MEDIUM: 1,
                Severity.LOW: 2,
            }[flag.severity],
        )

        risk_text = ", ".join(
            f"{flag.category} "
            f"({flag.severity.value})"
            for flag in ordered
        )

        lines.append(
            f"Structural risks flagged: "
            f"{risk_text}."
        )

    else:

        lines.append(
            "No structural risks were flagged "
            "from the available business context."
        )

    return " ".join(lines)


def _aggregate_confidence(
    *confidences: Confidence,
) -> Literal[
    "real",
    "estimated",
]:

    if all(
        confidence == Confidence.REAL
        for confidence in confidences
    ):

        return "real"

    return "estimated"


# ============================================================
# 13. CORE RISK ANALYSIS
# ============================================================

def analyze_risk(
    state: CaseState,
) -> RiskAnalysisResult:
    """
    Perform the complete deterministic risk analysis.

    This function does NOT mutate CaseState.
    """

    if state.entrepreneur_profile is None:

        raise ValueError(
            "entrepreneur_profile is required."
        )

    business = _selected_business(
        state
    )

    origin = (
        state
        .entrepreneur_profile
        .location
    )

    destination = (
        _nearest_distribution_point(
            state,
            origin,
        )
    )

    prices, start_period = _price_history(
        state
    )

    structural_context = (
        _structural_context(state)
    )

    # --------------------------------------------------------
    # Route risk
    # --------------------------------------------------------

    route_analyzer = RouteRiskAnalyzer()

    route_result = route_analyzer.analyze(
        origin,
        destination,
    )

    # --------------------------------------------------------
    # Seasonal risk
    # --------------------------------------------------------

    seasonal_analyzer = SeasonalRiskAnalyzer()

    seasonal_result = seasonal_analyzer.analyze(
        prices,
        start_period,
    )

    # --------------------------------------------------------
    # Structural risk
    # --------------------------------------------------------

    structural_analyzer = (
        StructuralRiskAnalyzer()
    )

    structural_flags = (
        structural_analyzer.analyze(
            business.business_category,
            structural_context,
        )
    )

    # --------------------------------------------------------
    # Overall risk
    # --------------------------------------------------------

    overall = _overall_severity(
        route_result.flag.severity,
        seasonal_result.flag.severity,
        structural_flags,
    )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    source_confidence = (
        _aggregate_confidence(
            route_result.confidence,
            seasonal_result.confidence,
        )
    )

    result = RiskAnalysisResult(
        route=route_result,
        seasonal=seasonal_result,
        structural_flags=structural_flags,
        overall_severity=overall,
        summary=_build_summary(
            route_result.flag,
            seasonal_result.flag,
            structural_flags,
            overall,
        ),
        source_confidence=source_confidence,
    )

    # --------------------------------------------------------
    # Hard validation
    # --------------------------------------------------------

    RiskValidator.validate(
        result
    )

    return result


# ============================================================
# 14. PUBLIC AGENT FUNCTION
# ============================================================

def run(
    state: CaseState,
) -> CaseState:
    """
    Run the complete Risk Agent.

    Writes only:

        state.market_intelligence.risk
    """

    result = analyze_risk(
        state
    )

    risk_record = RiskRecord(
        overall_severity=result.overall_severity,

        route_risk=result.route.flag,

        seasonal_risk=result.seasonal.flag,

        structural_risk_flags=list(
            result.structural_flags
        ),

        plain_language_summary=result.summary,

        raw_metrics={
            "route_distance_km": round(
                result.route.distance_km,
                2,
            ),

            "seasonal_amplitude_ratio": round(
                result.seasonal.amplitude_ratio,
                4,
            ),

            "structural_risk_count": float(
                len(result.structural_flags)
            ),
        },

        source_confidence=(
            result.source_confidence
        ),
    )

    if state.market_intelligence is None:

        state.market_intelligence = (
            MarketIntelligence()
        )

    state.market_intelligence.risk = (
        risk_record
    )

    return state


# ============================================================
# 15. DEMO INPUT
# ============================================================

def _mock_state() -> CaseState:

    rng = np.random.default_rng(42)

    months = 30

    trend = np.linspace(
        1200,
        1400,
        months,
    )

    seasonal = (
        250
        *
        np.sin(
            np.linspace(
                0,
                2 * np.pi * months / 12,
                months,
            )
        )
    )

    noise = rng.normal(
        0,
        20,
        months,
    )

    prices = list(
        trend
        +
        seasonal
        +
        noise
    )

    return CaseState(

        entrepreneur_profile=(
            EntrepreneurProfile(

                location=Coordinates(
                    lat=25.5941,
                    lon=85.1376,
                ),

                structural_context={
                    "buyer_count": "1",

                    "perishable": "yes",

                    "cold_storage": "no",

                    "license_required":
                        "municipal vending license",

                    "capital_intensity":
                        "medium",

                    "skill_experience":
                        "medium",

                    "infrastructure_reliability":
                        "intermittent",
                },
            )
        ),

        business_shortlist=[

            BusinessCandidate(
                business_category=(
                    "small-scale vegetable vending"
                ),
                selected=True,
            )
        ],

        market_intelligence=(

            MarketIntelligence(

                market_reach=(

                    MarketReachRecord(

                        population_within_radius=8400,

                        distribution_points=[

                            Coordinates(
                                lat=25.6100,
                                lon=85.2200,
                            )
                        ],

                        source_confidence="estimated",
                    )
                ),

                pricing=(

                    PricingRecord(

                        commodity_price_series=prices,

                        price_series_start="2023-01",

                        source_confidence="real",
                    )
                ),

                competitor=(

                    CompetitorRecord(

                        market_saturation="medium",

                        source_confidence="estimated",
                    )
                ),
            )
        ),
    )


# ============================================================
# 16. MAIN
# ============================================================

if __name__ == "__main__":

    import json

    print(
        "\nStarting Risk Agent..."
    )

    state = _mock_state()

    final_state = run(
        state
    )

    risk = (
        final_state
        .market_intelligence
        .risk
    )

    print(
        "\n=== Risk Agent Output ==="
    )

    print(
        json.dumps(
            risk.model_dump(
                mode="json"
            ),
            indent=2,
        )
    )