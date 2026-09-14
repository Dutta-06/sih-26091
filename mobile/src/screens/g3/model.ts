/**
 * Small derivations for the money & application screens. Every figure comes from the on-device case
 * (`computeCase`) or the core; nothing here is a result constant. Reference code lists (ISO state codes)
 * are lookup tables, not results.
 */
import type { CaseEvent } from "../../state/store";
import type { CaseView } from "../../core/session";
import type { AppEvent } from "../../core/tracker";
import { nextEvents } from "../../core/tracker";
import { catalogEntry } from "../../core/financial";
import { districts, stateRefEntry } from "../../core/pack";
import type { AppStage, Confidence, LocationCandidate } from "../../core/types";
import type { Installment } from "../../engine/finance";

/** Place the pipeline used: the chosen candidate, else the only candidate (mirrors computeCase). */
export const placeOf = (view: Pick<CaseView, "location">): LocationCandidate | null =>
  view.location.chosen ?? (view.location.candidates.length === 1 ? view.location.candidates[0] : null);

/** FNV-1a 32-bit hash: stable ids from inputs. */
export function fnv(text: string): number {
  let h = 2166136261;
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}

/* ------------------------------------------------------------------ seasons */

export interface SeasonView {
  values: number[]; // 12 values normalised to mean 1
  low: number[]; // month indexes 0-11
  basis: "price_history" | "catalog_profile";
  confidence: Confidence;
}

/**
 * The seasonal index the financial plan actually used (buildFinancial prefers the risk analysis index).
 * Low months: the risk analysis' `lowMonths` when that index was used; for the catalog profile, months below
 * an average month (normalised value < 1).
 */
export function seasonView(view: Pick<CaseView, "financial" | "intel" | "activityId">): SeasonView | null {
  if (!view.activityId || !view.financial) return null;
  if (view.financial.seasonalBasis === "risk_analysis" && view.intel) {
    const r = view.intel.risk;
    return { values: normalise(r.seasonalIndex), low: r.lowMonths, basis: r.seasonalBasis, confidence: r.seasonalBasis === "price_history" ? r.confidence : "estimated" };
  }
  const values = normalise(catalogEntry(view.activityId).seasonal_profile);
  return { values, low: values.flatMap((v, i) => (v < 1 ? [i] : [])), basis: "catalog_profile", confidence: "estimated" };
}

function normalise(v: number[]): number[] {
  const mean = v.reduce((a, b) => a + b, 0) / (v.length || 1);
  return mean > 0 ? v.map((x) => x / mean) : v.map(() => 1);
}

/* ------------------------------------------------------------------ dates */

/** ISO date (YYYY-MM-DD) plus whole months, in UTC; the day is clamped to the target month's length. */
export function addMonthsIso(iso: string, months: number, minusDays = 0): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  const total = y * 12 + (m - 1) + months;
  const ty = Math.floor(total / 12);
  const tm = total % 12;
  const last = new Date(Date.UTC(ty, tm + 1, 0)).getUTCDate();
  const date = new Date(Date.UTC(ty, tm, Math.min(d, last)));
  date.setUTCDate(date.getUTCDate() - minusDays);
  return date.toISOString().slice(0, 10);
}

/** Due date of each quarterly instalment: three months per quarter after disbursal. */
export const dueDates = (startIso: string, schedule: Installment[]) => schedule.map((i) => ({ ...i, due: addMonthsIso(startIso, i.quarter * 3) }));

/* ------------------------------------------------------------------ application */

export const STAGE_ORDER: AppStage[] = ["documents_pending", "submitted", "under_verification", "sanctioned", "disbursed"];

/** Position on the tracker; rejected sits where it was rejected (derived from the events). */
export function stageIndex(stage: AppStage, events: CaseEvent[]): number {
  if (stage === "not_started") return -1;
  if (stage !== "rejected") return STAGE_ORDER.indexOf(stage);
  const before = [...events].reverse().find((e) => e.type === "application" && e.data?.stage !== "rejected");
  return before ? STAGE_ORDER.indexOf(before.data!.stage as AppStage) : 1;
}

