/**
 * Shared Module 1 helpers: the full catalog record (fields the app's Activity type omits), constants mirrored
 * from config/settings.py and module1_feasibility/profiling_agent.py, and small numeric utilities.
 */
import { ACTIVITIES, type Activity } from "../../data/activities";
import type { Bi } from "../../i18n";
import type { Confidence, IntelMeta, LocationCandidate, Msg, SourceRef } from "../types";

/** Catalog fields present in data/reference/business_catalog.json but not declared on the app's Activity. */
export interface CatalogActivity extends Activity {
  nic_class: string;
  keywords: string[];
  commodity: string | null;
  price_unit: string;
  reference_price: { low: number; high: number } | null;
  osm_tags: [string, string][];
  typical_density_per_10k: number | null;
  infrastructure_needs: string[];
}

export const catalogActivity = (id: string): CatalogActivity | null => (ACTIVITIES[id] as CatalogActivity | undefined) ?? null;
export const catalogActivities = (): CatalogActivity[] => Object.values(ACTIVITIES) as CatalogActivity[];

/** settings.market_reach_radius_km */
export const RADIUS_KM = 10;
/** profiling_agent.MARGIN_SHARE / SCHEME_MAX_PROJECT_COST */
export const MARGIN_SHARE = 0.1;
export const SCHEME_MAX_PROJECT_COST = 5_000_000;
/** settings.max_feasibility_attempts */
export const MAX_ATTEMPTS = 3;

/** profiling_agent.affordable_project_cost */
export const affordableProjectCost = (capital: number) => Math.min(Math.max(capital, 0) / MARGIN_SHARE, SCHEME_MAX_PROJECT_COST);

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const round = (v: number, dp = 2) => {
  const f = 10 ** dp;
  return Math.round((v + Math.sign(v) * Number.EPSILON) * f) / f;
};

export const msg = (key: string, vars?: Record<string, string | number>): Msg => (vars ? { key, vars } : { key });
export const src = (en: string, hi: string, confidence: Confidence): SourceRef => ({ name: { en, hi } as Bi, confidence });

/** Location precise enough for a radius query (competitor_agent.usable_coordinates). */
export const usableCoords = (loc: LocationCandidate | null) => (loc && loc.method !== "state_centroid" ? { lat: loc.lat, lon: loc.lon } : null);

/** numpy.percentile with the default linear interpolation. */
export function percentile(values: number[], q: number): number {
  const s = [...values].sort((a, b) => a - b);
  if (!s.length) return NaN;
  const pos = ((s.length - 1) * q) / 100;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return s[lo] + (s[hi] - s[lo]) * (pos - lo);
}

export const emptyMeta = (): IntelMeta => ({ confidence: "estimated", sources: [], limitations: [] });

/** Latin keyword whole-word match with optional plural, as common.reference._keyword_in. */
export function keywordIn(keyword: string, text: string): boolean {
  const kw = keyword.toLowerCase();
  const lowered = text.toLowerCase();
  // eslint-disable-next-line no-control-regex
  if (/^[\x00-\x7f]*$/.test(kw)) {
    const esc = kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(?<![a-z])${esc}(?:s|es)?(?![a-z])`).test(lowered);
  }
  return lowered.includes(kw);
}

export const isAscii = (s: string) => /^[\x00-\x7f]*$/.test(s); // eslint-disable-line no-control-regex
