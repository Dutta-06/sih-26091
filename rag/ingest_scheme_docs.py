"""Build and validate the ``scheme_guidelines`` retrieval index (TECHNICAL_SETUP.md Section 8.6).

Usage:
    python -m rag.ingest_scheme_docs --source data/scheme_guidelines/

The guideline documents are prototype summaries of the problem-statement scheme structure. Their
"key terms" sections are parsed and compared with the deterministic financial engine
(``route_scheme_tier`` and the margin/loan shares) so the explanatory text can never drift from the
figures the engine actually uses. Validation errors make the command exit non-zero.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

from module2_financial.financial_engine import (
    LOAN_SHARE,
    MARGIN_SHARE,
    MICRO_FINANCE_MAX_PROJECT_COST,
    TERM_LOAN_MAX_PROJECT_COST,
    route_scheme_tier,
)
from rag import vector_store

TIER_DOCS = {"micro_finance": ("micro_finance.md", MICRO_FINANCE_MAX_PROJECT_COST),
             "term_loan": ("term_loan.md", TERM_LOAN_MAX_PROJECT_COST)}
REQUIRED_DOCS = ("micro_finance.md", "term_loan.md", "application_process.md", "required_documents.md")


def _number(text: str) -> Optional[float]:
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    return float(match.group().replace(",", "")) if match else None


def parse_key_terms(markdown: str) -> dict[str, str]:
    """``- Label: value`` lines under the '... key terms' heading, keyed by lower-case label."""
    terms: dict[str, str] = {}
    in_section = False
    for line in markdown.splitlines():
        if line.startswith("#"):
            in_section = "key terms" in line.lower()
        elif in_section and line.startswith("- ") and ":" in line:
            label, value = line[2:].split(":", 1)
            terms[label.strip().lower()] = value.strip()
    return terms


def expected_terms(tier_name: str) -> dict[str, float]:
    tier = route_scheme_tier(TIER_DOCS[tier_name][1])
    expected = {
        "maximum project cost": tier.max_project_cost,
        "maximum loan amount": tier.max_loan_amount,
        "beneficiary margin contribution": MARGIN_SHARE * 100,
        "loan share of project cost": LOAN_SHARE * 100,
        "interest rate": round(tier.interest_rate * 100, 4),
        "tenure": tier.tenure_years,
        "moratorium": tier.moratorium_months,
    }
    if tier_name == "term_loan":
        expected["minimum project cost"] = MICRO_FINANCE_MAX_PROJECT_COST
    return expected


def validate_scheme_docs(folder: Path) -> list[str]:
    """Return a list of human-readable mismatches (empty when the docs agree with the engine)."""
    errors = [f"missing document {name}" for name in REQUIRED_DOCS if not (folder / name).is_file()]
    for tier_name, (doc, _) in TIER_DOCS.items():
        path = folder / doc
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "â‚¹" in text or "�" in text:
            errors.append(f"{doc}: contains mojibake / invalid characters")
        terms = parse_key_terms(text)
        for label, value in expected_terms(tier_name).items():
            found = _number(terms.get(label, ""))
            if found is None:
                errors.append(f"{doc}: key term '{label}' missing")
            elif abs(found - value) > 1e-6:
                errors.append(f"{doc}: '{label}' is {found:g} but the engine uses {value:g}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and index scheme guideline documents")
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    from config.settings import settings

    source = args.source or Path(settings.scheme_guidelines_path)
    errors = validate_scheme_docs(source)
    for err in errors:
        print(f"[INVALID] {err}")
    vector_store.reset()
    index = vector_store.build_index("scheme_guidelines", source)
    print(f"Indexed {len(index.chunks)} chunks from {source}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
