"""Financial Engine (TDD Section 6.1 / "Rule-Based Financial Planning").

A deterministic mathematical engine with zero LLM calls. It turns available capital
and a feasibility verdict into a reproducible loan structure and amortization schedule.

Routing Rules:
- Logic A (Project Cost <= ₹1.40 Lakh): Micro Finance Scheme (6.5% interest, 3-year tenure, 3-month moratorium)
- Logic B (Project Cost > ₹1.40 Lakh and <= ₹50.00 Lakh): Term Loan Scheme (8.0% interest, 7-year tenure, 6-month moratorium)
- Project Cost > ₹50.00 Lakh: Exceeds supported loan ceiling.

Reads:  state.entrepreneur_profile.available_capital, state.feasibility_record.verdict
Writes: state.financial_plan.project_cost, state.financial_plan.loan_eligibility,
        state.financial_plan.scheme_tier, state.financial_plan.repayment_schedule
"""

from __future__ import annotations

from dataclasses import dataclass, is_dataclass, replace
from enum import Enum
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
    """Applicant and business facts."""

    available_capital: float
    state: str = "general"
    district: str = "general"
    business_category: str = "general"
    is_new_business: bool = True
    is_woman_owned: bool = False
    social_category: str | None = None
    is_shg_member: bool = False
    has_udyam_registration: bool = False
    previous_loan_repaid: bool = False


@dataclass(frozen=True)
class SchemeTier:
    """Funding terms selected based on project cost thresholds."""

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
    analyst_commentary: Any | None = None
    stress_test_result: Any | None = None


# Backward-compatible helper dataclasses for any external references
@dataclass(frozen=True)
class SchemeTerms:
    """Explicit terms override if provided."""

    margin_rate: float = 0.10
    working_capital_rate: float = 0.20
    interest_rate: float | None = None
    tenure_years: int | None = None
    moratorium_months: int | None = None


@dataclass(frozen=True)
class SchemeMatch:
    """Screening result summary."""

    scheme_name: str
    status: str
    reasons: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    source: str | None = None
    source_confidence: str = "verified"


@dataclass(frozen=True)
class CaseState:
    """Shared case state passed into and returned from the financial node."""

    applicant_profile: ApplicantProfile | None = None
    entrepreneur_profile: ApplicantProfile | None = None
    feasibility_verdict: FeasibilityVerdict | str = FeasibilityVerdict.RECOMMENDED
    scheme_terms: SchemeTerms | None = None
    preferred_scheme: str | None = None
    scheme_matches: tuple[SchemeMatch, ...] = ()
    selected_scheme: str | None = None
    financial_plan: FinancialPlan | None = None


# --- DETERMINISTIC MATHEMATICAL CORE FUNCTIONS ---

def _validate_capital(available_capital: float) -> float:
    capital = float(available_capital)
    if not math.isfinite(capital) or capital < 0:
        raise ValueError("available_capital must be a finite, non-negative number")
    return capital


def compute_project_cost(available_capital: float, margin_rate: float = 0.10) -> float:
    """Calculate total project cost from capital and promoter margin rate (default: 10%).

    Formula: Total Project Cost = Available Capital / Margin Rate (0.10)
    """
    capital = _validate_capital(available_capital)
    margin = float(margin_rate)
    if not math.isfinite(margin) or not 0 < margin <= 1:
        raise ValueError("margin_rate must be greater than 0 and at most 1")
    return round(capital / margin, 2)


def compute_loan_amount(project_cost: float, available_capital: float) -> float:
    """Calculate the loan requirement after owner's equity contribution (90% of cost)."""
    cost = float(project_cost)
    capital = _validate_capital(available_capital)
    if cost < 0 or not math.isfinite(cost):
        raise ValueError("project_cost must be a finite, non-negative number")
    if capital > cost:
        raise ValueError("available capital cannot exceed project cost")
    return round(cost - capital, 2)


def estimate_working_capital(project_cost: float, percentage: float = 0.20) -> float:
    """Estimate initial working capital reserve as a share of project cost (default: 20%)."""
    cost = float(project_cost)
    share = float(percentage)
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("project_cost must be a finite, non-negative number")
    if not math.isfinite(share) or not 0 <= share <= 1:
        raise ValueError("working capital percentage must be between 0 and 1")
    return round(cost * share, 2)


