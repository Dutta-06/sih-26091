# Term Loan Scheme

> Prototype summary of the scheme structure described in the problem statement (SIH 26091). This is NOT
> official guideline text. Confirm every term with the State Channelising Agency (SCA) or lending bank
> before applying. Figures in "Key terms" are validated against the platform's financial engine by
> `python -m rag.ingest_scheme_docs --source data/scheme_guidelines/`.

## Who the Term Loan Scheme is for

The Term Loan Scheme is the larger concessional tier. It serves income-generating projects whose total
project cost is above the Micro Finance ceiling of ₹1,40,000 and up to the Term Loan ceiling, such as a
dairy unit, a flour mill or a food processing unit. Projects costing more than the Term Loan ceiling are
outside the supported scheme range. Eligibility and the loan amount are decided by fixed rules in the
financial engine, not by this document.

## Term Loan Scheme key terms

- Minimum project cost: above ₹1,40,000
- Maximum project cost: ₹50,00,000
- Maximum loan amount: ₹45,00,000
- Beneficiary margin contribution: 10%
- Loan share of project cost: 90%
- Interest rate: 8% per annum
- Tenure: 7 years
- Moratorium: 6 months
- Repayment frequency: quarterly

## How the Term Loan is repaid

The loan is repaid over the tenure in quarterly installments. The moratorium is counted inside the
tenure: during the two moratorium quarters only interest is paid and no principal, giving the unit time
to start operating. After the moratorium, equal quarterly installments repay the principal with
interest, and the final quarter clears the remaining balance.

## How the Term Loan project cost is split

The platform shows an indicative planning split of the project cost into 80% capital expenditure
(machinery, animals, shed, equipment) and 20% working capital (raw material, running costs until sales
begin). The lender's appraisal of the project report decides the actual split.
