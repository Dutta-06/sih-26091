"""Rule-based financial planning engine.

This module deliberately contains no LLM or external-service calls. It turns
available capital and a feasibility verdict into a reproducible loan plan.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
import json
import math
from typing import Any


class LoanEligibility(str, Enum):
    """Supported outcomes for a funding request."""

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"


class FeasibilityVerdict(str, Enum):
    """Verdicts accepted from the feasibility review node."""

    RECOMMENDED = "recommended"
    MARGINAL = "marginal"
    NOT_RECOMMENDED = "not_recommended"


@dataclass(frozen=True)
class ApplicantProfile:
    """Applicant and business facts used for scheme screening."""

    available_capital: float
    state: str
    district: str
    business_category: str
    is_new_business: bool
    is_woman_owned: bool
    social_category: str | None = None
    is_shg_member: bool = False
    has_udyam_registration: bool = False
    previous_loan_repaid: bool = False


@dataclass(frozen=True)
class SchemePolicy:
    """Scheme rules and financial terms supplied by configuration."""

    name: str
    min_loan_amount: float | None = None
    max_project_cost: float | None = None
    max_loan_amount: float | None = None
    margin_rate: float | None = None
    working_capital_rate: float | None = None
    eligible_categories: tuple[str, ...] = ()
    allowed_states: tuple[str, ...] = ()
    requires_new_business: bool = False
    requires_woman_owned: bool = False
    required_social_categories: tuple[str, ...] = ()
    requires_shg_membership: bool = False
    requires_udyam_registration: bool = False
    requires_previous_loan_repaid: bool = False
    interest_rate: float | None = None
    tenure_years: int | None = None
    moratorium_months: int | None = None
    source: str | None = None
    source_confidence: str = "estimated"
    verified_fields: tuple[str, ...] = ()
    assumption_fields: tuple[str, ...] = ()
    policy_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchemeTerms:
    """Explicit financial terms supplied by a verified scheme or lender."""

    margin_rate: float
    working_capital_rate: float
    interest_rate: float
    tenure_years: int
    moratorium_months: int


@dataclass(frozen=True)
class SchemeMatch:
    """Explainable result of screening one scheme policy."""

    scheme_name: str
    status: str
    reasons: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    source: str | None
    source_confidence: str


@dataclass(frozen=True)
class FinancialAgentResult:
    """Complete standalone output from scheme screening and planning."""

    scheme_matches: tuple[SchemeMatch, ...]
    selected_scheme: str | None
    financial_plan: FinancialPlan | None


@dataclass(frozen=True)
class CaseState:
    """Shared case state passed into and returned from the financial node."""

    applicant_profile: ApplicantProfile
    feasibility_verdict: FeasibilityVerdict | str
    scheme_terms: SchemeTerms | None = None
    preferred_scheme: str | None = None
    scheme_matches: tuple[SchemeMatch, ...] = ()
    selected_scheme: str | None = None
    financial_plan: FinancialPlan | None = None

DEFAULT_SCHEME_POLICIES: tuple[dict[str, Any], ...] = (
    {
        "name": "pmmy",
        "max_loan_amount": 2_000_000,
        "eligible_categories": ("manufacturing", "services", "trading", "agri_allied"),
        "source": "https://www.mudra.org.in/offerings",
        "source_confidence": "mixed",
        "verified_fields": ("max_loan_amount", "eligible_categories"),
        "policy_notes": (
            "MUDRA publishes loan ceilings and eligible activities, not a universal borrower interest rate.",
            "Margin, working-capital split, tenure, interest, and moratorium must be supplied by the lender or verified scheme terms.",
        ),
    },
    {
        "name": "pmegp",
        "eligible_categories": ("manufacturing", "services"),
        "requires_new_business": True,
        "source": "https://www.kviconline.gov.in/pmegpeportal/pmegphome/index.jsp",
        "source_confidence": "estimated",
        "assumption_fields": (),
        "policy_notes": (
            "PMEGP limits and beneficiary contribution vary by activity and category; verify the current guideline before approval.",
        ),
    },
    {
        "name": "stand_up_india",
        "min_loan_amount": 1_000_000,
        "max_loan_amount": 10_000_000,
        "margin_rate": 0.15,
        "eligible_categories": ("manufacturing", "services", "trading"),
        "requires_new_business": True,
        "requires_woman_owned": True,
        "source": "https://www.standupmitra.in/",
        "source_confidence": "mixed",
        "verified_fields": (
            "min_loan_amount",
            "max_loan_amount",
            "margin_rate",
            "eligible_categories",
        ),
        "assumption_fields": (),
        "policy_notes": (
            "The official portal confirms loans of 10 lakh to 1 crore and 15% promoter contribution.",
            "Interest, tenure, moratorium, and working-capital allocation are lender-dependent.",
        ),
    },
    {
        "name": "stand_up_india_sc_st",
        "min_loan_amount": 1_000_000,
        "max_loan_amount": 10_000_000,
        "margin_rate": 0.15,
        "eligible_categories": ("manufacturing", "services", "trading", "agri_allied"),
        "required_social_categories": ("sc", "st"),
        "requires_new_business": True,
        "source": "https://www.standupmitra.in/",
        "source_confidence": "mixed",
        "verified_fields": (
            "min_loan_amount",
            "max_loan_amount",
            "margin_rate",
            "eligible_categories",
            "required_social_categories",
        ),
        "assumption_fields": (),
        "policy_notes": (
            "The official portal confirms SC/ST eligibility, loans of 10 lakh to 1 crore, and 15% promoter contribution.",
            "Interest, tenure, moratorium, and working-capital allocation are lender-dependent.",
        ),
    },
    {
        "name": "day_nrlm_shg_finance",
        "requires_shg_membership": True,
        "source": "https://aajeevika.gov.in/",
        "source_confidence": "estimated",
        "assumption_fields": (
            "margin_rate",
            "working_capital_rate",
            "interest_rate",
            "tenure_years",
            "moratorium_months",
        ),
        "policy_notes": (
            "DAY-NRLM terms depend on SHG and lending-institution rules; no universal terms are assumed as verified here.",
        ),
    },
)


@dataclass(frozen=True)
class SchemeTier:
    """Funding terms selected from the project cost."""

    name: str
    rate: float
    tenure_years: int
    moratorium_months: int


@dataclass(frozen=True)
class RepaymentInstallment:
    """One monthly installment in the repayment schedule."""

    installment_number: int
    period_type: str
    principal: float
    interest: float
    payment: float
    remaining_balance: float


@dataclass(frozen=True)
class FinancialPlan:
    """Complete deterministic output consumed by downstream agents."""

    available_capital: float
    scheme_name: str
    project_cost: float
    capital_expenditure: float
    working_capital_requirement: float
    loan_amount: float
    loan_eligibility: LoanEligibility
    scheme_tier: SchemeTier | None
    repayment_schedule: tuple[RepaymentInstallment, ...]


def _validate_capital(available_capital: float) -> float:
    capital = float(available_capital)
    if not math.isfinite(capital) or capital < 0:
        raise ValueError("available_capital must be a finite, non-negative number")
    return capital


def compute_project_cost(available_capital: float, margin_rate: float) -> float:
    """Calculate total project cost from capital and a scheme margin rate."""

    capital = _validate_capital(available_capital)
    margin = float(margin_rate)
    if not math.isfinite(margin) or not 0 < margin <= 1:
        raise ValueError("margin_rate must be greater than 0 and at most 1")
    return round(capital / margin, 2)


def policy_from_dict(data: dict[str, Any]) -> SchemePolicy:
    """Build a scheme policy from JSON-compatible configuration."""

    tuple_fields = ("eligible_categories", "allowed_states", "required_social_categories")
    normalized = dict(data)
    for field_name in tuple_fields:
        normalized[field_name] = tuple(normalized.get(field_name, ()))
    return SchemePolicy(**normalized)


def load_policies() -> tuple[SchemePolicy, ...]:
    """Load every built-in scheme policy."""

    return tuple(policy_from_dict(policy) for policy in DEFAULT_SCHEME_POLICIES)


def get_scheme_policy(scheme_name: str, policies: tuple[SchemePolicy, ...] | None = None) -> SchemePolicy:
    """Resolve a configured scheme by name."""

    available_policies = policies if policies is not None else load_policies()
    for policy in available_policies:
        if policy.name == scheme_name:
            return policy
    raise ValueError(f"unknown scheme policy: {scheme_name}")


def _normalise(value: str) -> str:
    return value.strip().casefold()


def screen_scheme(
    profile: ApplicantProfile,
    policy: SchemePolicy,
    scheme_terms: SchemeTerms | None = None,
) -> SchemeMatch:
    """Screen one scheme and explain why it matched or failed."""

    reasons = []
    missing_requirements = []
    project_cost = None
    loan_amount = None
    if scheme_terms is None:
        missing_requirements.append("explicit scheme terms for repayment calculation")
    else:
        project_cost = compute_project_cost(profile.available_capital, scheme_terms.margin_rate)
        loan_amount = compute_loan_amount(project_cost, profile.available_capital)

    if policy.max_project_cost is not None and project_cost is not None and project_cost > policy.max_project_cost:
        reasons.append("project cost exceeds the scheme maximum")
    if policy.min_loan_amount is not None and loan_amount is not None and loan_amount < policy.min_loan_amount:
        reasons.append("loan amount is below the scheme minimum")
    if policy.max_loan_amount is not None and loan_amount is not None and loan_amount > policy.max_loan_amount:
        reasons.append("loan amount exceeds the scheme maximum")
    if policy.eligible_categories and _normalise(profile.business_category) not in {
        _normalise(category) for category in policy.eligible_categories
    }:
        reasons.append("business category is outside the configured scheme scope")
    if policy.allowed_states and _normalise(profile.state) not in {
        _normalise(state) for state in policy.allowed_states
    }:
        reasons.append("state is outside the configured scheme scope")
    if policy.requires_new_business and not profile.is_new_business:
        reasons.append("scheme requires a new business")
    if policy.requires_woman_owned and not profile.is_woman_owned:
        reasons.append("scheme requires woman ownership")
    if policy.required_social_categories and _normalise(profile.social_category or "") not in {
        _normalise(category) for category in policy.required_social_categories
    }:
        reasons.append("social category requirement is not met")
    if policy.requires_shg_membership and not profile.is_shg_member:
        missing_requirements.append("SHG membership")
    if policy.requires_udyam_registration and not profile.has_udyam_registration:
        missing_requirements.append("Udyam registration")
    if policy.requires_previous_loan_repaid and not profile.previous_loan_repaid:
        missing_requirements.append("successful previous loan repayment")

    if reasons:
        status = "ineligible"
    elif any(requirement != "explicit scheme terms for repayment calculation" for requirement in missing_requirements):
        status = "needs_review"
    else:
        status = "potentially_eligible"
        if scheme_terms is None:
            reasons.append("scheme eligibility rules passed; repayment terms are still required")
        else:
            reasons.append("all configured screening rules passed")

    return SchemeMatch(
        scheme_name=policy.name,
        status=status,
        reasons=tuple(reasons),
        missing_requirements=tuple(missing_requirements),
        source=policy.source,
        source_confidence=policy.source_confidence,
    )


def find_applicable_schemes(
    profile: ApplicantProfile,
    policies: tuple[SchemePolicy, ...] | list[SchemePolicy] | None = None,
) -> tuple[SchemeMatch, ...]:
    """Screen all configured schemes without approving a loan."""

    return tuple(screen_scheme(profile, policy) for policy in (policies or load_policies()))


def _policy_limit_reasons(
    project_cost: float,
    loan_amount: float,
    policy: SchemePolicy,
) -> tuple[str, ...]:
    reasons = []
    if policy.max_project_cost is not None and project_cost > policy.max_project_cost:
        reasons.append("project cost exceeds the scheme maximum")
    if policy.min_loan_amount is not None and loan_amount < policy.min_loan_amount:
        reasons.append("loan amount is below the scheme minimum")
    if policy.max_loan_amount is not None and loan_amount > policy.max_loan_amount:
        reasons.append("loan amount exceeds the scheme maximum")
    return tuple(reasons)


def route_scheme_tier(policy: SchemePolicy, scheme_terms: SchemeTerms) -> SchemeTier:
    """Create financial terms from one selected scheme policy."""

    return SchemeTier(
        policy.name,
        scheme_terms.interest_rate,
        scheme_terms.tenure_years,
        scheme_terms.moratorium_months,
    )


def compute_loan_amount(project_cost: float, available_capital: float) -> float:
    """Calculate the requested loan after the owner's contribution."""

    cost = float(project_cost)
    capital = _validate_capital(available_capital)
    if cost < 0 or not math.isfinite(cost):
        raise ValueError("project_cost must be a finite, non-negative number")
    if capital > cost:
        raise ValueError("available capital cannot exceed project cost")
    return round(cost - capital, 2)


