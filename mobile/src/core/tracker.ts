/**
 * Application state machine (port of module2_financial/application_tracker.py). The backend's "not_applied"
 * is the app's "not_started". Verification, sanction, disbursement and rejection are officer events.
 */
import type { AppStage } from "./types";

export type AppEvent = "submit" | "start_verification" | "sanction" | "disburse" | "reject" | "request_documents" | "return_documents";

export const TRANSITIONS: [AppStage, AppEvent, AppStage][] = [
  ["not_started", "request_documents", "documents_pending"],
  ["not_started", "submit", "submitted"],
  ["documents_pending", "submit", "submitted"],
  ["submitted", "return_documents", "documents_pending"],
  ["under_verification", "return_documents", "documents_pending"],
  ["submitted", "start_verification", "under_verification"],
  ["under_verification", "sanction", "sanctioned"],
  ["sanctioned", "disburse", "disbursed"],
  ["submitted", "reject", "rejected"],
  ["under_verification", "reject", "rejected"],
  ["sanctioned", "reject", "rejected"],
];

export function nextEvents(stage: AppStage): AppEvent[] {
  return TRANSITIONS.filter(([s]) => s === stage).map(([, e]) => e);
}

/** Apply one event; throws on an illegal transition or a submit with incomplete documents. */
export function transition(stage: AppStage, event: AppEvent, ctx: { allDocsComplete: boolean }): AppStage {
  if (event === "submit" && !ctx.allDocsComplete) throw new Error("Cannot submit: required documents are not all complete.");
  const hit = TRANSITIONS.find(([s, e]) => s === stage && e === event);
  if (!hit) throw new Error(`Illegal transition: '${event}' from '${stage}' (allowed: ${nextEvents(stage).join(", ")})`);
  return hit[2];
}

/** The system step (application_tracker.run): auto-submit when complete, otherwise request documents once. */
export function autoAdvance(stage: AppStage, ctx: { allDocsComplete: boolean; hasChecklist: boolean }): AppStage {
  if ((stage !== "not_started" && stage !== "documents_pending") || !ctx.hasChecklist) return stage;
  if (ctx.allDocsComplete) return transition(stage, "submit", ctx);
  return stage === "not_started" ? transition(stage, "request_documents", ctx) : stage;
}
