from __future__ import annotations

import sqlite3

import pytest

from src.mockdb import queries, schema, seed_data


@pytest.fixture
def conn():
    """Fresh in-memory database, seeded deterministically, per test."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    schema.create_all(c)
    seed_data.seed_database(c, seed=seed_data.DEFAULT_SEED)
    yield c
    c.close()


# --- 1. Database creation -------------------------------------------------

def test_database_creation_creates_all_tables():
    c = sqlite3.connect(":memory:")
    schema.create_all(c)
    tables = {
        r[0]
        for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"businesses", "suppliers", "markets", "prices", "production", "locations"} <= tables
    c.close()


# --- 2. Seed execution -----------------------------------------------------

def test_seed_execution_hits_target_row_counts(conn):
    counts = {
        "businesses": conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0],
        "suppliers": conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
        "markets": conn.execute("SELECT COUNT(*) FROM markets").fetchone()[0],
        "prices": conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0],
        "production": conn.execute("SELECT COUNT(*) FROM production").fetchone()[0],
    }
    assert 150 <= counts["businesses"] <= 300
    assert 50 <= counts["suppliers"] <= 100
    assert 10 <= counts["markets"] <= 20
    assert 200 <= counts["prices"] <= 500
    assert 50 <= counts["production"] <= 100

    # Every row must be clearly marked as synthetic, never as real data.
    for table in ("businesses", "suppliers", "markets", "prices", "production"):
        statuses = {r[0] for r in conn.execute(f"SELECT DISTINCT data_status FROM {table}")}
        sources = {r[0] for r in conn.execute(f"SELECT DISTINCT source FROM {table}")}
        assert statuses == {"MOCK_DATA"}
        assert sources == {"MOCK_DATABASE"}
        assert "REAL_DATA" not in statuses


# --- 3. Business lookup -----------------------------------------------------

def test_business_lookup_by_category_and_village(conn):
    result = queries.find_businesses(conn, category="dairy", village="Rampur")
    assert result["count"] == 18
    assert all(b["category"] == "dairy" and b["village"] == "Rampur" for b in result["businesses"])


# --- 4. Radius-based competitor search --------------------------------------

def test_radius_based_competitor_search_finds_dairy_near_rampur(conn):
    # Rampur's own coordinates; a 10 km radius should catch Rampur's dairy
    # cluster and can reach into Sarurpur Khurd (~8 km away) too.
    result = queries.find_businesses(
        conn, category="dairy", latitude=28.9845, longitude=77.7064, radius_km=10,
    )
    assert result["count"] >= 18
    assert all(b["distance_km"] <= 10 for b in result["businesses"])
    # Sorted nearest-first
    distances = [b["distance_km"] for b in result["businesses"]]
    assert distances == sorted(distances)


def test_radius_search_excludes_far_village(conn):
    # A tight 3 km radius around Rampur should not reach Sisauli (~14 km away).
    result = queries.find_businesses(
        conn, category="dairy", latitude=28.9845, longitude=77.7064, radius_km=3,
    )
    assert all(b["village"] != "Sisauli" for b in result["businesses"])


# --- 5. Supplier lookup ------------------------------------------------------

def test_supplier_lookup_by_category(conn):
    result = queries.find_suppliers(conn, category="dairy_input")
    assert result["count"] > 0
    assert all(s["category"] == "dairy_input" for s in result["suppliers"])


def test_supplier_lookup_reflects_village_asymmetry(conn):
    # Per the seeding design: Sarurpur Khurd has only 1 dairy_input
    # supplier and Sisauli has none locally.
    sarurpur = queries.find_suppliers(conn, category="dairy_input", village="Sarurpur Khurd")
    sisauli = queries.find_suppliers(conn, category="dairy_input", village="Sisauli")
    assert sarurpur["count"] == 1
    assert sisauli["count"] == 0


# --- 6. Market lookup ---------------------------------------------------------

def test_market_lookup_by_type(conn):
    result = queries.find_markets(conn, market_type="wholesale_market")
    assert result["count"] > 0
    assert all(m["market_type"] == "wholesale_market" for m in result["markets"])


# --- 7. Price lookup -----------------------------------------------------------

def test_price_lookup_for_product_in_district(conn):
    result = queries.find_prices(conn, product="milk", district="Meerut")
    assert result["min_price"] is not None
    assert result["max_price"] >= result["min_price"]
    assert result["representative_price"] is not None
    assert result["unit"] == "litre"
    assert len(result["records"]) > 0


# --- 8. Production lookup -------------------------------------------------------

def test_production_lookup_for_product_and_district(conn):
    result = queries.find_production(conn, product="wheat", district="Meerut")
    assert result["count"] > 0
    assert all(r["product"] == "wheat" for r in result["records"])


# --- 9. Empty query results -------------------------------------------------------

def test_empty_results_for_nonexistent_category(conn):
    result = queries.find_businesses(conn, category="submarine_repair")
    assert result == {"businesses": [], "count": 0}


def test_empty_results_for_nonexistent_product_price(conn):
    result = queries.find_prices(conn, product="unobtainium")
    assert result["records"] == []
    assert result["min_price"] is None


# --- 10. Deterministic reseeding -----------------------------------------------------

def test_deterministic_reseeding_produces_identical_counts_and_data():
    c1 = sqlite3.connect(":memory:")
    schema.create_all(c1)
    counts1 = seed_data.seed_database(c1, seed=42)

    c2 = sqlite3.connect(":memory:")
    schema.create_all(c2)
    counts2 = seed_data.seed_database(c2, seed=42)

    assert counts1 == counts2

    rows1 = c1.execute("SELECT * FROM businesses ORDER BY business_id").fetchall()
    rows2 = c2.execute("SELECT * FROM businesses ORDER BY business_id").fetchall()
    assert rows1 == rows2

    prices1 = c1.execute("SELECT * FROM prices ORDER BY price_id").fetchall()
    prices2 = c2.execute("SELECT * FROM prices ORDER BY price_id").fetchall()
    assert prices1 == prices2

    c1.close()
    c2.close()
