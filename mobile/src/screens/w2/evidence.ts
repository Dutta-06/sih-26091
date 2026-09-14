/**
 * Local evidence (TDD 5.6): bundled pack feedback for the district/activity plus the observations submitted on this phone,
 * each linked to where the on-device analyses reference it. Option lists for the survey form are UI constants.
 */
import { feedbackSignal } from "../../core/intel/opportunity";
import { feedback } from "../../core/pack";
import type { Intel, Level, PackFeedback, Saturation } from "../../core/types";
import type { Observation } from "../../state/store";

export type EvidenceTopic = PackFeedback["topic"];
export const FEEDBACK_TOPICS: EvidenceTopic[] = ["demand", "pricing", "supply", "seasonality", "competition"];
export const FEEDBACK_PRESETS: Record<EvidenceTopic, string[]> = {
  demand: ["demandSteady", "demandMore"],
  pricing: ["priceLow", "priceOk"],
  supply: ["supplyLate", "supplyOk"],
  seasonality: ["seasonDip", "seasonPeak"],
  competition: ["compMany", "compFew"],
  other: [],
};
export const SURVEY_QUESTIONS: { id: string; multi: boolean; options: string[] }[] = [
  { id: "missing", multi: true, options: ["tailoring", "beauty", "mobile", "flour", "medical", "dairy"] },
  { id: "where", multi: false, options: ["village", "town", "city", "readymade"] },
  { id: "price", multi: false, options: ["p80", "p120", "p180", "p250"] },
  { id: "months", multi: true, options: ["marapr", "junjul", "octnov", "decfeb"] },
];

/* ------------------------------------------------------------------ Stored observation payloads */

export interface SurveyAnswers {
  answers: Record<string, string[]>;
  note?: string;
  voice: boolean;
  district: string | null;
  activityId: string | null;
}
export interface FeedbackAnswer {
  rating: number;
  preset: string | null;
  note: string;
  voice: boolean;
  district: string | null;
  activityId: string | null;
}

function parse<T>(o: Observation, ok: (v: T) => boolean): T | null {
  try {
    const v = JSON.parse(o.text) as T;
    return v && ok(v) ? v : null;
  } catch {
    return null;
  }
}
export const parseSurvey = (o: Observation) => parse<SurveyAnswers>(o, (v) => typeof v.answers === "object");
export const parseFeedback = (o: Observation) => parse<FeedbackAnswer>(o, (v) => typeof v.rating === "number");
export const observationDistrict = (o: Observation) => (o.kind === "resident_survey" ? parseSurvey(o)?.district : parseFeedback(o)?.district) ?? null;

/** Analysis a submission would feed, mirroring the pack pipeline: seasonality → risk, demand/competition → opportunity. */
export function observationUse(o: Observation): "opportunity" | "risk" | "pricing" | "supply" {
  if (o.kind === "resident_survey") return "opportunity";
  const topic = o.topic as EvidenceTopic;
  return topic === "seasonality" ? "risk" : topic === "pricing" ? "pricing" : topic === "supply" ? "supply" : "opportunity";
}

/* ------------------------------------------------------------------ Linking pack feedback to the analyses */

export type EvidenceUse =
  | { kind: "niche"; label: string; saturation: Saturation }
  | { kind: "risk"; severity: Level }
  | { kind: "signal"; saturation: "low" | "high" };

export interface PackEvidence {
  record: PackFeedback;
  uses: EvidenceUse[];
}

export function evidenceFor(district: string | null, activityId: string | null, intel: Intel | null, observations: Observation[]) {
  const rows = district ? feedback(district, activityId) : [];
  const pack: PackEvidence[] = rows.map((record) => {
    const uses: EvidenceUse[] = [];
    for (const n of intel?.opportunity.niches ?? []) if (n.evidenceIds.includes(record.id)) uses.push({ kind: "niche", label: n.name, saturation: n.saturation });
    const flag = intel?.risk.flags.find((f) => f.id === `local_feedback:${record.id}`);
    if (flag) uses.push({ kind: "risk", severity: flag.severity });
    const signal = feedbackSignal(`${record.topic}: ${record.text.en}`);
    if (signal === "low" || signal === "high") uses.push({ kind: "signal", saturation: signal });
    return { record, uses };
  });
  const mine = observations.filter((o) => {
    const d = observationDistrict(o);
    return d === null || d === district;
  });
  return { pack, mine, usedCount: pack.filter((p) => p.uses.length).length };
}

/* ------------------------------------------------------------------ Tallies (Survey) */

/** Grouped totals over pack feedback for the district and this phone's submissions (no individual answers shown). */
export function tallies(district: string | null, observations: Observation[]) {
  const rows = district ? feedback(district, null) : [];
  const byTopic = new Map<string, { n: number; ratings: number[] }>();
  for (const r of rows) {
    const e = byTopic.get(r.topic) ?? { n: 0, ratings: [] };
    e.n += 1;
    if (r.rating !== null) e.ratings.push(r.rating);
    byTopic.set(r.topic, e);
  }
  const mine = observations.filter((o) => observationDistrict(o) === district);
  for (const o of mine) {
    const f = o.kind === "funded_entrepreneur" ? parseFeedback(o) : null;
    if (!f) continue;
    const e = byTopic.get(o.topic) ?? { n: 0, ratings: [] };
    e.n += 1;
    e.ratings.push(f.rating);
    byTopic.set(o.topic, e);
  }
  const topics = [...byTopic].map(([topic, e]) => ({ topic, n: e.n, avg: e.ratings.length ? e.ratings.reduce((s, v) => s + v, 0) / e.ratings.length : null })).sort((a, b) => b.n - a.n);
  const surveys = mine.map(parseSurvey).filter((s): s is SurveyAnswers => !!s);
  const options = SURVEY_QUESTIONS.map((q) => ({
    id: q.id,
    counts: q.options.map((opt) => ({ opt, n: surveys.filter((s) => (s.answers[q.id] ?? []).includes(opt)).length })),
    respondents: surveys.filter((s) => (s.answers[q.id] ?? []).length).length,
  }));
  return {
    packCount: rows.length,
    funded: rows.filter((r) => r.kind === "funded_entrepreneur").length + mine.filter((o) => o.kind === "funded_entrepreneur").length,
    residents: rows.filter((r) => r.kind === "resident_survey").length + surveys.length,
    topics,
    options,
    mineCount: mine.length,
  };
}
