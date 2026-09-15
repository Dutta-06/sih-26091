"""All Census 2011 villages of India for the app (public/data/villages.dat).

Source (CC0; attribute datameet and the Census of India / LGD / Bharatmaps):
  https://github.com/ramSeraph/indian_admin_boundaries/releases/download/census-2011/Census_Villages.parquet
  645,828 villages: name, sub-district, district (Census 2011 code), state, point location, 2011 population.

Each village is linked to the app's district id through the Census 2011 district code (india_districts.json) or, for
the detailed districts, their name aliases. Villages without a location or population row are kept (population 0).

Binary layout (little-endian), gzip-compressed:
  "VIL1" | u32 count | u32 headerBytes | header JSON {"districts": [appId…], "subdistricts": [name…]}
  | u32 nameBytes | names UTF-8 blob | u32[count+1] name offsets | u16[count] sub-district index
  | u16[count] district index | i32[count] lat×1e5 | i32[count] lon×1e5 | u32[count] population
Villages are sorted by district, then name.

Run: python mobile/scripts/build_open_villages.py <path to Census_Villages.parquet>
"""

from __future__ import annotations

import gzip
import json
import re
import struct
import sys
from array import array
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
MOBILE = HERE.parent
OUT = MOBILE / "public" / "data" / "villages.dat"

norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def app_district_ids() -> dict[int, str]:
    """Census 2011 district code -> app district id (detailed districts keep their own ids)."""
    india = json.loads((MOBILE / "src/core/data/india_districts.json").read_text("utf-8"))
    detailed = json.loads((MOBILE / "src/core/data/districts.json").read_text("utf-8"))
    alias = {}
    for d in detailed:
        for a in [d["name"]["en"], *d["aliases"]]:
            alias[(d["state"].lower(), norm(a))] = d["id"]
    out = {}
    for row in india:
        did, name, state, code = row[0], row[1], row[2], row[9]
        plain = re.sub(r"\s*\(.*\)\s*", "", name)
        inner = re.search(r"\((.*)\)", name)
        hit = next((alias[(state.lower(), norm(v))] for v in [name, plain, inner.group(1) if inner else ""] if (state.lower(), norm(v)) in alias), None)
        out[code] = hit or did
    return out


aliases: dict[int, str] = {}  # newer district codes that name an existing district


def add_new_districts(table: list[dict]) -> int:
    """Districts formed after 2011 (codes the Census 2011 district table lacks) are appended to india_districts.json:
    centre = population-weighted mean of their villages, population = sum of village populations (rural only),
    area = population / the state's density. Returns how many were added."""
    path = MOBILE / "src/core/data/india_districts.json"
    india = [r for r in json.loads(path.read_text("utf-8")) if r[9] < 10_000]  # re-runs replace earlier additions
    known = {r[9] for r in india}
    states = {r[2].lower(): r[2] for r in india}
    density = {}
    for r in india:
        pop, area = density.get(r[2], (0, 0))
        density[r[2]] = (pop + r[5], area + r[6])
    groups: dict[int, list[dict]] = {}
    for r in table:
        try:
            code = int(r["dtcode11"])
        except (TypeError, ValueError):
            continue
        if code not in known and r["Lat"] is not None and r["Long"] is not None:
            groups.setdefault(code, []).append(r)
    ids = {r[0] for r in india}
    added = 0
    aliases.clear()
    for code, vs in sorted(groups.items()):
        state = states.get((vs[0]["stname"] or "").lower()) or (vs[0]["stname"] or "").title()
        name = (vs[0]["dtname"] or "").strip()
        if not name:
            continue
        if name in {"North", "South", "East", "West", "Central", "North West", "North East", "South West", "South East"} and state in {"Delhi", "Sikkim"}:
            name = f"{name} {state}"
        same = next((r for r in india if r[2] == state and norm(re.sub(r"\s*\(.*\)", "", r[1])) == norm(name)), None)
        if same:  # an existing district under a newer code
            aliases[code] = same[0]
            continue
        w = [max(1, int(v["t_pop2011"] or 0)) for v in vs]
        tw = sum(w)
        lat = sum(v["Lat"] * x for v, x in zip(vs, w)) / tw
        lon = sum(v["Long"] * x for v, x in zip(vs, w)) / tw
        pop = sum(int(v["t_pop2011"] or 0) for v in vs)
        sp, sa = density.get(state, (1, 1))
        did = re.sub(r"_+", "_", re.sub(r"[^a-z0-9]", "_", name.lower())).strip("_")
        if did in ids:
            did = f"{did}_{re.sub(r'[^a-z0-9]+', '_', state.lower())}"
        ids.add(did)
        india.append([did, name, state, round(lat, 4), round(lon, 4), pop, round(pop / max(1e-9, sp / sa)), 0, 0, 10_000 + code])
        added += 1
    path.write_text(json.dumps(india, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return added


def main() -> None:
    src = Path(sys.argv[1])
    table = pq.read_table(src, columns=["dtcode11", "dtname", "stname", "sdtname", "vilname", "t_pop2011", "Lat", "Long"]).to_pylist()
    print(f"{add_new_districts(table)} post-2011 districts added from their villages")
    codes = app_district_ids()
    codes.update({row[9] - 10_000: row[0] for row in json.loads((MOBILE / "src/core/data/india_districts.json").read_text("utf-8")) if row[9] >= 10_000})
    codes.update(aliases)
    rows = []
    skipped = 0
    for r in table:
        try:
            code = int(r["dtcode11"])
        except (TypeError, ValueError):
            skipped += 1
            continue
        did = codes.get(code)
        name = (r["vilname"] or "").strip()
        if not did or not name or r["Lat"] is None or r["Long"] is None:
            skipped += 1
            continue
        rows.append((did, name, (r["sdtname"] or "").strip(), float(r["Lat"]), float(r["Long"]), max(0, int(r["t_pop2011"] or 0))))
    rows.sort(key=lambda x: (x[0], x[1].lower()))
    districts = sorted({r[0] for r in rows})
    subdistricts = sorted({r[2] for r in rows})
    d_index = {d: i for i, d in enumerate(districts)}
    s_index = {s: i for i, s in enumerate(subdistricts)}

    names = bytearray()
    offsets = array("I", [0])
    sub, dist, lat, lon, pop = array("H"), array("H"), array("i"), array("i"), array("I")
    for did, name, sdt, la, lo, p in rows:
        names += name.encode("utf-8")
        offsets.append(len(names))
        sub.append(s_index[sdt])
        dist.append(d_index[did])
        lat.append(round(la * 1e5))
        lon.append(round(lo * 1e5))
        pop.append(p)
    header = json.dumps({"districts": districts, "subdistricts": subdistricts}, ensure_ascii=False).encode("utf-8")
    blob = bytearray(b"VIL1")
    blob += struct.pack("<II", len(rows), len(header)) + header
    blob += struct.pack("<I", len(names)) + names
    for arr in (offsets, sub, dist, lat, lon, pop):
        if sys.byteorder != "little":
            arr.byteswap()
        blob += arr.tobytes()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(gzip.compress(bytes(blob), 9))
    print(f"{len(rows)} villages in {len(districts)} districts ({skipped} skipped), {len(blob) / 2**20:.1f} MB raw, {OUT.stat().st_size / 2**20:.1f} MB gzip")


if __name__ == "__main__":
    main()