def estimate_working_capital(project_cost: float, percentage: float) -> float:
    """Estimate initial working capital as a configurable share of project cost."""

    cost = float(project_cost)
    share = float(percentage)
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("project_cost must be a finite, non-negative number")
    if not math.isfinite(share) or not 0 <= share <= 1:
        raise ValueError("working capital percentage must be between 0 and 1")
    return round(cost * share, 2)


def monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """Return the fixed monthly payment for an amortizing loan."""

    if principal < 0 or annual_rate < 0 or term_months <= 0:
        raise ValueError("loan terms must be non-negative with a positive term")
    if principal == 0:
        return 0.0
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return round(principal / term_months, 2)
    payment = principal * monthly_rate * (1 + monthly_rate) ** term_months
    payment /= (1 + monthly_rate) ** term_months - 1
    return round(payment, 2)


def build_repayment_schedule(loan_amount: float, tier: SchemeTier) -> tuple[RepaymentInstallment, ...]:
    """Build interest-only moratorium periods followed by monthly amortization."""

    if loan_amount < 0:
        raise ValueError("loan_amount cannot be negative")
    term_months = tier.tenure_years * 12
    payment = monthly_payment(loan_amount, tier.rate, term_months)
    monthly_rate = tier.rate / 12
    balance = round(loan_amount, 2)
    schedule = []

    for installment_number in range(1, tier.moratorium_months + term_months + 1):
        interest = round(balance * monthly_rate, 2)
        if installment_number <= tier.moratorium_months:
            schedule.append(
                RepaymentInstallment(
                    installment_number=installment_number,
                    period_type="moratorium",
                    principal=0.0,
                    interest=interest,
                    payment=interest,
                    remaining_balance=balance,
                )
            )
            continue

        principal = round(payment - interest, 2)
        if installment_number == tier.moratorium_months + term_months or principal > balance:
            principal = balance
        installment_payment = round(principal + interest, 2)
        balance = round(max(0.0, balance - principal), 2)
        schedule.append(
            RepaymentInstallment(
                installment_number=installment_number,
                period_type="repayment",
                principal=principal,
                interest=interest,
                payment=installment_payment,
                remaining_balance=balance,
            )
        )
    return tuple(schedule)


