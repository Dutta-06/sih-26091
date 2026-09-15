"""Build and validate the ``sector_reports`` retrieval index (TECHNICAL_SETUP §8.6).

Usage:
    python -m rag.ingest_sector_reports --source data/reference_corpus

Documents are Markdown/text/PDF files named ``<sector>__<activity_id>.<ext>`` with
``# Sector: ...`` and ``## Sub-niche: ...`` headings. The bundled files are
illustrative SAMPLES; drop published NABARD/KVIC model project reports into the
same folder (``REFERENCE_CORPUS_PATH``) to replace them. The TF-IDF index is
rebuilt in memory by ``rag.vector_store`` at first use in each process, so this
script builds it once to validate the corpus and reports chunk counts.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Optional

from config.settings import settings
from rag import vector_store


def ingest(source_dir: Optional[Path] = None) -> tuple[dict[str, int], list[str]]:
    """Index ``source_dir`` as ``sector_reports``; returns (chunk count per document, convention warnings)."""
    folder = Path(source_dir or settings.reference_corpus_path)
    if not folder.is_dir():
        raise FileNotFoundError(f"Sector report folder not found: {folder}")
    chunks = vector_store.build_index("sector_reports", folder).chunks
    if not chunks:
        raise ValueError(f"No .md/.txt/.pdf sector reports with text found in {folder}")
    counts = dict(sorted(Counter(c.source for c in chunks).items()))
    with_niches = {c.source for c in chunks if c.heading.lower().startswith("sub-niche")}
    warnings = [f"{s}: file name lacks the '<sector>__<activity>' form" for s in counts if "__" not in Path(s).stem]
    warnings += [f"{s}: no '## Sub-niche:' headings (only bullet extraction possible)" for s in counts
                 if s not in with_niches]
    return counts, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/validate the sector report retrieval index")
    parser.add_argument("--source", type=Path, default=None)
    source = parser.parse_args().source or Path(settings.reference_corpus_path)
    counts, warnings = ingest(source)
    for name, n in counts.items():
        print(f"{n:4d}  {name}")
    print(f"Indexed {sum(counts.values())} chunks from {len(counts)} documents in {source}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if Path(source).resolve() != Path(settings.reference_corpus_path).resolve():
        print(f"Note: agents read REFERENCE_CORPUS_PATH ({settings.reference_corpus_path}); set it to use this corpus.")


if __name__ == "__main__":
    main()
