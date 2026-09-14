import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, type ReactNode } from "react";
import { climateKey, type ClimateSummary } from "../core/climate";
import { fetchClimate } from "../lib/online";
import { computeCase, type CaseView, type SessionInputs } from "../core/session";
import { transition, type AppEvent } from "../core/tracker";
import type { AppStage, DocStatus, GrievanceTicket, OutcomeRecord, ProfileInput } from "../core/types";
import type { Lang } from "../i18n";
import { isLang } from "../i18n/languages";

/**
 * Persistent case state. It holds ONLY what the user entered and did (inputs + events).
 * Everything the screens show is derived on the device by `computeCase` (see `useCase()`).
 */
export type { AppStage, DocStatus };
export type ChatLang = Lang;
export type Intervention = OutcomeRecord["intervention_type"];

export interface ChatMessage {
  id: string;
  from: "assistant" | "user";
  /** i18n key (assistant) or the user's literal text */
  text: string;
  vars?: Record<string, string | number>;
  literal?: boolean;
  card?: string;
  at?: string;
}

export interface Observation {
  id: string;
  kind: "funded_entrepreneur" | "resident_survey";
  topic: string;
  text: string;
  at: string;
  district?: string | null;
  activityId?: string | null;
}

export interface CaseEvent {
  type:
    | "profile_started" | "location_confirmed" | "analysis_run" | "activity_chosen" | "documents_updated"
    | "application" | "consent" | "data_deleted" | "milestone" | "intervention" | "follow_up" | "grievance" | "observation" | "counsellor_request";
  at: string; // ISO date-time on the demo clock
  data?: Record<string, string | number | boolean | null>;
}

export interface JourneyState {
  lang: Lang;
  chatLang: ChatLang;
  readAloud: boolean;
  onboarded: boolean;
  chat: ChatMessage[];
  pendingSlot: string | null;
  profile: ProfileInput;
  chosenActivity: string | null;
  analysisSeen: boolean;
  documents: Record<string, DocStatus>;
  appStage: AppStage;
  disbursedOn: string | null;
  milestonesDone: string[];
  smsConsent: boolean;
  inbox: SessionInputs["inbox"];
  dataDeletedOn: string | null;
  interventionChosen: SessionInputs["interventionChosen"];
  followUp: { answer: "yes" | "little" | "no"; before: number; after: number; month: string } | null;
  realOutcomes: OutcomeRecord[];
  grievances: GrievanceTicket[];
  observations: Observation[];
  joinedPool: boolean;
  /** Application-form answers the pipeline does not model (masked where sensitive). */
  applicant: Record<string, string>;
  events: CaseEvent[];
  /** Presenter clock offset so months of business can pass during a demo. */
  clockOffsetDays: number;
  /** Which example person the presenter tools use (SAMPLE_PEOPLE index). */
  sampleIndex: number;
  /** Rainfall summaries fetched online (Open-Meteo), kept so the analysis works offline afterwards. */
  climate: Record<string, ClimateSummary>;
  lastVisitAt: string | null;
  previousVisitAt: string | null;
}

export const EMPTY_PROFILE: ProfileInput = {
  capital: 0, locationText: "", locationCode: null, activityId: null, reason: null, skills: [], assets: [],
  premises: null, category: null, womanOwned: false, shgMember: false,
};

