"""Build and validate the risk-taxonomy retrieval index (TECHNICAL_SETUP.md 8.6-8.7).

    python -m rag.ingest_risk_taxonomy --source data/risk_taxonomy/

Each taxonomy document must be Markdown with a ``# Title`` heading and
``Pattern:`` and ``Mitigation:`` paragraphs. The index is TF-IDF (rag.vector_store)
and is rebuilt in-process; this script validates the corpus and reports chunk counts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config.settings import settings
from rag import vector_store

REQUIRED_MARKERS = ("Pattern:", "Mitigation:")


def validate_corpus(source: Path) -> list[str]:
    problems: list[str] = []
    files = sorted(source.glob("*.md")) if source.exists() else []
    if not files:
        return [f"no .md taxonomy documents found in {source}"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not text.lstrip().startswith("# "):
            problems.append(f"{path.name}: missing '# Title' heading")
        problems.extend(f"{path.name}: missing '{m}' paragraph" for m in REQUIRED_MARKERS if m not in text)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=settings.risk_taxonomy_path)
    args = parser.parse_args(argv)
    problems = validate_corpus(args.source)
    for problem in problems:
        print(f"INVALID: {problem}")
    vector_store.reset()
    index = vector_store.build_index("risk_taxonomy", args.source)
    print(f"risk_taxonomy: {len({c.source for c in index.chunks})} documents, {len(index.chunks)} chunks indexed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
