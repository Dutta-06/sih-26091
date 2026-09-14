"""Policy / scheme explanation agent and guideline-document drift checks (TDD 6.4)."""

import shutil

import pytest

from config.settings import settings
from module2_financial import policy_scheme_agent
from module2_financial.financial_engine import build_financial_plan
from orchestrator.state import CaseState, SessionMeta
from rag import vector_store
from rag.ingest_scheme_docs import expected_terms, parse_key_terms, validate_scheme_docs


@pytest.fixture(autouse=True)
def fresh_index():
    vector_store.reset()
    yield
    vector_store.reset()


def _state(capital):
    return CaseState(session_meta=SessionMeta(session_id="t"), financial_plan=build_financial_plan(capital))


def test_guideline_numbers_match_engine():
    assert validate_scheme_docs(settings.scheme_guidelines_path) == []
    for tier, doc in (("micro_finance", "micro_finance.md"), ("term_loan", "term_loan.md")):
        terms = parse_key_terms((settings.scheme_guidelines_path / doc).read_text(encoding="utf-8"))
        assert set(expected_terms(tier)) <= set(terms)


def test_validator_detects_drift(tmp_path):
    folder = tmp_path / "schemes"
    shutil.copytree(settings.scheme_guidelines_path, folder)
    doc = folder / "micro_finance.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace("6.5% per annum", "7% per annum"), encoding="utf-8")
    (folder / "required_documents.md").unlink()
    errors = validate_scheme_docs(folder)
    assert any("interest rate" in e and "7" in e for e in errors)
    assert any("missing document required_documents.md" in e for e in errors)


def test_guideline_docs_are_clean_utf8_and_marked_as_prototype():
    for path in settings.scheme_guidelines_path.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "â‚¹" not in text and "�" not in text
        assert "NOT official guideline text" in " ".join(text.replace(">", " ").split())


def test_retrieval_returns_sources():
    chunks = vector_store.retrieve("scheme_guidelines", "Term Loan Scheme interest rate moratorium")
    assert chunks and chunks[0].source == "term_loan.md"


def test_agent_explains_eligible_tier_with_sources_documents_and_steps():
    state = _state(100_000.0)
    before = state.financial_plan.model_dump(exclude={"policy_explanation", "policy_sources", "required_documents", "process_steps"})
    plan = policy_scheme_agent.run(state)["financial_plan"]
    assert plan.model_dump(exclude={"policy_explanation", "policy_sources", "required_documents", "process_steps"}) == before
    assert plan.scheme_tier == state.financial_plan.scheme_tier
    assert "term_loan.md" in plan.policy_sources and "micro_finance.md" not in plan.policy_sources
    assert "8% per annum" in plan.policy_explanation and "do not decide eligibility" in plan.policy_explanation
    assert "Udyam registration certificate" in plan.required_documents
    assert "Identity proof (Aadhaar card or voter ID)" in plan.required_documents
    assert not any("Self-help group" in d for d in plan.required_documents)
    assert len(plan.process_steps) >= 5
    assert state.financial_plan.policy_explanation == ""  # input state not mutated


def test_agent_micro_tier_documents():
    plan = policy_scheme_agent.run(_state(12_000.0))["financial_plan"]
    assert "micro_finance.md" in plan.policy_sources and "6.5% per annum" in plan.policy_explanation
    assert any("Self-help group" in d for d in plan.required_documents)
    assert "Udyam registration certificate" not in plan.required_documents


def test_agent_outside_range_does_not_assign_tier():
    plan = policy_scheme_agent.run(_state(600_000.0))["financial_plan"]
    assert plan.scheme_tier is None and plan.eligibility_status == "outside_scheme_range"
    assert "no applicable scheme tier" in plan.policy_explanation
    assert {"micro_finance.md", "term_loan.md"} <= set(plan.policy_sources)
    assert plan.required_documents == []


def test_agent_without_plan_answers_scheme_inquiry_without_eligibility():
    update = policy_scheme_agent.run(CaseState(session_meta=SessionMeta(session_id="t")))
    assert set(update) == {"scheme_reference"}
    text = update["scheme_reference"]
    assert "Micro Finance Scheme" in text and "Term Loan Scheme" in text and "no tier has been assigned" in text
