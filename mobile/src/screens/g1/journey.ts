import type { CaseView } from "../../core/session";
import type { Route, Tab } from "../../nav";
import type { JourneyState } from "../../state/store";
import { profileComplete, profileStarted } from "./conversation";

export const STAGES = ["profile", "feasibility", "plan", "application", "launch", "monitoring"] as const;
export type Stage = (typeof STAGES)[number];

export interface JourneyStep {
  stage: Stage;
  index: number;
  /** i18n key suffix for the contextual call to action (home.cta.* / home.stageHint.*) */
  cta: string;
  tone: "forest" | "clay";
  target: { tab: Tab; route?: Route };
}

/** Derive the lifecycle stage and the single next action from the inputs and the computed case. */
export function currentStep(s: JourneyState, view: CaseView): JourneyStep {
  const step = (stage: Stage, cta: string, target: JourneyStep["target"], tone: JourneyStep["tone"] = "forest"): JourneyStep => ({
    stage,
    index: STAGES.indexOf(stage),
    cta,
    tone,
    target,
  });
  const f = view.feasibility;
  if (!profileStarted(s.profile)) return step("profile", "startChat", { tab: "assistant" });
  if (!profileComplete(s.profile, s.chat)) return step("profile", "continueChat", { tab: "assistant" });
  if (!s.analysisSeen) return step("feasibility", "runAnalysis", { tab: "assistant", route: { name: "analysis" } });
  if (f.exhausted && !s.chosenActivity) return step("feasibility", "noViable", { tab: "home", route: { name: "noViable" } }, "clay");
  if (!f.attempts.length && !s.chosenActivity) return step("profile", "fixProfile", { tab: "assistant" }, "clay");
  if (!s.chosenActivity) {
    const rejectedFirst = f.attempts.length > 1 || f.attempts[0]?.verdict !== "viable";
    return step("feasibility", "report", { tab: "home", route: { name: rejectedFirst ? "review" : "report" } });
  }
  if (s.appStage === "not_started") return step("plan", "plan", { tab: "plan" });
  if (s.appStage === "rejected") return step("application", "rejected", { tab: "home", route: { name: "application" } }, "clay");
  if (s.appStage !== "disbursed") return step("application", "application", { tab: "home", route: { name: "application" } });
  if (!s.smsConsent) return step("launch", "consent", { tab: "business" });
  if (view.warning && !s.interventionChosen) return step("monitoring", "warning", { tab: "home", route: { name: "warning" } }, "clay");
  if (s.interventionChosen && !s.followUp) return step("monitoring", "followup", { tab: "home", route: { name: "outcome" } });
  return step("monitoring", "monitoring", { tab: "home", route: { name: "monitoring" } });
}
