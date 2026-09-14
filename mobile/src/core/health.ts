/**
 * Enterprise health from parsed transactions: port of module3_monitoring/ongoing_monitoring_agent.py
 * (period aggregation, pro-rata installment status, approximate creditworthiness index) and
 * health_score_agent.py (weighted components, bands, early warning, intervention_type), thresholds from
 * config/health_thresholds.json via the data pack.
 *
 * Approximate creditworthiness index (0-100, NOT a credit score), over calendar weeks of the period:
 *   100 * (0.4 * regularity + 0.3 * max(0, 1 - CV of weekly credits) + 0.3 * repayment factor); null under 2 weeks.
 */
import type { Plan } from "../engine/finance";
import { catalogEntry } from "./financial";
import { healthThresholds, type HealthThresholds } from "./pack";
import type { FinancialResult, HealthSnapshot, Intel, Msg, Transaction } from "./types";

export type InstallmentStatus = "paid" | "grace_period" | "overdue" | "not_due" | "unknown";

/** Mirror of the backend HealthSnapshot fields used by the scoring agent. */
export interface PeriodRecord {
  start: string; // YYYY-MM-DD
  end: string;
  days: number;
  transactionsParsed: number;
  revenue: number;
  baseline: number;
  expenses: number;
  surplus: number;
  installmentDue: number;
  status: InstallmentStatus;
  creditIndex: number | null;
}

export interface ScoredRecord extends PeriodRecord {
  score: number | null;
  band: HealthSnapshot["band"] | null;
  components: { revenueVsPlan: number | null; coverage: number | null; repayment: number | null };
  earlyWarning: boolean;
  reasons: Msg[];
  intervention: HealthSnapshot["intervention"];
}

/** Monthly snapshot; score/band are null when nothing could be measured against the plan (type widening). */
export type MonthlyHealth = Omit<HealthSnapshot, "score" | "band" | "components"> & {
  score: number | null;
  band: HealthSnapshot["band"] | null;
  components: ScoredRecord["components"];
  status: InstallmentStatus;
  installmentDue: number;
  reasons: Msg[];
  transactions: number;
};

const MIN_PERIOD_DAYS = 7;
const DAYS_PER_QUARTER = 91.25;
const REPAYMENT_FACTOR: Record<InstallmentStatus, number> = { paid: 1, not_due: 0.8, grace_period: 0.5, unknown: 0.5, overdue: 0 };
const r1 = (v: number) => Math.round((v + Number.EPSILON) * 10) / 10;
const r2 = (v: number) => Math.round((v + Number.EPSILON) * 100) / 100;
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

const dayNum = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 86_400_000;
const dayIso = (n: number) => new Date(n * 86_400_000).toISOString().slice(0, 10);
const monthOf = (n: number) => new Date(n * 86_400_000).getUTCMonth();
const validIso = (s: string | null | undefined) => !!s && /^\d{4}-\d{2}-\d{2}/.test(s);

export function creditworthinessIndex(credits: Transaction[], start: string, days: number, status: InstallmentStatus): number | null {
  const weeks = Math.ceil(days / 7);
  if (weeks < 2) return null;
  const totals = new Array<number>(weeks).fill(0);
  const s = dayNum(start);
  for (const t of credits) {
    if (!validIso(t.at)) continue;
    totals[Math.min(weeks - 1, Math.max(0, Math.floor((dayNum(t.at) - s) / 7)))] += t.amount;
  }
  const regularity = totals.filter((v) => v > 0).length / weeks;
  const mean = totals.reduce((a, b) => a + b, 0) / weeks;
  const cv = mean > 0 ? Math.sqrt(totals.reduce((a, v) => a + (v - mean) ** 2, 0) / weeks) / mean : Infinity;
  return r1(100 * (0.4 * regularity + 0.3 * Math.max(0, 1 - cv) + 0.3 * REPAYMENT_FACTOR[status]));
}

export interface MonitoringContext {
  plan: Plan;
  annualRevenue: number | null; // operating projection revenue (null → no baseline)
  seasonalIndex: number[] | null;
  disbursedOn: string | null; // YYYY-MM-DD
}

/** ongoing_monitoring_agent._installment */
export function installmentFor(plan: Plan, start: string, days: number, repaid: number, disbursedOn: string | null): [number, InstallmentStatus] {
  if (!plan.eligible) return [0, "unknown"];
  const scale = days / DAYS_PER_QUARTER;
  let entry = null;
  if (disbursedOn && plan.schedule.length) {
    const quarter = Math.floor((dayNum(start) - dayNum(disbursedOn)) / DAYS_PER_QUARTER) + 1;
    entry = plan.schedule.find((q) => q.quarter === quarter) ?? null;
  }
  let full = plan.regularInstallment || Math.max(0, ...plan.schedule.filter((q) => !q.isMoratorium).map((q) => q.payment));
  if (entry) full = entry.payment;
  const due = r2(full * scale);
  if (entry?.isMoratorium) return [due, "not_due"];
  if (full <= 0) return [0, "unknown"];
  if (repaid >= 0.95 * Math.min(full, due)) return [due, "paid"];
  if (days >= DAYS_PER_QUARTER) return [due, "overdue"];
  return [due, repaid > 0 ? "grace_period" : "unknown"];
}

