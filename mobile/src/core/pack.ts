/**
 * Typed loaders over the bundled data pack (src/core/data/*.json, written by scripts/build_datapack.py).
 *
 * Coverage: every Census 2011 district (data/india_districts.json, scripts/build_india_districts.py). A few districts
 * carry detailed village / POI / Udyam / feedback tables; the others get generated local tables (core/localgen.ts).
 *
 * The open-data tables (villages, POIs, Udyam counts, price series, feedback) are a deterministic SAMPLE pack
 * standing in for real downloads (`_meta.json` → synthetic_sample: true). Callers label values read from these
 * tables "real" (they occupy the place of a real open source); state reference values are "estimated".
 */
import { biFromKey } from "../i18n";
import type { Bi } from "../i18n";
import type {
  OutcomeRecord,
  PackDistrict,
  PackDoc,
  PackFeedback,
  PackPoi,
  PackPriceSeries,
  PackVillage,
} from "./types";
import metaJson from "./data/_meta.json";
import districtsJson from "./data/districts.json";
import villagesJson from "./data/villages.json";
import poisJson from "./data/pois.json";
import udyamJson from "./data/udyam.json";
import pricesJson from "./data/prices.json";
import feedbackJson from "./data/feedback.json";
import docsJson from "./data/docs.json";
import outcomeJson from "./data/outcome_seed.json";
import stateRefJson from "./data/state_reference.json";
import healthJson from "./data/health_thresholds.json";
import indiaJson from "./data/india_districts.json";
import { GEN_RADIUS_KM, localTables, localUdyam } from "./localgen";
import { openPlacesLoaded, openPlacesNear, openVillagesLoaded, openVillagesNear } from "./openData";
import placeCategoriesJson from "./data/open_place_categories.json";
import placeCountsJson from "./data/open_place_counts.json";

export interface PackMeta {
  synthetic_sample: boolean;
  seed?: number;
  generated?: string;
  notes?: string[];
}

export interface StateRef {
  density: number;
  lat: number;
  lon: number;
  purchasing_power: "low" | "medium" | "high";
}

export interface HealthThresholds {
  weights: { revenue_vs_plan: number; surplus_coverage: number; repayment: number };
  bands: { healthy_min_score: number; watch_min_score: number };
  revenue_ratio_full_score: number;
  revenue_ratio_floor: number;
  revenue_shortfall_ratio: number;
  coverage_full_score: number;
  expense_ratio_spike_margin: number;
  normal_volume_min_transactions_per_week: number;
  normal_volume_vs_previous_ratio: number;
  persistent_at_risk_snapshots: number;
  repayment_scores: Record<"paid" | "not_due" | "unknown" | "grace_period" | "overdue", number>;
}

type VillageRow = [string, string, string, string, string, string, number, number, number];
type PoiRow = [string, string, string, PackPoi["kind"], string, number, number];
type PriceRow = { commodity: string; state: string; start: string; modal: number[] };

const lc = (s: string) => s.trim().toLowerCase();

export const packMeta = (): PackMeta => metaJson as PackMeta;

type IndiaRow = [string, string, string, number, number, number, number, number, 0 | 1];
const norm = (s: string) => lc(s).replace(/[^\p{L}\p{M}\p{N}]+/gu, " ").trim();

let _districts: PackDistrict[] | null = null;
let _detailed: Set<string> | null = null;
/** Detailed pack districts first, then every other Census 2011 district (generated local tables). */
export function districts(): PackDistrict[] {
  if (_districts) return _districts;
  const detailed = (districtsJson as unknown as PackDistrict[]).map((d) => ({ ...d, name: biFromKey(`place.district.${d.id}`, d.name) }));
  _detailed = new Set(detailed.map((d) => d.id));
  const taken = new Set(detailed.flatMap((d) => [d.name.en, ...d.aliases].map((a) => `${lc(d.state)}|${norm(a)}`)));
  const rest: PackDistrict[] = [];
  for (const [id, name, state, lat, lon, population, areaSqKm] of indiaJson as unknown as IndiaRow[]) {
    const plain = name.replace(/\s*\(.*\)\s*/, "").trim();
    const inner = /\((.*)\)/.exec(name)?.[1];
    const variants = [name, plain, inner].filter((x): x is string => !!x);
    if (variants.some((v) => taken.has(`${lc(state)}|${norm(v)}`)) || _detailed.has(id)) continue;
    const aliases = [...new Set(variants.map(norm))];
    rest.push({ id, name: biFromKey(`place.district.${id}`, { en: plain, hi: plain }), aliases, state, lat, lon, population, areaSqKm });
  }
  return (_districts = [...detailed, ...rest]);
}

