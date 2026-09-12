"""Deterministic Financial Structuring Engine (Module 2, Section 6.1).

CRITICAL ARCHITECTURAL PRINCIPLE:
Deterministic core, reasoning periphery.
All eligibility, project cost, loan amount, interest, tenure, and EMI calculations
are computed by fixed rules and pure functions, NEVER inferred by a language model.
"""

from __future__ import annotations

import math
from typing import Any
from orchestrator.state import (
    CaseState,
    FinancialPlan,
    QuarterlyRepaymentInstallment,
    SchemeTier,
)


def compute_project_cost(available_capital: float) -> float:
    """Computes total feasible project cost from stated available margin capital.
    
    Treats available margin as exactly a 10% contribution.
    Example: ₹1,00,000 / 0.10 = ₹10,00,000.
    """
    if available_capital <= 0:
        raise ValueError("Available margin capital must be positive.")
    return round(available_capital / 0.10, 2)


def compute_max_loan(project_cost: float, scheme_tier: SchemeTier) -> float:
    """Computes maximum loan eligibility (90% of project cost, capped at scheme ceiling).
    
    Example: ₹10,00,000 * 0.90 = ₹9,00,000 (below Term Loan max ₹45L).
    For Micro Finance (<= ₹1.40L), max loan is capped at ₹1,25,000.
    """
    theoretical_loan = round(project_cost * 0.90, 2)
    return min(theoretical_loan, scheme_tier.max_loan_amount)


def route_scheme_tier(project_cost: float) -> SchemeTier:
    """Applies fixed threshold logic to route the case to the applicable scheme tier.
    
    Logic A: Project Cost <= ₹1.40 Lakh -> Micro Finance Scheme (6.5%, 3y, 3m moratorium)
    Logic B: Project Cost > ₹1.40 Lakh and <= ₹50.00 Lakh -> Term Loan Scheme (8%, 7y, 6m moratorium)
    """
    if project_cost <= 0:
        raise ValueError("Project cost must be greater than zero.")
    elif project_cost <= 140_000:
        return SchemeTier(
            name="micro_finance",
            display_name="Micro Finance Scheme",
            max_project_cost=140_000.0,
            max_loan_amount=125_000.0,
            interest_rate=0.065,  # 6.5% p.a.
            tenure_years=3,       # 3 years = 12 quarters
            moratorium_months=3,  # 3 months = 1 quarter
        )
    elif project_cost <= 5_000_000:
        return SchemeTier(
            name="term_loan",
            display_name="Term Loan Scheme",
            max_project_cost=5_000_000.0,
            max_loan_amount=4_500_000.0,
            interest_rate=0.08,   # 8.0% p.a.
            tenure_years=7,       # 7 years = 28 quarters
            moratorium_months=6,  # 6 months = 2 quarters
        )
    else:
        raise ValueError(
            f"Project cost ₹{project_cost:,.2f} exceeds the maximum supported concessional scheme threshold (₹50,00,000)."
        )


