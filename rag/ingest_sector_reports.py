"""
Ingestion CLI for the NABARD/KVIC sector-report corpus feeding the
Opportunity Agent (TECHNICAL_SETUP.md Section 8.6).

Usage:
    python -m rag.ingest_sector_reports --source data/reference_corpus/

DATA CAVEAT (see IMPLEMENTATION_PLAN.md Section 4): the .txt files shipped
under data/reference_corpus/ are short SAMPLE snippets written for this
prototype, not real NABARD/KVIC documents. Real model project reports are
PDFs published on nabard.org and kvic.gov.in and have to be collected
manually, sector by sector -- there is no bulk API for this corpus. This
script accepts both .txt and .pdf so real reports can be dropped into the
same folder later with no code changes.

File naming convention: `<sector>__<anything>.txt` (or .pdf) -- the part
before the first "__" is used as the sector label in retrieval metadata.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


def _read_text_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "pypdf is required to ingest PDF sector reports: pip install pypdf"
            ) from e
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8")


def _chunk(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


def ingest(source_dir: Path) -> int:
    files = sorted(list(source_dir.glob("*.txt")) + list(source_dir.glob("*.pdf")))
    if not files:
        raise FileNotFoundError(f"No .txt or .pdf sector reports found in {source_dir}")

    docs: list[str] = []
    metadatas: list[dict] = []
    for path in files:
        text = _read_text_file(path)
        sector = path.stem.split("__")[0]
        for chunk in _chunk(text):
            docs.append(chunk)
            metadatas.append({"sector": sector, "source_file": path.name})

    store = VectorStore()
    store.ingest(docs, metadatas)
    store.save()
    logger.info("Ingested %d chunks from %d files into %s", len(docs), len(files), store.store_path)
    return len(docs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest sector reports into the RAG vector store")
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    from config.settings import settings

    source = args.source or Path(settings.reference_corpus_path)
    n = ingest(source)
    print(f"Ingested {n} chunks from {source}")


if __name__ == "__main__":
    main()