/** True for districts with detailed pack tables (villages, POIs, Udyam extract, feedback). */
export function isDetailed(id: string): boolean {
  districts();
  return _detailed!.has(id);
}

/** Districts without detailed tables whose generated tables can reach within radiusKm of the point. */
function generatedNear(lat: number, lon: number, radiusKm: number): PackDistrict[] {
  const reach = (d: PackDistrict) => (openVillagesLoaded() ? Math.max(GEN_RADIUS_KM, 1.4 * Math.sqrt(Math.max(1, d.areaSqKm) / Math.PI)) : GEN_RADIUS_KM);
  return districts().filter((d) => !isDetailed(d.id) && distanceKm(lat, lon, d.lat, d.lon) <= radiusKm + reach(d));
}

/* ------------------------------------------------------------------ real places coverage (Overture Maps) */

const PLACE_CATEGORIES = placeCategoriesJson as Record<string, { kind: string; activities: string[] }>;
const PLACE_COUNTS = placeCountsJson as Record<string, Record<string, number>>;
/** A state needs this many mapped places of an activity before mapped places stand for that activity there. */
export const MIN_STATE_MAPPED = 40;
/** Fewer mapped places of a kind than this in a district keeps the generated ones of that kind. */
const MIN_DISTRICT_KIND: Record<string, number> = { bank: 3, school: 10, transport: 2, supplier: 3, market: 1 };

/** Mapped places in a district: per activity and per place kind. */
const _mapped = new Map<string, { activities: Record<string, number>; kinds: Record<string, number> }>();
export function mappedCounts(districtId: string): { activities: Record<string, number>; kinds: Record<string, number> } {
  const hit = _mapped.get(districtId);
  if (hit) return hit;
  const activities: Record<string, number> = {};
  const kinds: Record<string, number> = {};
  for (const [cat, n] of Object.entries(PLACE_COUNTS[districtId] ?? {})) {
    const meta = PLACE_CATEGORIES[cat];
    if (!meta) continue;
    kinds[meta.kind] = (kinds[meta.kind] ?? 0) + n;
    if (meta.kind === "enterprise") for (const a of meta.activities) activities[a] = (activities[a] ?? 0) + n;
  }
  const out = { activities, kinds };
  _mapped.set(districtId, out);
  return out;
}

let _stateMapped: Map<string, { activities: Record<string, number>; population: number }> | null = null;
/** Mapped places per activity and population over all districts of a state. */
export function stateMapped(state: string): { activities: Record<string, number>; population: number } {
  if (!_stateMapped) {
    _stateMapped = new Map();
    for (const d of districts()) {
      const s = _stateMapped.get(d.state) ?? { activities: {}, population: 0 };
      s.population += d.population;
      for (const [a, n] of Object.entries(mappedCounts(d.id).activities)) s.activities[a] = (s.activities[a] ?? 0) + n;
      _stateMapped.set(d.state, s);
    }
  }
  return _stateMapped.get(state) ?? { activities: {}, population: 0 };
}

const _generated = new Map<string, PackPoi[]>();
/** A district's generated places that mapped places do not replace (cached). */
function generatedPlaces(d: PackDistrict): PackPoi[] {
  let list = _generated.get(d.id);
  if (!list) {
    const covered = openPlacesLoaded();
    const tables = localTables(d, covered ? {
      activity: (id) => (stateMapped(d.state).activities[id] ?? 0) < MIN_STATE_MAPPED,
      kind: (k) => k === "enterprise" || MIN_DISTRICT_KIND[k] === undefined || (mappedCounts(d.id).kinds[k] ?? 0) < MIN_DISTRICT_KIND[k],
    } : undefined);
    _generated.set(d.id, (list = tables.pois.filter((poi) => keepGenerated(poi, d))));
  }
  return list;
}

/** Generated places are kept only where mapped places do not cover their activity (state) or kind (district). */
function keepGenerated(poi: PackPoi, d: PackDistrict): boolean {
  if (!openPlacesLoaded()) return true;
  if (poi.kind === "enterprise") {
    const activity = poi.tags.find(([k]) => k === "activity")?.[1];
    return !activity || (stateMapped(d.state).activities[activity] ?? 0) < MIN_STATE_MAPPED;
  }
  const min = MIN_DISTRICT_KIND[poi.kind];
  return min === undefined || (mappedCounts(d.id).kinds[poi.kind] ?? 0) < min;
}

/** District by id (case-insensitive id or English name). */
export function district(id: string): PackDistrict | null {
  const k = lc(id);
  return districts().find((d) => d.id === k || lc(d.name.en) === k) ?? null;
}

