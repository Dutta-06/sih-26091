"""Policy & Scheme RAG Agent (Module 2, Section 6.4).

Reads: state.financial_plan.scheme_tier
Writes: state.financial_plan.policy_explanation
Tech: Plain-language explanation of scheme guidelines, subsidy norms, and eligibility criteria.
Constraint: Never modifies eligibility or financial terms; owned exclusively by financial_engine.py.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import CaseState


def run(state: CaseState) -> dict[str, Any]:
    plan = state.financial_plan
    if not plan:
        return {}

    tier_name = plan.scheme_tier.name
    if tier_name == "micro_finance":
        explanation = (
            "Scheme Guidelines (Micro Finance Scheme):\n"
            "• Objective: Concessional lending for ultra-micro income generation activities up to ₹1.40 Lakh project cost.\n"
            "• Beneficiary Margin: Exactly 10% self-contribution; SCA provides 90% (max ₹1.25 Lakh).\n"
            "• Terms: Concessional interest rate of 6.5% p.a., 3-year repayment tenure with a 3-month moratorium.\n"
            "• Pre-payment Penalty: Nil. Concessional credit designed to prevent indebtedness."
        )
    else:
        explanation = (
            "Scheme Guidelines (Term Loan Scheme):\n"
            "• Objective: Concessional medium-scale income generation for projects between ₹1.40 Lakh and ₹50.00 Lakh.\n"
            "• Beneficiary Margin: 10% self-contribution; State Channelizing Agency finances remaining 90% (max ₹45.00 Lakh).\n"
            "• Terms: Concessional interest rate of 8.0% p.a., 7-year repayment tenure with a 6-month moratorium.\n"
            "• Security Norms: Hypothecation of assets created out of loan; personal guarantee per SCA norms."
        )

    plan.policy_explanation = explanation
    return {"financial_plan": plan}