/** Example entrepreneurs for presenters across states (only inputs — every result is computed for their district). */
export interface SamplePerson {
  name: string;
  profile: ProfileInput;
}
const person = (name: string, p: Partial<ProfileInput> & Pick<ProfileInput, "capital" | "locationText" | "activityId">): SamplePerson => ({
  name,
  profile: { locationCode: null, reason: "", skills: [], assets: [], premises: "home", category: null, womanOwned: false, shgMember: false, ...p },
});
export const SAMPLE_PEOPLE: SamplePerson[] = [
  person("Sunita", { capital: 12_000, locationText: "Gopiganj, Bhadohi", locationCode: "184512", activityId: "handloom_weaving", reason: "My neighbour earns well from handloom", skills: ["stitching", "embroidery"], assets: ["foot_pedal_machine"], category: "obc", womanOwned: true }),
  person("Lakshmi", { capital: 18_000, locationText: "Tiruppur, Tamil Nadu", activityId: "tailoring", reason: "Garment units here always need stitching", skills: ["stitching"], assets: ["electric_machine"], category: "obc", womanOwned: true, shgMember: true }),
  person("Anjali", { capital: 15_000, locationText: "Murshidabad, West Bengal", activityId: "beauty_parlour", reason: "There is no parlour in my area", skills: ["beauty"], premises: "rented_shop", category: "sc", womanOwned: true }),
  person("Gurpreet", { capital: 20_000, locationText: "Ludhiana, Punjab", activityId: "food_processing_home", reason: "People like my pickles", skills: ["cooking"], category: "general", womanOwned: true, shgMember: true }),
  person("Ramesh", { capital: 40_000, locationText: "Nashik, Maharashtra", activityId: "dairy_farming", reason: "We have land and fodder", skills: ["livestock"], premises: "own_land", assets: ["cattle"], category: "general" }),
  person("Irfan", { capital: 10_000, locationText: "Gaya, Bihar", activityId: "mobile_repair", reason: "I have repaired phones for two years", skills: ["repair"], premises: "rented_shop", category: "obc" }),
];
export const SAMPLE_PROFILE: ProfileInput = SAMPLE_PEOPLE[0].profile;
export const samplePerson = (s: Pick<JourneyState, "sampleIndex">): SamplePerson => SAMPLE_PEOPLE[((s.sampleIndex ?? 0) % SAMPLE_PEOPLE.length + SAMPLE_PEOPLE.length) % SAMPLE_PEOPLE.length];

export const initialState = (lang: Lang = "en"): JourneyState => ({
  lang, chatLang: lang, readAloud: false, onboarded: false, chat: [], pendingSlot: null, profile: EMPTY_PROFILE,
  chosenActivity: null, analysisSeen: false, documents: {}, appStage: "not_started", disbursedOn: null, milestonesDone: [],
  smsConsent: false, inbox: "monsoon_disruption", dataDeletedOn: null, interventionChosen: null, followUp: null, realOutcomes: [],
  grievances: [], observations: [], joinedPool: false, applicant: {}, events: [], clockOffsetDays: 0, lastVisitAt: null, previousVisitAt: null, sampleIndex: 0, climate: {},
});

export const todayOf = (s: Pick<JourneyState, "clockOffsetDays">) => new Date(Date.now() + s.clockOffsetDays * 86_400_000).toISOString();

export type Action =
  | { type: "set"; patch: Partial<JourneyState> }
  | { type: "profile"; patch: Partial<ProfileInput> }
  | { type: "chat"; messages: ChatMessage[]; pendingSlot?: string | null }
  | { type: "doc"; id: string; status: DocStatus }
  | { type: "application"; event: AppEvent; allDocsComplete: boolean }
  | { type: "milestone"; id: string }
  | { type: "event"; event: Omit<CaseEvent, "at"> }
  | { type: "advanceClock"; days: number }
  | { type: "reset" }
  | { type: "climate"; key: string; summary: ClimateSummary }
  | { type: "jump"; to: DemoCheckpoint };

export type DemoCheckpoint = "start" | "sample_profile" | "report" | "plan" | "application" | "launched" | "monitoring" | "followup" | "no_viable" | "returning";

const iso = (d: Date) => d.toISOString().slice(0, 10);
const daysAgo = (n: number) => iso(new Date(Date.now() - n * 86_400_000));

function withEvent(state: JourneyState, event: Omit<CaseEvent, "at">): JourneyState {
  return { ...state, events: [...state.events, { ...event, at: todayOf(state) }] };
}

