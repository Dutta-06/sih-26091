/**
 * Lender (SCA) portfolio view over a deterministic SYNTHETIC applicant cohort generated from the sample data pack.
 * There is no cross-case server on the phone, so the dashboard runs a seeded cohort through the same on-device
 * pipeline (`computeCase`) the entrepreneur sees and aggregates the results. Nothing here is a typed-in figure.
 *
 * Cohort generation (seeded, mulberry32):
 *  - district: uniform over pack districts that have villages; village: uniform within the district.
 *  - activity preference: weighted by the district's Udyam count for the activity's NIC class (the pack's cluster
 *    signal — e.g. carpet weaving dominates Bhadohi), +1 so every catalog activity stays possible.
 *  - own capital: log-uniform between COHORT_CAPITAL_RANGE (₹3,000 – ₹2,00,000), rounded to ₹500.
 *  - skills: the catalog skills whose sector matches the preferred activity, each kept with probability 1/2.
 *  - premises / category / woman-owned / SHG: uniform picks.
 *  - stage: every applicant with a viable option is treated as sanctioned; DISBURSED_SHARE of them were disbursed
 *    1–12 months before `today` with SMS consent, and half of those phones see the monsoon-disruption inbox.
 *
 * Outcome classes: viable (first choice passed review), redirected (first choice rejected or unaffordable but an
 * alternative is viable), no option (nothing viable / profiling blocked).
 */
import { SKILL_SECTORS } from "./discovery";
import { catalogEntry } from "./financial";
import { districts, udyam, villages } from "./pack";
import { computeCase, type SessionInputs } from "./session";
import { prng } from "./sms";
import type { ProfileInput } from "./types";
import catalog from "../../../data/reference/business_catalog.json";

export const COHORT_SIZE = 80;
export const COHORT_SEED = 26091;
export const COHORT_CAPITAL_RANGE = [3_000, 200_000] as const;
/** Share of sanctioned applicants simulated as already disbursed and monitored. */
export const DISBURSED_SHARE = 0.6;

export interface CohortApplicant {
  id: string;
  districtId: string;
  profile: ProfileInput;
  /** months between disbursal and today when disbursed, else null */
  disbursedMonthsAgo: number | null;
  inbox: SessionInputs["inbox"];
}

export type ApplicantClass = "viable" | "redirected" | "no_option";

export interface ApplicantResult {
  id: string;
  districtId: string;
  preferred: string;
  selected: string | null;
  cls: ApplicantClass;
  loan: number; // sanctioned loan (0 when no option or outside scheme)
  coverage: number | null; // base DSCR of the selected plan
  disbursed: boolean;
  monitoredMonths: number;
  warned: boolean;
  latestScore: number | null;
  /** lowest monthly health score among complete monitored months */
  worstScore: number | null;
}

export interface PortfolioMetrics {
  total: number;
  byClass: Record<ApplicantClass, number>;
  districts: { id: string; total: number; viable: number; redirected: number; noOption: number; loan: number }[];
  loanVolume: number;
  avgCoverage: number | null;
  disbursed: number;
  monitored: number;
  warned: number;
  warningRate: number | null;
  avgHealth: number | null;
  flagged: ApplicantResult[];
}

const ACTIVITY_IDS = (catalog.activities as { id: string }[]).map((a) => a.id);
const SKILLS = Object.keys(SKILL_SECTORS);
const PREMISES: NonNullable<ProfileInput["premises"]>[] = ["home", "rented_shop", "own_land"];
const CATEGORIES: NonNullable<ProfileInput["category"]>[] = ["sc", "st", "obc", "general"];

const pick = <T>(rnd: () => number, xs: T[]): T => xs[Math.floor(rnd() * xs.length)];

function weightedPick(rnd: () => number, items: [string, number][]): string {
  const total = items.reduce((a, [, w]) => a + w, 0);
  let r = rnd() * total;
  for (const [id, w] of items) {
    r -= w;
    if (r < 0) return id;
  }
  return items[items.length - 1][0];
}

