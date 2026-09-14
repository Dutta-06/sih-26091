/**
 * Documentation assistance (port of module2_financial/documentation_agent.py): document checklist semantics
 * and deterministic field validators, plus an Aadhaar Verhoeff checksum and masking helpers.
 */
import type { Bi } from "../i18n";
import type { DocStatus, FinancialResult, Msg, ProfileInput } from "./types";

export const BASE_DOCUMENTS: Record<string, { aliases: string[]; name: Bi }> = {
  identity_proof: { aliases: ["aadhaar", "identity", "voter id", "voter card"], name: { en: "Identity proof (Aadhaar or voter ID)", hi: "पहचान पत्र (आधार या वोटर आईडी)" } },
  address_proof: { aliases: ["address", "ration card", "electricity bill", "domicile"], name: { en: "Address proof", hi: "पते का प्रमाण" } },
  caste_or_category_certificate: { aliases: ["caste", "category certificate", "sc certificate", "st certificate", "obc"], name: { en: "Caste / category certificate", hi: "जाति / वर्ग प्रमाण पत्र" } },
  bank_passbook: { aliases: ["passbook", "bank statement", "cancelled cheque", "bank account"], name: { en: "Bank passbook or cancelled cheque", hi: "बैंक पासबुक या रद्द चेक" } },
  project_quotation: { aliases: ["quotation", "estimate", "proforma", "project report"], name: { en: "Project report and quotations", hi: "प्रोजेक्ट रिपोर्ट और कोटेशन" } },
  land_or_premises_proof: { aliases: ["land", "khatauni", "lease", "rent agreement", "premises", "noc"], name: { en: "Land or premises proof", hi: "ज़मीन या जगह का प्रमाण" } },
  udyam_certificate: { aliases: ["udyam"], name: { en: "Udyam registration certificate", hi: "उद्यम पंजीकरण प्रमाण पत्र" } },
};

/** Hindi names for list items of data/scheme_guidelines/required_documents.md (other text falls back to English). */
const KNOWN_HI: Record<string, string> = {
  "recent passport-size photographs": "हाल की पासपोर्ट साइज़ फ़ोटो",
  "income certificate": "आय प्रमाण पत्र",
  "self-help group membership certificate, if applying through a group": "स्वयं सहायता समूह सदस्यता प्रमाण पत्र (समूह से आवेदन पर)",
  "licences applicable to the activity": "काम से जुड़े लाइसेंस",
  "guarantor or security documents as asked by the lender": "ऋणदाता द्वारा माँगे गए गारंटर या ज़मानत के कागज़",
};

const CATEGORY_CERT = new Set(["sc", "st", "obc"]);
const slug = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");

/** Base documents (category certificate only for SC/ST/OBC) merged with the scheme-required documents. */
export function requiredDocuments(input: ProfileInput, financial: Pick<FinancialResult, "policy"> | null): { id: string; name: Bi }[] {
  const docs = Object.entries(BASE_DOCUMENTS)
    .filter(([id]) => id !== "caste_or_category_certificate" || CATEGORY_CERT.has(input.category ?? ""))
    .map(([id, d]) => ({ id, name: d.name, aliases: d.aliases }));
  const allAliases = Object.values(BASE_DOCUMENTS).flatMap((d) => d.aliases); // as the backend: any base alias absorbs it
  for (const name of financial?.policy.documents ?? []) {
    const lowered = name.toLowerCase();
    if (allAliases.some((a) => lowered.includes(a))) continue;
    // "... if applying through a group": only asked of SHG members (backend lists it for every micro-finance case)
    if (lowered.includes("self-help group") && !input.shgMember) continue;
    const id = slug(name);
    if (!docs.some((d) => d.id === id)) docs.push({ id, name: { en: name, hi: KNOWN_HI[lowered] ?? name }, aliases: [lowered] });
  }
  return docs.map(({ id, name }) => ({ id, name }));
}

export interface ChecklistItem {
  id: string;
  name: Bi;
  status: DocStatus;
}

