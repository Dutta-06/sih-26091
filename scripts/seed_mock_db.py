#!/usr/bin/env python
"""
Creates/recreates the SQLite mock database at data/mock.db.

Usage:
    python scripts/seed_mock_db.py                # create if missing, seed if empty
    python scripts/seed_mock_db.py --reset         # drop + recreate + reseed
    python scripts/seed_mock_db.py --db path/to.db --seed 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/seed_mock_db.py` from the repo root
# without requiring the package to be installed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mockdb import schema, seed_data  # noqa: E402

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mock.db"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite file.")
    parser.add_argument("--seed", type=int, default=seed_data.DEFAULT_SEED, help="Deterministic RNG seed.")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables before seeding.")
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = schema.connect(str(db_path))
    try:
        if args.reset:
            schema.drop_all(conn)
        schema.create_all(conn)

        existing = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
        if existing and not args.reset:
            print(f"{db_path} already has {existing} business rows; use --reset to reseed. Nothing to do.")
            return

        counts = seed_data.seed_database(conn, seed=args.seed)
        print(f"Seeded {db_path} (seed={args.seed}):")
        for table, n in counts.items():
            print(f"  {table:12s} {n}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
