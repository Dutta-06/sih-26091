/**
 * Typed loaders over the bundled data pack (src/core/data/*.json, written by scripts/build_datapack.py).
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

let _districts: PackDistrict[] | null = null;
export function districts(): PackDistrict[] {
  return (_districts ??= (districtsJson as unknown as PackDistrict[]).map((d) => ({ ...d, name: biFromKey(`place.district.${d.id}`, d.name) })));
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

/** POIs within radiusKm, nearest first. */
export function poisNear(lat: number, lon: number, radiusKm: number, filter?: (p: PackPoi) => boolean): { poi: PackPoi; km: number }[] {
  const out: { poi: PackPoi; km: number }[] = [];
  for (const poi of pois()) {
    if (filter && !filter(poi)) continue;
    const km = distanceKm(lat, lon, poi.lat, poi.lon);
    if (km <= radiusKm) out.push({ poi, km: Math.round(km * 100) / 100 });
  }
  return out.sort((a, b) => a.km - b.km || a.poi.id.localeCompare(b.poi.id));
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
  const table = d ? UDYAM[d.id] : undefined;
  if (!table || nicPrefix.replace(/\D/g, "").length < 2) return null;
  let count = 0;
  for (const [nic, c] of Object.entries(table)) if (nicMatches(nic, nicPrefix)) count += c;
  return count;
}

/** State total over the pack districts in that state (count + their population); null when none are covered. */
export function udyamState(state: string, nicPrefix: string): { count: number; population: number } | null {
  const ds = districts().filter((d) => lc(d.state) === lc(state) && UDYAM[d.id]);
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
export const stateReference = (): StateRefFile => stateRefJson as unknown as StateRefFile;

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
