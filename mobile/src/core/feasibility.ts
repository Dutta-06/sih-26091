/**
 * Feasibility loop (TDD 5.3–5.5): profiling constraint → discovery → six intel analyses → SWOT → red-team review,
 * with a bounded rejection loop (settings.max_feasibility_attempts = 3).
 *
 * Decisions (documented):
 *  - Profiling constraint: capital ≤ 0, or a project (capital ÷ 10%) above the Rs 50 lakh scheme ceiling, is not a
 *    business rejection — no attempt is run; `constraints` explains why and `exhausted` stays false (nothing was
 *    evaluated). The shortlist is still returned with every option marked infeasible.
 *  - Attempt order: the stated preference first when it is feasible; after a non-viable verdict the activity is
 *    excluded and discovery re-ranks with adjacency to the latest rejection outranking score.
 *  - `exhausted` is true when no attempt was viable (no feasible activity left, or the attempt bound was reached).
 */
import { previewDebtService } from "../engine/finance";
import { cachedCompetitor, rankActivities } from "./discovery";
import { catalogActivity, MAX_ATTEMPTS, msg, SCHEME_MAX_PROJECT_COST, MARGIN_SHARE } from "./intel/catalog";
import { marketReach } from "./intel/marketReach";
import { opportunityIntel } from "./intel/opportunity";
import { pricingIntel } from "./intel/pricing";
import { riskIntel } from "./intel/risk";
import { supplyChainIntel } from "./intel/supplyChain";
import { evaluate } from "./review";
import { buildSwot, crossCheckSaturation } from "./swot";
import type { FeasibilityAttempt, FeasibilityResult, Intel, LocationCandidate, Msg, ProfileInput } from "./types";

/** FeasibilityResult plus the profiling constraints that stopped the loop before any attempt (optional extension). */
export interface FeasibilityOutcome extends FeasibilityResult {
  constraints: Msg[];
}

export function runIntel(activityId: string, input: ProfileInput, location: LocationCandidate | null): Intel {
  const activity = catalogActivity(activityId);
  if (!activity) throw new Error(`Unknown activity ${activityId}`);
  const competitor = cachedCompetitor(activity, location);
  const opportunity = opportunityIntel(activity, location);
  const { niches, notes } = crossCheckSaturation(opportunity.niches, competitor);
  return {
    marketReach: marketReach(location, activity.sector),
    // After the cross-check the opportunity as a whole takes the observed competitor crowding.
    opportunity: { ...opportunity, niches, saturation: competitor.saturation !== "unknown" ? competitor.saturation : opportunity.saturation, limitations: [...opportunity.limitations, ...notes] },
    competitor,
    pricing: pricingIntel(activity, location),
    risk: riskIntel(activity, location, input.reason),
    supplyChain: supplyChainIntel(activity, location),
  };
}

export function profilingConstraints(input: ProfileInput, location: LocationCandidate | null): { blocking: Msg[]; info: Msg[] } {
  const blocking: Msg[] = [];
  const info: Msg[] = [];
  if (input.capital <= 0) blocking.push(msg("c2.constraint.noCapital"));
  else if (input.capital / MARGIN_SHARE > SCHEME_MAX_PROJECT_COST) {
    blocking.push(msg("c2.constraint.aboveScheme", { capital: input.capital, project: input.capital / MARGIN_SHARE, max: SCHEME_MAX_PROJECT_COST }));
  }
  const pref = input.activityId ? catalogActivity(input.activityId) : null;
  if (pref && input.capital > 0 && pref.min_project_cost > Math.min(input.capital / MARGIN_SHARE, SCHEME_MAX_PROJECT_COST)) {
    info.push(msg("c2.constraint.preferenceUnaffordable", { activity: pref.id, need: pref.min_project_cost }));
  }
  if (!location) info.push(msg("c2.constraint.noLocation"));
  return { blocking, info };
}

export function runFeasibility(input: ProfileInput, location: LocationCandidate | null, maxAttempts = MAX_ATTEMPTS): FeasibilityOutcome {
  const shortlist = rankActivities(input, location);
  const { blocking, info } = profilingConstraints(input, location);
  if (blocking.length) return { attempts: [], selected: null, exhausted: false, shortlist, constraints: [...blocking, ...info] };

  const attempts: FeasibilityAttempt[] = [];
  const rejected: string[] = [];
  let selected: FeasibilityAttempt | null = null;
  while (attempts.length < maxAttempts) {
    const ranked = attempts.length === 0 ? shortlist : rankActivities(input, location, { rejected, adjacentTo: rejected[rejected.length - 1] ?? null });
    const next = ranked.find((r) => r.feasible && !rejected.includes(r.activityId));
    if (!next) break;
    const activity = catalogActivity(next.activityId)!;
    const intel = runIntel(activity.id, input, location);
    const preview = previewDebtService(input.capital, activity);
    const review = evaluate(input.capital, activity, intel, preview);
    const swot = buildSwot(intel, input.capital, activity);
    const notes: Msg[] = [...review.notes, swot.budgetNote];
    if (next.adjacentTo) notes.push(msg("c2.feas.adjacentTo", { activity: activity.id, rejected: next.adjacentTo }));
    const attempt: FeasibilityAttempt = {
      activityId: activity.id, intel, verdict: review.verdict, findings: review.findings, notes, preview, score: next.score,
      swot: { strengths: swot.strengths, weaknesses: swot.weaknesses, opportunities: swot.opportunities, threats: swot.threats },
    };
    attempts.push(attempt);
    if (review.verdict === "viable") {
      selected = attempt;
      break;
    }
    rejected.push(activity.id);
  }
  return { attempts, selected, exhausted: selected === null, shortlist, constraints: info };
}
