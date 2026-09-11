"""
SQLite schema for the local mock database.

This exists to let the Competitor / Pricing / Supply Chain agents run a
full demo offline, without depending on the real UdyamAdapter /
CommodityPriceAdapter / PurchasingPowerAdapter / OverpassAdapter /
RoutingAdapter external calls (which either need deployer-supplied
datasets/keys or network access — see README.md's "Blocking gaps in the
data layer" table).

Provenance rule enforced everywhere in this schema: every table carries
`source` and `data_status` columns. For rows inserted by seed_data.py,
these are always the literal strings "MOCK_DATABASE" / "MOCK_DATA" (see
mockdb/seed_data.py::SOURCE, DATA_STATUS). This is intentionally separate
from the existing `Confidence` enum (REAL_DATA / ESTIMATED /
INSUFFICIENT_DATA) in src/schemas.py, which describes an *agent output's*
reliability, not a raw record's provenance — conflating the two would mean
pretending mock rows carry a confidence judgement they don't. A future
MockDatabaseAdapter is expected to translate `data_status == "MOCK_DATA"`
into `Confidence.ESTIMATED` (or a dedicated tier) at the adapter boundary,
not by changing what's stored here.

No ORM: this is a demo-scale SQLite file, plain `sqlite3` from the
standard library keeps this milestone dependency-free per the "no
unnecessary frameworks" requirement.
"""

from __future__ import annotations

import sqlite3

# Schema version stamped into the db via PRAGMA user_version, bump this if
# the table shapes change so `seed_mock_db.py --reset` behavior stays sane.
SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS businesses (
    business_id               TEXT PRIMARY KEY,
    business_name             TEXT NOT NULL,
    category                  TEXT NOT NULL,
    subcategory                TEXT,
    village                    TEXT NOT NULL,
    block                       TEXT NOT NULL,
    district                   TEXT NOT NULL,
    latitude                   REAL NOT NULL,
    longitude                  REAL NOT NULL,
    products                   TEXT,
    estimated_price             REAL,
    estimated_daily_capacity    REAL,
    business_type               TEXT,
    years_active                 INTEGER,
    customer_segment            TEXT,
    source                      TEXT NOT NULL,
    data_status                  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id       TEXT PRIMARY KEY,
    supplier_name      TEXT NOT NULL,
    category            TEXT NOT NULL,
    products            TEXT,
    village              TEXT NOT NULL,
    block                 TEXT NOT NULL,
    district             TEXT NOT NULL,
    latitude             REAL NOT NULL,
    longitude            REAL NOT NULL,
    estimated_price       REAL,
    availability          TEXT,
    source                TEXT NOT NULL,
    data_status            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS markets (
    market_id      TEXT PRIMARY KEY,
    market_name     TEXT NOT NULL,
    market_type      TEXT NOT NULL,
    village           TEXT,
    block              TEXT NOT NULL,
    district          TEXT NOT NULL,
    latitude          REAL NOT NULL,
    longitude         REAL NOT NULL,
    products          TEXT,
    source            TEXT NOT NULL,
    data_status        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prices (
    price_id     TEXT PRIMARY KEY,
    product       TEXT NOT NULL,
    category       TEXT,
    market          TEXT,
    district        TEXT NOT NULL,
    min_price       REAL NOT NULL,
    max_price       REAL NOT NULL,
    modal_price      REAL NOT NULL,
    unit             TEXT NOT NULL,
    date              TEXT NOT NULL,
    source            TEXT NOT NULL,
    data_status        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production (
    production_id     TEXT PRIMARY KEY,
    district            TEXT NOT NULL,
    product              TEXT NOT NULL,
    season                TEXT NOT NULL,
    production_level      TEXT NOT NULL,
    availability_level     TEXT NOT NULL,
    year                    INTEGER NOT NULL,
    source                  TEXT NOT NULL,
    data_status              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
    location_id    TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    type              TEXT NOT NULL,
    village            TEXT,
    block               TEXT,
    district           TEXT NOT NULL,
    latitude           REAL NOT NULL,
    longitude          REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_businesses_category   ON businesses(category);
CREATE INDEX IF NOT EXISTS idx_businesses_geo         ON businesses(district, block, village);
CREATE INDEX IF NOT EXISTS idx_businesses_latlon      ON businesses(latitude, longitude);

CREATE INDEX IF NOT EXISTS idx_suppliers_category     ON suppliers(category);
CREATE INDEX IF NOT EXISTS idx_suppliers_geo          ON suppliers(district, block, village);
CREATE INDEX IF NOT EXISTS idx_suppliers_latlon        ON suppliers(latitude, longitude);

CREATE INDEX IF NOT EXISTS idx_markets_geo             ON markets(district, block, village);
CREATE INDEX IF NOT EXISTS idx_markets_type            ON markets(market_type);

CREATE INDEX IF NOT EXISTS idx_prices_product          ON prices(product);
CREATE INDEX IF NOT EXISTS idx_prices_district         ON prices(district);
CREATE INDEX IF NOT EXISTS idx_prices_product_district ON prices(product, district);

CREATE INDEX IF NOT EXISTS idx_production_district_product ON production(district, product);

CREATE INDEX IF NOT EXISTS idx_locations_type          ON locations(type);
CREATE INDEX IF NOT EXISTS idx_locations_geo           ON locations(district, block, village);
"""

_TABLES = ("businesses", "suppliers", "markets", "prices", "production", "locations")


def create_all(conn: sqlite3.Connection) -> None:
    """Creates every table/index if not already present. Safe to call
    repeatedly (idempotent)."""
    conn.executescript(_DDL)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
    conn.commit()


def drop_all(conn: sqlite3.Connection) -> None:
    """Drops every mockdb table. Used by --reset in scripts/seed_mock_db.py
    and by the deterministic-reseed test."""
    for table in _TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table};")
    conn.commit()


def connect(db_path: str) -> sqlite3.Connection:
    """Opens a connection with sane defaults for this use case (row access
    by column name, foreign-key-style integrity not needed at demo scale
    so it's left off deliberately)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
