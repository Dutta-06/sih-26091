"""
Query functions over the mock database.

Scope note: these are plain functions over a sqlite3.Connection, not a
MockDatabaseAdapter. Per the brief, wiring a real AdapterResult-returning
adapter (matching src/adapters/base.py::Adapter) into the Competitor /
Pricing / Supply Chain agents is a separate follow-up milestone. This
module exists so the database itself is testable/queryable right now.

Every function returns plain dicts (sqlite3.Row -> dict), not pydantic
models, for the same reason — no premature coupling to schemas.py ahead of
the adapter-integration step.
"""

from __future__ import annotations

import sqlite3

from src.mockdb.geo import bounding_box, haversine_km


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


def find_businesses(
    conn: sqlite3.Connection,
    *,
    category: str | None = None,
    village: str | None = None,
    block: str | None = None,
    district: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
) -> dict:
    """Competitor discovery: businesses matching a category, filtered by
    village/block/district and/or a lat-lon radius. Returns businesses,
    count, and (if a radius search was used) distance_km per business.
    """
    clauses, params = [], []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if village:
        clauses.append("village = ?")
        params.append(village)
    if block:
        clauses.append("block = ?")
        params.append(block)
    if district:
        clauses.append("district = ?")
        params.append(district)

    if latitude is not None and longitude is not None and radius_km is not None:
        lat_min, lat_max, lon_min, lon_max = bounding_box(latitude, longitude, radius_km)
        clauses += ["latitude BETWEEN ? AND ?", "longitude BETWEEN ? AND ?"]
        params += [lat_min, lat_max, lon_min, lon_max]

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM businesses {where}", params).fetchall()
    businesses = _rows_to_dicts(rows)

    if latitude is not None and longitude is not None and radius_km is not None:
        filtered = []
        for b in businesses:
            dist = round(haversine_km(latitude, longitude, b["latitude"], b["longitude"]), 3)
            if dist <= radius_km:
                b["distance_km"] = dist
                filtered.append(b)
        businesses = sorted(filtered, key=lambda b: b["distance_km"])

    return {"businesses": businesses, "count": len(businesses)}


def find_suppliers(
    conn: sqlite3.Connection,
    *,
    category: str | None = None,
    product: str | None = None,
    village: str | None = None,
    block: str | None = None,
    district: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
) -> dict:
    """Supply-chain: suppliers for a product/category, optionally filtered
    by geography or radius. Returns location info (lat/lon) that can be
    passed to the existing RoutingAdapter for real travel distance later.
    """
    clauses, params = [], []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if product:
        clauses.append("products LIKE ?")
        params.append(f"%{product}%")
    if village:
        clauses.append("village = ?")
        params.append(village)
    if block:
        clauses.append("block = ?")
        params.append(block)
    if district:
        clauses.append("district = ?")
        params.append(district)

    if latitude is not None and longitude is not None and radius_km is not None:
        lat_min, lat_max, lon_min, lon_max = bounding_box(latitude, longitude, radius_km)
        clauses += ["latitude BETWEEN ? AND ?", "longitude BETWEEN ? AND ?"]
        params += [lat_min, lat_max, lon_min, lon_max]

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM suppliers {where}", params).fetchall()
    suppliers = _rows_to_dicts(rows)

    if latitude is not None and longitude is not None and radius_km is not None:
        filtered = []
        for s in suppliers:
            dist = round(haversine_km(latitude, longitude, s["latitude"], s["longitude"]), 3)
            if dist <= radius_km:
                s["distance_km"] = dist
                filtered.append(s)
        suppliers = sorted(filtered, key=lambda s: s["distance_km"])

    return {"suppliers": suppliers, "count": len(suppliers)}


def find_markets(
    conn: sqlite3.Connection,
    *,
    market_type: str | None = None,
    village: str | None = None,
    block: str | None = None,
    district: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
) -> dict:
    """Supply-chain: nearby markets / distribution points."""
    clauses, params = [], []
    if market_type:
        clauses.append("market_type = ?")
        params.append(market_type)
    if village:
        clauses.append("village = ?")
        params.append(village)
    if block:
        clauses.append("block = ?")
        params.append(block)
    if district:
        clauses.append("district = ?")
        params.append(district)

    if latitude is not None and longitude is not None and radius_km is not None:
        lat_min, lat_max, lon_min, lon_max = bounding_box(latitude, longitude, radius_km)
        clauses += ["latitude BETWEEN ? AND ?", "longitude BETWEEN ? AND ?"]
        params += [lat_min, lat_max, lon_min, lon_max]

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM markets {where}", params).fetchall()
    markets = _rows_to_dicts(rows)

    if latitude is not None and longitude is not None and radius_km is not None:
        filtered = []
        for m in markets:
            dist = round(haversine_km(latitude, longitude, m["latitude"], m["longitude"]), 3)
            if dist <= radius_km:
                m["distance_km"] = dist
                filtered.append(m)
        markets = sorted(filtered, key=lambda m: m["distance_km"])

    return {"markets": markets, "count": len(markets)}


def find_prices(
    conn: sqlite3.Connection,
    *,
    product: str,
    district: str | None = None,
    market: str | None = None,
) -> dict:
    """Pricing: min/max/modal/representative price for a product, optionally
    narrowed to a district and/or a specific market. `representative_price`
    is the mean of modal prices across the matched rows (most recent date
    first in `records`)."""
    clauses, params = ["product = ?"], [product]
    if district:
        clauses.append("district = ?")
        params.append(district)
    if market:
        clauses.append("market = ?")
        params.append(market)

    where = f"WHERE {' AND '.join(clauses)}"
    rows = conn.execute(
        f"SELECT * FROM prices {where} ORDER BY date DESC", params
    ).fetchall()
    records = _rows_to_dicts(rows)

    if not records:
        return {
            "product": product, "records": [], "min_price": None, "max_price": None,
            "modal_price": None, "representative_price": None, "unit": None, "date": None,
        }

    modal_prices = [r["modal_price"] for r in records]
    return {
        "product": product,
        "records": records,
        "min_price": min(r["min_price"] for r in records),
        "max_price": max(r["max_price"] for r in records),
        "modal_price": records[0]["modal_price"],
        "representative_price": round(sum(modal_prices) / len(modal_prices), 2),
        "unit": records[0]["unit"],
        "date": records[0]["date"],
    }


def find_production(
    conn: sqlite3.Connection,
    *,
    product: str | None = None,
    district: str | None = None,
    season: str | None = None,
    year: int | None = None,
) -> dict:
    """Supply-chain: raw-material availability / seasonal supply / supply
    risk signal for a product in a district."""
    clauses, params = [], []
    if product:
        clauses.append("product = ?")
        params.append(product)
    if district:
        clauses.append("district = ?")
        params.append(district)
    if season:
        clauses.append("season = ?")
        params.append(season)
    if year:
        clauses.append("year = ?")
        params.append(year)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM production {where} ORDER BY year DESC", params
    ).fetchall()
    records = _rows_to_dicts(rows)
    return {"records": records, "count": len(records)}
