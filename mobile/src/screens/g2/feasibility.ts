/**
 * G2 view-model helpers over the on-device case (`useCase()`). Nothing here is a result constant: every figure is read
 * from the computed FeasibilityOutcome / Intel or derived from them with the small documented functions below.
 */
import { ACTIVITIES } from "../../data/activities";
import { previewDebtService } from "../../engine/finance";
import { runFeasibility } from "../../core/feasibility";
import { affordableProjectCost, catalogActivities, catalogActivity, MARGIN_SHARE, SCHEME_MAX_PROJECT_COST } from "../../core/intel/catalog";
import { evaluate } from "../../core/review";
import { buildSwot } from "../../core/swot";
import type { CaseView } from "../../core/session";
import type { FeasibilityAttempt, Intel, LocationCandidate, ProfileInput } from "../../core/types";

/** The location the pipeline used: the chosen candidate, or the only candidate. */
export const placeOf = (view: CaseView): LocationCandidate | null =>
  view.location.chosen ?? (view.location.candidates.length === 1 ? view.location.candidates[0] : null);

/** Display name + emoji of a catalog activity (falls back to the id for unknown ids). */
export function activityLabel(id: string | null | undefined) {
  const a = id ? ACTIVITIES[id] : undefined;
  return { name: a?.name ?? { en: id ?? "", hi: id ?? "" }, emoji: a?.emoji ?? "•" };
}

/** First attempt the red-team review did not pass (marginal or not_recommended). */
export const firstRejected = (view: CaseView): FeasibilityAttempt | null => view.feasibility.attempts.find((a) => a.verdict !== "viable") ?? null;

/**
 * Attempt whose report is shown: the one for `view.activityId`, else the latest attempt. When the activity being pursued
 * was never run through the loop (e.g. picked from the shortlist while infeasible) the same core steps the loop uses are
 * applied to `view.intel` (evaluate + buildSwot), with the shortlist score.
 */
export function reportAttempt(view: CaseView, profile: ProfileInput): FeasibilityAttempt | null {
  const { attempts, shortlist } = view.feasibility;
  if (view.activityId) {
    const hit = attempts.find((a) => a.activityId === view.activityId);
    if (hit) return hit;
    const activity = catalogActivity(view.activityId);
    if (activity && view.intel) return synthesizeAttempt(profile.capital, view.activityId, view.intel, shortlist.find((r) => r.activityId === view.activityId)?.score ?? 0);
  }
  return attempts.at(-1) ?? null;
}

function synthesizeAttempt(capital: number, activityId: string, intel: Intel, score: number): FeasibilityAttempt {
  const activity = catalogActivity(activityId)!;
  const preview = previewDebtService(capital, activity);
  const review = evaluate(capital, activity, intel, preview);
  const swot = buildSwot(intel, capital, activity);
  return {
    activityId, intel, verdict: review.verdict, findings: review.findings, notes: [...review.notes, swot.budgetNote], preview, score,
    swot: { strengths: swot.strengths, weaknesses: swot.weaknesses, opportunities: swot.opportunities, threats: swot.threats },
  };
}

/** Intel for the map/evidence: the report attempt's intel, else the case intel. */
export const caseIntel = (view: CaseView, profile: ProfileInput): Intel | null => reportAttempt(view, profile)?.intel ?? view.intel;

/** Six analyses' confidence labels → counts of real vs estimated. */
export function confidenceCounts(intel: Intel) {
  const all = [intel.marketReach, intel.opportunity, intel.competitor, intel.pricing, intel.risk, intel.supplyChain].map((i) => i.confidence);
  const real = all.filter((c) => c === "real").length;
  return { total: all.length, real, estimated: all.length - real };
}

/** Why an alternative follows a rejected activity: catalog adjacency list, same sector, or neither. */
export function adjacency(fromId: string, toId: string): "listed" | "sector" | "none" {
  const from = catalogActivity(fromId);
  const to = catalogActivity(toId);
  if (!from || !to) return "none";
  if (from.adjacent.includes(toId)) return "listed";
  return from.sector === to.sector ? "sector" : "none";
}

/** Benchmark the competitor z-score was computed against (see core/intel/competitor.ts comparison rules). */
export function competitorBenchmark(intel: Intel, activityId: string): { value: number | null; scope: "catalog" | "state" } {
  const c = intel.competitor;
  if (c.tier === "overpass") return { value: catalogActivity(activityId)?.typical_density_per_10k ?? null, scope: "catalog" };
  return c.statePer10k !== null ? { value: c.statePer10k, scope: "state" } : { value: catalogActivity(activityId)?.typical_density_per_10k ?? null, scope: "catalog" };
}

/* ------------------------------------------------------------------ Savings path (NoViable) */

/** Search grid for the savings path: ₹500 steps (a savings amount people can plan in). */
export const SAVINGS_STEP = 500;
/** Upper bound of the search: the capital that reaches the scheme's project ceiling. */
export const SAVINGS_MAX = SCHEME_MAX_PROJECT_COST * MARGIN_SHARE;

export interface SavingsTarget {
  activityId: string;
  capital: number; // savings at which the review first passes
  more: number; // capital − current savings
  project: number;
  dscr: number | null;
  confirmed: boolean; // runFeasibility at that capital selects this activity
}

/**
 * Cheapest viable activity by savings (documented search):
 *  1. intel does not depend on capital (runIntel reads only activity, location and reason), so each catalog activity's
 *     intel is the case's own when it was attempted, else runFeasibility's first attempt for that preference;
 *  2. candidate capitals above the current savings: from the catalog minimum project × margin share, in ₹500 steps up
 *     to ₹20,000 (this covers the ₹14,000 micro-finance tier boundary), ₹5,000 steps to ₹2 lakh, then ₹50,000 steps
 *     to the scheme ceiling — scanned in increasing order; `evaluate` (the red-team rules) must return "viable";
 *  3. the winner is confirmed with runFeasibility for that activity at the location with the found capital.
 * Activities rejected by capital-independent rules (crowding, risks) never become viable and are skipped.
 */
export function cheapestViable(profile: ProfileInput, place: LocationCandidate | null): SavingsTarget | null {
  let best: SavingsTarget | null = null;
  for (const a of catalogActivities()) {
    const start = Math.max(SAVINGS_STEP, Math.ceil((a.min_project_cost * MARGIN_SHARE) / SAVINGS_STEP) * SAVINGS_STEP);
    if (best && start >= best.capital) continue;
    const probe = runFeasibility({ ...profile, capital: Math.max(start, profile.capital), activityId: a.id }, place, 1).attempts[0];
    const intel = probe && probe.activityId === a.id ? probe.intel : null;
    if (!intel) continue;
    for (let c = start; c <= SAVINGS_MAX && (!best || c < best.capital); c += c < 20_000 ? SAVINGS_STEP : c < 200_000 ? 5_000 : 50_000) {
      if (c <= profile.capital) continue;
      const preview = previewDebtService(c, a);
      if (evaluate(c, a, intel, preview).verdict !== "viable") continue;
      best = { activityId: a.id, capital: c, more: c - profile.capital, project: affordableProjectCost(c), dscr: preview.baseDscr, confirmed: false };
      break;
    }
  }
  if (best) {
    const check = runFeasibility({ ...profile, capital: best.capital, activityId: best.activityId }, place);
    best.confirmed = check.selected?.activityId === best.activityId;
  }
  return best;
}
