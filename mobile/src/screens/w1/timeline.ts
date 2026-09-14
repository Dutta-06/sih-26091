/**
 * Case history derived from `state.events` (real timestamps on the demo clock) plus the start of the conversation.
 * Consecutive document updates on the same day are folded into one entry.
 */
import type { Route, Tab } from "../../nav";
import type { CaseEvent, JourneyState } from "../../state/store";

export type TimelineKind = CaseEvent["type"] | "chat";

export interface TimelineItem {
  id: string;
  at: string;
  kind: TimelineKind;
  title: string;
  /** vars for title/body: "@key" i18n keys, "~act:<id>" activity names (rendered by w1/chatI18n) */
  vars?: Record<string, string | number>;
  body?: string;
  tone: "forest" | "marigold" | "clay" | "sky";
  target: { tab: Tab; route?: Route };
}

const home = (name: Route["name"]): { tab: Tab; route: Route } => ({ tab: "home", route: { name } as Route });

export function describeEvent(e: CaseEvent, i: number): TimelineItem {
  const d = e.data ?? {};
  const base = { id: `${e.type}-${i}-${e.at}`, at: e.at, kind: e.type as TimelineKind };
  switch (e.type) {
    case "profile_started":
      return { ...base, title: "u1.tl.profile_started", tone: "forest", target: { tab: "assistant" } };
    case "location_confirmed":
      return { ...base, title: "u1.tl.location_confirmed", ...(d.lgd ? { body: "u1.tl.location_confirmedBody", vars: { lgd: String(d.lgd) } } : {}), tone: "sky", target: { tab: "assistant" } };
    case "analysis_run":
      return { ...base, title: "u1.tl.analysis_run", tone: "forest", target: home("report") };
    case "activity_chosen":
      return d.activityId
        ? { ...base, title: "u1.tl.activity_chosen", vars: { idea: `~act:${d.activityId}` }, tone: "forest", target: { tab: "plan" } }
        : { ...base, title: "u1.tl.analysis_run", tone: "forest", target: { tab: "plan" } };
    case "documents_updated":
      return { ...base, title: "u1.tl.documents_updated", tone: "marigold", target: home("documents") };
    case "application":
      return { ...base, title: "u1.tl.application", vars: { stage: `@u1.stage.${String(d.stage ?? "not_started")}` }, tone: d.stage === "rejected" ? "clay" : "sky", target: home("application") };
    case "consent":
      return { ...base, title: d.granted === true ? "u1.tl.consentOn" : d.granted === false ? "u1.tl.consentOff" : "u1.tl.consent", tone: d.granted === false ? "clay" : "forest", target: home("privacy") };
    case "data_deleted":
      return { ...base, title: "u1.tl.data_deleted", tone: "clay", target: home("privacy") };
    case "milestone":
      return { ...base, title: "u1.tl.milestone", tone: "marigold", target: home("roadmap") };
    case "intervention":
      return { ...base, title: "u1.tl.intervention", tone: "marigold", target: home("warning") };
    case "follow_up":
      return { ...base, title: "u1.tl.follow_up", tone: "forest", target: home("outcome") };
    case "grievance":
      return { ...base, title: "u1.tl.grievance", tone: "clay", target: home("grievance") };
    case "observation":
      return { ...base, title: "u1.tl.observation", tone: "sky", target: home("survey") };
    case "counsellor_request":
      return { ...base, title: "u1.tl.counsellor_request", tone: "marigold", target: home("scheme") };
    default:
      return { ...base, title: "u1.tl.other", tone: "sky", target: { tab: "home" } };
  }
}

export function timelineItems(s: Pick<JourneyState, "events" | "chat">): TimelineItem[] {
  const items: TimelineItem[] = [];
  const firstChat = s.chat.find((m) => m.at)?.at;
  if (firstChat) items.push({ id: "chat", at: firstChat, kind: "chat", title: "u1.tl.chat", tone: "forest", target: { tab: "assistant" } });
  s.events.forEach((e, i) => {
    const item = describeEvent(e, i);
    const prev = items.at(-1);
    if (item.kind === "documents_updated" && prev?.kind === "documents_updated" && prev.at.slice(0, 10) === item.at.slice(0, 10)) {
      const n = Number(prev.vars?.n ?? 1) + 1;
      items[items.length - 1] = { ...prev, at: item.at, body: "u1.tl.documents_updatedBody", vars: { n } };
      return;
    }
    items.push(item);
  });
  return items.sort((a, b) => a.at.localeCompare(b.at));
}
