/**
 * Adversarial (red-team) review — exact port of module1_feasibility/adversarial_review.evaluate.
 *
 *  not_recommended  R1 catalog minimum project cost > project the capital supports
 *                   R2 base DSCR < 1.0
 *                   R3 competitor saturation high AND z-score > 2
 *  marginal         M1 base DSCR < 1.25   M2 saturation high (competitor, or all sub-niches when competitor is not high)
 *                   M3 ≥ 2 high-severity non-seasonal risk flags (SEASONAL_RISK_IDS excluded; M4 judges seasonality)
 *                   M4 weakest seasonal-quarter DSCR < 0.8
 * Estimated inputs never reject on their own; they are counted in a note. Outside the scheme range the coverage
 * rules are not applied (the financial engine reports it).
 */
import type { DebtServicePreview } from "../engine/finance";
import { affordableProjectCost, type CatalogActivity, msg, round } from "./intel/catalog";
import type { Intel, Msg, ReviewFinding, Verdict } from "./types";

export const DSCR_REJECT = 1.0;
export const DSCR_MARGINAL = 1.25;
export const SEASONAL_DSCR_MARGINAL = 0.8;
export const Z_REJECT = 2.0;
export const SEASONAL_RISK_IDS = new Set(["seasonal_demand_variation", "working_capital_strain", "festival_season_concentration"]);

export interface ReviewResult {
  verdict: Verdict;
  findings: ReviewFinding[]; // reasons driving the verdict: rejections first, then marginal
  notes: Msg[];
}

type ReviewActivity = Pick<CatalogActivity, "id" | "min_project_cost">;

export function evaluate(capital: number, activity: ReviewActivity, intel: Intel | null, preview: DebtServicePreview | null): ReviewResult {
  const reject: ReviewFinding[] = [];
  const marginal: ReviewFinding[] = [];
  const notes: Msg[] = [];
  const affordable = affordableProjectCost(capital);
  if (activity.min_project_cost > affordable) {
    reject.push({ rule: "R1", msg: msg("c2.review.R1", { activity: activity.id, need: activity.min_project_cost, capital, have: affordable }) });
  }

  if (preview === null) notes.push(msg("c2.review.noPreview"));
  else if (!preview.plan.eligible) notes.push(msg("c2.review.outsideScheme", { project: preview.plan.projectCost }));
  else {
    const dscr = preview.baseDscr;
    const seasonal = preview.minSeasonalDscr;
    const basis = { surplus: Math.round(preview.quarterlySurplus), installment: Math.round(preview.plan.regularInstallment) };
    if (dscr !== null && dscr < DSCR_REJECT) reject.push({ rule: "R2", msg: msg("c2.review.R2", { dscr: round(dscr, 2), ...basis }) });
    else if (dscr !== null && dscr < DSCR_MARGINAL) marginal.push({ rule: "M1", msg: msg("c2.review.M1", { dscr: round(dscr, 2), ...basis }) });
    if (seasonal !== null && seasonal < SEASONAL_DSCR_MARGINAL) marginal.push({ rule: "M4", msg: msg("c2.review.M4", { dscr: round(seasonal, 2) }) });
  }

  if (intel) {
    const comp = intel.competitor;
    const z = comp.zScore;
    if (comp.saturation === "high" && z !== null && z > Z_REJECT) {
      reject.push({ rule: "R3", msg: msg("c2.review.R3", { z: round(z, 2), count: comp.count ?? 0, confidence: comp.confidence }) });
    } else if (comp.saturation === "high") {
      marginal.push({ rule: "M2", msg: msg("c2.review.M2", { count: comp.count ?? 0, confidence: comp.confidence }) });
    }
    const niches = intel.opportunity.niches;
    const saturated = niches.filter((n) => n.saturation === "high").map((n) => n.name);
    if (saturated.length && saturated.length === niches.length && comp.saturation !== "high") {
      marginal.push({ rule: "M2", msg: msg("c2.review.M2niches", { niches: saturated.slice(0, 3).join(", ") }) });
    }
    const highs = intel.risk.flags.filter((f) => f.severity === "high" && f.category !== "seasonal" && !SEASONAL_RISK_IDS.has(f.id));
    if (highs.length >= 2) marginal.push({ rule: "M3", msg: msg("c2.review.M3", { n: highs.length, ids: highs.slice(0, 3).map((f) => f.id).join(", ") }) });
    const confidences = [intel.marketReach, intel.opportunity, intel.risk, intel.competitor, intel.pricing, intel.supplyChain].map((i) => i.confidence);
    const estimated = confidences.filter((c) => c === "estimated").length;
    if (estimated) notes.push(msg("c2.review.estimates", { n: estimated }));
  } else {
    notes.push(msg("c2.review.noIntel"));
  }

  const verdict: Verdict = reject.length ? "not_recommended" : marginal.length ? "marginal" : "viable";
  return { verdict, findings: [...reject, ...marginal], notes };
}
