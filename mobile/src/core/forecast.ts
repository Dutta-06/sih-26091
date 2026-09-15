/**
 * Cash-flow forecast learned from the business's own finished months (TDD Module 3, predictive monitoring).
 *
 * Model: sales = plan(month) × level × noise, with log-normal noise.
 *  - plan(month) is the plan's base revenue × days/365 × seasonal factor (the same baseline the health score uses).
 *  - level is a recency-weighted average of actual/plan ratios (weight 0.6^age), shrunk toward 1 (the plan) with a
 *    prior worth PRIOR_MONTHS months, so one bad month moves it but does not define it.
 *  - noise σ is the recency-weighted spread of log ratios around the level, shrunk toward PRIOR_SIGMA.
 *  - expenses follow the same scheme around the plan's expense share; surplus = sales − expenses.
 * Intervals are 80% (±1.2816σ, widening with the horizon). The chance of covering the next instalment uses a normal
 * approximation of the quarter's cash surplus (finished months actual, remaining months forecast).
 * One-off receipts flagged by the unusual-activity check (large_credit) are taken out of sales before learning.
 * Accuracy is back-tested: each finished month from the third on is predicted from the months before it.
 */
import { catalogEntry } from "./financial";
import type { MonthlyHealth } from "./health";
import type { FinancialResult, Intel, Msg } from "./types";

export interface ForecastMonth {
  month: string; // YYYY-MM
  sales: number;
  low: number;
  high: number;
  planned: number;
  expenses: number;
  surplus: number;
  surplusSd: number;
}

export interface InstallmentOutlook {
  month: string; // month the instalment is debited
  amount: number;
  /** Expected cash surplus over that repayment quarter (actual + forecast). */
  expectedSurplus: number;
  /** Probability (0-1) the quarter's surplus covers the instalment. */
  chance: number;
}

export interface Forecast {
  basedOn: number; // finished months used
  level: number; // learned sales as a share of plan
  sigma: number;
  months: ForecastMonth[];
  installment: InstallmentOutlook | null;
  /** Mean absolute percentage error of back-tested one-month-ahead forecasts (null under 2 tests). */
  backtestError: number | null;
  backtests: number;
  reasons: Msg[];
}

const PRIOR_MONTHS = 2;
const PRIOR_SIGMA = 0.15;
const DECAY = 0.6;
const Z80 = 1.2816;
export const HORIZON = 3;

const r0 = (v: number) => Math.round(v);
const r2 = (v: number) => Math.round((v + Number.EPSILON) * 100) / 100;
const monthIndex = (ym: string) => +ym.slice(0, 4) * 12 + +ym.slice(5, 7) - 1;
const monthKey = (i: number) => `${Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, "0")}`;
const daysIn = (i: number) => new Date(Date.UTC(Math.floor(i / 12), (i % 12) + 1, 0)).getUTCDate();