def build_financial_plan(
    available_capital: float,
    feasibility_verdict: FeasibilityVerdict | str,
    scheme: str = "pmmy",
    applicant_profile: ApplicantProfile | None = None,
    scheme_terms: SchemeTerms | None = None,
) -> FinancialPlan:
    """Build a scheme-specific funding plan from configured policy data."""

    policy = get_scheme_policy(scheme)
    if scheme_terms is None:
        raise ValueError("explicit scheme_terms are required; no financial assumptions are allowed")
    if not 0 < scheme_terms.margin_rate <= 1 or not 0 <= scheme_terms.working_capital_rate <= 1:
        raise ValueError("scheme terms contain invalid margin or working-capital rates")
    capital = _validate_capital(available_capital)
    verdict = FeasibilityVerdict(feasibility_verdict)
    if applicant_profile is not None:
        match = screen_scheme(applicant_profile, policy, scheme_terms)
        if match.status != "potentially_eligible":
            project_cost = compute_project_cost(capital, scheme_terms.margin_rate)
            loan_amount = compute_loan_amount(project_cost, capital)
            return FinancialPlan(
                available_capital=capital,
                scheme_name=policy.name,
                project_cost=project_cost,
                capital_expenditure=0.0,
                working_capital_requirement=0.0,
                loan_amount=loan_amount,
                loan_eligibility=LoanEligibility.NOT_ELIGIBLE,
                scheme_tier=None,
                repayment_schedule=(),
            )

    project_cost = compute_project_cost(capital, scheme_terms.margin_rate)
    working_capital_requirement = estimate_working_capital(
        project_cost, scheme_terms.working_capital_rate
    )
    capital_expenditure = round(project_cost - working_capital_requirement, 2)
    loan_amount = compute_loan_amount(project_cost, capital)

    if _policy_limit_reasons(project_cost, loan_amount, policy):
        return FinancialPlan(
            available_capital=capital,
            scheme_name=policy.name,
            project_cost=project_cost,
            capital_expenditure=0.0,
            working_capital_requirement=0.0,
            loan_amount=loan_amount,
            loan_eligibility=LoanEligibility.NOT_ELIGIBLE,
            scheme_tier=None,
            repayment_schedule=(),
        )

    if verdict is not FeasibilityVerdict.RECOMMENDED:
        return FinancialPlan(
            available_capital=capital,
            scheme_name=policy.name,
            project_cost=project_cost,
            capital_expenditure=capital_expenditure,
            working_capital_requirement=working_capital_requirement,
            loan_amount=loan_amount,
            loan_eligibility=LoanEligibility.NOT_ELIGIBLE,
            scheme_tier=None,
            repayment_schedule=(),
        )

    tier = route_scheme_tier(policy, scheme_terms)
    return FinancialPlan(
        available_capital=capital,
        scheme_name=policy.name,
        project_cost=project_cost,
        capital_expenditure=capital_expenditure,
        working_capital_requirement=working_capital_requirement,
        loan_amount=loan_amount,
        loan_eligibility=LoanEligibility.ELIGIBLE,
        scheme_tier=tier,
        repayment_schedule=build_repayment_schedule(loan_amount, tier),
    )