let _villages: PackVillage[] | null = null;
export function villages(): PackVillage[] {
  return (_villages ??= (villagesJson as unknown as VillageRow[]).map(([lgd, en, hi, ben, bhi, d, lat, lon, population]) => ({
    lgd,
    name: { en, hi },
    block: { en: ben, hi: bhi },
    district: d,
    lat,
    lon,
    population,
  })));
}

let _pois: PackPoi[] | null = null;
export function pois(): PackPoi[] {
  return (_pois ??= (poisJson as unknown as PoiRow[]).map(([id, en, hi, kind, tags, lat, lon]) => ({
    id,
    name: { en, hi } as Bi,
    kind,
    tags: tags ? (tags.split(";").map((t) => t.split("=") as [string, string])) : [],
    lat,
    lon,
  })));
}

const R = 6371.0088;
const rad = (d: number) => (d * Math.PI) / 180;
/** Great-circle distance (km), same constant as common.reference.haversine_km. */
export function distanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dp = rad(lat2 - lat1);
  const dl = rad(lon2 - lon1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/** Villages within radiusKm: detailed pack villages, and Census 2011 villages elsewhere (generated settlements without them). */
const _settlements = new Map<string, PackVillage[]>();
export function settlementsNear(lat: number, lon: number, radiusKm: number): PackVillage[] {
  const key = `${lat.toFixed(4)},${lon.toFixed(4)},${radiusKm},${openVillagesLoaded()}`;
  const hit = _settlements.get(key);
  if (hit) return hit;
  if (_settlements.size > 40) _settlements.delete(_settlements.keys().next().value!);
  const result = settlementsNearUncached(lat, lon, radiusKm);
  _settlements.set(key, result);
  return result;
}

function settlementsNearUncached(lat: number, lon: number, radiusKm: number): PackVillage[] {
  const detailed = villages().filter((v) => distanceKm(lat, lon, v.lat, v.lon) <= radiusKm);
  if (openVillagesLoaded()) return [...detailed, ...openVillagesNear(lat, lon, radiusKm, (id) => !isDetailed(id))];
  const generated = generatedNear(lat, lon, radiusKm).flatMap((d) => localTables(d).settlements);
  return [...detailed, ...generated.filter((v) => distanceKm(lat, lon, v.lat, v.lon) <= radiusKm)];
}

/**
 * POIs within radiusKm, nearest first: detailed pack POIs; elsewhere real mapped places (Overture Maps) plus generated
 * places for activities and kinds the mapped places do not cover.
 */
export function poisNear(lat: number, lon: number, radiusKm: number, filter?: (p: PackPoi) => boolean): { poi: PackPoi; km: number }[] {
  const all = nearCache(`${lat.toFixed(4)},${lon.toFixed(4)},${radiusKm}`, () => {
    const out: { poi: PackPoi; km: number }[] = [];
    const real = openPlacesNear(lat, lon, radiusKm).filter((p) => !isDetailed(p.district)).map((p) => p.poi);
    const candidates = [...pois(), ...real, ...generatedNear(lat, lon, radiusKm).flatMap(generatedPlaces)];
    for (const poi of candidates) {
      const km = distanceKm(lat, lon, poi.lat, poi.lon);
      if (km <= radiusKm) out.push({ poi, km: Math.round(km * 100) / 100 });
    }
    return out.sort((a, b) => a.km - b.km || a.poi.id.localeCompare(b.poi.id));
  });
  return filter ? all.filter((p) => filter(p.poi)) : all;
}

/** Recent radius queries (the case is recomputed often for the same place). */
const _near = new Map<string, { poi: PackPoi; km: number }[]>();
function nearCache(key: string, compute: () => { poi: PackPoi; km: number }[]): { poi: PackPoi; km: number }[] {
  let hit = _near.get(key);
  if (!hit) {
    hit = compute();
    if (_near.size > 40) _near.delete(_near.keys().next().value!);
    _near.set(key, hit);
  }
  return hit;
}

const UDYAM = udyamJson as Record<string, Record<string, number>>;

/** NIC prefix match as in data_connectors/udyam.nic_matches (compare up to 4 digits, ≥ 2). */
function nicMatches(code: string, prefix: string): boolean {
  const a = code.replace(/\D/g, "");
  const b = prefix.replace(/\D/g, "");
  const n = Math.min(4, a.length, b.length);
  return n >= 2 && a.slice(0, n) === b.slice(0, n);
}

/** Registered enterprises in a district for the NIC class/prefix; null when the district is not in the extract. */
export function udyam(districtId: string, nicPrefix: string): number | null {
  const d = district(districtId);
  const table = d ? UDYAM[d.id] ?? (isDetailed(d.id) ? undefined : localUdyam(d)) : undefined;
  if (!table || nicPrefix.replace(/\D/g, "").length < 2) return null;
  let count = 0;
  for (const [nic, c] of Object.entries(table)) if (nicMatches(nic, nicPrefix)) count += c;
  return count;
}

/** State total over the pack districts in that state (count + their population); null when none are covered. */
export function udyamState(state: string, nicPrefix: string): { count: number; population: number } | null {
  const ds = districts().filter((d) => lc(d.state) === lc(state) && (UDYAM[d.id] || !isDetailed(d.id)));
  if (!ds.length) return null;
  let count = 0;
  let population = 0;
  for (const d of ds) {
    const c = udyam(d.id, nicPrefix);
    if (c === null) return null;
    count += c;
    population += d.population;
  }
  return { count, population };
}

function addMonths(start: string, i: number): string {
  const [y, m] = start.split("-").map(Number);
  const t = y * 12 + (m - 1) + i;
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, "0")}`;
}

let _prices: PackPriceSeries[] | null = null;
export function priceSeriesAll(): PackPriceSeries[] {
  return (_prices ??= (pricesJson as unknown as PriceRow[]).map((r) => ({
    commodity: r.commodity,
    state: r.state,
    months: r.modal.map((modal, i) => ({ month: addMonths(r.start, i), modal })),
  })));
}

/** Monthly modal price series (INR per quintal) for a commodity in a state; null when absent. */
export function priceSeries(commodity: string, state: string): PackPriceSeries | null {
  return priceSeriesAll().find((s) => lc(s.commodity) === lc(commodity) && lc(s.state) === lc(state)) ?? null;
}

/** Feedback records for a district; activityId null → all activities in the district. */
export function feedback(districtId: string, activityId: string | null): PackFeedback[] {
  const d = district(districtId);
  if (!d) return [];
  return (feedbackJson as unknown as PackFeedback[]).filter(
    (f) => f.district === d.id && (activityId === null || f.activityId === activityId),
  );
}

export function docs(collection: PackDoc["collection"]): PackDoc[] {
  return (docsJson as unknown as PackDoc[]).filter((d) => d.collection === collection);
}

export function outcomeSeed(): OutcomeRecord[] {
  return (outcomeJson as unknown as { records: OutcomeRecord[] }).records;
}

type StateRefFile = {
  states: Record<string, StateRef & { aliases?: string[] }>;
  national_average_density: number;
  districts: Record<string, { state: string; lat: number; lon: number; aliases?: string[] }>;
};
let _stateRef: StateRefFile | null = null;
/**
 * State reference from the repository, completed for states and union territories it lacks (Delhi, Goa, the
 * North-East, J&K, …) with Census 2011 density and a population-weighted centre from the district table.
 */
export function stateReference(): StateRefFile {
  if (_stateRef) return _stateRef;
  const base = stateRefJson as unknown as StateRefFile;
  const states = { ...base.states };
  const byState = new Map<string, IndiaRow[]>();
  for (const row of indiaJson as unknown as IndiaRow[]) byState.set(row[2], [...(byState.get(row[2]) ?? []), row]);
  const HIGH = new Set(["Delhi", "Goa", "Chandigarh", "Puducherry"]);
  for (const [state, rows] of byState) {
    if (states[state]) continue;
    const pop = rows.reduce((t, r) => t + r[5], 0);
    const area = rows.reduce((t, r) => t + r[6], 0);
    states[state] = {
      density: Math.round(pop / Math.max(1, area)),
      lat: Math.round((rows.reduce((t, r) => t + r[3] * r[5], 0) / pop) * 100) / 100,
      lon: Math.round((rows.reduce((t, r) => t + r[4] * r[5], 0) / pop) * 100) / 100,
      purchasing_power: HIGH.has(state) ? "high" : "medium",
      aliases: [],
    };
  }
  return (_stateRef = { ...base, states });
}

const normName = (s: string) => lc(s).replace(/-/g, " ").split(/\s+/).filter(Boolean).join(" ");

/** State reference by name or alias (e.g. "UP"), as common.reference.lookup_state. */
export function stateRef(name: string): StateRef | null {
  const hit = stateRefEntry(name);
  return hit ? hit[1] : null;
}

export function stateRefEntry(name: string): [string, StateRef] | null {
  if (!name) return null;
  const n = normName(name);
  for (const [state, info] of Object.entries(stateReference().states)) {
    if ([state, ...(info.aliases ?? [])].some((a) => normName(a) === n)) {
      return [state, { density: info.density, lat: info.lat, lon: info.lon, purchasing_power: info.purchasing_power }];
    }
  }
  return null;
}

export const healthThresholds = (): HealthThresholds => healthJson as unknown as HealthThresholds;