/** When each stage was last reached (application events), plus the first document update for "documents". */
export function stageDates(events: CaseEvent[]): Partial<Record<AppStage, string>> {
  const out: Partial<Record<AppStage, string>> = {};
  for (const e of events) {
    if (e.type === "application" && typeof e.data?.stage === "string") out[e.data.stage as AppStage] = e.at;
    if (e.type === "documents_updated" && !out.documents_pending) out.documents_pending = e.at;
  }
  return out;
}

/** Officer / system events that may follow the current stage (the user's own "submit" is on Documents). */
export const officerEvents = (stage: AppStage): AppEvent[] => nextEvents(stage).filter((e) => e !== "submit");

/** Three-letter district code from the pack id ("bhadohi" → "BHA"). */
export const districtCode = (districtId: string | null | undefined) => (districtId ?? "").replace(/[^a-z]/gi, "").slice(0, 3).toUpperCase() || "XXX";

/**
 * Application reference: district code, year and 5 digits hashed from the first application event's
 * timestamp. Null until the application has any event.
 */
export function applicationRef(districtId: string | null | undefined, events: CaseEvent[]): string | null {
  const first = events.find((e) => e.type === "application");
  if (!first) return null;
  return `ARB-${districtCode(districtId)}-${first.at.slice(0, 4)}-${String(fnv(`${districtId}|${first.at}`) % 100_000).padStart(5, "0")}`;
}

/* ------------------------------------------------------------------ Udyam */

/** ISO 3166-2:IN state codes (reference list) for states in the data pack. */
const ISO_STATE: Record<string, string> = {
  "Uttar Pradesh": "UP", Bihar: "BR", "West Bengal": "WB", Jharkhand: "JH", Odisha: "OD", "Madhya Pradesh": "MP",
  Chhattisgarh: "CG", Rajasthan: "RJ", Gujarat: "GJ", Maharashtra: "MH", Karnataka: "KA", "Tamil Nadu": "TN", Kerala: "KL",
  "Andhra Pradesh": "AP", Telangana: "TS", Punjab: "PB", Haryana: "HR", "Himachal Pradesh": "HP", Uttarakhand: "UK", Assam: "AS",
};

export function stateCode(stateName: string): string {
  const entry = stateRefEntry(stateName);
  const name = entry?.[0] ?? stateName;
  return ISO_STATE[name] ?? (name.replace(/[^a-z]/gi, "").slice(0, 2).toUpperCase().padEnd(2, "X"));
}

/** District number within its state: position in the pack's district list for that state (sorted by id), 2 digits. */
export function districtNumber(districtId: string, stateName: string): string {
  const ids = districts().filter((d) => d.state === stateName).map((d) => d.id).sort();
  const i = ids.indexOf(districtId);
  return String(i < 0 ? fnv(districtId) % 100 : i + 1).padStart(2, "0");
}

/** Simulated Udyam number UDYAM-<state>-<district no>-<7 digits hashed from the registration inputs>. */
export function udyamNumber(input: { districtId: string; stateName: string; nic: string; enterpriseName: string; aadhaarLast4: string; capital: number }): string {
  const digits = String(fnv(`${input.districtId}|${input.nic}|${input.enterpriseName.trim().toLowerCase()}|${input.aadhaarLast4}|${input.capital}`) % 10_000_000).padStart(7, "0");
  return `UDYAM-${stateCode(input.stateName)}-${districtNumber(input.districtId, input.stateName)}-${digits}`;
}

/** Six-digit simulated OTP derived from the masked Aadhaar and the day (no SMS is sent). */
export const simulatedOtp = (aadhaarLast4: string, dayIso: string) => String(fnv(`${aadhaarLast4}|${dayIso.slice(0, 10)}`) % 1_000_000).padStart(6, "0");