function totals(txns: Transaction[]) {
  const credits = txns.filter((t) => t.direction === "credit" && !t.isLoanRepayment);
  const sum = (xs: Transaction[]) => xs.reduce((a, t) => a + t.amount, 0);
  return {
    credits,
    revenue: sum(credits),
    expenses: sum(txns.filter((t) => t.direction === "debit" && !t.isLoanRepayment)),
    repaid: sum(txns.filter((t) => t.direction === "debit" && t.isLoanRepayment)),
  };
}

function baselineFor(ctx: MonitoringContext, start: string, days: number): number {
  if (!ctx.annualRevenue) return 0;
  const idx = ctx.seasonalIndex && ctx.seasonalIndex.length >= 12 ? ctx.seasonalIndex : null;
  const s = dayNum(start);
  const factor = idx ? Array.from({ length: days }, (_, i) => idx[monthOf(s + i)]).reduce((a, b) => a + b, 0) / days : 1;
  return (ctx.annualRevenue * days) / 365 * factor;
}

/** ongoing_monitoring_agent.run over one batch: period = first..last transaction date (min 7 days). */
export function aggregatePeriod(txns: Transaction[], ctx: MonitoringContext, today: string): PeriodRecord | null {
  if (!txns.length) return null;
  const dates = txns.filter((t) => validIso(t.at)).map((t) => dayNum(t.at));
  const start = dates.length ? Math.min(...dates) : dayNum(today);
  const end = dates.length ? Math.max(...dates) : dayNum(today);
  const days = Math.max(MIN_PERIOD_DAYS, end - start + 1);
  const t = totals(txns);
  const [due, status] = installmentFor(ctx.plan, dayIso(start), days, t.repaid, ctx.disbursedOn);
  return {
    start: dayIso(start), end: dayIso(end), days, transactionsParsed: txns.length,
    revenue: r2(t.revenue), baseline: r2(baselineFor(ctx, dayIso(start), days)), expenses: r2(t.expenses),
    surplus: r2(t.revenue - t.expenses), installmentDue: due, status,
    creditIndex: creditworthinessIndex(t.credits, dayIso(start), days, status),
  };
}

const weeksOf = (r: PeriodRecord) => Math.max(1, r.days / 7);

/** health_score_agent.run applied to each record in order (earlier scored records inform the later ones). */
export function scoreRecords(records: PeriodRecord[], plannedExpenseRatio: number | null, cfg: HealthThresholds = healthThresholds()): ScoredRecord[] {
  const out: ScoredRecord[] = [];
  for (const snap of records) {
    const ratio = snap.baseline > 0 ? snap.revenue / snap.baseline : null;
    const coverage = snap.installmentDue > 0 ? snap.surplus / snap.installmentDue : null;
    const components: ScoredRecord["components"] = {
      revenueVsPlan: ratio === null ? null : clamp01(ratio / cfg.revenue_ratio_full_score),
      coverage: coverage === null ? null : clamp01(coverage / cfg.coverage_full_score),
      repayment: (cfg.repayment_scores as Record<string, number>)[snap.status] ?? null,
    };
    if (snap.status === "unknown" && ratio === null && coverage === null) components.repayment = null;
    const weights: [number | null, number][] = [
      [components.revenueVsPlan, cfg.weights.revenue_vs_plan], [components.coverage, cfg.weights.surplus_coverage], [components.repayment, cfg.weights.repayment],
    ];
    const used = weights.filter(([v]) => v !== null) as [number, number][];
    if (!used.length) {
      out.push({ ...snap, score: null, band: null, components, earlyWarning: false, reasons: [{ key: "c3.health.reason.no_plan" }], intervention: null });
      continue;
    }
    const score = r1((100 * used.reduce((a, [v, w]) => a + v * w, 0)) / used.reduce((a, [, w]) => a + w, 0));
    const band = score >= cfg.bands.healthy_min_score ? "healthy" : score >= cfg.bands.watch_min_score ? "watch" : "at_risk";
    const reasons: Msg[] = [];
    if (band === "at_risk") reasons.push({ key: "c3.health.reason.at_risk", vars: { score: Math.round(score) } });
    if (ratio !== null && ratio < cfg.revenue_ratio_floor) {
      reasons.push({ key: "c3.health.reason.revenue_floor", vars: { pct: Math.round(ratio * 100), floor: Math.round(cfg.revenue_ratio_floor * 100) } });
    }
    const earlyWarning = reasons.length > 0;

    const expenseRatio = snap.revenue > 0 ? snap.expenses / snap.revenue : null;
    const prev = out.filter((r) => r.band !== null);
    const volume = snap.transactionsParsed / weeksOf(snap);
    const last = prev[prev.length - 1];
    const normalVolume = last
      ? volume >= (cfg.normal_volume_vs_previous_ratio * last.transactionsParsed) / weeksOf(last)
      : volume >= cfg.normal_volume_min_transactions_per_week;
    const k = cfg.persistent_at_risk_snapshots - 1;
    const tail = k === 0 ? prev : prev.slice(-k);
    const persistent = band === "at_risk" && prev.length >= k && tail.every((r) => r.band === "at_risk");

    let intervention: ScoredRecord["intervention"] = null;
    if (earlyWarning || band === "watch") {
      if (snap.status === "overdue" || (coverage !== null && coverage < 1)) intervention = "repayment_counselling";
      else if (expenseRatio !== null && plannedExpenseRatio !== null && expenseRatio > plannedExpenseRatio + cfg.expense_ratio_spike_margin && !persistent) intervention = "supply_chain_change";
      else if (ratio !== null && ratio < cfg.revenue_shortfall_ratio && normalVolume && !persistent) intervention = "pricing_adjustment";
      else intervention = "mentor_outreach";
    }
    out.push({ ...snap, score, band, components, earlyWarning, reasons, intervention });
  }
  return out;
}