/** Presenter shortcuts set inputs and events only; the case is recomputed from them. */
function checkpoint(state: JourneyState, to: DemoCheckpoint): JourneyState {
  // Monitoring jumps disburse the loan early enough that the sample inbox covers at least one July (monsoon month).
  const now = new Date();
  const monthsSinceJuly = (now.getUTCMonth() - 6 + 12) % 12; // 0 in July
  const monitoringDays = Math.round((monthsSinceJuly + 7) * 30.5);
  const sample = samplePerson(state).profile;
  const base: JourneyState = { ...initialState(state.lang), chatLang: state.chatLang, onboarded: true, lastVisitAt: new Date().toISOString(), sampleIndex: state.sampleIndex ?? 0, climate: state.climate ?? {} };
  const profiled: JourneyState = { ...base, profile: sample, analysisSeen: true, events: [{ type: "profile_started", at: new Date(Date.now() - 300 * 86_400_000).toISOString() }] };
  // Pursue what the review selected for this person (their own idea when it passed)
  const chosen: JourneyState = { ...profiled, chosenActivity: computeCase(sessionInputs(profiled)).activityId ?? sample.activityId };
  const planned = computeCase(sessionInputs(chosen));
  const docsComplete = Object.fromEntries(planned.requiredDocs.map((d) => [d.id, "complete" as DocStatus]));
  const milestones = planned.roadmap.map((m) => m.id);
  const disbursed = (days: number): JourneyState => ({ ...chosen, appStage: "disbursed", disbursedOn: daysAgo(days), documents: docsComplete });
  switch (to) {
    case "start":
      return base;
    case "sample_profile":
      return { ...base, profile: sample };
    case "report":
      return profiled;
    case "plan":
      return chosen;
    case "application":
      return { ...chosen, appStage: "documents_pending", documents: { identity_proof: "complete", bank_passbook: "complete" } };
    case "launched":
      return { ...disbursed(10), milestonesDone: milestones.slice(0, 1) };
    case "monitoring":
      return { ...disbursed(monitoringDays), milestonesDone: milestones, smsConsent: true };
    case "followup": {
      // Early warning acted on: the best-ranked intervention for the computed warning month.
      const mon = checkpoint(state, "monitoring");
      const v = computeCase(sessionInputs(mon));
      const best = [...v.interventions].sort((a, b) => b.successRate - a.successRate)[0];
      return { ...mon, interventionChosen: v.warning && best ? { type: best.type, month: v.warning.month } : null };
    }
    case "no_viable":
      return { ...base, profile: { ...sample, capital: 2_500, activityId: "flour_mill" }, analysisSeen: true };
    case "returning":
      return { ...checkpoint(state, "application"), previousVisitAt: new Date(Date.now() - 23 * 86_400_000).toISOString() };
  }
}

export { reducer as reducerForTests };
function reducer(state: JourneyState, action: Action): JourneyState {
  switch (action.type) {
    case "set":
      return { ...state, ...action.patch };
    case "profile":
      return { ...state, profile: { ...state.profile, ...action.patch } };
    case "chat":
      return { ...state, chat: [...state.chat, ...action.messages.map((m) => ({ ...m, at: m.at ?? todayOf(state) }))], pendingSlot: action.pendingSlot === undefined ? state.pendingSlot : action.pendingSlot };
    case "doc":
      return withEvent({ ...state, documents: { ...state.documents, [action.id]: action.status } }, { type: "documents_updated", data: { id: action.id, status: action.status } });
    case "application": {
      let next: AppStage;
      try {
        next = transition(state.appStage, action.event, { allDocsComplete: action.allDocsComplete });
      } catch {
        return state; // illegal transition (e.g. a double tap): ignore, screens offer only nextEvents()
      }
      const s = { ...state, appStage: next, disbursedOn: next === "disbursed" ? todayOf(state).slice(0, 10) : state.disbursedOn };
      return withEvent(s, { type: "application", data: { event: action.event, stage: next } });
    }
    case "milestone": {
      const done = state.milestonesDone.includes(action.id);
      const s = { ...state, milestonesDone: done ? state.milestonesDone.filter((m) => m !== action.id) : [...state.milestonesDone, action.id] };
      return done ? s : withEvent(s, { type: "milestone", data: { id: action.id } });
    }
    case "event":
      return withEvent(state, action.event);
    case "advanceClock":
      return { ...state, clockOffsetDays: state.clockOffsetDays + action.days };
    case "climate":
      return { ...state, climate: { ...(state.climate ?? {}), [action.key]: action.summary } };
    case "reset":
      return { ...initialState(state.lang), onboarded: true, chatLang: state.chatLang };
    case "jump":
      return checkpoint(state, action.to);
  }
}

