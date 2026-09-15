/**
 * Grievance classification and routing (port of module3_monitoring/grievance_engine.py): keyword classifier
 * (English + Hindi/Hinglish), static routing table to mentor ROLES, never named people.
 *
 * Response hours are an on-device addition (the backend has no SLA): repayment stress 24 h (a missed installment
 * compounds), supply delay and machinery breakdown 48 h (production stops), pricing and other issues 72 h.
 */
import { pyRe } from "./sms";
import type { GrievanceTicket, Msg, OutcomeRecord } from "./types";

type Issue = GrievanceTicket["issue"];

const KEYWORDS: [Exclude<Issue, "other">, string[]][] = [
  ["loan_repayment_stress", ["emi", "loan", "installment", "instalment", "repay", "repayment", "kist", "kisht",
    "karz", "karza", "qarz", "udhaar", "bank notice", "किस्त", "कर्ज", "लोन"]],
  ["machinery_breakdown", ["machine", "machinery", "broken", "breakdown", "repair", "motor", "not working",
    "kharab", "kharaab", "toot", "tuta", "band pad", "खराब", "मशीन", "टूट"]],
  ["pricing_collapse", ["price", "prices", "rate", "rates", "bhav", "daam", "dam", "keemat", "sasta",
    "no buyers", "not selling", "nahi bik", "mandi rate", "भाव", "दाम", "कीमत"]],
  ["supply_delay", ["delay", "delayed", "late", "not delivered", "shortage", "supply", "supplier", "stock",
    "raw material", "feed", "chara", "maal", "der", "deri", "nahi aaya", "nahi mila", "देरी", "चारा", "माल"]],
];

interface Route {
  role: string; // English role name (backend text), for parity
  roleKey: string;
  intervention: OutcomeRecord["intervention_type"];
  actionKey: string;
  hours: number;
  sectorRoles?: Record<string, [string, string]>;
}

const DIC: [string, string] = ["DIC / MSME facilitation desk", "c3.role.dic_desk"];
const LIVESTOCK: [string, string] = ["District livestock extension officer", "c3.role.livestock_officer"];
export const ROUTING: Record<Issue, Route> = {
  supply_delay: { role: DIC[0], roleKey: DIC[1], intervention: "supply_chain_change", actionKey: "c3.griev.action.supply_delay", hours: 48,
    sectorRoles: { animal_husbandry: LIVESTOCK, fisheries: ["District fisheries extension officer", "c3.role.fisheries_officer"] } },
  pricing_collapse: { role: DIC[0], roleKey: DIC[1], intervention: "pricing_adjustment", actionKey: "c3.griev.action.pricing_collapse", hours: 72,
    sectorRoles: { agri_allied: ["Block agriculture extension officer (ATMA)", "c3.role.atma_officer"] } },
  machinery_breakdown: { role: DIC[0], roleKey: DIC[1], intervention: "mentor_outreach", actionKey: "c3.griev.action.machinery_breakdown", hours: 48,
    sectorRoles: { animal_husbandry: LIVESTOCK } },
  loan_repayment_stress: { role: "SCA loan officer", roleKey: "c3.role.sca_loan_officer", intervention: "repayment_counselling", actionKey: "c3.griev.action.loan_repayment_stress", hours: 24 },
  other: { role: "Block-level enterprise mentor (SCA field staff)", roleKey: "c3.role.block_mentor", intervention: "mentor_outreach", actionKey: "c3.griev.action.other", hours: 72 },
};

const isAscii = (s: string) => /^[\x00-\x7f]*$/.test(s);
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function count(text: string, kw: string): number {
  if (!isAscii(kw)) return text.split(kw).length - 1;
  return [...text.matchAll(pyRe(`\\b${escapeRe(kw)}\\b`, "g"))].length;
}

export function classifyIssue(text: string): Issue {
  const lowered = (text ?? "").toLowerCase();
  let best: Issue = "other";
  let bestScore = 0;
  for (const [issue, kws] of KEYWORDS) {
    const score = kws.reduce((a, kw) => a + count(lowered, kw), 0);
    if (score > bestScore) [best, bestScore] = [issue, score]; // strict > keeps dict order on ties
  }
  return best;
}

export function routeTicket(issue: Issue, sector?: string | null): { routedTo: Msg; responseHours: number; intervention: OutcomeRecord["intervention_type"]; action: Msg; roleEn: string } {
  const entry = ROUTING[issue] ?? ROUTING.other;
  const [roleEn, roleKey] = entry.sectorRoles?.[sector ?? ""] ?? [entry.role, entry.roleKey];
  return { routedTo: { key: roleKey }, responseHours: entry.hours, intervention: entry.intervention, action: { key: entry.actionKey }, roleEn };
}

/** A new ticket with a deterministic id (FNV-1a of text + timestamp). */
export function createTicket(text: string, at: string, sector?: string | null): GrievanceTicket {
  const issue = classifyIssue(text);
  const { routedTo, responseHours } = routeTicket(issue, sector);
  let h = 0x811c9dc5;
  for (const ch of `${at}|${text}`) h = Math.imul(h ^ ch.codePointAt(0)!, 0x01000193) >>> 0;
  return { id: `TKT-${h.toString(16).toUpperCase().padStart(8, "0")}`, issue, text, routedTo, responseHours, status: "mentor_assigned", at };
}