def run_financial_agent(
    applicant_profile: ApplicantProfile,
    feasibility_verdict: FeasibilityVerdict | str,
    preferred_scheme: str | None = None,
    scheme_terms: SchemeTerms | None = None,
) -> FinancialAgentResult:
    """Screen every configured scheme and build one deterministic plan.

    When no preference is supplied, the first potentially eligible policy in
    configuration order is selected. A preference is honored only when that
    policy passes screening.
    """

    policies = load_policies()
    matches = tuple(
        screen_scheme(applicant_profile, policy, scheme_terms)
        for policy in policies
    )
    eligible_names = tuple(
        match.scheme_name for match in matches if match.status == "potentially_eligible"
    )
    selected_scheme = preferred_scheme
    if selected_scheme is None:
        selected_scheme = next(iter(eligible_names), None)
    if selected_scheme not in eligible_names:
        return FinancialAgentResult(matches, None, None)

    try:
        plan = build_financial_plan(
            applicant_profile.available_capital,
            feasibility_verdict,
            selected_scheme,
            applicant_profile,
            scheme_terms,
        )
    except ValueError as error:
        if scheme_terms is None and "explicit scheme_terms" in str(error):
            return FinancialAgentResult(matches, selected_scheme, None)
        raise
    return FinancialAgentResult(matches, selected_scheme, plan)


