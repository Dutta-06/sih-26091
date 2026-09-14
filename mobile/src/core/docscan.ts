/**
 * Reading a scanned document on the device. The phone's text recognition (ML Kit, bundled model) returns lines of
 * text; this module decides what kind of document it is, pulls out the fields the application needs, repairs
 * common recognition mix-ups (O/0, I/1, S/5, B/8, Z/2) where the field format fixes the character class, and checks
 * the result: format and checksums (Verhoeff for Aadhaar), the document matching the checklist item, and the name
 * matching the applicant. Only masked values leave this module; the raw text is not stored.
 */
import { maskAadhaar, maskAccount, verhoeffValid } from "./documents";
import type { Msg } from "./types";

export type DocKind = "aadhaar" | "pan" | "voter_id" | "bank_passbook" | "udyam" | "ration_card" | "electricity_bill" | "caste_certificate" | "other";

export interface ScanFields {
  name?: string;
  dob?: string; // DD/MM/YYYY or YYYY
  gender?: "female" | "male";
  aadhaarMasked?: string;
  aadhaarChecksumOk?: boolean;
  pan?: string;
  epic?: string;
  ifsc?: string;
  accountMasked?: string;
  pincode?: string;
  udyam?: string;
}

export interface ScanResult {
  kind: DocKind;
  /** 0-1: share of this kind's signals that were found. */
  confidence: number;
  fields: ScanFields;
  /** Problems to show before accepting the scan. */
  issues: Msg[];
  /** The document fits the checklist item it was scanned for. */
  matchesRequest: boolean;
}

const SIGNALS: Record<Exclude<DocKind, "other">, RegExp[]> = {
  aadhaar: [/aadhaa?r|आधार/i, /unique identification|uidai|भारतीय विशिष्ट/i, /government of india|भारत सरकार/i, /\b\d{4}\s\d{4}\s\d{4}\b/, /\b(dob|date of birth|year of birth)\b|जन्म/i],
  pan: [/income\s*tax/i, /permanent\s*account\s*number|आयकर/i, /\b[A-Z0-9]{5}[0-9OISBZ]{4}[A-Z0-9]\b/, /govt\.?\s*of\s*india/i],
  voter_id: [/election\s*commission|निर्वाचन/i, /elector|electoral|मतदाता/i, /\b[A-Z]{3}[0-9OISBZ]{7}\b/, /identity\s*card|पहचान पत्र/i],
  bank_passbook: [/\bifsc\b/i, /\b[A-Z]{4}[0O][A-Z0-9]{6}\b/, /a\/?c\.?\s*no|account\s*(no|number)|खाता/i, /passbook|savings|branch|cif|पासबुक|शाखा/i, /\bbank\b|बैंक/i],
  udyam: [/udyam/i, /UDYAM-[A-Z]{2}-\d{2}-\d{7}/i, /micro|small|medium|msme|enterprise|उद्यम/i],
  ration_card: [/ration\s*card|राशन\s*कार्ड/i, /food\s*(and|&)\s*civil\s*supplies|खाद्य/i, /\b(aay|phh|bpl|apl)\b/i],
  electricity_bill: [/electricity|बिजली|vidyut|विद्युत/i, /consumer\s*(no|number)|उपभोक्ता/i, /\bkwh\b|units|यूनिट/i, /bill\s*(date|amount|no)/i],
  caste_certificate: [/caste\s*certificate|जाति\s*प्रमाण/i, /scheduled\s*(caste|tribe)|other backward|अनुसूचित|पिछड़ा/i, /tehsildar|तहसीलदार|sdm/i],
};

/** Checklist item → document kinds that satisfy it (items not listed accept any readable document). */
export const ACCEPTS: Record<string, DocKind[]> = {
  identity_proof: ["aadhaar", "voter_id", "pan"],
  address_proof: ["aadhaar", "voter_id", "ration_card", "electricity_bill"],
  bank_passbook: ["bank_passbook"],
  udyam_certificate: ["udyam"],
  caste_or_category_certificate: ["caste_certificate"],
};

