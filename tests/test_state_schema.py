"""CaseState schema conventions and persistence round-trip."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator import persistence
from orchestrator.state import (
    BusinessCandidate,
    CaseState,
    FeasibilityRecord,
    MarketIntelligence,
    MarketReachIntelligence,
    RejectionEntry,
    SessionMeta,
    TransactionRecord,
)


def test_confidence_labels_are_strict():
    assert MarketReachIntelligence().source_confidence == "estimated"
    assert MarketReachIntelligence(source_confidence="real").source_confidence == "real"
    with pytest.raises(ValidationError):
        MarketReachIntelligence(source_confidence="verified")


def test_missing_data_defaults_are_none_not_good_news():
    reach = MarketReachIntelligence()
    assert reach.population_within_radius is None and reach.consumer_base_estimate is None
    mi = MarketIntelligence()
    assert mi.competitor.saturation_level == "unknown" and mi.competitor.z_score_vs_district is None
    assert set(mi.confidence_summary().values()) == {"estimated"}


def test_selected_candidate_and_rejected_ids():
    state = CaseState(session_meta=SessionMeta(session_id="s"))
    assert state.selected_candidate() is None
    state.business_shortlist = [BusinessCandidate(category="A", catalog_id="a"), BusinessCandidate(category="B", catalog_id="b", rank=2)]
    assert state.selected_candidate().catalog_id == "a"
    record = FeasibilityRecord(rejection_history=[RejectionEntry(category="A", catalog_id="a", verdict="marginal")])
    assert record.rejected_catalog_ids() == {"a"}


def test_transaction_record_has_no_raw_text_field():
    assert "raw_text" not in TransactionRecord.model_fields and "message" not in TransactionRecord.model_fields


def test_case_snapshot_round_trip():
    state = CaseState(session_meta=SessionMeta(session_id="persist_1", requested_stage="grievance"),
                      feasibility_record=FeasibilityRecord(verdict="viable", selected_catalog_id="tailoring"))
    persistence.save_case(state)
    loaded = persistence.load_case("persist_1")
    assert loaded.feasibility_record.selected_catalog_id == "tailoring"
    assert loaded.session_meta.requested_stage == "grievance"
    assert persistence.load_case("nope") is None


def test_checkpointer_self_test():
    assert persistence.test_checkpoint()