export function generateCohort(n = COHORT_SIZE, seed = COHORT_SEED): CohortApplicant[] {
  const rnd = prng(seed);
  const vs = villages();
  const ds = districts().filter((d) => vs.some((v) => v.district === d.id));
  const weightsFor = new Map<string, [string, number][]>();
  const out: CohortApplicant[] = [];
  for (let i = 0; i < n; i++) {
    const d = pick(rnd, ds);
    if (!weightsFor.has(d.id)) {
      weightsFor.set(d.id, ACTIVITY_IDS.map((id) => [id, (udyam(d.id, catalogEntry(id).nic_class) ?? 0) + 1]));
    }
    const village = pick(rnd, vs.filter((v) => v.district === d.id));
    const activityId = weightedPick(rnd, weightsFor.get(d.id)!);
    const [lo, hi] = COHORT_CAPITAL_RANGE;
    const capital = Math.round(Math.exp(Math.log(lo) + rnd() * (Math.log(hi) - Math.log(lo))) / 500) * 500;
    const sector = catalogEntry(activityId).sector;
    const skills = SKILLS.filter((s) => SKILL_SECTORS[s].includes(sector) && rnd() < 0.5);
    const disbursed = rnd() < DISBURSED_SHARE;
    out.push({
      id: `A${String(i + 1).padStart(3, "0")}`,
      districtId: d.id,
      profile: {
        capital,
        locationText: `${village.name.en}, ${d.name.en}`,
        locationCode: village.lgd,
        activityId,
        reason: null,
        skills,
        assets: [],
        premises: pick(rnd, PREMISES),
        category: pick(rnd, CATEGORIES),
        womanOwned: rnd() < 0.5,
        shgMember: rnd() < 0.5,
      },
      disbursedMonthsAgo: disbursed ? 1 + Math.floor(rnd() * 12) : null,
      inbox: rnd() < 0.5 ? "typical" : "monsoon_disruption",
    });
  }
  return out;
}

