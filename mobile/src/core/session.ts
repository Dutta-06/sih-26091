/**
 * Session layer: derives the whole case on the device from what the user has entered and done.
 * Nothing here is scripted — every screen reads `computeCase(inputs)` (via `useCase()`).
 *
 * Pipeline (mirrors the backend graph): location → profiling constraints → discovery → feasibility loop
 * (6 analyses → SWOT → red-team review → alternatives) → financial plan → documents/application →
 * launch roadmap & pooled procurement → consented SMS monitoring → health snapshots → interventions/outcomes.
 */
import { useClimates, type ClimateSummary } from "./climate";
import { buildFinancial, catalogEntry, type FinancialOutput } from "./financial";
import { checklist, requiredDocuments } from "./documents";
import { runFeasibility, runIntel, type FeasibilityOutcome } from "./feasibility";
import { resolveLocation } from "./geo";
import { monthlySnapshots } from "./health";
import { roadmap } from "./launch";
import { interventionOptions, categoryPrior } from "./outcomes";
import { pool } from "./procurement";
import { addIrregularEvents, parseNotifications, simulateBankAlerts } from "./sms";
import { detectAnomalies, type Anomaly } from "./anomalies";
import { forecast, type Forecast } from "./forecast";
import type { AppStage, DocStatus, GrievanceTicket, InterventionOption, Intel, OutcomeRecord, ProfileInput, ResolvedLocation, Transaction } from "./types";

export type MonthlyHealth = ReturnType<typeof monthlySnapshots>[number];

export interface SessionInputs {
  profile: ProfileInput;
  /** Activity the user chose to pursue (the review's recommendation, or an option picked from the shortlist). */
  chosenActivity: string | null;
  appStage: AppStage;
  documents: Record<string, DocStatus>;
  disbursedOn: string | null; // ISO date
  smsConsent: boolean;
  /** Sample SMS inbox on this phone: a typical year, or one with a monsoon disruption in the first July after disbursal. */
  inbox: "typical" | "monsoon_disruption";
  /** Monitoring data deleted by the user on this date: only alerts after it are read again. */
  dataDeletedOn: string | null;
  interventionChosen: { type: OutcomeRecord["intervention_type"]; month: string } | null;
  realOutcomes: OutcomeRecord[];
  grievances: GrievanceTicket[];
  today: string; // ISO date (device clock + presenter offset)
  /** Rainfall summaries fetched online for the case location (Open-Meteo), by 0.25° cell. */
  climate?: Record<string, ClimateSummary>;
}

export interface CaseView {
  location: ResolvedLocation;
  feasibility: FeasibilityOutcome;
  /** Activity whose plan, application and business are shown (chosen, else the review's selection). */
  activityId: string | null;
  intel: Intel | null;
  financial: FinancialOutput | null;
  documents: ReturnType<typeof checklist> | null;
  requiredDocs: ReturnType<typeof requiredDocuments>;
  roadmap: ReturnType<typeof roadmap>;
  pool: ReturnType<typeof pool> | null;
  transactions: Transaction[];
  health: MonthlyHealth[];
  latestHealth: MonthlyHealth | null;
  warning: MonthlyHealth | null; // latest snapshot with an early warning
  /** Next months learned from finished months (null before the first finished month). */
  forecast: Forecast | null;
  /** Unusual activity in the bank alerts up to today, newest first. */
  anomalies: Anomaly[];
  interventions: InterventionOption[];
  prior: ReturnType<typeof categoryPrior> | null;
}

const monthKey = (iso: string) => iso.slice(0, 7);

function monthsBetween(fromIso: string, toIso: string): number {
  const a = +fromIso.slice(0, 4) * 12 + +fromIso.slice(5, 7);
  const b = +toIso.slice(0, 4) * 12 + +toIso.slice(5, 7);
  return b - a + 1;
}

/** First July (month 7) on or after the disbursal month. */
function firstJulyAfter(iso: string): string {
  const y = +iso.slice(0, 4);
  return +iso.slice(5, 7) <= 7 ? `${y}-07` : `${y + 1}-07`;
}

/** Stable seed from profile inputs so the same case always sees the same sample inbox. */
function seedOf(p: ProfileInput): number {
  let h = 2166136261;
  for (const ch of `${p.locationCode ?? p.locationText}|${p.capital}|${p.activityId}`) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}

