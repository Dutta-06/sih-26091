"""Real places, PIN codes and bank branches for the app (public/data/*.dat, src/core/data/open_*.json).

Sources (downloaded by hand into one folder, see README "Open data"):
  - overture_places_india.parquet — Overture Maps places for India (2023-12 release), CDLA Permissive 2.0, via
    https://github.com/ramSeraph/indian_facilities/releases/tag/pois
  - Datagov_Pincode_Boundaries.parquet — India Post PIN code areas from data.gov.in, CC0 (attribute datameet / data.gov.in),
    via https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/postal
  - IFSC.csv, banknames.json — Razorpay IFSC dataset v2.0.62, MIT, https://github.com/razorpay/ifsc
  - public/data/villages.dat (build_open_villages.py) for assigning places and PIN codes to districts.

Only categories the app uses are kept (open_place_categories.json maps them to business activities and place kinds);
names are kept, phone numbers, e-mails and websites are not. Every place and PIN code is assigned to the district of
its nearest Census village. Outputs:
  places.dat   "PLC1" | u32 n | u32 nameBytes | names | u32[n+1] offsets | i32 lat×1e5 | i32 lon×1e5 | u16 category | u16 district
  open_place_counts.json  {district: {category: count}} for the district-versus-state density comparison
  pincodes.dat  {pin: [lat, lon, district, office]}
  ifsc.dat      {bankCode: [bankName, [[suffix, branch, district, state, upi], …]]}

Run: python mobile/scripts/build_open_places.py <folder with the downloads>
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import struct
import sys
from array import array
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
MOBILE = HERE.parent
PUBLIC = MOBILE / "public" / "data"
CORE = MOBILE / "src" / "core" / "data"

# Overture main category -> (place kind, activity ids it evidences)
CATEGORIES: dict[str, tuple[str, list[str]]] = {
    "dairy_farm": ("enterprise", ["dairy_farming"]),
    "livestock_breeder": ("enterprise", ["goat_rearing"]),
    "poultry_farm": ("enterprise", ["poultry_backyard", "poultry_layer"]),
    "poultry_farming": ("enterprise", ["poultry_backyard", "poultry_layer"]),
    "fish_farm": ("enterprise", ["fisheries_pond"]),
    "fish_farms_and_hatcheries": ("enterprise", ["fisheries_pond"]),
    "fishmonger": ("enterprise", ["fisheries_pond"]),
    "honey_farm_shop": ("enterprise", ["beekeeping"]),
    "oil_refiners": ("enterprise", ["mustard_oil_mill"]),
    "flour_mill": ("enterprise", ["flour_mill"]),
    "rice_mill": ("enterprise", ["flour_mill"]),
    "indian_sweets_shop": ("enterprise", ["food_processing_home"]),
    "herb_and_spice_shop": ("enterprise", ["food_processing_home"]),
    "grocery_store": ("enterprise", ["grocery_kirana"]),
    "indian_grocery_store": ("enterprise", ["grocery_kirana"]),
    "convenience_store": ("enterprise", ["grocery_kirana"]),
    "supermarket": ("enterprise", ["grocery_kirana"]),
    "agricultural_service": ("enterprise", ["agri_input_depot"]),
    "fertilizer_store": ("enterprise", ["agri_input_depot"]),
    "agricultural_seed_store": ("enterprise", ["agri_input_depot"]),
    "agricultural_cooperatives": ("enterprise", ["agri_input_depot"]),
    "sewing_and_alterations": ("enterprise", ["tailoring"]),
    "gents_tailor": ("enterprise", ["tailoring"]),
    "b2b_textiles": ("enterprise", ["handloom_weaving"]),
    "textile_mill": ("enterprise", ["handloom_weaving"]),
    "weaving_mill": ("enterprise", ["handloom_weaving"]),
    "saree_shop": ("enterprise", ["handloom_weaving"]),
    "carpet_store": ("enterprise", ["carpet_weaving"]),
    "mobile_phone_repair": ("enterprise", ["mobile_repair"]),
    "mobile_phone_store": ("enterprise", ["mobile_repair"]),
    "beauty_salon": ("enterprise", ["beauty_parlour"]),
    "beauty_and_spa": ("enterprise", ["beauty_parlour"]),
    "hair_salon": ("enterprise", ["beauty_parlour"]),
    "tea_room": ("enterprise", ["tea_snack_stall"]),
    "cafe": ("enterprise", ["tea_snack_stall"]),
    "food_stand": ("enterprise", ["tea_snack_stall"]),
    "fast_food_restaurant": ("enterprise", ["tea_snack_stall"]),
    "smoothie_juice_bar": ("enterprise", ["tea_snack_stall"]),
    "bank_credit_union": ("bank", []),
    "banks": ("bank", []),
    "farmers_market": ("market", []),
    "flea_market": ("market", []),
    "bus_station": ("transport", []),
    "train_station": ("transport", []),
    "school": ("school", []),
    "elementary_school": ("school", []),
    "high_school": ("school", []),
    "post_office": ("post_office", []),
    "wholesale_store": ("supplier", []),
    "wholesaler": ("supplier", []),
    "wholesale_grocer": ("supplier", []),
    "hardware_store": ("supplier", []),
    "fabric_store": ("supplier", ["handloom_weaving"]),
    "cosmetic_and_beauty_supplies": ("supplier", []),
    "livestock_feed_and_supply_store": ("supplier", []),
    "tools_wholesaler": ("supplier", []),
    "spices_wholesaler": ("supplier", []),
}


class VillageGrid:
    """Nearest Census village (for its district) on a 0.1° grid."""

    def __init__(self, path: Path):
        raw = gzip.decompress(path.read_bytes())
        n, hlen = struct.unpack_from("<II", raw, 4)
        header = json.loads(raw[12:12 + hlen])
        o = 12 + hlen
        (nb,) = struct.unpack_from("<I", raw, o)
        o += 4 + nb
        o += 4 * (n + 1) + 2 * n  # offsets, sub-district
        dist = array("H", raw[o:o + 2 * n]); o += 2 * n
        lat = array("i", raw[o:o + 4 * n]); o += 4 * n
        lon = array("i", raw[o:o + 4 * n])
        self.districts = header["districts"]
        self.cells: dict[tuple[int, int], list[tuple[float, float, int]]] = {}
        for i in range(n):
            la, lo = lat[i] / 1e5, lon[i] / 1e5
            self.cells.setdefault((int(la * 10), int(lo * 10)), []).append((la, lo, dist[i]))

    def district(self, la: float, lo: float) -> str | None:
        cx, cy = int(la * 10), int(lo * 10)
        best, best_d = None, 1e9
        for ring in range(0, 4):
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    if max(abs(dx), abs(dy)) != ring:
                        continue
                    for vla, vlo, d in self.cells.get((cx + dx, cy + dy), ()):
                        dd = (vla - la) ** 2 + ((vlo - lo) * math.cos(math.radians(la))) ** 2
                        if dd < best_d:
                            best, best_d = d, dd
            if best is not None and ring >= 1:
                break
        return self.districts[best] if best is not None else None


def main() -> None:
    src = Path(sys.argv[1])
    grid = VillageGrid(PUBLIC / "villages.dat")
    cats = sorted(CATEGORIES)
    cat_index = {c: i for i, c in enumerate(cats)}
    districts: list[str] = []
    d_index: dict[str, int] = {}

    # ---------------------------------------------------------------- places
    table = pq.read_table(src / "overture_places_india.parquet", columns=["names", "categories", "bbox", "confidence"]).to_pylist()
    names = bytearray()
    offsets, lat, lon, cat, dist = array("I", [0]), array("i"), array("i"), array("H"), array("H")
    counts: dict[str, dict[str, int]] = {}
    kept = 0
    for r in table:
        try:
            main_cat = json.loads(r["categories"])["main"]
        except Exception:
            continue
        if main_cat not in CATEGORIES or (r["confidence"] or 0) < 0.3:
            continue
        try:
            name = (json.loads(r["names"])["common"][0]["value"] or "").strip()[:60]
        except Exception:
            name = ""
        la, lo = r["bbox"]["ymin"], r["bbox"]["xmin"]
        did = grid.district(la, lo)
        if not name or not did:
            continue
        if did not in d_index:
            d_index[did] = len(districts)
            districts.append(did)
        names += name.encode("utf-8")
        offsets.append(len(names))
        lat.append(round(la * 1e5))
        lon.append(round(lo * 1e5))
        cat.append(cat_index[main_cat])
        dist.append(d_index[did])
        counts.setdefault(did, {})
        counts[did][main_cat] = counts[did].get(main_cat, 0) + 1
        kept += 1
    header = json.dumps({"categories": cats, "districts": districts}).encode("utf-8")
    blob = bytearray(b"PLC1") + struct.pack("<II", kept, len(header)) + header + struct.pack("<I", len(names)) + names
    for arr in (offsets, lat, lon, cat, dist):
        blob += arr.tobytes()
    (PUBLIC / "places.dat").write_bytes(gzip.compress(bytes(blob), 9))
    (CORE / "open_place_counts.json").write_text(json.dumps(counts, separators=(",", ":")), "utf-8")
    (CORE / "open_place_categories.json").write_text(json.dumps({c: {"kind": k, "activities": a} for c, (k, a) in CATEGORIES.items()}, indent=1), "utf-8")
    print(f"places: {kept} kept, {(PUBLIC / 'places.dat').stat().st_size / 2**20:.1f} MB")

    # ---------------------------------------------------------------- PIN codes
    pins = {}
    for r in pq.read_table(src / "Datagov_Pincode_Boundaries.parquet", columns=["Pincode", "Office_Name", "bbox"]).to_pylist():
        b = r["bbox"]
        if not b or not r["Pincode"]:
            continue
        la, lo = (b["ymin"] + b["ymax"]) / 2, (b["xmin"] + b["xmax"]) / 2
        pins[r["Pincode"].strip()] = [round(la, 4), round(lo, 4), grid.district(la, lo), (r["Office_Name"] or "").strip()]
    (PUBLIC / "pincodes.dat").write_bytes(gzip.compress(json.dumps(pins, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9))
    print(f"pincodes: {len(pins)}, {(PUBLIC / 'pincodes.dat').stat().st_size / 2**20:.1f} MB")

    # ---------------------------------------------------------------- IFSC
    bank_names = json.loads((src / "banknames.json").read_text("utf-8"))
    banks: dict[str, list] = {}
    with (src / "IFSC.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            code = r["IFSC"].strip().upper()
            if len(code) != 11:
                continue
            entry = banks.setdefault(code[:4], [bank_names.get(code[:4], r["BANK"] or code[:4]), []])
            entry[1].append([code[4:], r["BRANCH"].strip().title(), r["DISTRICT"].strip().title(), r["STATE"].strip().title(), 1 if r["UPI"] == "true" else 0])
    (PUBLIC / "ifsc.dat").write_bytes(gzip.compress(json.dumps(banks, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9))
    print(f"ifsc: {sum(len(v[1]) for v in banks.values())} branches of {len(banks)} banks, {(PUBLIC / 'ifsc.dat').stat().st_size / 2**20:.1f} MB")


if __name__ == "__main__":
    main()
