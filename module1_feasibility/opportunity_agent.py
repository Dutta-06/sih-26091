"""Opportunity Agent (TDD 5.3 opportunity, 5.6 local feedback; TECHNICAL_SETUP §5.4).

Reads: state.selected_candidate() (catalog_id, category, sector), state.entrepreneur_profile.location.district,
       orchestrator.stores.local_feedback(district, catalog_id)
Writes: state.opportunity_intel
Tech: TF-IDF retrieval (rag.vector_store, collection ``sector_reports``) restricted to documents about the
      selected activity; sub-niche extraction from ``## Sub-niche:`` headings or bullet items; rule-based
      saturation classification.

This node runs in parallel with the Competitor Agent, so it cannot read this pass's competitor density.
Sub-niche saturation therefore stays "unknown" ("pending competitor cross-check") unless local feedback
from funded entrepreneurs/residents indicates it; ``swot_synthesis`` completes the cross-check with
:func:`classify_saturation`.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from common.reference import get_activity
from config.settings import settings
from orchestrator import stores
from orchestrator.state import CaseState, DataSourceRef, OpportunityIntelligence, SaturationLevel, SubNiche
from rag.vector_store import RetrievedChunk, retrieve

logger = logging.getLogger(__name__)

MIN_RETRIEVAL_SCORE = 0.02
PENDING_BASIS = "pending competitor cross-check"
_HIGH_CUES = ("saturated", "too many", "overcrowded", "crowded", "many sellers", "price war", "stiff competition")
_LOW_CUES = ("unserved", "no one sells", "nobody sells", "shortage", "few sellers", "no shop", "have to travel",
             "demand exceeds")
_STOPWORDS = {"local", "village", "supply", "sale", "sales", "services", "products", "direct", "small", "farmers"}


def classify_saturation(density_per_10k: Optional[float],
                        benchmark_per_10k: Optional[float]) -> tuple[SaturationLevel, Optional[float], str]:
    """Local competitor density vs a benchmark: ratio ≤0.75 low, ≤1.25 medium, else high.

    Returns (level, score in 0..1 where 0.5 = at benchmark, basis text); missing inputs -> "unknown".
    """
    if density_per_10k is None or benchmark_per_10k is None or benchmark_per_10k <= 0 or density_per_10k < 0:
        return "unknown", None, "competitor density or benchmark unavailable"
    ratio = density_per_10k / benchmark_per_10k
    level: SaturationLevel = "low" if ratio <= 0.75 else "medium" if ratio <= 1.25 else "high"
    return level, round(ratio / (1 + ratio), 3), (
        f"{density_per_10k:.2f} competitors per 10k vs benchmark {benchmark_per_10k:.2f} (ratio {ratio:.2f})"
    )


def _doc_relevance(source: str, activity: dict[str, Any]) -> int:
    """2 = document is about this activity, 1 = same sector and keyword in its topic, 0 = unrelated."""
    prefix, _, topic = Path(source).stem.lower().partition("__")
    cid = activity["id"]
    if prefix == cid or (topic and (topic in cid or cid in topic)):
        return 2
    keywords = [k.lower() for k in activity.get("keywords", []) if k.isascii()]
    topic_words = topic.replace("_", " ")
    if prefix in keywords or (prefix == activity.get("sector") and
                              any(re.search(rf"\b{re.escape(k)}\b", topic_words) for k in keywords)):
        return 1
    return 0


def extract_sub_niches(chunk: RetrievedChunk) -> list[tuple[str, str]]:
    """(name, description) pairs from a ``Sub-niche:`` heading or ``- Name: description`` bullets."""
    if m := re.match(r"\s*sub[- ]?niche\s*[:\-]\s*(.+)", chunk.heading, re.I):
        return [(m.group(1).strip(), " ".join(chunk.text.split()))]
    pairs = []
    for line in chunk.text.splitlines():
        if m := re.match(r"\s*[-*•]\s+\**([^:*\n]{3,70}?)\**\s*[:–—]\s+(.+)", line):
            pairs.append((m.group(1).strip(), m.group(2).strip()))
    return pairs


def _feedback_signal(text: str) -> Optional[SaturationLevel]:
    lowered = text.lower()
    high, low = any(c in lowered for c in _HIGH_CUES), any(c in lowered for c in _LOW_CUES)
    return "high" if high and not low else "low" if low and not high else None


def _mentions(name: str, text: str) -> bool:
    tokens = {t for t in re.findall(r"[a-z]{5,}", name.lower()) if t not in _STOPWORDS}
    return any(t in text.lower() for t in tokens)


def run(state: CaseState) -> dict[str, Any]:
    intel = OpportunityIntelligence()
    candidate = state.selected_candidate()
    activity = get_activity(candidate.catalog_id) if candidate and candidate.catalog_id else None
    if activity is None:
        intel.limitations.append("No catalogued business activity selected; sub-niche retrieval skipped.")
        return {"opportunity_intel": intel}

    intel.sector_niche = f"{activity['category']} ({activity['sector']})"
    query = " ".join([activity["category"], activity["sector"].replace("_", " "),
                      *(k for k in activity.get("keywords", []) if k.isascii())])
    chunks = retrieve("sector_reports", query, top_k=60, min_score=MIN_RETRIEVAL_SCORE)
    scored = [(c, _doc_relevance(c.source, activity)) for c in chunks]
    best = max((r for _, r in scored), default=0)
    relevant = [c for c, r in scored if r and r == best]

    niches: dict[str, SubNiche] = {}
    for chunk in relevant:
        for name, description in extract_sub_niches(chunk):
            key = name.lower()
            if key in niches:
                niches[key].relevance_score = max(niches[key].relevance_score, chunk.score)
                continue
            niches[key] = SubNiche(
                name=name, description=description[:400], evidence=[description[:300]],
                source_document=chunk.source, relevance_score=chunk.score,
                saturation_level="unknown", saturation_basis=PENDING_BASIS, source_confidence="estimated",
            )
    sub_niches = sorted(niches.values(), key=lambda n: n.relevance_score, reverse=True)
    sub_niches = sub_niches[:max(settings.opportunity_top_k, 1)]
    docs = sorted({n.source_document for n in sub_niches if n.source_document})
    intel.sources.append(DataSourceRef(name="Sector reference corpus (sample documents)", source_confidence="estimated",
                                       detail=", ".join(docs) or "no relevant document"))
    if not sub_niches:
        intel.limitations.append(f"No sector reference document in the corpus covers {activity['category']}; "
                                 "no sub-niches could be retrieved.")
    else:
        intel.limitations.append("Sub-niches come from illustrative SAMPLE sector documents, not published "
                                 "NABARD/KVIC model project reports; treat them as prompts for local checking.")

    # --- TDD 5.6: feedback from previously funded entrepreneurs / residents ------
    district = state.entrepreneur_profile.location.district if state.entrepreneur_profile else None
    try:
        feedback = stores.local_feedback(district, activity["id"])
    except Exception as exc:  # store unavailable must not break the node
        logger.warning("local feedback unavailable: %s", exc)
        feedback = []
    overall: set[SaturationLevel] = set()
    conflicted: set[str] = set()
    for row in feedback:
        text = f"{row.get('topic', '')}: {row.get('observation', '')}"
        rating = f", rating {row['rating']}" if row.get("rating") is not None else ""
        intel.local_feedback_evidence.append(f"{row.get('kind', 'feedback')} ({row.get('topic', '')}{rating}): "
                                             f"{row.get('observation', '')}")
        if signal := _feedback_signal(text):
            overall.add(signal)
            for niche in sub_niches:
                if not _mentions(niche.name, text) or niche.name in conflicted:
                    continue
                if niche.saturation_level in ("unknown", signal):
                    niche.saturation_level = signal
                    niche.saturation_basis = "local feedback from funded entrepreneurs / residents"
                else:
                    conflicted.add(niche.name)
                    niche.saturation_level, niche.saturation_basis = "unknown", "conflicting local feedback"
    if len(overall) == 1:
        intel.saturation_level = overall.pop()
        intel.limitations.append("Overall saturation reflects local feedback only and is not yet cross-checked "
                                 "against competitor density.")
    if feedback:
        intel.sources.append(DataSourceRef(name="Local feedback store", source_confidence="estimated",
                                           detail=f"{len(feedback)} observation(s) for {district}"))
    else:
        intel.limitations.append("No feedback from previously funded entrepreneurs or residents is recorded for "
                                 "this district and activity.")

    intel.sub_niches = sub_niches
    intel.unserved_demand_niches = [n.name for n in sub_niches if n.saturation_level == "low"]
    intel.supporting_evidence = [f"{n.name}: {n.description[:160]} [{n.source_document}, sample]" for n in sub_niches]
    intel.data_source_detail = (f"{len(sub_niches)} sub-niche(s) from {len(docs)} sample sector document(s); "
                                f"saturation {PENDING_BASIS} unless local feedback indicates otherwise")
    return {"opportunity_intel": intel}
