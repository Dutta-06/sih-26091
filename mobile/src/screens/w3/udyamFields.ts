import { useMemo } from "react";
import type { Field as CoreField } from "../../core/documents";
import type { ProfileInput } from "../../core/types";
import { useI18n } from "../../i18n";
import { rupees } from "../../lib/format";
import { useStore } from "../../state/store";
import { useApplicant, type Applicant } from "../g3/applicant";
import { placeOf } from "../g3/model";
import { activityDisplay } from "../g3/util";

export type FieldId = "aadhaar" | "name" | "nic" | "investment" | "turnover" | "ifsc" | "category" | "women";
export type Section = "identity" | "enterprise" | "money" | "bank";

export interface FieldOption {
  value: string;
  label: string;
}

export interface Field {
  id: FieldId;
  section: Section;
  source: "profile" | "plan" | "ask";
  /** "otp": Aadhaar + simulated OTP; "auto": confirm a computed value; "text": validated input; "choice": chips */
  kind: "otp" | "auto" | "text" | "choice";
  /** auto-filled value (profile / plan / catalog) */
  auto?: string;
  hint?: string;
  options?: FieldOption[];
  /** text fields: core validator and suggestions derived from the case */
  validator?: CoreField;
  suggestions?: string[];
}

/** Lets a pushed route open a specific tab (routes carry no params). */
export const udyamTab = { initial: "register" as "register" | "form" };

const CATS: NonNullable<ProfileInput["category"]>[] = ["sc", "st", "obc", "general"];

/**
 * Udyam registration fields, pre-filled from the computed case: NIC from the catalog nic_class, investment =
 * the plan's capital expenditure (budget minus working capital), turnover = the preview's annual revenue,
 * category / women-owned from the profile, IFSC from the application form (TDD 6.5).
 */
export function useUdyamFields(): Field[] {
  const { t, pick } = useI18n();
  const { state, view } = useStore();
  const [applicant] = useApplicant();
  const { activityId, financial } = view;
  const place = placeOf(view);
  const cat = state.profile.category;
  const hasIfsc = !!applicant.ifsc;
  const fullName = applicant.fullName ?? "";

  return useMemo(() => {
    if (!activityId || !financial) return [];
    const act = activityDisplay(activityId);
    const actName = pick(act.name);
    const firstName = fullName.split(" ")[0];
    const placeName = place ? pick(place.village ?? place.district.name) : "";
    const suggestions = [...new Set([firstName && `${firstName} ${actName}`, placeName && `${placeName} ${actName}`].filter(Boolean) as string[])];
    const fields: Field[] = [
      { id: "aadhaar", section: "identity", source: "ask", kind: "otp" },
      { id: "name", section: "enterprise", source: "ask", kind: "text", validator: "enterprise_name", suggestions },
      { id: "nic", section: "enterprise", source: "plan", kind: "auto", auto: `${act.nic} · ${act.category}`, hint: t("g3.udyam.nicHint", { activity: actName }) },
      { id: "investment", section: "money", source: "plan", kind: "auto", auto: rupees(financial.plan.capex), hint: t("g3.udyam.investmentHint", { items: financial.budget.length - 1 }) },
      { id: "turnover", section: "money", source: "plan", kind: "auto", auto: rupees(financial.preview.annualRevenue), hint: t("udyam.q.turnover.hint") },
      hasIfsc
        ? { id: "ifsc", section: "bank", source: "profile", kind: "auto", auto: applicant.ifsc!, hint: applicant.accountMasked ? t("g3.udyam.account", { v: applicant.accountMasked }) : undefined }
        : { id: "ifsc", section: "bank", source: "ask", kind: "text", validator: "ifsc_code" },
      cat
        ? { id: "category", section: "identity", source: "profile", kind: "auto", auto: t(`udyam.cat.${cat}`) }
        : { id: "category", section: "identity", source: "ask", kind: "choice", options: CATS.map((c) => ({ value: c, label: t(`udyam.cat.${c}`) })) },
      { id: "women", section: "identity", source: "profile", kind: "auto", auto: t(state.profile.womanOwned ? "udyam.yes" : "udyam.no"), hint: t("udyam.q.women.hint") },
    ];
    return fields;
  }, [t, pick, activityId, financial, place, cat, hasIfsc, applicant.ifsc, applicant.accountMasked, fullName, state.profile.womanOwned]);
}

/** Text that appears in the form for a field and its answer. */
export function shownValue(f: Field, answer: string | undefined, t: (k: string, v?: Record<string, string | number>) => string, applicant: Applicant): string {
  if (f.id === "aadhaar") return applicant.aadhaarLast4 && answer ? t("g3.udyam.aadhaarVerified", { last4: applicant.aadhaarLast4 }) : "—";
  if (f.auto) return f.auto;
  if (f.kind === "choice") return f.options?.find((x) => x.value === answer)?.label ?? "—";
  return answer ?? "—";
}
