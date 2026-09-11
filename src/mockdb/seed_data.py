"""
Deterministic synthetic data for the mock database.

Demo geography: Meerut district, Uttar Pradesh — the same district already
used in the existing test fixture (tests/conftest.py::base_case_state,
village "Rampur", block "Sadar", lat/lon 28.9845/77.7064). Reusing it means
the mock database lines up with data the rest of the repo already assumes,
instead of introducing an unrelated demo location.

Every synthetic record is explicitly marked:
    source      = "MOCK_DATABASE"
    data_status = "MOCK_DATA"
Never "REAL_DATA" / a real source name — see schema.py's provenance note.

Relationship design (per the brief: villages should differ, not be
independent random noise):

  - Rampur (hub, Sadar block): the largest dairy cluster, a nearby
    cattle-feed/fodder supplier cluster, and the main local market.
    Moderate milk prices (healthy supply).
  - Sarurpur Khurd (Sadar block, ~8 km from Rampur): MORE dairy
    competitors than Rampur, but only one supplier, and it's farther out.
    Slightly lower milk prices (oversupply / competition pressure).
  - Sisauli (Sardhana block, ~14 km from Rampur): few dairy competitors,
    sparse/no local suppliers (nearest is in Rampur or Kharkhoda), and
    higher milk prices (scarcity).
  - Kharkhoda (Kharkhoda block, ~15 km from Rampur): a wholesale-market
    town — fewer standalone businesses, but hosts the district's main
    wholesale market and a wider spread of supplier categories that the
    other three villages draw on.

This intentionally makes the same "dairy in <village>" query produce
different feasibility signals depending on which village is picked, per
the brief's "Village A vs Village B" example.
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass, field

SOURCE = "MOCK_DATABASE"
DATA_STATUS = "MOCK_DATA"
DEFAULT_SEED = 1337

DISTRICT = "Meerut"
STATE = "Uttar Pradesh"


@dataclass(frozen=True)
class Village:
    name: str
    block: str
    latitude: float
    longitude: float
    tier: str  # "hub" | "medium" | "small"


VILLAGES: tuple[Village, ...] = (
    Village("Rampur", "Sadar", 28.9845, 77.7064, "hub"),
    Village("Sarurpur Khurd", "Sadar", 28.9200, 77.7500, "medium"),
    Village("Sisauli", "Sardhana", 29.0700, 77.6200, "small"),
    Village("Kharkhoda", "Kharkhoda", 28.8700, 77.6000, "medium"),
)

_VILLAGE_BY_NAME = {v.name: v for v in VILLAGES}


# ---------------------------------------------------------------------------
# Category metadata (drives business/supplier generation + price bands)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CategoryProfile:
    category: str
    subcategories: tuple[str, ...]
    products: tuple[str, ...]
    price_range: tuple[float, float]      # estimated_price band (INR)
    capacity_range: tuple[float, float]     # estimated_daily_capacity band
    capacity_unit_note: str                  # documented in `notes`, not a column
    customer_segments: tuple[str, ...]


CATEGORY_PROFILES: dict[str, CategoryProfile] = {
    "dairy": CategoryProfile(
        "dairy", ("milk_collection", "milk_dairy_shop"), ("milk", "curd", "ghee", "paneer"),
        (42.0, 68.0), (60.0, 400.0), "litres/day", ("local_household", "mixed"),
    ),
    "grocery": CategoryProfile(
        "grocery", ("kirana_store", "general_store"),
        ("rice", "wheat_flour", "pulses", "edible_oil", "sugar"),
        (10.0, 90.0), (40.0, 250.0), "customers/day", ("local_household", "retail"),
    ),
    "tailoring": CategoryProfile(
        "tailoring", ("stitching_shop", "boutique"), ("stitching", "alterations", "uniforms"),
        (150.0, 900.0), (2.0, 15.0), "garments/day", ("local_household", "retail"),
    ),
    "bakery": CategoryProfile(
        "bakery", ("bread_bakery", "sweet_shop"), ("bread", "biscuits", "sweets", "namkeen"),
        (20.0, 320.0), (30.0, 200.0), "kg/day", ("local_household", "retail"),
    ),
    "hardware": CategoryProfile(
        "hardware", ("hardware_store", "building_materials"),
        ("cement", "paint", "hand_tools", "pipes_fittings"),
        (25.0, 1500.0), (10.0, 80.0), "customers/day", ("retail", "mixed"),
    ),
    "agro_input": CategoryProfile(
        "agro_input", ("seed_fertilizer_shop",), ("seeds", "fertilizer", "pesticides", "cattle_feed"),
        (200.0, 2200.0), (20.0, 120.0), "customers/day", ("mixed", "wholesale"),
    ),
}

_SUPPLIER_PROFILES: dict[str, CategoryProfile] = {
    "dairy_input": CategoryProfile(
        "dairy_input", ("cattle_feed_supplier", "fodder_supplier"),
        ("cattle_feed", "fodder", "mineral_mixture"),
        (18.0, 32.0), (500.0, 3000.0), "kg/day", ("wholesale",),
    ),
    "grocery_wholesale": CategoryProfile(
        "grocery_wholesale", ("wholesale_grocery",), ("rice", "wheat_flour", "pulses", "edible_oil"),
        (8.0, 70.0), (500.0, 4000.0), "kg/day", ("wholesale",),
    ),
    "fabric_wholesale": CategoryProfile(
        "fabric_wholesale", ("fabric_trader",), ("cotton_fabric", "thread", "buttons_trims"),
        (60.0, 400.0), (100.0, 900.0), "metres/day", ("wholesale",),
    ),
    "bakery_supplies": CategoryProfile(
        "bakery_supplies", ("bakery_ingredient_supplier",), ("maida", "sugar", "yeast", "packaging"),
        (25.0, 90.0), (100.0, 600.0), "kg/day", ("wholesale",),
    ),
    "hardware_trade": CategoryProfile(
        "hardware_trade", ("building_materials_wholesale",), ("cement", "steel", "pipes_fittings"),
        (300.0, 1800.0), (200.0, 1500.0), "units/day", ("wholesale",),
    ),
    "agro_wholesale": CategoryProfile(
        "agro_wholesale", ("agri_input_wholesale",), ("seeds", "fertilizer", "pesticides"),
        (150.0, 2000.0), (300.0, 2500.0), "kg/day", ("wholesale",),
    ),
}

_OWNER_FIRST_NAMES = (
    "Rakesh", "Sunita", "Vijay", "Meena", "Anil", "Kavita", "Suresh", "Poonam",
    "Ramesh", "Geeta", "Satish", "Rekha", "Manoj", "Sarita", "Ajay", "Neelam",
    "Naresh", "Usha", "Pramod", "Kiran", "Devendra", "Shobha", "Yogendra", "Anita",
)

_BUSINESS_SUFFIX = {
    "dairy": ("Dairy", "Milk Dairy", "Dugdh Kendra"),
    "grocery": ("Kirana Store", "General Store", "Provision Store"),
    "tailoring": ("Tailors", "Boutique", "Garments"),
    "bakery": ("Bakery", "Sweet House", "Bakers"),
    "hardware": ("Hardware Store", "Building Depot", "Traders"),
    "agro_input": ("Agro Centre", "Beej Bhandar", "Krishi Kendra"),
}

_SUPPLIER_SUFFIX = {
    "dairy_input": ("Cattle Feed Suppliers", "Fodder Depot"),
    "grocery_wholesale": ("Wholesale Traders", "General Wholesale"),
    "fabric_wholesale": ("Fabric Traders", "Textile Wholesale"),
    "bakery_supplies": ("Bakery Supplies", "Ingredient Traders"),
    "hardware_trade": ("Building Materials Wholesale", "Steel & Cement Traders"),
    "agro_wholesale": ("Agro Wholesale", "Seed & Fertilizer Traders"),
}

_BUSINESS_TYPES = ("individual", "family_business", "partnership")

# Village dairy-cluster sizing per the narrative above: (dairy_count, dairy_price_band)
_DAIRY_PROFILE_BY_VILLAGE = {
    "Rampur": (18, (44.0, 60.0)),
    "Sarurpur Khurd": (24, (40.0, 54.0)),
    "Sisauli": (8, (52.0, 68.0)),
    "Kharkhoda": (12, (46.0, 62.0)),
}

# Non-dairy category counts per village tier
_TIER_CATEGORY_COUNTS = {
    "hub": {"grocery": 20, "tailoring": 10, "bakery": 8, "hardware": 8, "agro_input": 6},
    "medium": {"grocery": 14, "tailoring": 6, "bakery": 4, "hardware": 4, "agro_input": 4},
    "small": {"grocery": 6, "tailoring": 2, "bakery": 2, "hardware": 2, "agro_input": 2},
}

# Suppliers per village: (category -> count). Sarurpur Khurd deliberately
# has only one, and Sisauli has none locally (nearest supplier is Rampur /
# Kharkhoda) — this is the "fewer suppliers, farther away" contrast.
_SUPPLIER_COUNTS_BY_VILLAGE = {
    "Rampur": {"dairy_input": 8, "grocery_wholesale": 6, "agro_wholesale": 4},
    "Sarurpur Khurd": {"dairy_input": 1},
    "Sisauli": {},
    "Kharkhoda": {
        "dairy_input": 6, "grocery_wholesale": 8, "fabric_wholesale": 8,
        "bakery_supplies": 6, "hardware_trade": 8, "agro_wholesale": 8,
    },
}

_MARKETS_BY_VILLAGE = {
    "Rampur": [("Rampur Sadar Bazaar", "local_market")],
    "Sarurpur Khurd": [("Sarurpur Khurd Haat", "haat")],
    "Sisauli": [("Sisauli Village Market", "local_market")],
    "Kharkhoda": [
        ("Kharkhoda Wholesale Mandi", "wholesale_market"),
        ("Kharkhoda Grain Market", "wholesale_market"),
        ("Kharkhoda Local Bazaar", "local_market"),
    ],
}
# A handful of extra district-level markets to round out the 10-20 target
# and give the Pricing agent more than one market per product.
_EXTRA_DISTRICT_MARKETS = [
    ("Meerut City Sabzi Mandi", "wholesale_market", "Sadar"),
    ("Meerut Dairy Cooperative Market", "wholesale_market", "Sadar"),
    ("Sardhana Grain Market", "wholesale_market", "Sardhana"),
    ("Meerut General Wholesale Market", "wholesale_market", "Sadar"),
]

_PRICE_PRODUCTS = (
    # product, category, unit, base_min, base_max
    ("milk", "dairy", "litre", 40.0, 62.0),
    ("wheat", "agro_input", "quintal", 2100.0, 2400.0),
    ("rice", "grocery", "quintal", 2800.0, 3600.0),
    ("sugarcane", "agro_input", "quintal", 340.0, 400.0),
    ("cattle_feed", "dairy_input", "quintal", 1800.0, 2600.0),
    ("vegetables_mixed", "grocery", "quintal", 1200.0, 2600.0),
    ("cotton_fabric", "tailoring", "metre", 60.0, 400.0),
    ("pulses_mixed", "grocery", "quintal", 6500.0, 9500.0),
)

# Fixed, deterministic date list (no wall-clock dependency -> reproducible)
_PRICE_DATES = (
    "2026-06-05", "2026-06-19", "2026-07-03", "2026-07-17",
    "2026-07-31", "2026-08-14", "2026-08-28",
)

_PRODUCTION_PRODUCTS = ("wheat", "sugarcane", "milk", "rice", "vegetables_mixed", "fodder", "pulses_mixed")
_SEASONS = ("kharif", "rabi", "zaid")
_YEARS = (2024, 2025, 2026)


def _jitter_latlon(rng: random.Random, lat: float, lon: float, max_km: float) -> tuple[float, float]:
    """Small deterministic offset so businesses/suppliers within a village
    aren't all stacked on one exact point, while staying within max_km."""
    d_lat = (rng.uniform(-1, 1) * max_km) / 111.32
    d_lon = (rng.uniform(-1, 1) * max_km) / (111.32 * max(0.01, abs(__import__("math").cos(__import__("math").radians(lat)))))
    return round(lat + d_lat, 6), round(lon + d_lon, 6)