const LETTER: Record<string, string> = { "0": "O", "1": "I", "5": "S", "8": "B", "2": "Z" };
const DIGIT: Record<string, string> = { O: "0", Q: "0", D: "0", I: "1", L: "1", S: "5", B: "8", Z: "2" };
const asLetters = (s: string) => s.replace(/[01582]/g, (c) => LETTER[c]);
const asDigits = (s: string) => s.replace(/[OQDILSBZ]/g, (c) => DIGIT[c]);

/** PAN: 5 letters, 4 digits, 1 letter — repaired by position. */
export function findPan(text: string): string | undefined {
  for (const m of text.toUpperCase().matchAll(/\b([A-Z0-9]{5})([A-Z0-9]{4})([A-Z0-9])\b/g)) {
    const pan = asLetters(m[1]) + asDigits(m[2]) + asLetters(m[3]);
    if (/^[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]$/.test(pan)) return pan;
  }
  return undefined;
}

/** IFSC: 4 letters, 0, 6 alphanumerics. */
export function findIfsc(text: string): string | undefined {
  const labelled = /ifsc\s*(code)?\s*[:.\-]?\s*([A-Z0-9]{11})\b/i.exec(text);
  const candidates = [labelled?.[2], ...[...text.toUpperCase().matchAll(/\b([A-Z0-9]{4})([0O])([A-Z0-9]{6})\b/g)].map((m) => m[0])].filter(Boolean) as string[];
  for (const c of candidates) {
    const u = c.toUpperCase();
    const ifsc = asLetters(u.slice(0, 4)) + "0" + u.slice(5);
    if (/^[A-Z]{4}0[A-Z0-9]{6}$/.test(ifsc)) return ifsc;
  }
  return undefined;
}

function findAadhaar(text: string): { digits: string; ok: boolean } | undefined {
  const found = [...text.matchAll(/\b([2-9OISBZ][0-9OISBZ]{3})[\s-]?([0-9OISBZ]{4})[\s-]?([0-9OISBZ]{4})\b/g)].map((m) => asDigits(m[1] + m[2] + m[3]));
  const valid = found.find((d) => /^[2-9]\d{11}$/.test(d) && verhoeffValid(d));
  if (valid) return { digits: valid, ok: true };
  const shaped = found.find((d) => /^[2-9]\d{11}$/.test(d));
  return shaped ? { digits: shaped, ok: false } : undefined;
}

function findAccount(text: string): string | undefined {
  const labelled = /(?:a\/?c\.?|account)\s*(?:no\.?|number)?\s*[:.\-]?\s*([0-9OISB][0-9OISB\s]{7,20}[0-9])/i.exec(text);
  const raw = labelled ? asDigits(labelled[1].toUpperCase()).replace(/\s/g, "") : undefined;
  if (raw && raw.length >= 9 && raw.length <= 18) return raw;
  const bare = [...text.matchAll(/\b\d{11,16}\b/g)].map((m) => m[0]).find((d) => !/^[2-9]\d{11}$/.test(d) || !verhoeffValid(d));
  return bare;
}