/**
 * Per calendar month (first to last transaction month; empty months in between count as zero-sale months).
 * Baseline = catalog base projection (the figure the plan uses) × days/365 × seasonal factor.
 * Installment per month (documented extension of the quarterly backend rule): due = installment × days/91.25;
 * months are counted from the disbursement month (default: first transaction month); quarter n falls due in
 * month 3n; moratorium quarters are not_due; a due month without ≥95% of the pro-rata due repaid is overdue;
 * a non-due month is not_due unless a partial repayment makes it grace_period.
 */
export function monthlySnapshots(
  txns: Transaction[],
  financial: FinancialResult,
  activityId: string,
  opts: { intel?: Intel | null; disbursedOn?: string | null } = {},
): MonthlyHealth[] {
  const dated = txns.filter((t) => validIso(t.at));
  if (!dated.length) return [];
  const act = catalogEntry(activityId);
  const riskIdx = opts.intel?.risk.seasonalIndex;
  const index = riskIdx && riskIdx.length === 12 ? riskIdx : act.seasonal_profile;
  const plan = financial.plan;
  const key = (iso: string) => +iso.slice(0, 4) * 12 + +iso.slice(5, 7) - 1;
  const first = Math.min(...dated.map((t) => key(t.at)));
  const lastM = Math.max(...dated.map((t) => key(t.at)));
  const disb = opts.disbursedOn && validIso(opts.disbursedOn) ? key(opts.disbursedOn) : first;
  const ctx: MonitoringContext = { plan, annualRevenue: financial.preview.annualRevenue, seasonalIndex: index, disbursedOn: null };

  const records: PeriodRecord[] = [];
  for (let m = first; m <= lastM; m++) {
    const y = Math.floor(m / 12);
    const mo = m % 12;
    const start = `${y}-${String(mo + 1).padStart(2, "0")}-01`;
    const days = new Date(Date.UTC(y, mo + 1, 0)).getUTCDate();
    const inMonth = dated.filter((t) => key(t.at) === m);
    const t = totals(inMonth);
    let due = 0;
    let status: InstallmentStatus = "unknown";
    if (plan.eligible) {
      const k = m - disb;
      const entry = k >= 0 ? plan.schedule[Math.floor(k / 3)] : undefined;
      const full = entry ? entry.payment : plan.regularInstallment;
      due = r2((full * days) / DAYS_PER_QUARTER);
      if (k < 0 || entry?.isMoratorium) status = "not_due";
      else if (!entry) status = "not_due"; // loan fully repaid
      else if (t.repaid >= 0.95 * Math.min(full, due)) status = "paid";
      else if (k % 3 === 2) status = "overdue";
      else status = t.repaid > 0 ? "grace_period" : "not_due";
      if (k < 0 || !entry) due = 0;
    }
    records.push({
      start, end: `${start.slice(0, 8)}${String(days).padStart(2, "0")}`, days, transactionsParsed: inMonth.length,
      revenue: r2(t.revenue), baseline: r2(baselineFor(ctx, start, days)), expenses: r2(t.expenses), surplus: r2(t.revenue - t.expenses),
      installmentDue: due, status, creditIndex: creditworthinessIndex(t.credits, start, days, status),
    });
  }
  return scoreRecords(records, 1 - act.operating_margin).map((r) => ({
    month: r.start.slice(0, 7),
    revenue: r.revenue,
    expenses: r.expenses,
    planned: r.baseline,
    surplus: r.surplus,
    score: r.score,
    band: r.band,
    components: r.components,
    earlyWarning: r.earlyWarning,
    intervention: r.intervention,
    creditIndex: r.creditIndex,
    status: r.status,
    installmentDue: r.installmentDue,
    reasons: r.reasons,
    transactions: r.transactionsParsed,
  }));
}