def run(state: CaseState) -> CaseState:
    """Run the complete financial agent using only shared user state."""

    result = run_financial_agent(
        applicant_profile=state.applicant_profile,
        feasibility_verdict=state.feasibility_verdict,
        preferred_scheme=state.preferred_scheme,
        scheme_terms=state.scheme_terms,
    )
    return replace(
        state,
        scheme_matches=result.scheme_matches,
        selected_scheme=result.selected_scheme,
        financial_plan=result.financial_plan,
    )


MOCK_INPUT = {
    "available_capital": 100_000,
    "feasibility_verdict": FeasibilityVerdict.RECOMMENDED.value,
    "scheme_terms": SchemeTerms(
        margin_rate=0.10,
        working_capital_rate=0.20,
        interest_rate=0.08,
        tenure_years=7,
        moratorium_months=6,
    ),
}


def _json_plan(plan: FinancialPlan) -> dict:
    result = asdict(plan)
    result["loan_eligibility"] = plan.loan_eligibility.value
    result["repayment_schedule"] = [asdict(item) for item in plan.repayment_schedule[:3]]
    if plan.scheme_tier is not None:
        result["scheme_tier"]["rate"] = plan.scheme_tier.rate
    return result


if __name__ == "__main__":
    print(json.dumps(_json_plan(build_financial_plan(**MOCK_INPUT)), indent=2))