@dataclass
class _IdCounter:
    counters: dict[str, int] = field(default_factory=dict)

    def next(self, prefix: str) -> str:
        n = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = n
        return f"{prefix}-{n:04d}"


def _insert_location(cur, ids, *, name, ltype, village, block, district, lat, lon):
    cur.execute(
        "INSERT INTO locations (location_id, name, type, village, block, district, latitude, longitude) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ids.next("LOC"), name, ltype, village, block, district, lat, lon),
    )


def _seed_villages(cur, ids) -> None:
    for v in VILLAGES:
        _insert_location(
            cur, ids, name=v.name, ltype="VILLAGE", village=v.name, block=v.block,
            district=DISTRICT, lat=v.latitude, lon=v.longitude,
        )


def _seed_businesses(cur, ids, rng: random.Random) -> int:
    count = 0
    for v in VILLAGES:
        # Dairy cluster (the category the brief's example focuses on)
        dairy_count, dairy_band = _DAIRY_PROFILE_BY_VILLAGE[v.name]
        count += _seed_businesses_for_category(cur, ids, rng, v, "dairy", dairy_count, price_band=dairy_band)

        # Other categories, scaled by village tier
        for category, n in _TIER_CATEGORY_COUNTS[v.tier].items():
            count += _seed_businesses_for_category(cur, ids, rng, v, category, n)
    return count


