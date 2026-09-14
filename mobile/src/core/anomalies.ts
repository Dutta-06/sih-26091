/**
 * Unusual activity in the parsed bank alerts (TDD Module 3 early warning, between monthly scores).
 *
 *  - duplicate_debit: two non-loan debits of the same amount (≥ ₹200) on the same day — a possible double charge.
 *  - large_debit / large_credit: amount far outside this business's own pattern — robust z-score of log amount
 *    against the previous 90 days (median / MAD × 1.4826), z ≥ 3.5, at least 8 earlier transactions of that direction
 *    and at least 3× their median.
 *  - sales_gap: a run of days with no incoming payment longer than max(6, 3 × the usual gap between sales days),
 *    judged on the 90 days before the gap (open gaps count up to today).
 *  - sales_slowdown: the last 14 days brought in under half of what the previous 60 days' pace predicts, adjusted
 *    for season; checked only for today, so it can warn before a month closes.
 * Each finding carries the evidence (amounts, days, usual pattern) so the screen can explain it.
 */
import type { Transaction } from "./types";

export type AnomalyKind = "duplicate_debit" | "large_debit" | "large_credit" | "sales_gap" | "sales_slowdown";

export interface Anomaly {
  kind: AnomalyKind;
  at: string; // YYYY-MM-DD the finding refers to (gap start for sales_gap)
  severity: "high" | "medium";
  amount?: number;
  /** Evidence for the explanation: usual amount, times above usual, days, expected vs actual, … */
  vars: Record<string, number | string>;
}

const DAY = 86_400_000;
const day = (iso: string) => Math.floor(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / DAY);
const iso = (d: number) => new Date(d * DAY).toISOString().slice(0, 10);
const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

const MIN_HISTORY = 8;
const Z_LIMIT = 3.5;
const LOOKBACK = 90;

/** Robust z of `value` (log scale) against `history` amounts. */
export function robustZ(value: number, history: number[]): number {
  const logs = history.filter((v) => v > 0).map(Math.log);
  const med = median(logs);
  const mad = median(logs.map((l) => Math.abs(l - med))) * 1.4826;
  return (Math.log(value) - med) / Math.max(mad, 0.05);
}

function duplicates(txns: Transaction[]): Anomaly[] {
  const seen = new Map<string, number>();
  const out: Anomaly[] = [];
  for (const t of txns) {
    if (t.direction !== "debit" || t.isLoanRepayment || t.amount < 200) continue;
    const key = `${t.at.slice(0, 10)}|${t.amount}`;
    const n = (seen.get(key) ?? 0) + 1;
    seen.set(key, n);
    if (n === 2) out.push({ kind: "duplicate_debit", at: t.at.slice(0, 10), severity: "high", amount: t.amount, vars: { amount: t.amount, count: 2 } });
  }
  return out;
}

function outliers(txns: Transaction[]): Anomaly[] {
  const out: Anomaly[] = [];
  for (const dir of ["debit", "credit"] as const) {
    const series = txns.filter((t) => t.direction === dir && !t.isLoanRepayment);
    series.forEach((t, i) => {
      const d = day(t.at);
      const history = series.slice(0, i).filter((h) => day(h.at) >= d - LOOKBACK).map((h) => h.amount);
      if (history.length < MIN_HISTORY) return;
      const usual = median(history);
      if (t.amount < 3 * usual || robustZ(t.amount, history) < Z_LIMIT) return;
      out.push({
        kind: dir === "debit" ? "large_debit" : "large_credit",
        at: t.at.slice(0, 10),
        severity: dir === "debit" && t.amount >= 8 * usual ? "high" : "medium",
        amount: t.amount,
        vars: { amount: t.amount, usual: Math.round(usual), times: Math.round(t.amount / usual) },
      });
    });
  }
  return out;
}

function salesGaps(txns: Transaction[], today: string): Anomaly[] {
  const days = [...new Set(txns.filter((t) => t.direction === "credit" && !t.isLoanRepayment).map((t) => day(t.at)))].sort((a, b) => a - b);
  if (days.length < MIN_HISTORY) return [];
  const end = day(today);
  const points = [...days, end + 1]; // an open gap runs to today
  const out: Anomaly[] = [];
  for (let i = 1; i < points.length; i++) {
    const gap = points[i] - points[i - 1] - 1;
    if (gap < 6) continue;
    const before = days.filter((d) => d < points[i - 1] + 1 && d >= points[i - 1] - LOOKBACK);
    if (before.length < MIN_HISTORY) continue;
    const usualGap = median(before.slice(1).map((d, j) => d - before[j] - 1));
    const limit = Math.max(6, 3 * usualGap);
    if (gap <= limit) continue;
    out.push({
      kind: "sales_gap",
      at: iso(points[i - 1] + 1),
      severity: gap >= 2 * limit ? "high" : "medium",
      vars: { days: gap, usualDays: Math.max(1, Math.round(usualGap)), open: i === points.length - 1 ? 1 : 0 },
    });
  }
  return out;
}

function slowdown(txns: Transaction[], today: string, seasonal: number[] | null): Anomaly[] {
  const end = day(today);
  const credits = txns.filter((t) => t.direction === "credit" && !t.isLoanRepayment);
  const recent = credits.filter((t) => day(t.at) > end - 14 && day(t.at) <= end);
  const prior = credits.filter((t) => day(t.at) > end - 74 && day(t.at) <= end - 14);
  if (prior.length < MIN_HISTORY || !credits.some((t) => day(t.at) <= end - 74)) return [];
  const month = (d: number) => new Date(d * DAY).getUTCMonth();
  const factor = (from: number, to: number) => {
    if (!seasonal || seasonal.length !== 12) return 1;
    let s = 0;
    for (let d = from; d <= to; d++) s += seasonal[month(d)];
    return s / (to - from + 1);
  };
  const pace = prior.reduce((a, t) => a + t.amount, 0) / 60 / factor(end - 73, end - 14);
  const expected = pace * 14 * factor(end - 13, end);
  const actual = recent.reduce((a, t) => a + t.amount, 0);
  if (expected <= 0 || actual >= 0.5 * expected) return [];
  return [{
    kind: "sales_slowdown",
    at: iso(end),
    severity: actual < 0.25 * expected ? "high" : "medium",
    amount: Math.round(actual),
    vars: { actual: Math.round(actual), expected: Math.round(expected), pct: Math.round((actual / expected) * 100) },
  }];
}

/** All findings up to `today`, newest first. */
export function detectAnomalies(transactions: Transaction[], today: string, seasonal: number[] | null = null): Anomaly[] {
  const txns = transactions.filter((t) => t.at.slice(0, 10) <= today).sort((a, b) => a.at.localeCompare(b.at));
  return [...duplicates(txns), ...outliers(txns), ...salesGaps(txns, today), ...slowdown(txns, today, seasonal)].sort(
    (a, b) => b.at.localeCompare(a.at) || (a.severity === b.severity ? 0 : a.severity === "high" ? -1 : 1),
  );
}
