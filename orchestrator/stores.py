"""Cross-case stores (SQLite), kept separate from per-case ``CaseState``.

* procurement clusters keyed by (district, business category)   - TDD 7.1
* outcome records, real and synthetic (``is_synthetic`` flag)     - TDD 7.5
* feedback from previously funded entrepreneurs                   - TDD 5.6
* local resident survey observations                             - TDD 5.6
* session snapshots (latest CaseState JSON per session)          - TDD 4.1
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from config.settings import settings
from orchestrator.state import utc_now_iso

_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS procurement_members (
    district TEXT NOT NULL,
    business_category TEXT NOT NULL,
    session_id TEXT NOT NULL,
    items TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (district, business_category, session_id)
);
CREATE TABLE IF NOT EXISTS outcome_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id TEXT NOT NULL,
    district TEXT,
    intervention_type TEXT,
    health_before REAL,
    health_after REAL,
    improved INTEGER,
    is_synthetic INTEGER NOT NULL,
    session_id TEXT,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('funded_entrepreneur', 'resident_survey')),
    catalog_id TEXT,
    district TEXT NOT NULL,
    topic TEXT NOT NULL,
    observation TEXT NOT NULL,
    rating INTEGER,
    submitted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session_snapshots (
    session_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _db_path() -> Path:
    path = Path(settings.sqlite_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(_SCHEMA)
            yield conn
            conn.commit()
        finally:
            conn.close()


# --- Procurement clusters ----------------------------------------------------

def join_procurement_cluster(district: str, business_category: str, session_id: str, items: list[str]) -> None:
    with connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO procurement_members VALUES (?, ?, ?, ?, ?)",
            (district.lower(), business_category, session_id, json.dumps(items), utc_now_iso()),
        )


def procurement_cluster_members(district: str, business_category: str) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            "SELECT session_id, items, joined_at FROM procurement_members WHERE district = ? AND business_category = ?",
            (district.lower(), business_category),
        ).fetchall()
    return [{"session_id": r["session_id"], "items": json.loads(r["items"]), "joined_at": r["joined_at"]} for r in rows]


# --- Outcome records ---------------------------------------------------------

def add_outcome_record(
    catalog_id: str,
    district: Optional[str],
    intervention_type: Optional[str],
    health_before: Optional[float],
    health_after: Optional[float],
    is_synthetic: bool,
    session_id: Optional[str] = None,
) -> None:
    improved = None
    if health_before is not None and health_after is not None:
        improved = int(health_after > health_before)
    with connect() as c:
        c.execute(
            "INSERT INTO outcome_records (catalog_id, district, intervention_type, health_before, health_after,"
            " improved, is_synthetic, session_id, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (catalog_id, district, intervention_type, health_before, health_after, improved,
             int(is_synthetic), session_id, utc_now_iso()),
        )


def outcome_records(catalog_id: Optional[str] = None) -> list[dict[str, Any]]:
    query, params = "SELECT * FROM outcome_records", ()
    if catalog_id:
        query, params = query + " WHERE catalog_id = ?", (catalog_id,)
    with connect() as c:
        return [dict(r) | {"is_synthetic": bool(r["is_synthetic"])} for r in c.execute(query, params).fetchall()]


# --- Local feedback and surveys (TDD 5.6) -------------------------------------

def add_local_feedback(kind: str, district: str, topic: str, observation: str,
                       catalog_id: Optional[str] = None, rating: Optional[int] = None) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO local_feedback (kind, catalog_id, district, topic, observation, rating, submitted_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, catalog_id, district.lower(), topic, observation, rating, utc_now_iso()),
        )


def local_feedback(district: Optional[str], catalog_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Feedback for a district, matching the activity or general (catalog_id NULL) observations."""
    if not district:
        return []
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM local_feedback WHERE district = ? AND (catalog_id IS NULL OR catalog_id = ?)"
            " ORDER BY submitted_at DESC",
            (district.lower(), catalog_id),
        ).fetchall()
    return [dict(r) for r in rows]


# --- Session snapshots ---------------------------------------------------------

def save_session(session_id: str, state_json: str) -> None:
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO session_snapshots VALUES (?, ?, ?)", (session_id, state_json, utc_now_iso()))


def load_session(session_id: str) -> Optional[str]:
    with connect() as c:
        row = c.execute("SELECT state_json FROM session_snapshots WHERE session_id = ?", (session_id,)).fetchone()
    return row["state_json"] if row else None