def _seed_businesses_for_category(cur, ids, rng, village: Village, category: str, n: int,
                                    price_band: tuple[float, float] | None = None) -> int:
    profile = CATEGORY_PROFILES[category]
    band = price_band or profile.price_range
    for _ in range(n):
        owner = rng.choice(_OWNER_FIRST_NAMES)
        suffix = rng.choice(_BUSINESS_SUFFIX[category])
        name = f"{owner} {suffix}"
        subcategory = rng.choice(profile.subcategories)
        lat, lon = _jitter_latlon(rng, village.latitude, village.longitude, max_km=1.2)
        business_id = ids.next("BIZ")
        cur.execute(
            """INSERT INTO businesses (
                business_id, business_name, category, subcategory, village, block, district,
                latitude, longitude, products, estimated_price, estimated_daily_capacity,
                business_type, years_active, customer_segment, source, data_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                business_id, name, category, subcategory, village.name, village.block, DISTRICT,
                lat, lon, ",".join(profile.products),
                round(rng.uniform(*band), 2), round(rng.uniform(*profile.capacity_range), 1),
                rng.choice(_BUSINESS_TYPES), rng.randint(1, 20), rng.choice(profile.customer_segments),
                SOURCE, DATA_STATUS,
            ),
        )
        _insert_location(
            cur, ids, name=name, ltype="BUSINESS", village=village.name, block=village.block,
            district=DISTRICT, lat=lat, lon=lon,
        )
    return n


def _seed_suppliers(cur, ids, rng: random.Random) -> int:
    count = 0
    for v in VILLAGES:
        for category, n in _SUPPLIER_COUNTS_BY_VILLAGE.get(v.name, {}).items():
            profile = _SUPPLIER_PROFILES[category]
            for _ in range(n):
                owner = rng.choice(_OWNER_FIRST_NAMES)
                suffix = rng.choice(_SUPPLIER_SUFFIX[category])
                name = f"{owner} {suffix}"
                # Suppliers sit a little farther from village center than
                # businesses do (2.5 km jitter vs 1.2 km) — models them as
                # being on the outskirts / along the approach road.
                lat, lon = _jitter_latlon(rng, v.latitude, v.longitude, max_km=2.5)
                supplier_id = ids.next("SUP")
                cur.execute(
                    """INSERT INTO suppliers (
                        supplier_id, supplier_name, category, products, village, block, district,
                        latitude, longitude, estimated_price, availability, source, data_status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        supplier_id, name, category, ",".join(profile.products), v.name, v.block, DISTRICT,
                        lat, lon, round(rng.uniform(*profile.price_range), 2),
                        rng.choice(("in_stock", "seasonal", "limited")), SOURCE, DATA_STATUS,
                    ),
                )
                _insert_location(
                    cur, ids, name=name, ltype="SUPPLIER", village=v.name, block=v.block,
                    district=DISTRICT, lat=lat, lon=lon,
                )
                count += 1
    return count


