/**
 * Business discovery (TDD 5.2 / 5.5) — data-driven replacement of the prototype screens/w2/rank.ts.
 *
 * Documented 100-point breakdown (each part is computed, never a constant):
 *  capitalFit /20  0 if the catalog minimum project cost exceeds what the capital supports (profiling rule) or the
 *                  project is outside the scheme range; else 20 × (1 − 0.5 × min_project_cost / affordable project)
 *                  (discovery_agent.score_candidate capital_fit).
 *  repayment  /30  previewDebtService base DSCR, piecewise-linear inside the coverage bands:
 *                  does_not_cover 0.5→1.0 ⇒ 0→10 · thin 1.0→1.25 ⇒ 10→20 · comfortable 1.25→1.75 ⇒ 20→30 (capped).
 *  skills     /20  20 when a profile skill names the activity (skill keyword in the catalog keywords/id), 12 when a
 *                  skill belongs to the activity's sector, 4 otherwise (skills can be learned), 0 with no skills given.
 *  localDemand/20  competitor saturation from competitorIntel for this activity at the location:
 *                  low 20 · medium 12 · high 4 · unknown 10 (neutral, not good news).
 *  outcomes   /10  outcome-learning category prior (outcome_learning_loop.category_prior: synthetic weight 0.3,
 *                  district bonus 2, shrinkage strength 10, bounds 0.9–1.1) mapped 0.9→0 … 1.1→10.
 *
 * Ordering mirrors discovery_agent.run: feasible first; first pass puts the stated preference first; after a
 * rejection adjacency to the rejected activity (catalog `adjacent` 1.0, same sector 0.7) outranks score.
 */
import { buildPlan, coverageBand, previewDebtService } from "../engine/finance";
import { outcomeSeed } from "./pack";
import { affordableProjectCost, type CatalogActivity, catalogActivities, catalogActivity, keywordIn, msg, round } from "./intel/catalog";
import { competitorIntel } from "./intel/competitor";
import type { CompetitorIntel, LocationCandidate, OutcomeRecord, ProfileInput, RankedActivity, Saturation } from "./types";

export const SKILL_SECTORS: Record<string, string[]> = {
  stitching: ["textiles_apparel"], embroidery: ["textiles_apparel"], weaving: ["textiles_apparel"],
  cooking: ["food_processing"], livestock: ["animal_husbandry"], retail: ["retail_trade"], repair: ["services"], beauty: ["services"],
};
export const SKILL_KEYWORDS: Record<string, string[]> = {
  stitching: ["stitching", "tailor", "tailoring", "silai", "garment"], embroidery: ["embroidery", "garment", "tailoring"],
  weaving: ["weaving", "handloom", "loom", "carpet", "rug"], cooking: ["snack", "pickle", "papad", "food processing", "tea"],
  livestock: ["dairy", "goat", "poultry", "cattle", "milk"], retail: ["kirana", "grocery", "retail", "general store"],
  repair: ["repair", "mobile", "electronics repair"], beauty: ["beauty", "parlour", "salon"],
};
export const DEMAND_POINTS: Record<Saturation, number> = { low: 20, medium: 12, high: 4, unknown: 10 };
export const SYNTHETIC_WEIGHT = 0.3;
export const DISTRICT_BONUS = 2;
export const PRIOR_STRENGTH = 10;
export const PRIOR_BOUNDS: [number, number] = [0.9, 1.1];

/** Small duplicate of outcome_learning_loop.category_prior (C3 owns the full module). */
export function categoryPriorMultiplier(activityId: string, districtId: string | null, records: OutcomeRecord[] = outcomeSeed()): number {
  const rows = records.filter((r) => r.catalog_id === activityId);
  if (!rows.length) return 1;
  const weight = (r: OutcomeRecord) => (r.is_synthetic ? SYNTHETIC_WEIGHT : 1) * (districtId && r.district && r.district.toLowerCase() === districtId.toLowerCase() ? DISTRICT_BONUS : 1);
  const total = rows.reduce((s, r) => s + weight(r), 0);
  const improved = rows.reduce((s, r) => s + weight(r) * (r.health_after > r.health_before ? 1 : 0), 0);
  const rate = (improved + PRIOR_STRENGTH * 0.5) / (total + PRIOR_STRENGTH);
  return round(Math.max(PRIOR_BOUNDS[0], Math.min(PRIOR_BOUNDS[1], 1 + 0.2 * (rate - 0.5))), 3);
}