const KEY = "aashaudyami.case.v1";

function load(): JourneyState {
  if (import.meta.env.DEV) {
    // Dev-only screenshot hook: #tab/route?jump=<checkpoint>&lang=hi&state=<json>&clock=<days>
    const params = new URLSearchParams(location.hash.split("?")[1] ?? "");
    const jump = params.get("jump") as DemoCheckpoint | null;
    if (jump) {
      const requested = params.get("lang");
      const lang = isLang(requested) ? requested : "en";
      const s = reducer(initialState(lang), { type: "jump", to: jump });
      const extra = params.get("state");
      return { ...s, ...(extra ? JSON.parse(extra) : {}), clockOffsetDays: Number(params.get("clock") ?? s.clockOffsetDays) };
    }
  }
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const saved = { ...initialState(), ...JSON.parse(raw) } as JourneyState;
      return { ...saved, previousVisitAt: saved.lastVisitAt, lastVisitAt: new Date().toISOString() };
    }
  } catch {
    /* storage unavailable or corrupt: start fresh */
  }
  return { ...initialState(), lastVisitAt: new Date().toISOString() };
}

/** Inputs for the on-device pipeline, derived from persistent state. */
export function sessionInputs(s: JourneyState): SessionInputs {
  return {
    profile: s.profile, chosenActivity: s.chosenActivity, appStage: s.appStage, documents: s.documents, disbursedOn: s.disbursedOn,
    smsConsent: s.smsConsent, inbox: s.inbox, dataDeletedOn: s.dataDeletedOn, interventionChosen: s.interventionChosen,
    realOutcomes: s.realOutcomes, grievances: s.grievances, today: todayOf(s).slice(0, 10), climate: s.climate,
  };
}

interface Store {
  state: JourneyState;
  dispatch: (a: Action) => void;
  set: (patch: Partial<JourneyState>) => void;
  /** The case computed on the device from the current inputs (memoised). */
  view: CaseView;
}

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, load);
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* ignore */
    }
  }, [state]);
  const set = useCallback((patch: Partial<JourneyState>) => dispatch({ type: "set", patch }), []);
  const inputs = sessionInputs(state);
  const inputsKey = JSON.stringify(inputs);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const view = useMemo(() => computeCase(inputs), [inputsKey]);
  // Rainfall climate for the case location, fetched once online (Open-Meteo, no key) and kept with the case
  const place = view.location.chosen;
  const climateCell = place && place.method !== "state_centroid" ? climateKey(place.lat, place.lon) : null;
  useEffect(() => {
    if (!place || !climateCell || state.climate?.[climateCell]) return;
    let alive = true;
    void fetchClimate(place.lat, place.lon).then((summary) => {
      if (alive && summary) dispatch({ type: "climate", key: climateCell, summary });
    });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [climateCell]);
  const value = useMemo(() => ({ state, dispatch, set, view }), [state, set, view]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStore outside StoreProvider");
  return ctx;
}

/** Shorthand for screens that only read the computed case. */
export const useCase = () => useStore().view;

export const uid = () => Math.random().toString(36).slice(2, 10);