def _seed_markets(cur, ids, rng: random.Random) -> int:
    count = 0
    for v in VILLAGES:
        for market_name, market_type in _MARKETS_BY_VILLAGE.get(v.name, []):
            lat, lon = _jitter_latlon(rng, v.latitude, v.longitude, max_km=0.8)
            ltype = "WHOLESALE_MARKET" if market_type == "wholesale_market" else "MARKET"
            market_id = ids.next("MKT")
            cur.execute(
                """INSERT INTO markets (
                    market_id, market_name, market_type, village, block, district,
                    latitude, longitude, products, source, data_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    market_id, market_name, market_type, v.name, v.block, DISTRICT,
                    lat, lon, "mixed_produce_and_goods", SOURCE, DATA_STATUS,
                ),
            )
            _insert_location(
                cur, ids, name=market_name, ltype=ltype, village=v.name, block=v.block,
                district=DISTRICT, lat=lat, lon=lon,
            )
            count += 1

    # District-level markets not tied to one specific village (still given
    # a representative point near Meerut/Sadar so they're queryable by
    # radius too).
    for market_name, market_type, block in _EXTRA_DISTRICT_MARKETS:
        lat, lon = _jitter_latlon(rng, 28.9845, 77.7064, max_km=4.0)
        ltype = "WHOLESALE_MARKET" if market_type == "wholesale_market" else "MARKET"
        market_id = ids.next("MKT")
        cur.execute(
            """INSERT INTO markets (
                market_id, market_name, market_type, village, block, district,
                latitude, longitude, products, source, data_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (market_id, market_name, market_type, None, block, DISTRICT, lat, lon,
             "mixed_produce_and_goods", SOURCE, DATA_STATUS),
        )
        _insert_location(
            cur, ids, name=market_name, ltype=ltype, village=None, block=block,
            district=DISTRICT, lat=lat, lon=lon,
        )
        count += 1
    return count


def _seed_prices(cur, ids, rng: random.Random) -> int:
    count = 0
    cur.execute("SELECT market_name FROM markets")
    market_names = [r[0] for r in cur.fetchall()]
    for product, category, unit, base_min, base_max in _PRICE_PRODUCTS:
        for date in _PRICE_DATES:
            # A handful of markets report this product on this date —
            # keeps the table realistic (not every market prices every
            # product every date) while staying deterministic.
            reporting_markets = rng.sample(market_names, k=min(4, len(market_names)))
            for market in reporting_markets:
                spread = rng.uniform(0.9, 1.1)
                min_p = round(base_min * spread * rng.uniform(0.95, 1.0), 2)
                max_p = round(base_max * spread * rng.uniform(1.0, 1.05), 2)
                modal_p = round((min_p + max_p) / 2 * rng.uniform(0.97, 1.03), 2)
                price_id = ids.next("PRC")
                cur.execute(
                    """INSERT INTO prices (
                        price_id, product, category, market, district, min_price, max_price,
                        modal_price, unit, date, source, data_status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (price_id, product, category, market, DISTRICT, min_p, max_p, modal_p,
                     unit, date, SOURCE, DATA_STATUS),
                )
                count += 1
    return count


def _seed_production(cur, ids, rng: random.Random) -> int:
    count = 0
    levels = ("low", "medium", "high")
    for product in _PRODUCTION_PRODUCTS:
        for year in _YEARS:
            for season in _SEASONS:
                # Not every product is grown in every season (e.g. milk
                # production is reported year-round via all three season
                # slots as a proxy for quarters, sugarcane mainly kharif).
                if product == "sugarcane" and season != "kharif":
                    continue
                production_id = ids.next("PRD")
                cur.execute(
                    """INSERT INTO production (
                        production_id, district, product, season, production_level,
                        availability_level, year, source, data_status
                    ) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        production_id, DISTRICT, product, season,
                        rng.choice(levels), rng.choice(levels), year, SOURCE, DATA_STATUS,
                    ),
                )
                count += 1
    return count


def seed_database(conn: sqlite3.Connection, seed: int = DEFAULT_SEED) -> dict[str, int]:
    """Populates every table with deterministic synthetic data. Assumes the
    schema already exists (call schema.create_all first) and that the
    tables are currently empty (call schema.drop_all + create_all, or use
    scripts/seed_mock_db.py --reset, to reseed from scratch).

    Returns a dict of table -> row count inserted, for logging/tests.
    """
    rng = random.Random(seed)
    ids = _IdCounter()
    cur = conn.cursor()

    _seed_villages(cur, ids)
    business_count = _seed_businesses(cur, ids, rng)
    supplier_count = _seed_suppliers(cur, ids, rng)
    market_count = _seed_markets(cur, ids, rng)
    price_count = _seed_prices(cur, ids, rng)
    production_count = _seed_production(cur, ids, rng)

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM locations")
    location_count = cur.fetchone()[0]

    return {
        "businesses": business_count,
        "suppliers": supplier_count,
        "markets": market_count,
        "prices": price_count,
        "production": production_count,
        "locations": location_count,
    }
