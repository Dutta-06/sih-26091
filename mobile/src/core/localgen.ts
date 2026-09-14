/**
 * Local sample data for any district of India, generated on the phone.
 *
 * The data pack carries detailed village / POI / Udyam tables for a few districts (scripts/build_datapack.py). Every
 * other Census 2011 district (data/india_districts.json: real name, state, centroid, population, area) gets the same
 * kinds of tables generated deterministically from its own figures, with the same rules as the Python builder:
 *  - settlements: a disc of GEN_RADIUS_KM around the district centre holding density × disc area people; the
 *    headquarters town takes HQ_SHARE of them, villages share the rest (log-normal sizes), names from the region's
 *    place-name parts (data/regions.json);
 *  - places: headquarters mandi, bazaar, bus stand, railway station, banks (incl. the state's regional rural bank),
 *    schools and input suppliers; per settlement a school, bank, bus stop, weekly haat and suppliers by size;
 *  - enterprises: Poisson counts at the catalog typical_density_per_10k × the district craft-cluster factor, tagged
 *    with the catalog OSM tags (the same measure the competitor analysis compares against);
 *  - Udyam registrations: district population / 10k × density × cluster factor × the sector registration rate.
 * Seeds come from the district id, so a district always gets the same tables.
 */
import catalog from "../../../data/reference/business_catalog.json";
import gen from "./data/gen_content.json";
import regions from "./data/regions.json";
import { prng } from "./sms";
import type { PackDistrict, PackPoi, PackVillage } from "./types";

export const GEN_RADIUS_KM = 14;
const HQ_SHARE = 0.3;
/** Metro districts would generate tens of thousands of places; the disc is capped (the app targets rural and small-town areas). */
const MAX_DISC_POP = 600_000;

type Pair = [string, string];
interface Region {
  prefixes: Pair[];
  suffixes: Pair[];
  surnames: Pair[];
  rrb: Pair;
}
interface CatalogRow {
  id: string;
  sector: string;
  nic_class: string;
  typical_density_per_10k: number;
  osm_tags: [string, string][];
}
const ACTIVITIES = (catalog as unknown as { activities: CatalogRow[] }).activities;
const REGIONS = (regions as unknown as { regions: Record<string, Region> }).regions;
const STATE_REGION = (regions as unknown as { states: Record<string, string> }).states;
const STATE_RRB = (regions as unknown as { stateRrb: Record<string, Pair> }).stateRrb;
const CLUSTERS = (regions as unknown as { clusters: Record<string, Record<string, number>> }).clusters;
const SUPPLIERS = gen.suppliers as unknown as Record<string, [string, string, [string, string][]]>;
const TAG_LABELS = gen.tagLabels as unknown as Record<string, Pair>;
const DAYS = gen.days as unknown as Pair[];
const REG_RATE = gen.regRate as Record<string, number>;
const VILLAGE_SUPPLIERS = gen.genericVillageSuppliers as Record<string, number>;
const HQ_SUPPLIERS = gen.genericHqSuppliers as string[];

export interface LocalTables {
  settlements: PackVillage[];
  pois: PackPoi[];
}

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