function isoMonthsBefore(today: string, months: number): string {
  const d = new Date(`${today.slice(0, 10)}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() - months);
  return d.toISOString().slice(0, 10);
}

/**
 * Snapshots for calendar months that have ended by `today`. The month in progress holds only part of a month's
 * sales against a full-month plan baseline, so scoring it would raise a false early warning.
 */
export function completedMonths<T extends { month: string }>(health: T[], today: string): T[] {
  const d = new Date(`${today.slice(0, 10)}T00:00:00Z`);
  const lastDay = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
  const current = today.slice(0, 7);
  return d.getUTCDate() === lastDay ? health : health.filter((h) => h.month < current);
}

/** Run one applicant through the on-device pipeline. */
export function evaluateApplicant(a: CohortApplicant, today: string): ApplicantResult {
  const base: SessionInputs = {
    profile: a.profile, chosenActivity: null, appStage: "not_started", documents: {}, disbursedOn: null, smsConsent: false,
    inbox: a.inbox, dataDeletedOn: null, interventionChosen: null, realOutcomes: [], grievances: [], today: today.slice(0, 10),
  };
  const first = computeCase(base);
  const selected = first.feasibility.selected?.activityId ?? null;
  const cls: ApplicantClass = !selected ? "no_option" : selected === a.profile.activityId ? "viable" : "redirected";
  const plan = first.financial?.plan;
  const loan = selected && plan?.eligible ? plan.loan : 0;
  const coverage = selected ? first.financial?.preview.baseDscr ?? null : null;
  let disbursed = false;
  let monitoredMonths = 0;
  let warned = false;
  let latestScore: number | null = null;
  let worstScore: number | null = null;
  if (selected && loan > 0 && a.disbursedMonthsAgo !== null) {
    disbursed = true;
    const v = computeCase({ ...base, chosenActivity: selected, appStage: "disbursed", disbursedOn: isoMonthsBefore(today, a.disbursedMonthsAgo), smsConsent: true });
    const done = completedMonths(v.health, today);
    monitoredMonths = done.length;
    warned = done.some((h) => h.earlyWarning);
    latestScore = done.at(-1)?.score ?? null;
    const scores = done.map((h) => h.score).filter((x): x is number => x !== null);
    worstScore = scores.length ? Math.min(...scores) : null;
  }
  return { id: a.id, districtId: a.districtId, preferred: a.profile.activityId!, selected, cls, loan, coverage, disbursed, monitoredMonths, warned, latestScore, worstScore };
}

const mean = (xs: number[]) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null);

export function summarize(results: ApplicantResult[]): PortfolioMetrics {
  const byClass: Record<ApplicantClass, number> = { viable: 0, redirected: 0, no_option: 0 };
  const dist = new Map<string, PortfolioMetrics["districts"][number]>();
  for (const r of results) {
    byClass[r.cls]++;
    const d = dist.get(r.districtId) ?? { id: r.districtId, total: 0, viable: 0, redirected: 0, noOption: 0, loan: 0 };
    d.total++;
    if (r.cls === "viable") d.viable++;
    else if (r.cls === "redirected") d.redirected++;
    else d.noOption++;
    d.loan += r.loan;
    dist.set(r.districtId, d);
  }
  const monitored = results.filter((r) => r.monitoredMonths > 0);
  const warned = monitored.filter((r) => r.warned);
  const coverages = results.map((r) => r.coverage).filter((c): c is number => c !== null && Number.isFinite(c));
  const scores = monitored.map((r) => r.latestScore).filter((s): s is number => s !== null);
  return {
    total: results.length,
    byClass,
    districts: [...dist.values()].sort((a, b) => b.total - a.total || a.id.localeCompare(b.id)),
    loanVolume: results.reduce((s, r) => s + r.loan, 0),
    avgCoverage: mean(coverages),
    disbursed: results.filter((r) => r.disbursed).length,
    monitored: monitored.length,
    warned: warned.length,
    warningRate: monitored.length ? warned.length / monitored.length : null,
    avgHealth: mean(scores),
    flagged: [...warned].sort((a, b) => (a.worstScore ?? 101) - (b.worstScore ?? 101) || a.id.localeCompare(b.id)),
  };
}

const cache = new Map<string, PortfolioMetrics>();

/** Synchronous full computation (tests, or callers that don't mind blocking). */
export function computePortfolio(today: string, n = COHORT_SIZE, seed = COHORT_SEED): PortfolioMetrics {
  const key = `${today.slice(0, 7)}|${n}|${seed}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const m = summarize(generateCohort(n, seed).map((a) => evaluateApplicant(a, today)));
  cache.set(key, m);
  return m;
}

export const cachedPortfolio = (today: string, n = COHORT_SIZE, seed = COHORT_SEED) => cache.get(`${today.slice(0, 7)}|${n}|${seed}`) ?? null;

/**
 * Computes in small chunks on timers so the UI stays responsive; calls onProgress(done, total) and resolves
 * with the metrics. `signal.cancelled` stops early.
 */
export function computePortfolioChunked(
  today: string,
  onProgress?: (done: number, total: number) => void,
  signal: { cancelled: boolean } = { cancelled: false },
  n = COHORT_SIZE,
  seed = COHORT_SEED,
): Promise<PortfolioMetrics | null> {
  const hit = cachedPortfolio(today, n, seed);
  if (hit) return Promise.resolve(hit);
  const cohort = generateCohort(n, seed);
  const results: ApplicantResult[] = [];
  return new Promise((resolve) => {
    const step = () => {
      if (signal.cancelled) return resolve(null);
      const end = Math.min(cohort.length, results.length + 4);
      for (let i = results.length; i < end; i++) results.push(evaluateApplicant(cohort[i], today));
      onProgress?.(results.length, cohort.length);
      if (results.length < cohort.length) setTimeout(step, 0);
      else {
        const m = summarize(results);
        cache.set(`${today.slice(0, 7)}|${n}|${seed}`, m);
        resolve(m);
      }
    };
    setTimeout(step, 0);
  });
}
