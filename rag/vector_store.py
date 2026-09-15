"""Retrieval wrapper shared by the Opportunity, Risk and Policy agents.

TECHNICAL_SETUP.md Section 8.6. Each *collection* is a folder of plain-text /
Markdown (and optionally PDF) documents that is chunked and indexed with a
TF-IDF vectoriser; queries are ranked by cosine similarity. TF-IDF is used
instead of a neural embedding model so the prototype needs no model download
or GPU; the interface is kept small so a dense-embedding backend can replace it
without touching the agents.

Collections:
    sector_reports    -> settings.reference_corpus_path
    risk_taxonomy     -> settings.risk_taxonomy_path
    scheme_guidelines -> settings.scheme_guidelines_path
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from config.settings import settings

COLLECTIONS = {
    "sector_reports": lambda: settings.reference_corpus_path,
    "risk_taxonomy": lambda: settings.risk_taxonomy_path,
    "scheme_guidelines": lambda: settings.scheme_guidelines_path,
}


@dataclass
class RetrievedChunk:
    text: str
    source: str  # file name relative to the collection folder
    heading: str
    score: float


@dataclass
class _Index:
    chunks: list[RetrievedChunk]
    vectorizer: Optional[TfidfVectorizer]
    matrix: object


_indexes: dict[str, _Index] = {}


def _read_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_document(text: str, source: str, max_chars: int = 900) -> list[RetrievedChunk]:
    """Split on Markdown headings / blank lines, then pack paragraphs up to max_chars."""
    chunks: list[RetrievedChunk] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            chunks.append(RetrievedChunk(text=body, source=source, heading=heading, score=0.0))
        buffer.clear()

    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        first_line = block.splitlines()[0]
        if first_line.startswith("#"):
            flush()
            heading = first_line.lstrip("#").strip()
            block = "\n".join(block.splitlines()[1:]).strip()
            if not block:
                continue
        if sum(len(b) for b in buffer) + len(block) > max_chars:
            flush()
        buffer.append(block)
    flush()
    return chunks


def build_index(collection: str, source_dir: Optional[Path] = None) -> _Index:
    folder = Path(source_dir) if source_dir else Path(COLLECTIONS[collection]())
    chunks: list[RetrievedChunk] = []
    if folder.exists():
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".pdf"}:
                chunks.extend(chunk_document(_read_document(path), str(path.relative_to(folder))))
    if not chunks:
        index = _Index(chunks=[], vectorizer=None, matrix=None)
    else:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        matrix = vectorizer.fit_transform([f"{c.heading}\n{c.text}" for c in chunks])
        index = _Index(chunks=chunks, vectorizer=vectorizer, matrix=matrix)
    _indexes[collection] = index
    return index


def retrieve(collection: str, query: str, top_k: int = 5, min_score: float = 0.05) -> list[RetrievedChunk]:
    """Top-k chunks for ``query`` whose cosine similarity is at least ``min_score``."""
    index = _indexes.get(collection) or build_index(collection)
    if not index.chunks or index.vectorizer is None:
        return []
    scores = linear_kernel(index.vectorizer.transform([query]), index.matrix).ravel()
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [
        RetrievedChunk(text=index.chunks[i].text, source=index.chunks[i].source,
                       heading=index.chunks[i].heading, score=round(float(scores[i]), 4))
        for i in ranked
        if scores[i] >= min_score
    ]


def reset() -> None:
    """Drop cached indexes (used by ingestion scripts and tests)."""
    _indexes.clear()
