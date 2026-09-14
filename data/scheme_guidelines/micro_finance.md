# Micro Finance Scheme

> Prototype summary of the scheme structure described in the problem statement (SIH 26091). This is NOT
> official guideline text. Confirm every term with the State Channelising Agency (SCA) or lending bank
> before applying. Figures in "Key terms" are validated against the platform's financial engine by
> `python -m rag.ingest_scheme_docs --source data/scheme_guidelines/`.

## Who the Micro Finance Scheme is for

The Micro Finance Scheme is the smaller concessional tier. It serves very small income-generating
activities, such as a tailoring unit, a tea stall or a small backyard poultry unit, whose total project
cost does not exceed the Micro Finance ceiling. Eligibility and the loan amount are decided by fixed
rules in the financial engine, not by this document.

## Micro Finance Scheme key terms

- Maximum project cost: ₹1,40,000
- Maximum loan amount: ₹1,25,000
- Beneficiary margin contribution: 10%
- Loan share of project cost: 90%
- Interest rate: 6.5% per annum
- Tenure: 3 years
- Moratorium: 3 months
- Repayment frequency: quarterly

## How the Micro Finance loan is repaid

The loan is repaid over the tenure in quarterly installments. The moratorium is counted inside the
tenure: during the moratorium quarter only interest is paid and no principal. After the moratorium,
equal quarterly installments repay the principal with interest, and the final quarter clears the
remaining balance.

## Micro Finance loan cap

The loan share is 90% of project cost, but the loan cannot exceed the maximum loan amount. For project
costs close to the ceiling, 90% of the cost is more than the cap, so the entrepreneur must contribute
slightly more than 10% to cover the difference.
