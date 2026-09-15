"""Policy & Scheme RAG Agent (Module 2, Section 6.4).

Reads: state.financial_plan.scheme_tier
Writes: state.financial_plan.policy_explanation
Tech: RAG over scheme guideline documents (embedding model plus vector retrieval).
Constraint: Never modifies eligibility or financial terms; owned exclusively by financial_engine.py.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import CaseState
from config.settings import settings
from rag.vector_store import get_retriever


def _mock_llm_chain(query: str, context: str) -> str:
    """Mock LLM response generation that summarizes the retrieved context."""
    if settings.LLM_API_KEY == "mock-key":
        return (
            f"[Mock LLM Output using {settings.LLM_MODEL}]\n"
            f"Based on the scheme rules for '{query}', here is the plain-language explanation:\n\n"
            f"{context.strip()}\n\n"
            "This eligibility was determined deterministically by the financial engine."
        )
    else:
        # In a real setup, this would invoke a LangChain ChatModel like ChatGoogleGenerativeAI
        return f"Real LLM explanation for {query}:\n{context}"


def run(state: CaseState) -> dict[str, Any]:
    plan = state.financial_plan
    if not plan:
        return {}

    tier_name = plan.scheme_tier.name
    
    # 1. Retrieve scheme guidelines via RAG
    retriever = get_retriever()
    docs = retriever.invoke(tier_name)
    
    # 2. Combine context
    context = "\n\n".join(d.page_content for d in docs)
    
    # 3. Generate explanation using LLM (mocked based on settings)
    explanation = _mock_llm_chain(tier_name, context)

    plan.policy_explanation = explanation
    return {"financial_plan": plan}
