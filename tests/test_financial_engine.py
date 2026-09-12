"""Golden Unit Tests for Deterministic Financial Engine (Module 2, Section 6.1)."""

import pytest
from module2_financial.financial_engine import (
    compute_project_cost,
    compute_max_loan,
    route_scheme_tier,
    generate_quarterly_schedule,
    build_financial_plan,
)


def test_worked_example_problem_statement():
    """Verify the canonical example directly from the SIH problem statement:
    ₹1,00,000 available margin capital ->
    ₹10,00,000 total project cost ->
    ₹9,00,000 loan eligibility (90%) ->
    Term Loan Scheme (8.0% interest, 7-year tenure, 6-month moratorium).
    """
    capital = 100_000.0

    # 1. Project cost
    project_cost = compute_project_cost(capital)
    assert project_cost == 1_000_000.0

    # 2. Scheme routing
    tier = route_scheme_tier(project_cost)
    assert tier.name == "term_loan"
    assert tier.interest_rate == 0.08
    assert tier.tenure_years == 7
    assert tier.moratorium_months == 6

    # 3. Maximum loan eligibility
    loan_amount = compute_max_loan(project_cost, tier)
    assert loan_amount == 900_000.0

    # 4. End-to-end plan
    plan = build_financial_plan(capital, "Dairy Farming")
    assert plan.computed_project_cost == 1_000_000.0
    assert plan.maximum_loan_eligibility == 900_000.0
    assert plan.margin_percentage == 10.0
    assert plan.loan_percentage == 90.0
    assert plan.scheme_tier.name == "term_loan"

    # 5. Repayment schedule assertions
    schedule = plan.repayment_schedule
    assert len(schedule) == 28  # 7 years * 4 quarters = 28 quarters
    
    # Moratorium quarters: quarters 1 and 2 (6 months = 2 quarters)
    assert schedule[0].is_moratorium is True
    assert schedule[0].quarter_number == 1
    assert schedule[0].principal_payment == 0.0
    # Quarterly interest on 9L at 8% p.a. (2% per quarter) = 900,000 * 0.02 = 18,000
    assert schedule[0].interest_payment == 18_000.0
    assert schedule[0].closing_balance == 900_000.0

    assert schedule[1].is_moratorium is True
    assert schedule[1].quarter_number == 2
    assert schedule[1].principal_payment == 0.0
    assert schedule[1].interest_payment == 18_000.0
    assert schedule[1].closing_balance == 900_000.0

    # Post-moratorium: quarter 3 starts amortizing principal
    assert schedule[2].is_moratorium is False
    assert schedule[2].principal_payment > 0.0

    # Final quarter must amortize loan to 0.00
    last_quarter = schedule[-1]
    assert last_quarter.quarter_number == 28
    assert last_quarter.closing_balance == 0.0


def test_micro_finance_scheme_tier():
    """Verify Micro Finance routing for projects <= ₹1.40 Lakh:
    ₹12,000 available capital ->
    ₹1,20,000 project cost ->
    ₹1,08,000 loan eligibility (90%) ->
    Micro Finance Scheme (6.5% interest, 3-year tenure, 3-month moratorium).
    """
    capital = 12_000.0
    project_cost = compute_project_cost(capital)
    assert project_cost == 120_000.0

    tier = route_scheme_tier(project_cost)
    assert tier.name == "micro_finance"
    assert tier.interest_rate == 0.065
    assert tier.tenure_years == 3
    assert tier.moratorium_months == 3

    loan_amount = compute_max_loan(project_cost, tier)
    assert loan_amount == 108_000.0

    plan = build_financial_plan(capital, "Tailoring Shop")
    schedule = plan.repayment_schedule
    assert len(schedule) == 12  # 3 years * 4 quarters = 12 quarters
    assert schedule[0].is_moratorium is True
    assert schedule[0].principal_payment == 0.0
    assert schedule[1].is_moratorium is False
    assert schedule[-1].closing_balance == 0.0


def test_micro_finance_ceiling_cap():
    """Verify that projects costing ₹1.40 Lakh respect the ₹1.25 Lakh loan ceiling."""
    project_cost = 140_000.0
    tier = route_scheme_tier(project_cost)
    loan_amount = compute_max_loan(project_cost, tier)
    # 90% of 140,000 is 126,000, but Micro Finance cap is 125,000
    assert loan_amount == 125_000.0


def test_invalid_inputs():
    """Verify input validation handles non-positive and out-of-bounds amounts."""
    with pytest.raises(ValueError, match="must be positive"):
        compute_project_cost(0.0)

    with pytest.raises(ValueError, match="must be positive"):
        compute_project_cost(-500.0)

    # Over ₹50 Lakh project cost exceeds scheme limits
    with pytest.raises(ValueError, match="exceeds the maximum supported"):
        route_scheme_tier(5_500_000.0)
