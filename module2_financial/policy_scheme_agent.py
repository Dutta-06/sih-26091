"""Policy / Scheme explanation agent (Module 2, TDD Section 6.4).

Reads: state.financial_plan (scheme_tier, eligibility_status, figures - read only)
Writes: state.financial_plan.policy_explanation, .policy_sources, .required_documents, .process_steps;
        state.scheme_reference when a scheme question is asked before any plan exists
Tech: TF-IDF retrieval over data/scheme_guidelines (rag.vector_store.retrieve("scheme_guidelines", ...));
      lists are parsed from the retrieved chunks, prose is assembled from them and optionally rephrased
      by common.llm.explain. Explains rules only: never writes scheme_tier, eligibility or any figure.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from common.llm import explain
from orchestrator.state import CaseState, FinancialPlan
from rag.vector_store import RetrievedChunk, retrieve

COLLECTION = "scheme_guidelines"
TIER_DOC = {"micro_finance": "micro_finance.md", "term_loan": "term_loan.md"}
TIER_LABEL = {"micro_finance": "Micro Finance Scheme", "term_loan": "Term Loan Scheme"}
SYSTEM_PROMPT = (
    "You explain loan scheme rules to a first-time entrepreneur in plain language. Rephrase the text you are given. "
    "Do not change any number, add rules, or say anything about eligibility beyond what the text states."
)
_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*\S)")


def _items(chunks: list[RetrievedChunk]) -> list[str]:
    out: list[str] = []
    for chunk in chunks:
        for line in chunk.text.splitlines():
            match = _ITEM.match(line)
            if match and match.group(1) not in out:
                out.append(match.group(1))
    return out


def _search(query: str, source: str, heading_filter=lambda h: True, top_k: int = 20) -> list[RetrievedChunk]:
    return [c for c in retrieve(COLLECTION, query, top_k=top_k, min_score=0.02)
            if c.source == source and heading_filter(c.heading.lower())]


def explain_scheme(tier_name: Optional[str]) -> dict[str, Any]:
    """Retrieve rules, documents and process steps for a tier (None = both tiers, e.g. outside range)."""
    tiers = [tier_name] if tier_name in TIER_DOC else list(TIER_DOC)
    rule_chunks: list[RetrievedChunk] = []
    for tier in tiers:
        label = TIER_LABEL[tier]
        rule_chunks += _search(f"{label} key terms interest rate tenure moratorium maximum loan project cost",
                               TIER_DOC[tier], lambda h: h != label.lower())
    doc_chunks: list[RetrievedChunk] = []
    if tier_name in TIER_DOC:
        label = TIER_LABEL[tier_name].lower()
        doc_chunks = _search(f"documents required for all applicants and additional documents for the {label}",
                             "required_documents.md", lambda h: "all applicants" in h or label in h)
    step_chunks = _search("application process steps", "application_process.md", lambda h: "steps" in h)
    used = rule_chunks + doc_chunks + step_chunks
    return {
        "rule_chunks": rule_chunks,
        "required_documents": _items(doc_chunks),
        "process_steps": _items(step_chunks),
        "sources": sorted({c.source for c in used}),
    }


def build_explanation(plan: FinancialPlan, retrieved: dict[str, Any]) -> str:
    if plan.eligibility_status == "eligible" and plan.scheme_tier is not None:
        lines = [f"The financial engine placed this case in the {plan.scheme_tier.display_name} based on a project cost "
                 f"of Rs {plan.computed_project_cost:,.0f}. The scheme rules below explain that tier; they do not "
                 "decide eligibility."]
    else:
        reason = plan.ineligibility_reason or "The case is outside the supported scheme range."
        lines = [f"The financial engine found no applicable scheme tier. {reason} The tiers that exist are:"]
    for chunk in retrieved["rule_chunks"]:
        lines.append(f"{chunk.heading} (source: {chunk.source}):\n{chunk.text}")
    if not retrieved["rule_chunks"]:
        lines.append("No scheme guideline text could be retrieved; ask the channelising agency for the rules.")
    lines.append("These guideline documents are prototype summaries of the problem-statement scheme structure, "
                 "not official text; confirm terms with the channelising agency or bank.")
    return "\n\n".join(lines)


def general_reference(retrieved: dict[str, Any]) -> str:
    """Scheme rules for an inquiry made before any financial plan exists (no eligibility statement)."""
    lines = ["No financial plan has been computed for this case yet, so no tier has been assigned. "
             "The scheme tiers are:"]
    lines += [f"{c.heading} (source: {c.source}):\n{c.text}" for c in retrieved["rule_chunks"]]
    if retrieved["process_steps"]:
        lines.append("How to apply:\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(retrieved["process_steps"], 1)))
    lines.append("These guideline documents are prototype summaries of the problem-statement scheme structure, "
                 "not official text; confirm terms with the channelising agency or bank.")
    return "\n\n".join(lines)


def run(state: CaseState) -> dict[str, Any]:
    plan = state.financial_plan
    if plan is None:
        template = general_reference(explain_scheme(None))
        text, _ = explain(SYSTEM_PROMPT, f"Rephrase for the entrepreneur:\n\n{template}", template)
        return {"scheme_reference": text}
    tier_name = plan.scheme_tier.name if plan.eligibility_status == "eligible" and plan.scheme_tier else None
    retrieved = explain_scheme(tier_name)
    template = build_explanation(plan, retrieved)
    text, _ = explain(SYSTEM_PROMPT, f"Rephrase for the entrepreneur:\n\n{template}", template)
    return {"financial_plan": plan.model_copy(update={
        "policy_explanation": text,
        "policy_sources": retrieved["sources"],
        "required_documents": retrieved["required_documents"],
        "process_steps": retrieved["process_steps"],
    })}
