/**
 * Outcome learning (port of module3_monitoring/outcome_learning_loop.py) over the bundled synthetic seed plus
 * genuine records kept on the device.
 *
 * category_prior: weight = (1 real | 0.3 synthetic) × (2 when same district);
 *   rate = (Σ w·improved + 10 × 0.5) / (Σ w + 10); multiplier = clamp(1 + 0.2 (rate − 0.5), 0.9, 1.1).
 * interventionOptions (on-device addition, same weighting): per intervention type
 *   successRate = (Σ w·improved + 2 × 0.5) / (Σ w + 2), bounded to [0.1, 0.9]. The lighter shrinkage (2 instead
 *   of 10) lets six synthetic seed records (Σ w = 1.8) move the rate while a handful still cannot reach the bounds.
 */
import { outcomeSeed } from "./pack";
import type { InterventionOption, OutcomeRecord } from "./types";

export const SYNTHETIC_WEIGHT = 0.3;
export const DISTRICT_BONUS = 2.0;
export const PRIOR_STRENGTH = 10.0;
export const PRIOR_BOUNDS = [0.9, 1.1] as const;
export const OPTION_PRIOR_STRENGTH = 2.0;
export const OPTION_BOUNDS = [0.1, 0.9] as const;
export const INTERVENTIONS: OutcomeRecord["intervention_type"][] = ["pricing_adjustment", "supply_chain_change", "mentor_outreach", "repayment_counselling"];

export interface CategoryPrior {
  realRecords: number;
  syntheticRecords: number;
  isSyntheticDominant: boolean;
  prior: number;
  rate: number | null;
}

const improved = (r: OutcomeRecord) => (r.health_before == null || r.health_after == null ? null : r.health_after > r.health_before ? 1 : 0);

function recordsFor(activityId: string, realRecords: OutcomeRecord[]): OutcomeRecord[] {
  return [...outcomeSeed(), ...realRecords].filter((r) => r.catalog_id === activityId && improved(r) !== null);
}

function weigher(district: string | null) {
  return (r: OutcomeRecord) => {
    const same = !!district && !!r.district && r.district.toLowerCase() === district.toLowerCase();
    return (r.is_synthetic ? SYNTHETIC_WEIGHT : 1) * (same ? DISTRICT_BONUS : 1);
  };
}

export function categoryPrior(activityId: string, district: string | null, realRecords: OutcomeRecord[]): CategoryPrior {
  const records = activityId ? recordsFor(activityId, realRecords) : [];
  const real = records.filter((r) => !r.is_synthetic).length;
  if (!records.length) return { realRecords: 0, syntheticRecords: 0, isSyntheticDominant: false, prior: 1, rate: null };
  const w = weigher(district);
  const total = records.reduce((a, r) => a + w(r), 0);
  const rate = (records.reduce((a, r) => a + w(r) * improved(r)!, 0) + PRIOR_STRENGTH * 0.5) / (total + PRIOR_STRENGTH);
  const prior = Math.round(Math.max(PRIOR_BOUNDS[0], Math.min(PRIOR_BOUNDS[1], 1 + 0.2 * (rate - 0.5))) * 1000) / 1000;
  const synthW = records.filter((r) => r.is_synthetic).reduce((a, r) => a + w(r), 0);
  return { realRecords: real, syntheticRecords: records.length - real, isSyntheticDominant: synthW >= total - synthW, prior, rate };
}

/** Success rate per intervention type for the activity (district-weighted), best first. */
export function interventionOptions(activityId: string, district: string | null, realRecords: OutcomeRecord[]): InterventionOption[] {
  const records = recordsFor(activityId, realRecords);
  const w = weigher(district);
  return INTERVENTIONS.map((type) => {
    const rs = records.filter((r) => r.intervention_type === type);
    const total = rs.reduce((a, r) => a + w(r), 0);
    const rate = (rs.reduce((a, r) => a + w(r) * improved(r)!, 0) + OPTION_PRIOR_STRENGTH * 0.5) / (total + OPTION_PRIOR_STRENGTH);
    const real = rs.filter((r) => !r.is_synthetic).length;
    return {
      type,
      successRate: Math.round(Math.max(OPTION_BOUNDS[0], Math.min(OPTION_BOUNDS[1], rate)) * 1000) / 1000,
      real,
      synthetic: rs.length - real,
      improved: rs.filter((r) => improved(r) === 1).length,
      total: rs.length,
    };
  }).sort((a, b) => b.successRate - a.successRate || INTERVENTIONS.indexOf(a.type) - INTERVENTIONS.indexOf(b.type));
}