const NAME_LABEL = /^(?:name|नाम|customer\s*name|account\s*holder|a\/c\s*holder|elector'?s?\s*name)\s*[:.\-]?\s*(.*)$/i;
const NOT_NAME = /government|india|income|tax|department|permanent|account|number|bank|branch|election|commission|card|father|husband|address|dob|birth|male|female|signature|ifsc|udyam|certificate|भारत|सरकार|पिता|पति|जन्म|पता/i;

const cleanName = (s: string) => s.replace(/[^A-Za-zऀ-ॿ .]/g, " ").replace(/\s+/g, " ").trim();
const looksLikeName = (s: string) => {
  const c = cleanName(s);
  const words = c.split(" ").filter(Boolean);
  return words.length >= 1 && words.length <= 4 && c.length >= 3 && c.length <= 40 && !NOT_NAME.test(c) && /[A-Za-zऀ-ॿ]{2}/.test(c);
};
const titleCase = (s: string) => s.replace(/\b([A-Za-z])([A-Za-z]*)/g, (_, a: string, b: string) => a.toUpperCase() + b.toLowerCase());

function findName(lines: string[], kind: DocKind): string | undefined {
  for (let i = 0; i < lines.length; i++) {
    const m = NAME_LABEL.exec(lines[i].trim());
    if (!m) continue;
    const same = cleanName(m[1]);
    if (same && looksLikeName(same)) return titleCase(same);
    const next = lines[i + 1];
    if (next && looksLikeName(next)) return titleCase(cleanName(next));
  }
  const latin = (s: string) => /^[A-Za-z .]+$/.test(cleanName(s)) && looksLikeName(s);
  if (kind === "aadhaar") {
    // Aadhaar front: the English name sits on the line just above the date of birth
    const dobAt = lines.findIndex((l) => /\b(dob|date of birth|year of birth)\b|जन्म/i.test(l));
    for (let i = dobAt - 1; i >= Math.max(0, dobAt - 3); i--) if (latin(lines[i])) return titleCase(cleanName(lines[i]));
  }
  if (kind === "pan") {
    // PAN card: the first all-capitals name after the department header, before the father's name
    const start = lines.findIndex((l) => /govt|income\s*tax/i.test(l));
    for (let i = start + 1; i < lines.length && i <= start + 4; i++) if (latin(lines[i]) && lines[i] === lines[i].toUpperCase()) return titleCase(cleanName(lines[i]));
  }
  return undefined;
}

/** Share of name tokens that match (edit distance ≤ 1 per token, initials match a same-letter token). */
export function nameSimilarity(a: string, b: string): number {
  const tokens = (s: string) => s.toLowerCase().replace(/[^a-zऀ-ॿ ]/g, " ").split(/\s+/).filter(Boolean);
  const ta = tokens(a);
  const tb = tokens(b);
  if (!ta.length || !tb.length) return 0;
  const close = (x: string, y: string) => {
    if (x === y) return true;
    if (x.length === 1 || y.length === 1) return x[0] === y[0];
    if (Math.abs(x.length - y.length) > 1) return false;
    let i = 0;
    let j = 0;
    let edits = 0;
    while (i < x.length && j < y.length) {
      if (x[i] === y[j]) { i++; j++; continue; }
      if (++edits > 1) return false;
      if (x.length > y.length) i++;
      else if (y.length > x.length) j++;
      else { i++; j++; }
    }
    return edits + (x.length - i) + (y.length - j) <= 1;
  };
  const [short, long] = ta.length <= tb.length ? [ta, tb] : [tb, ta];
  return short.filter((t) => long.some((u) => close(t, u))).length / short.length;
}

export function classify(text: string): { kind: DocKind; confidence: number } {
  let best: { kind: DocKind; confidence: number; hits: number } = { kind: "other", confidence: 0, hits: 0 };
  for (const [kind, signals] of Object.entries(SIGNALS) as [Exclude<DocKind, "other">, RegExp[]][]) {
    const hits = signals.filter((re) => re.test(text)).length;
    const confidence = hits / signals.length;
    if (hits >= 2 && (confidence > best.confidence || (confidence === best.confidence && hits > best.hits))) best = { kind, confidence, hits };
  }
  // An Udyam number or a valid Aadhaar number is decisive on its own
  if (/UDYAM-[A-Z]{2}-\d{2}-\d{7}/i.test(text)) return { kind: "udyam", confidence: Math.max(best.kind === "udyam" ? best.confidence : 0, 0.67) };
  return { kind: best.kind, confidence: Math.round(best.confidence * 100) / 100 };
}

/** Read recognised lines for checklist item `docId`; `applicantName` (if known) is compared with the name found. */
export function readDocument(lines: string[], docId: string, applicantName?: string): ScanResult {
  const text = lines.join("\n");
  const { kind, confidence } = classify(text);
  const fields: ScanFields = {};
  const issues: Msg[] = [];

  const name = findName(lines, kind);
  if (name) fields.name = name;
  const dob = /(?:dob|date of birth|जन्म तिथि|जन्म)\s*[:/\-]?\s*(\d{2}[/\-.]\d{2}[/\-.]\d{4})/i.exec(text) ?? /\b(\d{2}\/\d{2}\/\d{4})\b/.exec(text);
  const yob = /(?:year of birth|जन्म वर्ष)\s*[:/\-]?\s*(\d{4})/i.exec(text);
  if (dob) fields.dob = dob[1].replace(/[-.]/g, "/");
  else if (yob) fields.dob = yob[1];
  if (/\bfemale\b|महिला/i.test(text)) fields.gender = "female";
  else if (/\bmale\b|पुरुष/i.test(text)) fields.gender = "male";

  if (kind === "aadhaar" || kind === "other") {
    const a = findAadhaar(text);
    if (a) {
      fields.aadhaarMasked = maskAadhaar(a.digits);
      fields.aadhaarChecksumOk = a.ok;
      if (!a.ok) issues.push({ key: "c3.scan.issue.aadhaarChecksum" });
    }
  }
  const pan = findPan(text);
  if (pan && (kind === "pan" || kind === "other" || kind === "bank_passbook")) fields.pan = pan;
  const epic = /\b([A-Z]{3})([0-9OISBZ]{7})\b/.exec(text.toUpperCase());
  if (epic && kind === "voter_id") fields.epic = epic[1] + asDigits(epic[2]);
  if (kind === "bank_passbook" || kind === "other") {
    const ifsc = findIfsc(text);
    if (ifsc) fields.ifsc = ifsc;
    const acct = findAccount(text);
    if (acct) fields.accountMasked = maskAccount(acct);
  }
  const pin = /(?:pin(?:\s*code)?|पिन)\s*[:.\-]?\s*([1-9]\d{2}\s?\d{3})\b/i.exec(text) ?? /\b([1-9]\d{5})\b(?!\d)/.exec(lines.slice(-4).join(" "));
  if (pin && kind !== "pan") fields.pincode = pin[1].replace(/\s/g, "");
  const udyam = /UDYAM-?\s*([A-Z]{2})-?\s*(\d{2})-?\s*(\d{7})/i.exec(text);
  if (udyam) fields.udyam = `UDYAM-${udyam[1].toUpperCase()}-${udyam[2]}-${udyam[3]}`;

  const accepts = ACCEPTS[docId];
  const matchesRequest = !accepts || accepts.includes(kind);
  if (kind === "other" && lines.join("").replace(/\s/g, "").length < 20) issues.unshift({ key: "c3.scan.issue.unreadable" });
  else if (!matchesRequest) issues.unshift({ key: "c3.scan.issue.wrongDoc", vars: { found: kind } });

  const expected: Partial<Record<DocKind, (keyof ScanFields)[]>> = {
    aadhaar: ["name", "aadhaarMasked"], pan: ["name", "pan"], bank_passbook: ["ifsc", "accountMasked"], udyam: ["udyam"], voter_id: ["epic"],
  };
  const missing = (expected[kind] ?? []).filter((f) => !fields[f]);
  if (missing.length) issues.push({ key: "c3.scan.issue.missing", vars: { fields: missing.join(",") } });

  if (applicantName && fields.name && nameSimilarity(applicantName, fields.name) < 0.5) {
    issues.push({ key: "c3.scan.issue.nameMismatch", vars: { found: fields.name, expected: applicantName } });
  }
  return { kind, confidence, fields, issues, matchesRequest };
}