/** Status per document (unknown → missing); `complete` mirrors application_tracker.checklist_complete. */
export function checklist(docs: { id: string; name: Bi }[], available: Record<string, DocStatus>) {
  const items: ChecklistItem[] = docs.map((d) => ({ ...d, status: available[d.id] ?? "missing" }));
  return {
    items,
    complete: items.length > 0 && items.every((i) => i.status === "complete"),
    outstanding: items.filter((i) => i.status !== "complete").map((i) => i.id),
  };
}

/* ------------------------------------------------------------------ validators */

export type Field =
  | "full_name" | "enterprise_name" | "residential_address" | "social_category" | "land_or_premises"
  | "phone_number" | "aadhaar_number" | "pan_number" | "ifsc_code" | "bank_account_number" | "pincode" | "amount"
  | "udyam_registration_number";

const D = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
  [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
  [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
];
const P = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
  [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1], [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
];
const INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9];

/** True when the digit string's last digit is a valid Verhoeff check digit (UIDAI uses Verhoeff for Aadhaar). */
export function verhoeffValid(digits: string): boolean {
  let c = 0;
  [...digits].reverse().forEach((ch, i) => (c = D[c][P[i % 8][Number(ch)]]));
  return c === 0;
}

/** Check digit to append to `digits` (used to build valid test numbers). */
export function verhoeffDigit(digits: string): number {
  let c = 0;
  [...digits].reverse().forEach((ch, i) => (c = D[c][P[(i + 1) % 8][Number(ch)]]));
  return INV[c];
}

export const maskAadhaar = (digits: string) => `XXXX-XXXX-${digits.slice(-4)}`;
export const maskAccount = (digits: string) => "X".repeat(Math.max(0, digits.length - 4)) + digits.slice(-4);

const digitsOnly = (v: string) => v.replace(/\D/g, "");
const err = (k: string): { ok: false; error: Msg } => ({ ok: false, error: { key: `c3.doc.err.${k}` } });

export function validateField(field: Field, raw: string): { ok: boolean; value?: string; error?: Msg } {
  const value = raw ?? "";
  switch (field) {
    case "phone_number": {
      let d = digitsOnly(value);
      if (d.length === 12 && d.startsWith("91")) d = d.slice(2);
      return /^[6-9]\d{9}$/.test(d) ? { ok: true, value: d } : err("phone");
    }
    case "aadhaar_number": {
      const d = digitsOnly(value);
      if (!/^[2-9]\d{11}$/.test(d)) return err("aadhaar");
      return verhoeffValid(d) ? { ok: true, value: d } : err("aadhaar_checksum");
    }
    case "pan_number": {
      const p = value.replace(/ /g, "").toUpperCase();
      return /^[A-Z]{5}\d{4}[A-Z]$/.test(p) ? { ok: true, value: p } : err("pan");
    }
    case "ifsc_code": {
      const c = value.replace(/ /g, "").toUpperCase();
      return /^[A-Z]{4}0[A-Z0-9]{6}$/.test(c) ? { ok: true, value: c } : err("ifsc");
    }
    case "bank_account_number": {
      const d = digitsOnly(value);
      return d.length >= 9 && d.length <= 18 ? { ok: true, value: d } : err("account");
    }
    case "pincode": {
      const d = digitsOnly(value);
      return /^[1-9]\d{5}$/.test(d) ? { ok: true, value: d } : err("pincode");
    }
    case "amount": {
      const s = value.replace(/,/g, "").replace(/₹/g, "").replace(/Rs/g, "").trim();
      const n = /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(s) ? Number(s) : NaN;
      if (Number.isNaN(n)) return err("amount");
      return n >= 0 ? { ok: true, value: String(n) } : err("amount_negative");
    }
    case "udyam_registration_number": {
      const c = value.replace(/ /g, "").toUpperCase();
      return /^UDYAM-[A-Z]{2}-\d{2}-\d{7}$/.test(c) ? { ok: true, value: c } : err("udyam");
    }
    default: {
      const t = value.split(/\s+/).filter(Boolean).join(" ");
      return t.length >= 2 ? { ok: true, value: t } : err("blank");
    }
  }
}