/** Standard normal CDF (Abramowitz-Stegun 7.1.26 via erf). */
export function normalCdf(z: number): number {
  const t = 1 / (1 + 0.3275911 * Math.abs(z) / Math.SQRT2);
  const erf = 1 - (((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t) * Math.exp(-(z * z) / 2);
  return z >= 0 ? (1 + erf) / 2 : (1 - erf) / 2;
}

/** Recency-weighted mean and spread of log ratios, shrunk toward the prior (log 1 = 0, PRIOR_SIGMA). */
export function learnLevel(ratios: number[]): { level: number; sigma: number } {
  const logs = ratios.filter((r) => r > 0).map((r) => Math.log(r));
  const n = logs.length;
  let wSum = PRIOR_MONTHS;
  let mean = 0;
  logs.forEach((l, i) => {
    const w = DECAY ** (n - 1 - i);
    mean += w * l;
    wSum += w;
  });
  mean /= wSum;
  let sq = PRIOR_MONTHS * PRIOR_SIGMA ** 2;
  let sw = PRIOR_MONTHS;
  logs.forEach((l, i) => {
    const w = DECAY ** (n - 1 - i);
    sq += w * (l - mean) ** 2;
    sw += w;
  });
  return { level: Math.exp(mean), sigma: Math.sqrt(sq / sw) };
}

export interface ForecastContext {
  financial: FinancialResult;
  activityId: string;
  intel?: Intel | null;
  disbursedOn?: string | null;
  /** One-off receipts to leave out of sales, by YYYY-MM. */
  oneOff?: Record<string, number>;
}

function seasonalIndex(ctx: ForecastContext): number[] {
  const idx = ctx.intel?.risk.seasonalIndex;
  return idx && idx.length === 12 ? idx : catalogEntry(ctx.activityId).seasonal_profile;
}

const plannedFor = (annual: number, idx: number[], m: number) => ((annual * daysIn(m)) / 365) * idx[m % 12];

/** Forecast the months after the last finished month. `history` must be finished months in order. */
export function forecast(history: MonthlyHealth[], ctx: ForecastContext): Forecast | null {
  const annual = ctx.financial.preview.annualRevenue;
  if (!history.length || !annual) return null;
  const idx = seasonalIndex(ctx);
  const excluded = history.reduce((a, h) => a + Math.min(h.revenue, ctx.oneOff?.[h.month] ?? 0), 0);
  history = history.map((h) => (ctx.oneOff?.[h.month] ? { ...h, revenue: Math.max(0, h.revenue - ctx.oneOff[h.month]), surplus: h.surplus - Math.min(h.revenue, ctx.oneOff[h.month]) } : h));
  const margin = catalogEntry(ctx.activityId).operating_margin;
  const usable = history.filter((h) => h.planned > 0);
  const { level, sigma } = learnLevel(usable.map((h) => h.revenue / h.planned));
  const expenseShare = 1 - margin;
  const exp = learnLevel(usable.filter((h) => h.expenses > 0).map((h) => h.expenses / (h.planned * expenseShare)));

  const last = monthIndex(history[history.length - 1].month);
  const months: ForecastMonth[] = [];
  for (let h = 1; h <= HORIZON; h++) {
    const m = last + h;
    const planned = plannedFor(annual, idx, m);
    const spread = sigma * Math.sqrt(1 + 0.35 * (h - 1));
    const sales = planned * level * Math.exp(spread ** 2 / 2);
    const expenses = planned * expenseShare * exp.level;
    const salesSd = sales * Math.sqrt(Math.exp(spread ** 2) - 1);
    months.push({
      month: monthKey(m),
      sales: r0(sales),
      low: r0(planned * level * Math.exp(-Z80 * spread)),
      high: r0(planned * level * Math.exp(Z80 * spread)),
      planned: r0(planned),
      expenses: r0(expenses),
      surplus: r0(sales - expenses),
      surplusSd: r0(Math.hypot(salesSd, expenses * exp.sigma)),
    });
  }

  const backtest = backtestError(history);
  return {
    basedOn: history.length,
    level: r2(level),
    sigma: r2(sigma),
    months,
    installment: installmentOutlook(history, months, ctx),
    backtestError: backtest.error,
    backtests: backtest.n,
    reasons: [...explain(history, months, level, idx), ...(excluded > 0 ? [{ key: "c3.fc.reason.oneOff", vars: { amount: Math.round(excluded) } }] : [])],
  };
}

/** One-month-ahead back-test over finished months (predict month t from months before t). */
export function backtestError(history: MonthlyHealth[]): { error: number | null; n: number } {
  const errors: number[] = [];
  for (let t = 2; t < history.length; t++) {
    const actual = history[t].revenue;
    if (actual <= 0 || history[t].planned <= 0) continue;
    const past = history.slice(0, t).filter((h) => h.planned > 0);
    const { level, sigma } = learnLevel(past.map((h) => h.revenue / h.planned));
    const predicted = history[t].planned * level * Math.exp(sigma ** 2 / 2);
    errors.push(Math.abs(predicted - actual) / actual);
  }
  return { error: errors.length >= 2 ? r2(errors.reduce((a, b) => a + b, 0) / errors.length) : null, n: errors.length };
}

/**
 * Next loan debit inside the horizon: quarter n (counted from the disbursal month) is debited in its third month.
 * Covering it depends on the whole quarter's surplus; finished months count as known.
 */
function installmentOutlook(history: MonthlyHealth[], months: ForecastMonth[], ctx: ForecastContext): InstallmentOutlook | null {
  const plan = ctx.financial.plan;
  if (!plan.eligible || !plan.schedule.length) return null;
  const disb = ctx.disbursedOn ? monthIndex(ctx.disbursedOn.slice(0, 7)) : monthIndex(history[0].month);
  for (const f of months) {
    const m = monthIndex(f.month);
    const k = m - disb;
    if (k < 0 || k % 3 !== 2) continue;
    const entry = plan.schedule[Math.floor(k / 3)];
    if (!entry || entry.payment <= 0) return null;
    let mean = 0;
    let variance = 0;
    for (let q = m - 2; q <= m; q++) {
      const done = history.find((h) => monthIndex(h.month) === q);
      const ahead = months.find((x) => monthIndex(x.month) === q);
      if (done) mean += done.surplus;
      else if (ahead) {
        mean += ahead.surplus;
        variance += ahead.surplusSd ** 2;
      }
    }
    const sd = Math.sqrt(variance);
    const chance = sd > 0 ? normalCdf((mean - entry.payment) / sd) : mean >= entry.payment ? 1 : 0;
    return { month: f.month, amount: r0(entry.payment), expectedSurplus: r0(mean), chance: r2(Math.min(0.99, Math.max(0.01, chance))) };
  }
  return null;
}

function explain(history: MonthlyHealth[], months: ForecastMonth[], level: number, idx: number[]): Msg[] {
  const reasons: Msg[] = [{ key: "c3.fc.reason.level", vars: { pct: Math.round(level * 100), n: history.length } }];
  const recent = history.slice(-2);
  if (recent.length === 2 && recent[0].planned > 0 && recent[1].planned > 0) {
    const a = recent[0].revenue / recent[0].planned;
    const b = recent[1].revenue / recent[1].planned;
    if (b - a >= 0.12) reasons.push({ key: "c3.fc.reason.recovering", vars: { month: recent[1].month } });
    else if (a - b >= 0.12) reasons.push({ key: "c3.fc.reason.slipping", vars: { month: recent[1].month } });
  }
  const avg = idx.reduce((s, v) => s + v, 0) / 12;
  const peak = months.reduce((best, f) => (idx[monthIndex(f.month) % 12] > idx[monthIndex(best.month) % 12] ? f : best), months[0]);
  const low = months.reduce((w, f) => (idx[monthIndex(f.month) % 12] < idx[monthIndex(w.month) % 12] ? f : w), months[0]);
  const lowFactor = idx[monthIndex(low.month) % 12] / avg;
  const peakFactor = idx[monthIndex(peak.month) % 12] / avg;
  if (lowFactor <= 0.9) reasons.push({ key: "c3.fc.reason.lowSeason", vars: { month: low.month, pct: Math.round((1 - lowFactor) * 100) } });
  else if (peakFactor >= 1.1) reasons.push({ key: "c3.fc.reason.highSeason", vars: { month: peak.month, pct: Math.round((peakFactor - 1) * 100) } });
  if (history.length < 4) reasons.push({ key: "c3.fc.reason.fewMonths", vars: { n: history.length } });
  return reasons;
}
