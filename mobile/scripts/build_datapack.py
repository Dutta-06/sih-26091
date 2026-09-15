"""Build the on-device data pack for the mobile app (mobile/src/core/data/*.json).

Run from anywhere:  python mobile/scripts/build_datapack.py

Two kinds of content:
1. Converted from the repository (unchanged facts): state reference, health thresholds, synthetic outcome seed
   records, and the three RAG collections chunked with ``rag.vector_store.chunk_document`` (same rules the backend
   retriever indexes), plus sklearn's English stop-word list so the TypeScript TF-IDF port tokenises identically.
2. A deterministic SAMPLE open-data pack (fixed RNG seed; ``_meta.json`` -> ``synthetic_sample: true``) standing in
   for Census/LGD village tables, OpenStreetMap POIs, a Udyam extract, Agmarknet price series and field feedback
   for the nine districts in state_reference.json. Densities are driven by the catalog benchmarks
   (typical_density_per_10k x a documented district craft-cluster factor), so outcomes emerge from the data
   rather than being special-cased. The business catalog is NOT copied (the app imports it directly).
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("DATA_MODE", "offline")

from rag.vector_store import chunk_document  # noqa: E402
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS  # noqa: E402

from datapack_content import (  # noqa: E402
    BLOCKS, DISTRICTS, FACTORS, FEEDBACK, NAME_POOLS, SURNAMES, TAG_LABELS, FIXED_VILLAGES, CLUSTER_BLOCKS,
    REG_RATE, PRICE_SERIES,
)

OUT = ROOT / "mobile" / "src" / "core" / "data"
SEED = 26091
CATALOG = {a["id"]: a for a in json.loads((ROOT / "data/reference/business_catalog.json").read_text("utf-8"))["activities"]}


def dump(name: str, obj) -> int:
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    (OUT / name).write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def jitter(rng: random.Random, lat: float, lon: float, km: float) -> tuple[float, float]:
    """Gaussian offset with ~km standard deviation."""
    dlat = rng.gauss(0, km) / 111.0
    dlon = rng.gauss(0, km) / (111.0 * math.cos(math.radians(lat)))
    return round(lat + dlat, 4), round(lon + dlon, 4)


# ---------------------------------------------------------------- converted repository content

def build_docs() -> list[dict]:
    docs = []
    for collection, folder in [("sector_reports", "reference_corpus"), ("risk_taxonomy", "risk_taxonomy"),
                               ("scheme_guidelines", "scheme_guidelines")]:
        base = ROOT / "data" / folder
        for path in sorted(base.rglob("*")):  # same ordering as rag.vector_store.build_index
            if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                for c in chunk_document(text, str(path.relative_to(base))):
                    docs.append({"collection": collection, "source": c.source.replace("\\", "/"),
                                 "heading": c.heading, "text": c.text})
    return docs


# ---------------------------------------------------------------- sample open-data pack

def build_villages(rng: random.Random) -> list[list]:
    rows: list[list] = []
    for d in DISTRICTS:
        did = d["id"]
        drng = random.Random(f"{SEED}-villages-{did}")
        pool_en = NAME_POOLS[d["pool"]]
        names: list[tuple[str, str]] = []
        seen = {v["en"].lower() for v in FIXED_VILLAGES if v["district"] == did}
        combos = [(p[0] + s[0], p[1] + s[1]) for p in pool_en["prefixes"] for s in pool_en["suffixes"]]
        drng.shuffle(combos)
        n_total = drng.randint(25, 40)
        fixed = [v for v in FIXED_VILLAGES if v["district"] == did]
        for en, hi in combos:
            if len(names) + len(fixed) >= n_total:
                break
            if en.lower() in seen or en.lower() == "gopiganj":
                continue
            seen.add(en.lower())
            names.append((en, hi))
        blocks = BLOCKS[did]
        centers = {}
        for i, (ben, bhi, *center) in enumerate(blocks):
            if center:
                centers[ben] = tuple(center)
            else:
                ang = 2 * math.pi * i / len(blocks) + drng.uniform(-0.3, 0.3)
                r = drng.uniform(0.35, 0.8) * d["spread_km"]
                centers[ben] = (d["lat"] + r * math.sin(ang) / 111.0,
                                d["lon"] + r * math.cos(ang) / (111.0 * math.cos(math.radians(d["lat"]))))
        base = d["lgd_base"]
        used = {v["lgd"] for v in fixed}
        code = base
        for i, (en, hi) in enumerate(names):
            ben, bhi = blocks[i % len(blocks)][:2]
            lat, lon = jitter(drng, *centers[ben], km=d["spread_km"] * 0.18)
            while str(code) in used:
                code += 1
            pop = int(min(14000, max(420, drng.lognormvariate(math.log(2800), 0.55))))
            rows.append([str(code), en, hi, ben, bhi, did, lat, lon, pop])
            used.add(str(code))
            code += 1
        for v in fixed:
            rows.append([v["lgd"], v["en"], v["hi"], v["block_en"], v["block_hi"], did, v["lat"], v["lon"], v["population"]])
    rows.sort(key=lambda r: (r[5], r[0]))
    return rows


def activity_factor(did: str, block_en: str, activity_id: str, rng: random.Random) -> float:
    f = FACTORS.get(did, {}).get(activity_id, 1.0)
    cluster = CLUSTER_BLOCKS.get(did)
    if cluster and activity_id in cluster["activities"] and f > 1:
        f *= 1.3 if block_en in cluster["blocks"] else 0.8
    return f * rng.uniform(0.85, 1.15)


def build_pois(villages: list[list]) -> list[list]:
    rng = random.Random(f"{SEED}-pois")
    pois: list[list] = []
    counter = [0]

    def add(en: str, hi: str, kind: str, tags: list[tuple[str, str]], lat: float, lon: float) -> None:
        counter[0] += 1
        pois.append([f"p{counter[0]:05d}", en, hi, kind, ";".join(f"{k}={v}" for k, v in tags), lat, lon])

    by_district = {d["id"]: d for d in DISTRICTS}
    for d in DISTRICTS:
        hq_en, hq_hi, lat, lon = d["hq_en"], d["hq_hi"], d["lat"], d["lon"]
        add(f"{hq_en} Krishi Utpadan Mandi", f"{hq_hi} कृषि उत्पादन मंडी", "market",
            [("amenity", "marketplace"), ("market", "mandi")], *jitter(rng, lat, lon, 1.2))
        add(f"{hq_en} Main Bazaar", f"{hq_hi} मुख्य बाज़ार", "market", [("amenity", "marketplace")], *jitter(rng, lat, lon, 0.5))
        add(f"{hq_en} Bus Stand", f"{hq_hi} बस स्टैंड", "transport", [("amenity", "bus_station")], *jitter(rng, lat, lon, 0.6))
        add(f"{hq_en} Railway Station", f"{hq_hi} रेलवे स्टेशन", "transport", [("railway", "station")], *jitter(rng, lat, lon, 1.0))
        for bank_en, bank_hi in [("State Bank of India", "भारतीय स्टेट बैंक"), ("Bank of Baroda", "बैंक ऑफ़ बड़ौदा"),
                                 ("Punjab National Bank", "पंजाब नेशनल बैंक"), d["rrb"]]:
            add(f"{bank_en}, {hq_en}", f"{bank_hi}, {hq_hi}", "bank", [("amenity", "bank"), ("operator", bank_en)],
                *jitter(rng, lat, lon, 0.9))
        for i in range(3):
            add(f"Government Inter College {i + 1}, {hq_en}", f"राजकीय इंटर कॉलेज {i + 1}, {hq_hi}", "school",
                [("amenity", "school")], *jitter(rng, lat, lon, 1.5))
        for sup in d["hq_suppliers"]:
            en, hi, tags = SUPPLIERS[sup]
            add(f"{SURNAMES[d['pool']][rng.randrange(len(SURNAMES[d['pool']]))][0]} {en}, {hq_en}",
                f"{SURNAMES[d['pool']][rng.randrange(len(SURNAMES[d['pool']]))][1]} {hi}, {hq_hi}", "supplier", tags,
                *jitter(rng, lat, lon, 1.0))

    for v in villages:
        lgd, en, hi, ben, bhi, did, lat, lon, pop = v
        d = by_district[did]
        vr = random.Random(f"{SEED}-poi-{lgd}")
        sur = SURNAMES[d["pool"]]
        if vr.random() < 0.92:
            add(f"Primary School, {en}", f"प्राथमिक विद्यालय, {hi}", "school", [("amenity", "school")], *jitter(vr, lat, lon, 0.3))
        if pop >= 10000 or vr.random() < 0.12:
            add(f"{d['rrb'][0]}, {en}", f"{d['rrb'][1]}, {hi}", "bank", [("amenity", "bank"), ("operator", d["rrb"][0])],
                *jitter(vr, lat, lon, 0.3))
        if pop >= 10000:
            add(f"State Bank of India, {en}", f"भारतीय स्टेट बैंक, {hi}", "bank",
                [("amenity", "bank"), ("operator", "State Bank of India")], *jitter(vr, lat, lon, 0.3))
            add(f"{en} Bazaar", f"{hi} बाज़ार", "market", [("amenity", "marketplace")], *jitter(vr, lat, lon, 0.3))
            add(f"{en} Bus Stand", f"{hi} बस स्टैंड", "transport", [("amenity", "bus_station")], *jitter(vr, lat, lon, 0.4))
        elif vr.random() < 0.3:
            add(f"{en} Bus Stop", f"{hi} बस स्टॉप", "transport", [("highway", "bus_stop")], *jitter(vr, lat, lon, 0.4))
        if pop >= 6000 or vr.random() < 0.22:
            day_en, day_hi = DAYS[vr.randrange(7)]
            add(f"{en} Weekly Haat ({day_en})", f"{hi} साप्ताहिक हाट ({day_hi})", "haat",
                [("amenity", "marketplace"), ("market", "weekly_haat"), ("haat_day", day_en)], *jitter(vr, lat, lon, 0.4))
        for sup, base_p in d["village_suppliers"].items():
            p = min(0.95, base_p * (3 if pop >= 10000 else 1))
            if vr.random() < p:
                s_en, s_hi, tags = SUPPLIERS[sup]
                n = sur[vr.randrange(len(sur))]
                add(f"{n[0]} {s_en}, {en}", f"{n[1]} {s_hi}, {hi}", "supplier", tags, *jitter(vr, lat, lon, 0.5))
        # enterprises tagged with the catalog osm_tags at benchmark densities x district cluster factor
        for aid, a in CATALOG.items():
            lam = pop / 10_000 * a["typical_density_per_10k"] * activity_factor(did, ben, aid, vr)
            for _ in range(poisson(vr, lam)):
                tags = a["osm_tags"]
                tag = tuple(tags[0] if len(tags) == 1 or vr.random() < 0.7 else tags[1 + vr.randrange(len(tags) - 1)])
                lab_en, lab_hi = TAG_LABELS[f"{tag[0]}={tag[1]}"]
                n = sur[vr.randrange(len(sur))]
                add(f"{n[0]} {lab_en}", f"{n[1]} {lab_hi}", "enterprise", [tag], *jitter(vr, lat, lon, 0.8))
    return pois


def build_udyam() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for d in DISTRICTS:
        rng = random.Random(f"{SEED}-udyam-{d['id']}")
        table: dict[str, int] = {}
        for aid, a in CATALOG.items():
            f = FACTORS.get(d["id"], {}).get(aid, 1.0) * rng.uniform(0.9, 1.1)
            n = d["population"] / 10_000 * a["typical_density_per_10k"] * f * REG_RATE[a["sector"]]
            table[a["nic_class"]] = table.get(a["nic_class"], 0) + int(round(n))
        out[d["id"]] = dict(sorted(table.items()))
    return out


def build_prices() -> list[dict]:
    series = []
    start_y, start_m, months = 2023, 7, 36
    for commodity, spec in PRICE_SERIES.items():
        for state, base in spec["states"].items():
            rng = random.Random(f"{SEED}-price-{commodity}-{state}")
            modal = []
            for i in range(months):
                y, m = start_y + (start_m - 1 + i) // 12, (start_m - 1 + i) % 12 + 1
                season = spec["season"][m - 1]
                if commodity == "Goat" and (y, m) in spec.get("events", []):
                    season *= 1.18
                trend = (1 + spec["trend"]) ** (i / 12)
                modal.append(round(base * season * trend * rng.uniform(0.97, 1.03)))
            series.append({"commodity": commodity, "state": state, "unit": "INR per quintal", "start": "2023-07", "modal": modal})
    return series


def build_districts() -> list[dict]:
    ref = json.loads((ROOT / "data/reference/state_reference.json").read_text("utf-8"))["districts"]
    out = []
    for d in DISTRICTS:
        r = ref[d["en"]]
        aliases = sorted({d["en"].lower(), d["hi"], *[a.lower() for a in r.get("aliases", [])], *d.get("extra_aliases", [])})
        out.append({"id": d["id"], "name": {"en": d["en"], "hi": d["hi"]}, "aliases": aliases, "state": r["state"],
                    "lat": r["lat"], "lon": r["lon"], "population": d["population"], "areaSqKm": d["area"]})
    return out


from datapack_content import DAYS, SUPPLIERS  # noqa: E402


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    sizes = {}
    villages = build_villages(rng)
    pois = build_pois(villages)
    sizes["_meta.json"] = dump("_meta.json", {
        "synthetic_sample": True,
        "seed": SEED,
        "generated_by": "mobile/scripts/build_datapack.py",
        "notes": [
            "districts/villages/pois/udyam/prices/feedback are a deterministic SAMPLE standing in for Census/LGD, "
            "OpenStreetMap, Udyam, Agmarknet and field-survey data; not observed values.",
            "Enterprise POI and Udyam densities = catalog typical_density_per_10k x district cluster factor (datapack_content.FACTORS).",
            "Price series are INR per quintal, 36 months ending 2026-06, seasonal profile x trend x +-3% noise.",
            "docs.json, state_reference.json, health_thresholds.json and outcome_seed.json are converted from the repository.",
        ],
        "counts": {"villages": len(villages), "pois": len(pois)},
    })
    sizes["districts.json"] = dump("districts.json", build_districts())
    sizes["villages.json"] = dump("villages.json", villages)
    sizes["pois.json"] = dump("pois.json", pois)
    sizes["udyam.json"] = dump("udyam.json", build_udyam())
    sizes["prices.json"] = dump("prices.json", build_prices())
    sizes["feedback.json"] = dump("feedback.json", FEEDBACK)
    sizes["docs.json"] = dump("docs.json", build_docs())
    sizes["stopwords.json"] = dump("stopwords.json", sorted(ENGLISH_STOP_WORDS))
    sizes["state_reference.json"] = dump("state_reference.json", json.loads((ROOT / "data/reference/state_reference.json").read_text("utf-8")))
    sizes["health_thresholds.json"] = dump("health_thresholds.json", json.loads((ROOT / "config/health_thresholds.json").read_text("utf-8")))
    seed = json.loads((ROOT / "data/synthetic/seed_outcomes.json").read_text("utf-8"))
    sizes["outcome_seed.json"] = dump("outcome_seed.json", seed)
    for k, v in sizes.items():
        print(f"{k:24s} {v / 1024:8.1f} KB")
    print(f"{'TOTAL':24s} {sum(sizes.values()) / 1024:8.1f} KB  ({len(villages)} villages, {len(pois)} POIs)")


if __name__ == "__main__":
    main()