def generate_quarterly_schedule(
    loan_amount: float,
    interest_rate: float,
    tenure_years: int,
    moratorium_months: int,
) -> tuple[list[QuarterlyRepaymentInstallment], float, float]:
    """Generates a period-by-period quarterly repayment schedule reflecting moratorium period.
    
    During moratorium quarters:
      - Principal installment = 0.
      - Quarterly interest is serviced.
    Post-moratorium quarters:
      - Standard Equal Quarterly Installment (EQI) amortization over the remaining quarters.
    """
    total_quarters = tenure_years * 4
    moratorium_quarters = moratorium_months // 3
    repayment_quarters = total_quarters - moratorium_quarters

    quarterly_rate = interest_rate / 4.0
    schedule: list[QuarterlyRepaymentInstallment] = []

    current_balance = loan_amount
    total_interest = 0.0
    total_repayment = 0.0

    # 1. Moratorium period quarters
    for q in range(1, moratorium_quarters + 1):
        interest_payment = round(current_balance * quarterly_rate, 2)
        schedule.append(
            QuarterlyRepaymentInstallment(
                quarter_number=q,
                is_moratorium=True,
                opening_balance=current_balance,
                interest_payment=interest_payment,
                principal_payment=0.0,
                total_installment=interest_payment,
                closing_balance=current_balance,
            )
        )
        total_interest += interest_payment
        total_repayment += interest_payment

    # 2. Post-moratorium amortization (Equal Quarterly Installments)
    if repayment_quarters > 0 and current_balance > 0:
        # Standard amortization factor: (r * (1+r)^n) / ((1+r)^n - 1)
        factor = (quarterly_rate * math.pow(1 + quarterly_rate, repayment_quarters)) / (
            math.pow(1 + quarterly_rate, repayment_quarters) - 1
        )
        equal_quarterly_installment = round(current_balance * factor, 2)

        for q in range(moratorium_quarters + 1, total_quarters + 1):
            interest_payment = round(current_balance * quarterly_rate, 2)
            
            # For the last quarter, adjust principal to match exact remaining balance
            if q == total_quarters:
                principal_payment = current_balance
                total_installment = round(principal_payment + interest_payment, 2)
                closing_balance = 0.0
            else:
                principal_payment = round(equal_quarterly_installment - interest_payment, 2)
                closing_balance = round(current_balance - principal_payment, 2)

            schedule.append(
                QuarterlyRepaymentInstallment(
                    quarter_number=q,
                    is_moratorium=False,
                    opening_balance=current_balance,
                    interest_payment=interest_payment,
                    principal_payment=principal_payment,
                    total_installment=total_installment if q == total_quarters else equal_quarterly_installment,
                    closing_balance=max(0.0, closing_balance),
                )
            )

            total_interest += interest_payment
            total_repayment += (total_installment if q == total_quarters else equal_quarterly_installment)
            current_balance = max(0.0, closing_balance)

    return schedule, round(total_interest, 2), round(total_repayment, 2)


def build_financial_plan(available_capital: float, business_category: str = "") -> FinancialPlan:
    """End-to-end pure deterministic financial structuring for a stated available margin capital."""
    project_cost = compute_project_cost(available_capital)
    scheme_tier = route_scheme_tier(project_cost)
    loan_eligibility = compute_max_loan(project_cost, scheme_tier)

    # Standard rural micro-enterprise capital split: 20% working capital, 80% capex
    working_capital = round(project_cost * 0.20, 2)
    capex = round(project_cost * 0.80, 2)

    schedule, total_interest, total_repayment = generate_quarterly_schedule(
        loan_amount=loan_eligibility,
        interest_rate=scheme_tier.interest_rate,
        tenure_years=scheme_tier.tenure_years,
        moratorium_months=scheme_tier.moratorium_months,
    )

    return FinancialPlan(
        available_margin_capital=available_capital,
        computed_project_cost=project_cost,
        maximum_loan_eligibility=loan_eligibility,
        margin_percentage=10.0,
        loan_percentage=90.0,
        scheme_tier=scheme_tier,
        working_capital_requirement=working_capital,
        capital_expenditure_allocation=capex,
        repayment_schedule=schedule,
        total_interest_payable=total_interest,
        total_repayment_amount=total_repayment,
        analyst_commentary="",  # populated by financial_analyst_agent
        policy_explanation="",  # populated by policy_scheme_agent
    )


def run(state: CaseState) -> dict[str, Any]:
    """LangGraph node callable signature: def run(state: CaseState) -> dict[str, Any]."""
    if not state.entrepreneur_profile:
        raise ValueError("Cannot execute Financial Engine without an EntrepreneurProfile.")

    capital = state.entrepreneur_profile.available_capital
    category = state.entrepreneur_profile.business_preference or "General Micro-Enterprise"

    plan = build_financial_plan(capital, category)
    return {"financial_plan": plan}