def route_scheme_tier(project_cost: float) -> SchemeTier | None:
    """Deterministic scheme router based strictly on project cost thresholds.

    - Logic A: <= ₹1.40 Lakh (₹1,40,000) -> Micro Finance Scheme (6.5% interest, 3-year tenure, 3-month moratorium)
    - Logic B: > ₹1.40 Lakh and <= ₹50.00 Lakh (₹50,00,000) -> Term Loan Scheme (8% interest, 7-year tenure, 6-month moratorium)
    - Beyond ₹50.00 Lakh -> None (exceeds maximum threshold)
    """
    if project_cost < 0:
        return None
    if project_cost <= 140_000:
        return SchemeTier(
            name="micro_finance",
            rate=0.065,
            tenure_years=3,
            moratorium_months=3,
        )
    elif project_cost <= 5_000_000:
        return SchemeTier(
            name="term_loan",
            rate=0.08,
            tenure_years=7,
            moratorium_months=6,
        )
    return None


def monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """Calculate fixed monthly amortized repayment (EMI)."""
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
    """Build month-by-month repayment schedule with interest-only moratorium followed by amortization."""
    if loan_amount < 0:
        raise ValueError("loan_amount cannot be negative")
    
    term_months = tier.tenure_years * 12
    payment = monthly_payment(loan_amount, tier.rate, term_months)
    monthly_rate = tier.rate / 12
    balance = round(loan_amount, 2)
    schedule: list[RepaymentInstallment] = []

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
    feasibility_verdict: FeasibilityVerdict | str = FeasibilityVerdict.RECOMMENDED,
    scheme: str | None = None,
    applicant_profile: ApplicantProfile | None = None,
    scheme_terms: SchemeTerms | None = None,
    margin_rate: float = 0.10,
    working_capital_rate: float = 0.20,
) -> FinancialPlan:
    """Build a deterministic financial plan based on capital, margin, and threshold rules."""
    capital = _validate_capital(available_capital)
    effective_margin = scheme_terms.margin_rate if (scheme_terms and scheme_terms.margin_rate) else margin_rate
    effective_wc_rate = scheme_terms.working_capital_rate if (scheme_terms and scheme_terms.working_capital_rate) else working_capital_rate

    project_cost = compute_project_cost(capital, effective_margin)
    working_capital_req = estimate_working_capital(project_cost, effective_wc_rate)
    capex = round(project_cost - working_capital_req, 2)
    loan_amount = compute_loan_amount(project_cost, capital)

    # Convert verdict
    if isinstance(feasibility_verdict, str):
        try:
            verdict = FeasibilityVerdict(feasibility_verdict.lower())
        except ValueError:
            verdict = FeasibilityVerdict.NOT_RECOMMENDED
    else:
        verdict = feasibility_verdict

    # Route tier based on project cost
    tier = route_scheme_tier(project_cost)

    # If scheme terms are explicitly provided with custom rates, allow override
    if scheme_terms and scheme_terms.interest_rate is not None and scheme_terms.tenure_years is not None and scheme_terms.moratorium_months is not None:
        scheme_name = scheme or (tier.name if tier else "custom_loan")
        tier = SchemeTier(
            name=scheme_name,
            rate=scheme_terms.interest_rate,
            tenure_years=scheme_terms.tenure_years,
            moratorium_months=scheme_terms.moratorium_months,
        )

    # Ineligible conditions:
    # 1. Feasibility verdict is not recommended
    # 2. Project cost exceeds ceiling (₹50 Lakh)
    # 3. No valid tier found
    if verdict != FeasibilityVerdict.RECOMMENDED or tier is None or project_cost > 5_000_000:
        scheme_name = scheme or (tier.name if tier else "unsupported")
        return FinancialPlan(
            available_capital=capital,
            scheme_name=scheme_name,
            project_cost=project_cost,
            capital_expenditure=capex,
            working_capital_requirement=working_capital_req,
            loan_amount=loan_amount,
            loan_eligibility=LoanEligibility.NOT_ELIGIBLE,
            scheme_tier=None,
            repayment_schedule=(),
        )

    scheme_name = scheme or tier.name
    return FinancialPlan(
        available_capital=capital,
        scheme_name=scheme_name,
        project_cost=project_cost,
        capital_expenditure=capex,
        working_capital_requirement=working_capital_req,
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
) -> Any:
    """Run mathematical financial plan builder for applicant profile."""
    plan = build_financial_plan(
        available_capital=applicant_profile.available_capital,
        feasibility_verdict=feasibility_verdict,
        scheme=preferred_scheme,
        applicant_profile=applicant_profile,
        scheme_terms=scheme_terms,
    )
    matches = (
        SchemeMatch(
            scheme_name=plan.scheme_name,
            status="eligible" if plan.loan_eligibility == LoanEligibility.ELIGIBLE else "ineligible",
            reasons=("Passed project cost threshold routing",) if plan.loan_eligibility == LoanEligibility.ELIGIBLE else ("Did not meet threshold / feasibility criteria",),
        ),
    )
    return type(
        "FinancialAgentResult",
        (),
        {
            "scheme_matches": matches,
            "selected_scheme": plan.scheme_name,
            "financial_plan": plan,
        },
    )()


