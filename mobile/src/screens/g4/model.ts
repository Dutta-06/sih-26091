import { LANG_INFO } from "../../i18n";
/**
 * G4 derived figures for the business lifecycle. Everything is computed from the on-device case (`useStore().view`)
 * and the user's own inputs/events; no result is typed in here.
 */
import { useMemo } from "react";
import { ACTIVITIES } from "../../data/activities";
import type { Plan } from "../../engine/finance";
import type { Bi, Lang } from "../../i18n";
import { completedMonths } from "../../core/portfolio";
import type { CaseView, MonthlyHealth } from "../../core/session";
import type { GrievanceTicket, OutcomeRecord } from "../../core/types";
import { todayOf, useStore, type JourneyState } from "../../state/store";

export type InterventionType = OutcomeRecord["intervention_type"];

/** Display name + emoji for a catalog activity (display table; falls back to the humanised id). */
export function activityLabel(id: string | null): { name: Bi | string; emoji: string } {
  if (!id) return { name: "—", emoji: "🏪" };
  const a = ACTIVITIES[id];
  if (a) return { name: a.name, emoji: a.emoji };
  const words = id.replace(/_/g, " ");
  return { name: words.charAt(0).toUpperCase() + words.slice(1), emoji: "🏪" };
}

const locale = (lang: Lang) => (LANG_INFO[lang].dateLocale);

/** "2026-07" → "July 2026" (or short "Jul"). */
export function monthLabel(month: string, lang: Lang, style: "long" | "short" = "long"): string {
  const d = new Date(Date.UTC(+month.slice(0, 4), +month.slice(5, 7) - 1, 1));
  return d.toLocaleDateString(locale(lang), style === "long" ? { month: "long", year: "numeric", timeZone: "UTC", numberingSystem: "latn" } : { month: "short", timeZone: "UTC", numberingSystem: "latn" });
}

export function dateLabel(iso: string, lang: Lang, withTime = false): string {
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00Z` : iso);
  return d.toLocaleString(locale(lang), {
    day: "numeric", month: "short", year: "numeric", numberingSystem: "latn",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : { timeZone: "UTC" }),
  });
}

export function addMonthsIso(iso: string, months: number): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  const day = d.getUTCDate();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() + months);
  const last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
  d.setUTCDate(Math.min(day, last));
  return d.toISOString().slice(0, 10);
}

export const daysBetween = (fromIso: string, toIso: string) =>
  Math.round((Date.parse(`${toIso.slice(0, 10)}T00:00:00Z`) - Date.parse(`${fromIso.slice(0, 10)}T00:00:00Z`)) / 86_400_000);

/** Next quarterly instalment: quarter n falls due at disbursal + 3n months (the monitoring rule in core/health). */
export function nextInstalment(plan: Plan | null | undefined, disbursedOn: string | null, today: string) {
  if (!plan?.eligible || !disbursedOn || !plan.schedule.length) return null;
  for (const q of plan.schedule) {
    const due = addMonthsIso(disbursedOn, 3 * q.quarter);
    if (due >= today) return { ...q, due, inDays: daysBetween(today, due), total: plan.schedule.length };
  }
  return { done: true as const, total: plan.schedule.length };
}

/** Revenue as a percentage of the month's plan baseline (null without a baseline). */
export const pctOfPlan = (h: Pick<MonthlyHealth, "revenue" | "planned">) => (h.planned > 0 ? Math.round((h.revenue / h.planned) * 100) : null);

/**
 * Ticket progress on the demo clock (on-device rule, the backend has no SLA tracker):
 * mentor assigned on creation → in progress once the response window has passed → resolved after three windows.
 */
export function ticketStatus(ticket: GrievanceTicket, nowIso: string): GrievanceTicket["status"] {
  const hours = (Date.parse(nowIso) - Date.parse(ticket.at)) / 3_600_000;
  if (hours >= 3 * ticket.responseHours) return "resolved";
  if (hours >= ticket.responseHours) return "in_progress";
  return ticket.status;
}

export const ticketResolvedAt = (ticket: GrievanceTicket) => new Date(Date.parse(ticket.at) + 3 * ticket.responseHours * 3_600_000).toISOString();

/** Consent history from the case events. */
export function consentLog(state: JourneyState) {
  return state.events.filter((e) => e.type === "consent").map((e) => ({ granted: !!e.data?.granted, at: e.at }));
}

export interface Lifecycle {
  today: string; // YYYY-MM-DD
  now: string; // ISO date-time on the demo clock
  /** Snapshots of calendar months that have ended. */
  done: MonthlyHealth[];
  /** The month in progress (partial; never scored as a warning). */
  current: MonthlyHealth | null;
  latest: MonthlyHealth | null;
  previous: MonthlyHealth | null;
  warning: MonthlyHealth | null;
  acted: boolean;
  chosenSnap: MonthlyHealth | null;
  afterSnap: MonthlyHealth | null;
  followUpDue: boolean;
  instalment: ReturnType<typeof nextInstalment>;
}

export function lifecycle(state: JourneyState, view: CaseView, now: string): Lifecycle {
  const today = now.slice(0, 10);
  const done = completedMonths(view.health, today);
  const current = view.health.find((h) => !done.includes(h)) ?? null;
  const warning = [...done].reverse().find((h) => h.earlyWarning) ?? null;
  const chosen = state.interventionChosen;
  const chosenSnap = chosen ? view.health.find((h) => h.month === chosen.month) ?? null : null;
  const afterSnap = chosen ? done.find((h) => h.month > chosen.month && h.score !== null) ?? null : null;
  return {
    today,
    now,
    done,
    current,
    latest: done.at(-1) ?? null,
    previous: done.at(-2) ?? null,
    warning,
    acted: !!warning && chosen?.month === warning.month,
    chosenSnap,
    afterSnap,
    followUpDue: !!chosen && !!afterSnap && !state.followUp,
    instalment: nextInstalment(view.financial?.plan, state.disbursedOn, today),
  };
}

export function useLifecycle() {
  const store = useStore();
  const now = todayOf(store.state);
  const day = now.slice(0, 13); // recompute at most hourly on the demo clock
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const lc = useMemo(() => lifecycle(store.state, store.view, now), [store.state, store.view, day]);
  return { ...store, lc };
}

const grouping = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** Core Msg with money-like numbers given Indian digit grouping before `tm()` renders them. */
export function fmtMsg<M extends { key: string; vars?: Record<string, unknown> }>(msg: M): M {
  if (!msg.vars) return msg;
  const vars: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(msg.vars)) vars[k] = typeof v === "number" && Math.abs(v) >= 1000 ? grouping.format(v) : v;
  return { ...msg, vars };
}

export const BAND_TONE ={ healthy: "good", watch: "warn", at_risk: "risk" } as const;
export const RING_TONE = { healthy: "azure", watch: "marigold", at_risk: "clay" } as const;
export const STATUS_TONE = { paid: "good", not_due: "neutral", grace_period: "warn", overdue: "risk", unknown: "neutral" } as const;

