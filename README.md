# Module 2: Financial Structuring and Funding Preparation

This module provides the financial planning and credit assessment pipeline for micro-enterprise loan applications.

## Implemented Agents

### 1. Financial Engine (`module2_financial/financial_engine.py`)
A deterministic mathematical engine with zero LLM calls. It computes total project cost (10% promoter contribution), requested loan amount (90% debt), and working capital allocation (20%). It routes applications based on project cost thresholds:
- Project Cost <= Rs 1.40 Lakh: Micro Finance Scheme (6.5% interest, 3-year tenure, 3-month moratorium)
- Project Cost > Rs 1.40 Lakh and <= Rs 50.00 Lakh: Term Loan Scheme (8.0% interest, 7-year tenure, 6-month moratorium)
- Project Cost > Rs 50.00 Lakh: Ineligible (exceeds scheme limits)

It generates the full month-by-month repayment schedule with interest-only moratorium and amortized repayment periods.

### 2. Financial Analyst Agent (`module2_financial/financial_analyst_agent.py`)
A structured reasoning agent that interprets deterministic financial figures in plain language. It evaluates whether projected operating surplus is sufficient to service the monthly loan installment. It computes debt-service coverage ratio (DSCR), margin of safety, and working capital runway, while identifying operational risks and actionable recommendations without modifying deterministic figures.

### 3. Scenario / Digital Twin Agent (`module2_financial/scenario_digital_twin.py`)
A stress-testing agent that simulates month-by-month cash flow trajectories over the full loan schedule to determine whether the business maintains liquidity during lean seasons. It evaluates four distinct scenarios:
- Baseline: Normal business conditions with average demand and stable input costs.
- Seasonal Demand Cycle: Ingests 12-month demand multipliers and seasonal trough drops from the risk model.
- Raw Material Inflation Shock: Evaluates the impact of a 15% surge in input costs (COGS).
- Compound Stress: Simultaneous occurrence of lean seasonal demand and elevated input costs.

It classifies overall resilience (resilient, vulnerable, or critical risk) and generates actionable liquidity mitigation strategies.

## Evaluation

Run golden case checks:
```bash
python3 -m eval.harness --module all
```
