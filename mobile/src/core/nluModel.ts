/**
 * Combining the on-device message model with the rule-based reader (core/nlu.ts).
 *
 * The rules stay authoritative where they are exact: amounts are parsed by extractCapital, business phrases are mapped
 * to catalog ids by the lexicons, places must resolve in the district / village tables. The model contributes what
 * rules miss: it finds the name, place, amount, business and reason wherever they sit in a free sentence, and an
 * intent for messages with no cue words. A model span is only used when the rules can turn it into a valid value.
 */
import { resolveLocation } from "./geo";
import { extract, extractCapital } from "./nlu";
import type { Extraction, Intent, Slot } from "./types";

export type SpanLabel = "NAME" | "LOC" | "AMT" | "ACT" | "REASON";

export interface ModelReading {
  intent: string; // provide_info | greeting | raise_grievance | … | other
  intentConfidence: number;
  spans: { label: SpanLabel; text: string; confidence: number }[];
}

const INTENT_MIN = 0.7;
const OVERRIDE_MIN = 0.9;
const SPAN_MIN = 0.55;
/** Rule intents triggered by explicit cue words are kept even when the model disagrees. */
const PRECISE: Intent[] = ["raise_grievance", "new_case", "change_language"];

const toIntent = (s: string): Intent => (s === "other" ? "unknown" : (s as Intent));

const best = (m: ModelReading | null, label: SpanLabel) =>
  m?.spans.filter((s) => s.label === label && s.confidence >= SPAN_MIN).sort((a, b) => b.confidence - a.confidence)[0]?.text.trim();

export function mergeExtraction(rules: Extraction, m: ModelReading | null, pending: Slot | null): { ext: Extraction; name?: string; fromModel: string[] } {
  const ext: Extraction = { ...rules };
  const fromModel: string[] = [];
  if (!m) return { ext, fromModel };

  const loc = best(m, "LOC");
  if (loc) {
    const ruleResolves = !!ext.locationText && resolveLocation(ext.locationText, null).candidates.length > 0;
    if (!ruleResolves && resolveLocation(loc, null).candidates.length > 0) {
      ext.locationText = loc;
      fromModel.push("location");
    }
  }
  const amt = best(m, "AMT");
  if (ext.capital === undefined && amt && !(/^\s*[1-9]\d{5}\s*$/.test(amt) && ext.locationText?.trim() === amt.trim())) {
    const v = extractCapital(amt, true);
    if (v !== null) {
      ext.capital = v;
      fromModel.push("capital");
    }
  }
  const act = best(m, "ACT");
  if (!ext.activityId && act) {
    const id = extract(act, "activity").activityId;
    if (id) {
      ext.activityId = id;
      fromModel.push("activity");
    }
  }
  const reason = best(m, "REASON");
  if (!ext.reason && reason && reason.length >= 4 && pending !== "location" && pending !== "capital") {
    ext.reason = reason.replace(/^(because|since|kyunki|kyonki|क्योंकि|কারণ|ஏனென்றால்|ఎందుకంటే|ਕਿਉਂਕਿ|ಏಕೆಂದರೆ|कारण)\s*/iu, "");
    fromModel.push("reason");
  }
  const rawName = best(m, "NAME");
  const name = rawName && rawName.length <= 40 && rawName !== ext.locationText && !/\d/.test(rawName) ? rawName : undefined;
  if (name) fromModel.push("name");
  return { ext, name, fromModel };
}

export function mergeIntent(rule: Intent, m: ModelReading | null, ext: Extraction): Intent {
  if (!m) return rule;
  const modelIntent = toIntent(m.intent);
  if (PRECISE.includes(rule) || modelIntent === rule) return rule;
  const hasSlots = ext.capital !== undefined || !!ext.activityId || !!ext.locationText || !!ext.reason;
  if (rule === "unknown" && m.intentConfidence >= INTENT_MIN) return modelIntent === "provide_info" && !hasSlots ? rule : modelIntent;
  if (rule === "provide_info" && !hasSlots && modelIntent !== "provide_info" && m.intentConfidence >= OVERRIDE_MIN) return modelIntent;
  if (rule === "greeting" && modelIntent === "provide_info" && hasSlots) return "provide_info";
  return rule;
}
