"""
Embedding + retrieval wrapper for the Opportunity Agent's RAG pipeline
(design doc Section 5.3 / TECHNICAL_SETUP.md Section 8.6).

Tech: FAISS for the vector index (per the design doc's "FAISS/Chroma"
choice), TF-IDF (scikit-learn) as the default embedding backend so the
project runs with no model download and no GPU. This is a deliberate
substitution for a transformer embedding model, documented in
IMPLEMENTATION_PLAN.md: swap in `sentence-transformers` behind the same
interface later for higher-quality retrieval once that heavier dependency
is acceptable for your deployment target.
"""
from __future__ import annotations

import json
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedDoc:
    text: str
    metadata: dict
    score: float


class VectorStore:
    """FAISS-backed cosine-similarity store over TF-IDF vectors."""

    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = Path(store_path or settings.vector_store_path)
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.index: Optional[faiss.Index] = None
        self.docs: list[str] = []
        self.metadatas: list[dict] = []

    def ingest(self, docs: list[str], metadatas: list[dict]) -> None:
        if len(docs) != len(metadatas):
            raise ValueError("docs and metadatas must be the same length")
        if not docs:
            raise ValueError("cannot ingest an empty document set")

        self.vectorizer = TfidfVectorizer(max_features=4096)
        matrix = self.vectorizer.fit_transform(docs).toarray().astype("float32")
        faiss.normalize_L2(matrix)
        self.index = faiss.IndexFlatIP(matrix.shape[1])
        self.index.add(matrix)
        self.docs = docs
        self.metadatas = metadatas

    def save(self) -> None:
        if self.index is None:
            raise RuntimeError("nothing to save -- call ingest() first")
        self.store_path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.store_path / "index.faiss"))
        with (self.store_path / "vectorizer.pkl").open("wb") as f:
            pickle.dump(self.vectorizer, f)
        with (self.store_path / "docs.json").open("w", encoding="utf-8") as f:
            json.dump({"docs": self.docs, "metadatas": self.metadatas}, f)

    def load(self) -> None:
        index_path = self.store_path / "index.faiss"
        if not index_path.exists():
            raise FileNotFoundError(
                f"No vector store found at {self.store_path}. "
                f"Run `python -m rag.ingest_sector_reports` first."
            )
        self.index = faiss.read_index(str(index_path))
        with (self.store_path / "vectorizer.pkl").open("rb") as f:
            self.vectorizer = pickle.load(f)
        with (self.store_path / "docs.json").open("r", encoding="utf-8") as f:
            payload = json.load(f)
        self.docs = payload["docs"]
        self.metadatas = payload["metadatas"]

    def query(self, text: str, k: int = 5) -> list[RetrievedDoc]:
        if self.index is None:
            self.load()
        vec = self.vectorizer.transform([text]).toarray().astype("float32")
        faiss.normalize_L2(vec)
        scores, idxs = self.index.search(vec, min(k, len(self.docs)))
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            results.append(
                RetrievedDoc(text=self.docs[idx], metadata=self.metadatas[idx], score=float(score))
            )
        return results