def run(state: Any) -> Any:
    """Run the complete financial engine mathematical node.

    Reads:  state.entrepreneur_profile.available_capital, state.feasibility_record.verdict
    Writes: state.financial_plan
    """
    profile = getattr(state, "applicant_profile", None) or getattr(state, "entrepreneur_profile", None)
    if profile is None:
        capital = 100_000.0
    else:
        capital = getattr(profile, "available_capital", 100_000.0)

    verdict_raw = getattr(state, "feasibility_verdict", None)
    if verdict_raw is None:
        feasibility_rec = getattr(state, "feasibility_record", None)
        verdict_raw = getattr(feasibility_rec, "verdict", FeasibilityVerdict.RECOMMENDED)

    terms = getattr(state, "scheme_terms", None)
    pref = getattr(state, "preferred_scheme", None)

    plan = build_financial_plan(
        available_capital=capital,
        feasibility_verdict=verdict_raw,
        scheme=pref,
        scheme_terms=terms,
    )

    if is_dataclass(state):
        return replace(
            state,
            selected_scheme=plan.scheme_name,
            financial_plan=plan,
        )
    elif hasattr(state, "model_copy"):
        updates: dict[str, Any] = {"financial_plan": plan}
        if hasattr(state, "selected_scheme"):
            updates["selected_scheme"] = plan.scheme_name
        return state.model_copy(update=updates)
    else:
        if hasattr(state, "selected_scheme"):
            state.selected_scheme = plan.scheme_name
        if hasattr(state, "financial_plan"):
            state.financial_plan = plan
        return state


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Clean Financial Math Engine")
    print("=" * 70)

    # Test 1: Micro Finance Boundary (₹14k capital -> ₹1.40L project cost)
    micro_plan = build_financial_plan(available_capital=14_000)
    print("\n[Test 1] Micro Finance Scheme (<= ₹1.40L):")
    print(f"  • Capital: ₹{micro_plan.available_capital:,.2f}")
    print(f"  • Project Cost: ₹{micro_plan.project_cost:,.2f}")
    print(f"  • Loan Amount: ₹{micro_plan.loan_amount:,.2f}")
    print(f"  • Scheme: {micro_plan.scheme_name} (Rate: {micro_plan.scheme_tier.rate*100}%, Tenure: {micro_plan.scheme_tier.tenure_years}y, Moratorium: {micro_plan.scheme_tier.moratorium_months}m)")
    print(f"  • Total Installments: {len(micro_plan.repayment_schedule)}")

    # Test 2: Term Loan (₹1 Lakh capital -> ₹10 Lakh project cost)
    term_plan = build_financial_plan(available_capital=100_000)
    print("\n[Test 2] Term Loan Scheme (₹1.40L - ₹50L):")
    print(f"  • Capital: ₹{term_plan.available_capital:,.2f}")
    print(f"  • Project Cost: ₹{term_plan.project_cost:,.2f}")
    print(f"  • Loan Amount: ₹{term_plan.loan_amount:,.2f}")
    print(f"  • Capex: ₹{term_plan.capital_expenditure:,.2f} | Working Capital: ₹{term_plan.working_capital_requirement:,.2f}")
    print(f"  • Scheme: {term_plan.scheme_name} (Rate: {term_plan.scheme_tier.rate*100}%, Tenure: {term_plan.scheme_tier.tenure_years}y, Moratorium: {term_plan.scheme_tier.moratorium_months}m)")
    print(f"  • Total Installments: {len(term_plan.repayment_schedule)}")

    # Test 3: Over ₹50L project cost
    over_plan = build_financial_plan(available_capital=6_000_000)
    print("\n[Test 3] Over ₹50L Limit (₹60 Lakh capital -> ₹6 Crore project cost):")
    print(f"  • Project Cost: ₹{over_plan.project_cost:,.2f}")
    print(f"  • Eligibility: {over_plan.loan_eligibility.value}")
    print("=" * 70)
