"""Module 2: Financial Structuring and Funding Preparation."""

from module2_financial.financial_engine import (
    ApplicantProfile,
    CaseState,
    FeasibilityVerdict,
    FinancialPlan,
    LoanEligibility,
    SchemeMatch,
    SchemeTerms,
    SchemeTier,
    build_financial_plan,
    run_financial_agent,
)
from module2_financial.schemas import (
    DebtServiceMetrics,
    FinancialAnalystCommentary,
    Module1IntelligenceSnapshot,
    ScenarioRunDetail,
    SeasonalRiskSnapshot,
    StressTestResult,
)

__all__ = [
    "ApplicantProfile",
    "CaseState",
    "FeasibilityVerdict",
    "FinancialPlan",
    "LoanEligibility",
    "SchemeMatch",
    "SchemeTerms",
    "SchemeTier",
    "build_financial_plan",
    "run_financial_agent",
    "DebtServiceMetrics",
    "FinancialAnalystCommentary",
    "Module1IntelligenceSnapshot",
    "SeasonalRiskSnapshot",
    "ScenarioRunDetail",
    "StressTestResult",
    "FinancialAnalystAgent",
    "ScenarioDigitalTwinAgent",
]


def __getattr__(name: str):
    if name == "FinancialAnalystAgent":
        from module2_financial.financial_analyst_agent import FinancialAnalystAgent
        return FinancialAnalystAgent
    if name == "ScenarioDigitalTwinAgent":
        from module2_financial.scenario_digital_twin import ScenarioDigitalTwinAgent
        return ScenarioDigitalTwinAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

