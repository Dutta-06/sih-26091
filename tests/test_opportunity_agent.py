"""Opportunity Agent: sector-restricted sub-niche retrieval, pending saturation, local feedback, classifier."""

from __future__ import annotations

import pytest

from common.reference import load_catalog
from config.settings import settings
from module1_feasibility import opportunity_agent
from orchestrator import stores
from orchestrator.state import BusinessCandidate, CaseState, EntrepreneurProfile, LocationDetails, SessionMeta
from rag import vector_store
from rag.ingest_sector_reports import ingest


@pytest.fixture(autouse=True)
def _index():
    vector_store.reset()
    yield
    vector_store.reset()


def _state(catalog_id: str, district: str | None = None) -> CaseState:
    a = load_catalog()[catalog_id]
    return CaseState(
        entrepreneur_profile=EntrepreneurProfile(location_query="q", location=LocationDetails(district=district)),
        business_shortlist=[BusinessCandidate(category=a["category"], catalog_id=catalog_id, sector=a["sector"])],
        session_meta=SessionMeta(session_id="t"),
    )


def test_ingest_reports_counts_and_no_warnings():
    counts, warnings = ingest(settings.reference_corpus_path)
    assert sum(counts.values()) > 0
    assert warnings == []


@pytest.mark.parametrize("catalog_id", sorted(load_catalog()))
def test_every_catalog_activity_gets_sub_niches(catalog_id):
    intel = opportunity_agent.run(_state(catalog_id))["opportunity_intel"]
    assert intel.sub_niches, catalog_id
    assert intel.source_confidence == "estimated"
    assert any("SAMPLE" in l for l in intel.limitations)
    for niche in intel.sub_niches:
        assert niche.saturation_level == "unknown"
        assert niche.saturation_basis == opportunity_agent.PENDING_BASIS
        assert niche.evidence and niche.source_document
    assert intel.unserved_demand_niches == []


def test_sub_niches_come_only_from_the_activity_documents():
    dairy = opportunity_agent.run(_state("dairy_farming"))["opportunity_intel"]
    assert {n.source_document for n in dairy.sub_niches} == {"animal_husbandry__dairy_farming.md"}
    handloom = opportunity_agent.run(_state("handloom_weaving"))["opportunity_intel"]
    assert {n.source_document for n in handloom.sub_niches} == {"textiles_apparel__handloom_weaving.md"}
    names = {n.name for n in handloom.sub_niches}
    assert len(names) == len(handloom.sub_niches)
    assert not names & {"Handloom Weaving Unit", "textiles_apparel"}


def test_no_candidate_degrades():
    intel = opportunity_agent.run(CaseState(session_meta=SessionMeta(session_id="t")))["opportunity_intel"]
    assert intel.sub_niches == [] and intel.limitations


def test_local_feedback_is_incorporated():
    stores.add_local_feedback("funded_entrepreneur", "Testpur", "competition",
                              "Too many paneer sellers already supply the sweet shops here.", catalog_id="dairy_farming",
                              rating=2)
    intel = opportunity_agent.run(_state("dairy_farming", district="Testpur"))["opportunity_intel"]
    assert intel.local_feedback_evidence and "paneer" in intel.local_feedback_evidence[0]
    assert intel.saturation_level == "high"
    paneer = [n for n in intel.sub_niches if "Paneer" in n.name]
    assert paneer and paneer[0].saturation_level == "high"
    assert "local feedback" in paneer[0].saturation_basis
    others = [n for n in intel.sub_niches if "Paneer" not in n.name]
    assert all(n.saturation_level == "unknown" for n in others)


def test_extract_bullet_sub_niches():
    chunk = vector_store.RetrievedChunk(text="- **Door delivery**: morning milk rounds\n- Fodder bank: shared fodder",
                                        source="animal_husbandry__dairy_farming.txt", heading="Options", score=0.2)
    assert opportunity_agent.extract_sub_niches(chunk) == [("Door delivery", "morning milk rounds"),
                                                           ("Fodder bank", "shared fodder")]


@pytest.mark.parametrize("density,benchmark,level", [
    (1.5, 2.0, "low"), (2.5, 2.0, "medium"), (3.0, 2.0, "high"), (None, 2.0, "unknown"), (1.0, None, "unknown"),
    (1.0, 0.0, "unknown"),
])
def test_classify_saturation(density, benchmark, level):
    got, score, basis = opportunity_agent.classify_saturation(density, benchmark)
    assert got == level
    assert (score is None) == (level == "unknown")
    assert basis
