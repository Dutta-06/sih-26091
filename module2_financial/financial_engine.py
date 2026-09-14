"""Deterministic Financial Structuring Engine (Module 2, TDD Section 6.1).

Reads: state.entrepreneur_profile.available_capital, state.feasibility_record.verdict,
       state.selected_candidate().category
Writes: state.financial_plan (project cost, loan eligibility, scheme tier, quarterly repayment schedule,
        working-capital / capex split, totals)
Tech: pure Python functions with fixed rules - no language model is ever called in this module.

Rules
-----
* The stated available capital is treated as a fixed 10% margin contribution, so
  project cost = capital / 0.10; the loan covers the remaining 90%, capped at the tier ceiling.
* Tier routing by project cost: <= Rs 1.40 lakh -> Micro Finance (6.5% p.a., 3 years, 3-month
  moratorium, loan cap Rs 1.25 lakh); <= Rs 50 lakh -> Term Loan (8% p.a., 7 years, 6-month
  moratorium, loan cap Rs 45 lakh); above that the case is outside the supported scheme range.
* Repayment is quarterly. The moratorium is counted inside the tenure: moratorium quarters pay
  interest only, the remaining quarters amortise with an equal quarterly installment and the last
  quarter clears the exact residual balance.
* When the micro-finance loan cap binds (project cost above ~Rs 1.389 lakh) the reported
  margin/loan percentages are the effective ones and ``loan_cap_applied`` is set.
* Working capital is carved out of the project cost as an indicative 20% working capital / 80%
  capital expenditure planning split; it is not a separately assessed requirement.
* All money figures are rounded to 2 decimals (paise); percentages to 2 decimals.
"""

from __future__ import annotations

import math
from typing import Any

from orchestrator.state import CaseState, FinancialPlan, QuarterlyRepaymentInstallment, SchemeTier

MARGIN_SHARE = 0.10
LOAN_SHARE = 0.90
WORKING_CAPITAL_SHARE = 0.20
MICRO_FINANCE_MAX_PROJECT_COST = 140_000.0
TERM_LOAN_MAX_PROJECT_COST = 5_000_000.0


def _r(value: float) -> float:
    return round(value + 0.0, 2)


def compute_project_cost(available_capital: float) -> float:
    """Project cost implied by a 10% margin contribution (Rs 1,00,000 -> Rs 10,00,000)."""
    if available_capital <= 0:
        raise ValueError("Available margin capital must be positive.")
    return _r(available_capital / MARGIN_SHARE)


def route_scheme_tier(project_cost: float) -> SchemeTier:
    """Fixed threshold routing. Raises ValueError for non-positive or > Rs 50 lakh project cost."""
    if project_cost <= 0:
        raise ValueError("Project cost must be greater than zero.")
    if project_cost <= MICRO_FINANCE_MAX_PROJECT_COST:
        return SchemeTier(
            name="micro_finance", display_name="Micro Finance Scheme",
            max_project_cost=MICRO_FINANCE_MAX_PROJECT_COST, max_loan_amount=125_000.0,
            interest_rate=0.065, tenure_years=3, moratorium_months=3,
        )
    if project_cost <= TERM_LOAN_MAX_PROJECT_COST:
        return SchemeTier(
            name="term_loan", display_name="Term Loan Scheme",
            max_project_cost=TERM_LOAN_MAX_PROJECT_COST, max_loan_amount=4_500_000.0,
            interest_rate=0.08, tenure_years=7, moratorium_months=6,
        )
    raise ValueError(
        f"Project cost Rs {project_cost:,.2f} exceeds the maximum supported concessional scheme "
        f"threshold (Rs {TERM_LOAN_MAX_PROJECT_COST:,.0f})."
    )


def compute_max_loan(project_cost: float, scheme_tier: SchemeTier) -> float:
    """90% of project cost, capped at the tier's maximum loan amount."""
    return min(_r(project_cost * LOAN_SHARE), scheme_tier.max_loan_amount)


