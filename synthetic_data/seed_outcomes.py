"""Synthetic outcome seed for the outcome learning loop cold start (TDD 7.5, TECHNICAL_SETUP 7.6).

Run once: ``python -m synthetic_data.seed_outcomes``. Writes ``settings.synthetic_outcomes_path`` deterministically
(fixed RNG seed) and inserts the records into the outcome store with ``is_synthetic=1``. Re-running is idempotent:
records are inserted only when the store holds no synthetic records yet.

Patterns are illustrative assumptions, NOT observed outcomes: a base improvement probability per intervention type,
nudged per activity (perishable activities respond better to supply-chain changes and worse to pricing changes;
activities with thin operating margins respond less to repayment counselling).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Optional

from common.reference import load_catalog
from config.settings import settings
from orchestrator import stores
from orchestrator.state import utc_now_iso

SEED = 26091
RECORDS_PER_INTERVENTION = 6
BASE_IMPROVEMENT = {"pricing_adjustment": 0.55, "supply_chain_change": 0.60,
                    "mentor_outreach": 0.50, "repayment_counselling": 0.45}


def generate() -> dict[str, Any]:
    rng = random.Random(SEED)
    records = []
    for cid, act in sorted(load_catalog().items()):
        for kind, base in BASE_IMPROVEMENT.items():
            p = base
            if act.get("perishable"):
                p += 0.10 if kind == "supply_chain_change" else -0.05 if kind == "pricing_adjustment" else 0
            if kind == "repayment_counselling" and act.get("operating_margin", 0.3) < 0.2:
                p -= 0.10
            for _ in range(RECORDS_PER_INTERVENTION):
                before = round(rng.uniform(30, 62), 1)
                delta = rng.uniform(3, 18) if rng.random() < p else -rng.uniform(0, 12)
                records.append({"catalog_id": cid, "district": None, "intervention_type": kind,
                                "health_before": before, "health_after": round(min(100, before + delta), 1),
                                "is_synthetic": True})
    return {"_meta": {"is_synthetic": True, "seed": SEED,
                      "description": "SYNTHETIC cold-start outcome records (illustrative, not observed). "
                                     "Down-weighted and progressively replaced by genuine outcome records."},
            "records": records}


def insert(records: list[dict[str, Any]]) -> int:
    """Insert synthetic records unless the store already has some. Returns the number inserted."""
    with stores.connect() as c:
        if c.execute("SELECT 1 FROM outcome_records WHERE is_synthetic = 1 LIMIT 1").fetchone():
            return 0
        now = utc_now_iso()
        c.executemany(
            "INSERT INTO outcome_records (catalog_id, district, intervention_type, health_before, health_after,"
            " improved, is_synthetic, session_id, recorded_at) VALUES (?, ?, ?, ?, ?, ?, 1, NULL, ?)",
            [(r["catalog_id"], r["district"], r["intervention_type"], r["health_before"], r["health_after"],
              int(r["health_after"] > r["health_before"]), now) for r in records if r.get("is_synthetic") is True],
        )
    return len(records)


def load_or_generate(path: Optional[Path] = None) -> dict[str, Any]:
    path = Path(path or settings.synthetic_outcomes_path)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return generate()


def main(path: Optional[Path] = None) -> int:
    path = Path(path or settings.synthetic_outcomes_path)
    data = generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    inserted = insert(data["records"])
    print(f"Wrote {len(data['records'])} synthetic outcome records to {path}; inserted {inserted} into the store.")
    return inserted


if __name__ == "__main__":
    main()