export function repaymentPoints(dscr: number | null): number {
  if (dscr === null || !Number.isFinite(dscr)) return dscr === Infinity ? 30 : 0;
  const lerp = (x: number, x0: number, x1: number, y0: number, y1: number) => y0 + ((Math.min(Math.max(x, x0), x1) - x0) / (x1 - x0)) * (y1 - y0);
  const band = coverageBand(dscr);
  return round(band === "does_not_cover" ? lerp(dscr, 0.5, 1, 0, 10) : band === "thin" ? lerp(dscr, 1, 1.25, 10, 20) : lerp(dscr, 1.25, 1.75, 20, 30), 1);
}

export function skillPoints(skills: string[], activity: CatalogActivity): number {
  if (!skills.length) return 0;
  const text = [activity.id.replace(/_/g, " "), ...activity.keywords].join(" | ");
  if (skills.some((s) => (SKILL_KEYWORDS[s] ?? [s]).some((k) => keywordIn(k, text)))) return 20;
  if (skills.some((s) => (SKILL_SECTORS[s] ?? []).includes(activity.sector))) return 12;
  return 4;
}

const competitorCache = new Map<string, CompetitorIntel>();
/** competitorIntel memoised per activity × location (the pack is static). */
export function cachedCompetitor(activity: CatalogActivity, location: LocationCandidate | null): CompetitorIntel {
  const key = `${activity.id}|${location ? `${location.district.id}|${location.lgd}|${location.lat},${location.lon}|${location.method}` : "-"}`;
  let hit = competitorCache.get(key);
  if (!hit) competitorCache.set(key, (hit = competitorIntel(activity, location)));
  return hit;
}

/** Most recent rejected activity this one is adjacent to (catalog list first, then same sector). */
function adjacentSource(activity: CatalogActivity, rejected: string[]): { id: string; weight: number } | null {
  const rej = [...rejected].reverse().map(catalogActivity).filter((a): a is CatalogActivity => !!a);
  const listed = rej.find((r) => r.adjacent.includes(activity.id));
  if (listed) return { id: listed.id, weight: 1 };
  const sector = rej.find((r) => r.sector === activity.sector);
  return sector ? { id: sector.id, weight: 0.7 } : null;
}

export function rankActivities(input: ProfileInput, location: LocationCandidate | null, opts: { rejected?: string[]; adjacentTo?: string | null } = {}): RankedActivity[] {
  const rejected = opts.rejected ?? [];
  const history = rejected.length > 0;
  const affordable = affordableProjectCost(input.capital);
  const plan = buildPlan(input.capital);
  const districtId = location?.district.id ?? null;

  const rows = catalogActivities().filter((a) => !rejected.includes(a.id)).map((a) => {
    const preview = previewDebtService(input.capital, a);
    let infeasibleReason = null;
    if (input.capital <= 0) infeasibleReason = msg("c2.infeasible.noCapital");
    else if (!plan.eligible) infeasibleReason = msg("c2.infeasible.outsideScheme", { project: plan.projectCost });
    else if (a.min_project_cost > affordable) infeasibleReason = msg("c2.infeasible.projectMin", { need: a.min_project_cost, have: affordable });
    const feasible = infeasibleReason === null;
    const comp = cachedCompetitor(a, location);
    const prior = categoryPriorMultiplier(a.id, districtId);
    const breakdown = {
      capitalFit: feasible ? round(20 * (1 - (0.5 * a.min_project_cost) / affordable), 1) : 0,
      repayment: repaymentPoints(preview.baseDscr),
      skills: skillPoints(input.skills, a),
      localDemand: DEMAND_POINTS[comp.saturation],
      outcomes: round(((prior - PRIOR_BOUNDS[0]) / (PRIOR_BOUNDS[1] - PRIOR_BOUNDS[0])) * 10, 1),
    };
    const score = round(Object.values(breakdown).reduce((s, v) => s + v, 0), 1);
    const adj = history ? adjacentSource(a, opts.adjacentTo ? [...rejected.filter((r) => r !== opts.adjacentTo), opts.adjacentTo] : rejected) : null;
    const ranked: RankedActivity = {
      activityId: a.id, score, breakdown, feasible, infeasibleReason, isPreference: input.activityId === a.id,
      adjacentTo: adj?.id ?? null, preview, crowding: comp.saturation,
    };
    return { ranked, adjacency: adj?.weight ?? 0 };
  });
  rows.sort((x, y) =>
    Number(y.ranked.feasible) - Number(x.ranked.feasible)
    || Number(y.ranked.isPreference && !history) - Number(x.ranked.isPreference && !history)
    || (history ? y.adjacency - x.adjacency : 0)
    || y.ranked.score - x.ranked.score
    || x.ranked.activityId.localeCompare(y.ranked.activityId));
  return rows.map((r) => r.ranked);
}
