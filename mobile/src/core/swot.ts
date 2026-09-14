/**
 * SWOT synthesis — port of module1_feasibility/swot_synthesis.py. Every bullet is produced from an actual value
 * (bullets whose data is missing are skipped) and carries the confidence of its source in `vars.confidence`.
 * Also the sub-niche saturation cross-check against competitor density and the budget scaling note.
 */
import { affordableProjectCost, type CatalogActivity, MONTHS, msg, round } from "./intel/catalog";
import { rawMaterialAvailability } from "./intel/supplyChain";
import type { CompetitorIntel, Intel, Msg, Saturation, SubNicheIntel, Swot } from "./types";

/** swot_synthesis.cross_check_saturation: re-grade niches against observed competitor density. */
export function crossCheckSaturation(niches: SubNicheIntel[], comp: CompetitorIntel): { niches: SubNicheIntel[]; notes: Msg[] } {
  if (comp.densityPer10k === null) return { niches, notes: [msg("c2.swot.crossCheck.noDensity")] };
  // competitorIntel already classified density against the benchmark matching its scope (classify_saturation rule).
  const observed: Saturation | null = comp.saturation !== "unknown" ? comp.saturation : null;
  if (observed === null) return { niches, notes: [msg("c2.swot.crossCheck.noBenchmark")] };
  const notes: Msg[] = [];
  const out = niches.map((n) => {
    if (n.saturation === observed) return n;
    notes.push(msg("c2.swot.crossCheck.regraded", { niche: n.name, from: n.saturation, to: observed!, density: round(comp.densityPer10k!, 2) }));
    return { ...n, saturation: observed! };
  });
  return { niches: out, notes };
}

export function buildSwot(intel: Intel, capital: number, activity: CatalogActivity | null): Swot & { budgetNote: Msg } {
  const s: Msg[] = [], w: Msg[] = [], o: Msg[] = [], t: Msg[] = [];
  const { marketReach: reach, opportunity: opp, risk, competitor: comp, pricing, supplyChain: supply } = intel;

  if (reach.consumerBase !== null) {
    (reach.consumerBase >= 10_000 ? s : w).push(msg("c2.swot.consumerBase", { n: reach.consumerBase, km: reach.radiusKm, confidence: reach.confidence }));
  }
  if (reach.places.length) {
    const near = reach.places[0];
    s.push(msg("c2.swot.places", { n: reach.places.length, nearest: near.poi.name.en, km: round(near.km, 1), confidence: "real" }));
  }

  if (comp.count !== null) {
    const bullet = msg(comp.zScore !== null ? "c2.swot.competitorsZ" : "c2.swot.competitors", {
      n: comp.count, saturation: comp.saturation, ...(comp.zScore !== null ? { z: round(comp.zScore, 2) } : {}), confidence: comp.confidence,
    });
    (comp.saturation === "high" ? t : comp.saturation === "low" ? s : w).push(bullet);
  }

  for (const n of opp.niches.slice(0, 3)) {
    if (n.saturation === "low" || n.saturation === "medium") o.push(msg("c2.swot.niche", { niche: n.name, saturation: n.saturation, confidence: "estimated" }));
    else if (n.saturation === "high") t.push(msg("c2.swot.nicheSaturated", { niche: n.name, confidence: "estimated" }));
  }
  for (const n of opp.niches.filter((x) => x.saturation === "low").slice(0, 2)) o.push(msg("c2.swot.unserved", { niche: n.name, confidence: opp.confidence }));
  const evidence = [...new Set(opp.niches.flatMap((n) => n.evidenceIds))].slice(0, 2);
  for (const id of evidence) o.push(msg("c2.swot.feedback", { id, confidence: "real" }));

  const range = pricing.points.find((p) => p.low !== p.high) ?? pricing.points[0];
  if (range) {
    o.push(msg("c2.swot.priceBand", { low: range.low, high: range.high, unit: typeof range.unit === "string" ? range.unit : range.unit.en, basis: pricing.basis, confidence: pricing.confidence }));
  }
  if (pricing.purchasingPowerIndex !== null && pricing.purchasingPowerIndex < 0.925) w.push(msg("c2.swot.lowPurchasingPower", { confidence: pricing.confidence }));

  if (risk.lowMonths.length) {
    const seasonalFlag = risk.flags.find((f) => f.id === "seasonal_demand_variation");
    t.push(msg("c2.swot.lowMonths", { months: risk.lowMonths.map((m) => MONTHS[m]).join(", "), variation: seasonalFlag?.severity ?? "medium", confidence: risk.confidence }));
  }
  if (risk.hubKm !== null) {
    const routeRisk = risk.flags.find((f) => f.id === "route_distance")?.severity ?? "medium";
    (routeRisk === "high" ? t : routeRisk === "medium" ? w : s).push(msg("c2.swot.route", { km: risk.hubKm, method: risk.routeMethod, risk: routeRisk, confidence: risk.confidence }));
  }
  for (const f of risk.flags.filter((x) => x.severity === "high")) t.push(msg("c2.swot.highRisk", { id: f.id, titleKey: f.title.key, confidence: f.confidence }));

  const availability = rawMaterialAvailability(supply);
  if (availability !== "unknown") (availability === "locally_available" ? s : w).push(msg(`c2.swot.materials.${availability}`, { confidence: "real" }));
  for (const id of supply.singlePointsOfFailure.slice(0, 2)) {
    const node = supply.nodes.find((n) => n.id === id);
    const label = node ? (typeof node.label === "string" ? node.label : node.label.en) : id;
    w.push(msg("c2.swot.spof", { node: label, confidence: supply.confidence }));
  }

  const affordable = affordableProjectCost(capital);
  let budgetNote: Msg;
  if (activity && affordable > 0) {
    const ratio = activity.min_project_cost ? affordable / activity.min_project_cost : 0;
    const key = ratio < 1 ? "c2.swot.budget.below" : ratio < 1.5 ? "c2.swot.budget.tight" : "c2.swot.budget.ok";
    budgetNote = msg(key, { capital, project: affordable, ratio: round(ratio, 1), min: activity.min_project_cost });
  } else budgetNote = msg("c2.swot.budget.unknown");
  return { strengths: s, weaknesses: w, opportunities: o, threats: t, budgetNote };
}
