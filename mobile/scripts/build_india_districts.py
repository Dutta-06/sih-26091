"""All-India district table for the mobile data pack (mobile/src/core/data/india_districts.json).

Sources (downloaded into mobile/scripts/cache/, not committed):
  - Census of India 2011 district primary census abstract (640 districts: state, name, population, literacy)
    https://raw.githubusercontent.com/nishusharma1608/India-Census-2011-Analysis/master/india-districts-census-2011.csv
  - GADM district boundaries (centroid and area are computed here; polygons are not shipped)
    https://raw.githubusercontent.com/geohacker/india/master/district/india_district.geojson

Districts are matched within their state on normalised names (aliases for renamed districts below). A Census district
without a boundary match takes the population-weighted position of matched districts in its state shifted by a
deterministic offset, and is flagged "approxLocation". Output rows:
  [id, name, state, lat, lon, population, areaSqKm, literacyPct, approxLocation(0/1)]

Run: python mobile/scripts/build_india_districts.py
"""

from __future__ import annotations

import csv
import difflib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
OUT = HERE.parent / "src" / "core" / "data" / "india_districts.json"

STATE_ALIASES = {
    "nct of delhi": "delhi", "orissa": "odisha", "uttaranchal": "uttarakhand", "pondicherry": "puducherry",
    "andaman and nicobar islands": "andaman and nicobar", "dadra and nagar haveli": "dadra and nagar haveli",
    "jammu and kashmir": "jammu and kashmir",
}
STATE_TITLE = {
    "delhi": "Delhi", "odisha": "Odisha", "uttarakhand": "Uttarakhand", "puducherry": "Puducherry",
    "andaman and nicobar": "Andaman and Nicobar Islands", "jammu and kashmir": "Jammu and Kashmir",
    "dadra and nagar haveli": "Dadra and Nagar Haveli", "daman and diu": "Daman and Diu",
}
# Census 2011 name -> GADM name (normalised), for renamed or differently spelt districts
NAME_ALIASES = {
    "sant ravidas nagar bhadohi": "sant ravi das nagar", "kanshiram nagar": "kanshiram nagar", "mahamaya nagar": "hathras",
    "jyotiba phule nagar": "jyotiba phule nagar", "gautam buddha nagar": "gautam buddha nagar", "allahabad": "allahabad",
    "faizabad": "faizabad", "bara banki": "barabanki", "mahrajganj": "maharajganj", "siddharthnagar": "siddharth nagar",
    "sant kabir nagar": "sant kabir nagar", "kheri": "lakhimpur kheri", "kaimur bhabua": "kaimur", "pashchim champaran": "west champaran",
    "purba champaran": "east champaran", "purbi singhbhum": "east singhbhum", "pashchimi singhbhum": "west singhbhum",
    "saraikela kharsawan": "saraikela kharsawan", "the dangs": "dang", "panch mahals": "panch mahal", "dohad": "dahod",
    "banas kantha": "banaskantha", "sabar kantha": "sabarkantha", "kachchh": "kachchh", "ahmadabad": "ahmedabad",
    "bid": "bid", "raigarh": "raigarh", "mumbai suburban": "mumbai suburban", "thane": "thane", "ahmadnagar": "ahmednagar",
    "buldana": "buldhana", "gondiya": "gondiya", "bangalore": "bangalore urban", "bangalore rural": "bangalore rural",
    "chikmagalur": "chikmagalur", "dakshina kannada": "dakshina kannada", "uttara kannada": "uttara kannada",
    "belgaum": "belgaum", "bellary": "bellary", "bijapur": "bijapur", "gulbarga": "gulbarga", "mysore": "mysore",
    "shimoga": "shimoga", "tumkur": "tumkur", "the nilgiris": "nilgiris", "tiruvallur": "thiruvallur",
    "kancheepuram": "kancheepuram", "tiruvannamalai": "tiruvannamalai", "viluppuram": "villupuram", "thoothukkudi": "thoothukudi",
    "tirunelveli": "tirunelveli", "kanniyakumari": "kanniyakumari", "sri potti sriramulu nellore": "nellore",
    "y s r": "cuddapah", "anantapur": "anantapur", "mahbubnagar": "mahbubnagar", "rangareddy": "rangareddi",
    "north twenty four parganas": "north 24 parganas", "south twenty four parganas": "south 24 parganas",
    "paschim medinipur": "west midnapore", "purba medinipur": "east midnapore", "dakshin dinajpur": "dakshin dinajpur",
    "uttar dinajpur": "uttar dinajpur", "haora": "howrah", "hugli": "hooghly", "koch bihar": "cooch behar",
    "barddhaman": "bardhaman", "puruliya": "purulia", "maldah": "maldah", "darjiling": "darjeeling",
    "baleshwar": "baleshwar", "debagarh": "deogarh", "nabarangapur": "nabarangpur", "subarnapur": "sonepur",
    "anugul": "angul", "jajapur": "jajpur", "kendujhar": "keonjhar", "khordha": "khurda", "baudh": "boudh",
    "firozpur": "firozpur", "sahibzada ajit singh nagar": "mohali", "shahid bhagat singh nagar": "nawanshahr",
    "muktsar": "muktsar", "kamrup metropolitan": "kamrup metropolitan", "marigaon": "morigaon", "sivasagar": "sibsagar",
    "dima hasao": "north cachar hills", "leh ladakh": "leh", "rajouri": "rajauri", "badgam": "budgam", "bandipore": "bandipura",
    "shupiyan": "shopian", "punch": "poonch", "janjgir champa": "janjgir champa", "uttar bastar kanker": "kanker",
    "dakshin bastar dantewada": "dantewada", "kabeerdham": "kawardha", "narsimhapur": "narsinghpur", "khandwa east nimar": "east nimar",
    "khargone west nimar": "west nimar", "chittaurgarh": "chittorgarh", "dhaulpur": "dholpur", "jhunjhunun": "jhunjhunu",
    "ganganagar": "ganganagar", "lahul and spiti": "lahul and spiti", "hardwar": "haridwar", "garhwal": "pauri garhwal",
    "sonipat": "sonipat", "mewat": "mewat", "north goa": "north goa", "south goa": "south goa", "leh": "leh",
    "mumbai": "greater bombay", "mumbai suburban": "greater bombay", "imphal west": "west imphal", "imphal east": "east imphal",
    "north district": "north sikkim", "west district": "west sikkim", "south district": "south sikkim", "east district": "east",
    "krishnagiri": "dharmapuri", "tiruppur": "coimbatore", "ramanagara": "bangalore rural", "chikkaballapura": "kolar",
    "yadgir": "gulbarga", "singrauli": "sidhi", "alirajpur": "jhabua", "tapi": "surat", "pondicherry": "puducherry",
    "nicobars": "nicobar islands", "north and middle andaman": "andaman islands", "south andaman": "andaman islands",
    "chamarajanagar": "chamrajnagar", "uttara kannada": "uttar kannand", "dakshina kannada": "dakshin kannad",
}
# Districts sharing a parent boundary (split after the boundary data) get the parent centroid shifted slightly.

norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower().replace("&", " and "))).strip()


def ring_area_centroid(ring: list[list[float]]) -> tuple[float, float, float]:
    """Signed area (km²) and centroid of a lon/lat ring on a local equirectangular projection."""
    lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
    kx = 111.32 * math.cos(lat0)
    ky = 110.57
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        X0, Y0, X1, Y1 = x0 * kx, y0 * ky, x1 * kx, y1 * ky
        cross = X0 * Y1 - X1 * Y0
        a += cross
        cx += (X0 + X1) * cross
        cy += (Y0 + Y1) * cross
    a /= 2
    if abs(a) < 1e-9:
        return 0.0, ring[0][0], ring[0][1]
    return a, cx / (6 * a) / kx, cy / (6 * a) / ky


def feature_shape(geom: dict) -> tuple[float, float, float]:
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    total = sx = sy = 0.0
    for poly in polys:
        for k, ring in enumerate(poly):
            a, x, y = ring_area_centroid([p[:2] for p in ring])
            a = abs(a) * (1 if k == 0 else -1)  # holes subtract
            total += a
            sx += a * x
            sy += a * y
    return total, sy / total, sx / total  # area, lat, lon


def slug(s: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]", "_", s.lower())).strip("_")


def main() -> None:
    geo = json.loads((CACHE / "india_district.geojson").read_text("utf-8"))
    shapes: dict[tuple[str, str], tuple[float, float, float]] = {}
    for f in geo["features"]:
        p = f["properties"]
        st = norm(p["NAME_1"])
        st = STATE_ALIASES.get(st, st)
        shapes[(st, norm(p["NAME_2"]))] = feature_shape(f["geometry"])

    rows, unmatched = [], []
    with (CACHE / "districts2011.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            st = norm(r["State name"])
            st = STATE_ALIASES.get(st, st)
            name = r["District name"].strip()
            key = norm(name)
            cands = [NAME_ALIASES.get(key, key), key, key.replace(" ", ""), *(["delhi"] if st == "delhi" else [])]
            hit = next((shapes[(st, c)] for c in cands if (st, c) in shapes), None)
            if hit is None:  # loose: one name contains the other, same state
                loose = [v for (s2, n2), v in shapes.items() if s2 == st and (n2 in key or key in n2) and min(len(n2), len(key)) >= 4]
                hit = loose[0] if len(loose) == 1 else None
            if hit is None:  # spelling variants (Dehradun/Dehra Dun, Visakhapatnam/Vishakhapatnam)
                names = [n2 for (s2, n2) in shapes if s2 == st]
                close = difflib.get_close_matches(key.replace(" ", ""), [n.replace(" ", "") for n in names], n=2, cutoff=0.8)
                if len(close) == 1 or (len(close) == 2 and difflib.SequenceMatcher(None, key.replace(" ", ""), close[0]).ratio() > 0.92):
                    hit = shapes[(st, next(n for n in names if n.replace(" ", "") == close[0]))]
            pop = int(r["Population"])
            lit = round(100 * int(r["Literate"]) / pop, 1) if pop else 0
            rows.append({"name": name, "state": STATE_TITLE.get(st, r["State name"].title().replace(" And ", " and ")), "st": st,
                         "pop": pop, "lit": lit, "shape": hit})
            if hit is None:
                unmatched.append(f"{name} ({st})")

    # unmatched: population-weighted centre of the state's matched districts, offset deterministically; area = state median
    for r in rows:
        if r["shape"]:
            continue
        same = [x for x in rows if x["st"] == r["st"] and x["shape"]]
        if not same:
            continue
        w = sum(x["pop"] for x in same)
        lat = sum(x["shape"][1] * x["pop"] for x in same) / w
        lon = sum(x["shape"][2] * x["pop"] for x in same) / w
        h = sum(map(ord, r["name"]))
        area = sorted(x["shape"][0] for x in same)[len(same) // 2]
        r["shape"] = (area, lat + ((h % 7) - 3) * 0.12, lon + ((h // 7 % 7) - 3) * 0.12)
        r["approx"] = True

    # districts that share a boundary (split later, or Delhi's nine): spread around the shared centre, area divided
    groups: dict[tuple[float, float], list[dict]] = {}
    for r in rows:
        if r["shape"]:
            groups.setdefault((round(r["shape"][1], 3), round(r["shape"][2], 3)), []).append(r)
    for members in groups.values():
        if len(members) < 2:
            continue
        for i, r in enumerate(members):
            area, lat, lon = r["shape"]
            ang = 2 * math.pi * i / len(members)
            step = 0.25 * math.sqrt(area / len(members)) / 111
            r["shape"] = (area / len(members), lat + step * math.sin(ang), lon + step * math.cos(ang))
            r["approx"] = True

    # Telangana was carved out of Andhra Pradesh in 2014
    telangana = {"adilabad", "nizamabad", "karimnagar", "medak", "hyderabad", "rangareddy", "mahbubnagar", "nalgonda", "warangal", "khammam"}
    for r in rows:
        if r["st"] == "andhra pradesh" and norm(r["name"]) in telangana:
            r["state"] = "Telangana"

    out, ids = [], set()
    for r in rows:
        if not r["shape"]:
            continue
        # Census names that are only a direction (Delhi, Sikkim) or carry a suffix get the readable form people use
        r["name"] = re.sub(r"\s+", " ", re.sub(r"\s*district\s*$", "", r["name"].strip(), flags=re.I)).replace("Leh(Ladakh)", "Leh (Ladakh)").strip()
        if r["name"] in {"North", "South", "East", "West", "Central", "North West", "North East", "South West", "New Delhi"} and r["state"] in {"Delhi", "Sikkim"}:
            r["name"] = r["name"] if r["name"] == "New Delhi" else f"{r['name']} {r['state']}"
        base = slug(r["name"])
        did = base if base not in ids else f"{base}_{slug(r['state'])}"
        ids.add(did)
        area, lat, lon = r["shape"]
        out.append([did, r["name"], r["state"], round(lat, 4), round(lon, 4), r["pop"], round(area), r["lit"], 1 if r.get("approx") else 0])
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} districts written, {sum(x[8] for x in out)} with approximate location, dropped {len(rows) - len(out)}")
    print("approximate:", ", ".join(unmatched[:80]), file=sys.stderr)


if __name__ == "__main__":
    main()