class Rng {
  private next: () => number;
  constructor(seed: string) {
    this.next = prng(hash(seed));
  }
  random = () => this.next();
  uniform = (a: number, b: number) => a + (b - a) * this.next();
  int = (n: number) => Math.floor(this.next() * n);
  pick = <T,>(xs: T[]): T => xs[this.int(xs.length)];
  gauss(mu = 0, sd = 1) {
    const u = 1 - this.next();
    const v = this.next();
    return mu + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  poisson(lam: number): number {
    if (lam <= 0) return 0;
    if (lam > 30) return Math.max(0, Math.round(this.gauss(lam, Math.sqrt(lam))));
    const limit = Math.exp(-lam);
    let k = 0;
    let p = 1;
    for (;;) {
      p *= this.next();
      if (p <= limit) return k;
      k++;
    }
  }
}

const jitter = (rng: Rng, lat: number, lon: number, km: number): [number, number] => [
  Math.round((lat + rng.gauss(0, km) / 111) * 1e4) / 1e4,
  Math.round((lon + rng.gauss(0, km) / (111 * Math.cos((lat * Math.PI) / 180))) * 1e4) / 1e4,
];

export const regionOf = (state: string): Region => REGIONS[STATE_REGION[state] ?? "north"] ?? REGIONS.north;

/** Craft-cluster factor for an activity in a district (by Census name), 1 when none is known. */
export function clusterFactor(district: PackDistrict, activityId: string): number {
  const row = CLUSTERS[district.name.en] ?? CLUSTERS[district.name.en.replace(/\s*\(.*\)\s*/, "")];
  return row?.[activityId] ?? 1;
}

const cache = new Map<string, LocalTables>();

export function localTables(d: PackDistrict): LocalTables {
  const hit = cache.get(d.id);
  if (hit) return hit;
  const rng = new Rng(`26091-local-${d.id}`);
  const region = regionOf(d.state);
  const rrb = STATE_RRB[d.state] ?? region.rrb;
  const hq: Pair = [d.name.en.replace(/\s*\(.*\)\s*/, ""), d.name.hi.replace(/\s*\(.*\)\s*/, "")];
  const density = d.areaSqKm > 0 ? d.population / d.areaSqKm : 400;
  const discPop = Math.min(d.population, density * Math.PI * GEN_RADIUS_KM ** 2, MAX_DISC_POP);

  // settlements
  const settlements: PackVillage[] = [];
  const block: Pair = [hq[0], hq[1]];
  settlements.push({ lgd: `g-${d.id}-0`, name: { en: hq[0], hi: hq[1] }, block: { en: block[0], hi: block[1] }, district: d.id, lat: d.lat, lon: d.lon, population: Math.round(discPop * HQ_SHARE) });
  const rest = discPop * (1 - HQ_SHARE);
  const n = Math.max(18, Math.min(140, Math.round(rest / 3200)));
  const sizes = Array.from({ length: n }, () => Math.exp(rng.gauss(Math.log(2800), 0.55)));
  const total = sizes.reduce((a, b) => a + b, 0);
  const used = new Set<string>([hq[0].toLowerCase()]);
  const combos: Pair[] = region.prefixes.flatMap((p) => region.suffixes.map((s): Pair => [p[0] + s[0], p[1] + s[1]]));
  for (let i = 0; i < n; i++) {
    let name = rng.pick(combos);
    for (let tries = 0; used.has(name[0].toLowerCase()) && tries < 20; tries++) name = rng.pick(combos);
    if (used.has(name[0].toLowerCase())) name = [`${name[0]} ${i + 1}`, `${name[1]} ${i + 1}`];
    used.add(name[0].toLowerCase());
    const r = GEN_RADIUS_KM * Math.sqrt(rng.random());
    const ang = rng.uniform(0, 2 * Math.PI);
    const lat = d.lat + (r * Math.sin(ang)) / 111;
    const lon = d.lon + (r * Math.cos(ang)) / (111 * Math.cos((d.lat * Math.PI) / 180));
    settlements.push({
      lgd: `g-${d.id}-${i + 1}`, name: { en: name[0], hi: name[1] }, block: { en: block[0], hi: block[1] }, district: d.id,
      lat: Math.round(lat * 1e4) / 1e4, lon: Math.round(lon * 1e4) / 1e4, population: Math.max(300, Math.round((rest * sizes[i]) / total)),
    });
  }

  // places
  const pois: PackPoi[] = [];
  const add = (en: string, hi: string, kind: PackPoi["kind"], tags: [string, string][], [lat, lon]: [number, number]) =>
    pois.push({ id: `g${d.id}-${pois.length + 1}`, name: { en, hi }, kind, tags, lat, lon });
  const person = (): Pair => rng.pick(region.surnames);
  add(`${hq[0]} Krishi Utpadan Mandi`, `${hq[1]} कृषि उत्पादन मंडी`, "market", [["amenity", "marketplace"], ["market", "mandi"]], jitter(rng, d.lat, d.lon, 1.2));
  add(`${hq[0]} Main Bazaar`, `${hq[1]} मुख्य बाज़ार`, "market", [["amenity", "marketplace"]], jitter(rng, d.lat, d.lon, 0.5));
  add(`${hq[0]} Bus Stand`, `${hq[1]} बस स्टैंड`, "transport", [["amenity", "bus_station"]], jitter(rng, d.lat, d.lon, 0.6));
  if (density > 120) add(`${hq[0]} Railway Station`, `${hq[1]} रेलवे स्टेशन`, "transport", [["railway", "station"]], jitter(rng, d.lat, d.lon, 1.0));
  for (const [en, hi] of [["State Bank of India", "भारतीय स्टेट बैंक"], ["Bank of Baroda", "बैंक ऑफ़ बड़ौदा"], ["Punjab National Bank", "पंजाब नेशनल बैंक"], rrb] as Pair[]) {
    add(`${en}, ${hq[0]}`, `${hi}, ${hq[1]}`, "bank", [["amenity", "bank"], ["operator", en]], jitter(rng, d.lat, d.lon, 0.9));
  }
  for (let i = 1; i <= 3; i++) add(`Government Higher Secondary School ${i}, ${hq[0]}`, `राजकीय उच्च माध्यमिक विद्यालय ${i}, ${hq[1]}`, "school", [["amenity", "school"]], jitter(rng, d.lat, d.lon, 1.5));
  for (const sup of HQ_SUPPLIERS) {
    const [en, hi, tags] = SUPPLIERS[sup];
    const p = person();
    add(`${p[0]} ${en}, ${hq[0]}`, `${p[1]} ${hi}, ${hq[1]}`, "supplier", tags, jitter(rng, d.lat, d.lon, 1.0));
  }

  for (const v of settlements) {
    const vr = new Rng(`26091-local-${v.lgd}`);
    const isHq = v === settlements[0];
    const [en, hi] = [v.name.en, v.name.hi];
    if (!isHq) {
      if (vr.random() < 0.92) add(`Primary School, ${en}`, `प्राथमिक विद्यालय, ${hi}`, "school", [["amenity", "school"]], jitter(vr, v.lat, v.lon, 0.3));
      if (v.population >= 10000 || vr.random() < 0.12) add(`${rrb[0]}, ${en}`, `${rrb[1]}, ${hi}`, "bank", [["amenity", "bank"], ["operator", rrb[0]]], jitter(vr, v.lat, v.lon, 0.3));
      if (v.population >= 10000) {
        add(`${en} Bazaar`, `${hi} बाज़ार`, "market", [["amenity", "marketplace"]], jitter(vr, v.lat, v.lon, 0.3));
        add(`${en} Bus Stand`, `${hi} बस स्टैंड`, "transport", [["amenity", "bus_station"]], jitter(vr, v.lat, v.lon, 0.4));
      } else if (vr.random() < 0.3) {
        add(`${en} Bus Stop`, `${hi} बस स्टॉप`, "transport", [["highway", "bus_stop"]], jitter(vr, v.lat, v.lon, 0.4));
      }
      if (v.population >= 6000 || vr.random() < 0.22) {
        const [den, dhi] = vr.pick(DAYS);
        add(`${en} Weekly Haat (${den})`, `${hi} साप्ताहिक हाट (${dhi})`, "haat", [["amenity", "marketplace"], ["market", "weekly_haat"], ["haat_day", den]], jitter(vr, v.lat, v.lon, 0.4));
      }
      for (const [sup, base] of Object.entries(VILLAGE_SUPPLIERS)) {
        if (vr.random() < Math.min(0.95, base * (v.population >= 10000 ? 3 : 1))) {
          const [sen, shi, tags] = SUPPLIERS[sup];
          const p = vr.pick(region.surnames);
          add(`${p[0]} ${sen}, ${en}`, `${p[1]} ${shi}, ${hi}`, "supplier", tags, jitter(vr, v.lat, v.lon, 0.5));
        }
      }
    }
    for (const a of ACTIVITIES) {
      const lam = (v.population / 10_000) * a.typical_density_per_10k * clusterFactor(d, a.id) * vr.uniform(0.85, 1.15);
      const count = vr.poisson(lam);
      for (let k = 0; k < count; k++) {
        const tags = a.osm_tags;
        const tag = tags.length === 1 || vr.random() < 0.7 ? tags[0] : tags[1 + vr.int(tags.length - 1)];
        const [len, lhi] = TAG_LABELS[`${tag[0]}=${tag[1]}`] ?? [a.id, a.id];
        const p = vr.pick(region.surnames);
        add(`${p[0]} ${len}`, `${p[1]} ${lhi}`, "enterprise", [tag], jitter(vr, v.lat, v.lon, isHq ? 2.5 : 0.8));
      }
    }
  }

  const tables = { settlements, pois };
  cache.set(d.id, tables);
  return tables;
}

/** Udyam registrations by NIC class for a district without a detailed extract. */
export function localUdyam(d: PackDistrict): Record<string, number> {
  const rng = new Rng(`26091-udyam-${d.id}`);
  const table: Record<string, number> = {};
  for (const a of ACTIVITIES) {
    const count = (d.population / 10_000) * a.typical_density_per_10k * clusterFactor(d, a.id) * rng.uniform(0.9, 1.1) * (REG_RATE[a.sector] ?? 0.2);
    table[a.nic_class] = (table[a.nic_class] ?? 0) + Math.round(count);
  }
  return table;
}