/** Reads the (sample) bank alerts on the phone, parses them and discards the raw text (TDD 7.3). */
export function readInbox(inputs: SessionInputs, financial: FinancialOutput, activityId: string, intel: Intel | null): Transaction[] {
  if (!inputs.smsConsent || !inputs.disbursedOn || !financial.plan.eligible) return [];
  const months = monthsBetween(inputs.disbursedOn, inputs.today);
  if (months <= 0) return [];
  const shock = inputs.inbox === "monsoon_disruption" ? { month: firstJulyAfter(inputs.disbursedOn), revenueDropPct: 35 } : undefined;
  const seed = seedOf(inputs.profile);
  const start = monthKey(inputs.disbursedOn);
  const raw = addIrregularEvents(simulateBankAlerts(financial, activityId, start, months, seed, shock, intel?.risk.seasonalIndex ?? null), start, months, seed, shock?.month);
  const today = new Date(`${inputs.today}T23:59:59Z`);
  return parseNotifications(raw, today).filter((t) => t.at.slice(0, 10) <= inputs.today && (!inputs.dataDeletedOn || t.at.slice(0, 10) > inputs.dataDeletedOn));
}

/** Snapshots for calendar months that have ended on `today` (the current month counts only on its last day). */
export function finishedMonths<T extends { month: string }>(health: T[], today: string): T[] {
  const d = new Date(`${today.slice(0, 10)}T00:00:00Z`);
  const lastDay = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
  return d.getUTCDate() === lastDay ? health : health.filter((h) => h.month < today.slice(0, 7));
}

export function computeCase(inputs: SessionInputs): CaseView {
  useClimates(inputs.climate);
  const { profile } = inputs;
  const location = resolveLocation(profile.locationText, profile.locationCode);
  const place = location.chosen ?? (location.candidates.length === 1 ? location.candidates[0] : null);
  const feasibility = runFeasibility(profile, place);
  const activityId = inputs.chosenActivity ?? feasibility.selected?.activityId ?? null;
  const intel = activityId ? feasibility.attempts.find((a) => a.activityId === activityId)?.intel ?? runIntel(activityId, profile, place) : null;
  const financial = activityId ? buildFinancial(profile, activityId, intel) : null;
  const requiredDocs = financial ? requiredDocuments(profile, financial) : [];
  const documents = financial ? checklist(requiredDocs, inputs.documents) : null;
  const transactions = activityId && financial ? readInbox(inputs, financial, activityId, intel) : [];
  // Only finished calendar months are scored: a month in progress has partial sales but a full month's plan.
  const allMonths = activityId && financial ? monthlySnapshots(transactions, financial, activityId, { intel, disbursedOn: inputs.disbursedOn }) : [];
  const health = finishedMonths(allMonths, inputs.today);
  const warning = [...health].reverse().find((h) => h.earlyWarning) ?? null;
  const seasonal = activityId ? intel?.risk.seasonalIndex ?? catalogEntry(activityId).seasonal_profile : null;
  const anomalies = transactions.length ? detectAnomalies(transactions, inputs.today, seasonal) : [];
  const oneOff: Record<string, number> = {};
  for (const a of anomalies) if (a.kind === "large_credit" && a.amount) oneOff[a.at.slice(0, 7)] = (oneOff[a.at.slice(0, 7)] ?? 0) + a.amount;
  const district = place?.district.id ?? null;
  return {
    location,
    feasibility,
    activityId,
    intel,
    financial,
    documents,
    requiredDocs,
    roadmap: activityId && financial ? roadmap(profile, activityId, financial, intel) : [],
    pool: activityId ? pool(activityId, place, intel) : null,
    transactions,
    health,
    latestHealth: health.at(-1) ?? null,
    warning,
    forecast: activityId && financial ? forecast(health, { financial, activityId, intel, disbursedOn: inputs.disbursedOn, oneOff }) : null,
    anomalies,
    interventions: activityId ? interventionOptions(activityId, district, inputs.realOutcomes) : [],
    prior: activityId ? categoryPrior(activityId, district, inputs.realOutcomes) : null,
  };
}