def generate_quarterly_schedule(
    loan_amount: float, interest_rate: float, tenure_years: int, moratorium_months: int
) -> tuple[list[QuarterlyRepaymentInstallment], float, float]:
    """Quarterly schedule: interest-only moratorium quarters, then equal quarterly installments.

    Returns (schedule, total_interest, total_repayment).
    """
    total_quarters = tenure_years * 4
    moratorium_quarters = moratorium_months // 3
    repayment_quarters = total_quarters - moratorium_quarters
    rate = interest_rate / 4.0
    balance = _r(loan_amount)
    schedule: list[QuarterlyRepaymentInstallment] = []

    for q in range(1, moratorium_quarters + 1):
        interest = _r(balance * rate)
        schedule.append(QuarterlyRepaymentInstallment(
            quarter_number=q, is_moratorium=True, opening_balance=balance, interest_payment=interest,
            principal_payment=0.0, total_installment=interest, closing_balance=balance,
        ))

    if repayment_quarters > 0 and balance > 0:
        if rate > 0:
            growth = math.pow(1 + rate, repayment_quarters)
            installment = _r(balance * rate * growth / (growth - 1))
        else:
            installment = _r(balance / repayment_quarters)
        for q in range(moratorium_quarters + 1, total_quarters + 1):
            interest = _r(balance * rate)
            if q == total_quarters:
                principal = balance
                payment = _r(principal + interest)
            else:
                principal = _r(installment - interest)
                payment = installment
            closing = _r(balance - principal)
            schedule.append(QuarterlyRepaymentInstallment(
                quarter_number=q, is_moratorium=False, opening_balance=balance, interest_payment=interest,
                principal_payment=principal, total_installment=payment, closing_balance=max(0.0, closing),
            ))
            balance = max(0.0, closing)

    total_interest = _r(sum(i.interest_payment for i in schedule))
    total_repayment = _r(sum(i.total_installment for i in schedule))
    return schedule, total_interest, total_repayment


def build_financial_plan(available_capital: float, business_category: str = "") -> FinancialPlan:
    """End-to-end deterministic structuring. Never raises for out-of-range inputs.

    ``business_category`` is accepted for the contract/logging only; no rule depends on it.
    """
    if available_capital <= 0:
        return FinancialPlan(
            eligibility_status="outside_scheme_range",
            ineligibility_reason="Available margin capital must be positive to compute a project cost.",
            available_margin_capital=_r(max(available_capital, 0.0)), loan_percentage=0.0,
        )

    project_cost = compute_project_cost(available_capital)
    working_capital = _r(project_cost * WORKING_CAPITAL_SHARE)
    capex = _r(project_cost - working_capital)

    if project_cost > TERM_LOAN_MAX_PROJECT_COST:
        return FinancialPlan(
            eligibility_status="outside_scheme_range",
            ineligibility_reason=(
                f"Project cost Rs {project_cost:,.0f} (10% margin of Rs {available_capital:,.0f}) exceeds the "
                f"Rs {TERM_LOAN_MAX_PROJECT_COST:,.0f} ceiling of the Term Loan Scheme; no concessional tier applies."
            ),
            available_margin_capital=_r(available_capital), computed_project_cost=project_cost,
            maximum_loan_eligibility=0.0, margin_percentage=MARGIN_SHARE * 100, loan_percentage=0.0,
            working_capital_requirement=working_capital, capital_expenditure_allocation=capex,
        )

    tier = route_scheme_tier(project_cost)
    loan = compute_max_loan(project_cost, tier)
    cap_applied = _r(project_cost * LOAN_SHARE) > tier.max_loan_amount
    loan_pct = round(loan / project_cost * 100, 2)
    schedule, total_interest, total_repayment = generate_quarterly_schedule(
        loan, tier.interest_rate, tier.tenure_years, tier.moratorium_months
    )
    regular = next((i.total_installment for i in schedule if not i.is_moratorium), 0.0)

    return FinancialPlan(
        eligibility_status="eligible",
        available_margin_capital=_r(available_capital),
        computed_project_cost=project_cost,
        maximum_loan_eligibility=loan,
        margin_percentage=round(100 - loan_pct, 2),
        loan_percentage=loan_pct,
        loan_cap_applied=cap_applied,
        scheme_tier=tier,
        working_capital_requirement=working_capital,
        capital_expenditure_allocation=capex,
        repayment_schedule=schedule,
        regular_quarterly_installment=regular,
        total_interest_payable=total_interest,
        total_repayment_amount=total_repayment,
    )


def run(state: CaseState) -> dict[str, Any]:
    """Build the plan only for a profiled case whose feasibility verdict is 'viable'."""
    profile = state.entrepreneur_profile
    record = state.feasibility_record
    if profile is None or record is None or record.verdict != "viable":
        return {}
    candidate = state.selected_candidate()
    category = (candidate.category if candidate else "") or profile.business_preference or ""
    return {"financial_plan": build_financial_plan(profile.available_capital, category)}
