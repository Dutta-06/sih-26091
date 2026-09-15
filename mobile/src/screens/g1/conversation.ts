/**
 * Rule-based profiling conversation on the device — mirrors orchestrator/router.py: every message goes through
 * `extract(text, pendingSlot)` and `classifyIntent(text)`, extractions merge into the profile, and the next missing
 * slot is asked one at a time. Information given out of order (or several slots at once) is accepted.
 *
 * Messages store i18n keys + vars (never rendered prose) so they re-render in the conversation language.
 * Var conventions (rendered by w1/chatI18n): "@key" = i18n key · "~act:<id>" = activity name · a JSON string
 * starting with {"en" = bilingual text (place names from the data pack).
 *
 * Local decisions (documented):
 *  - Skills are only taken from a message while the skills question is open, or when the message has a skill cue
 *    ("I know…", "आता है"), so "I want handloom weaving" does not record weaving as a skill.
 *  - While skills / work place / category are asked, an activity keyword only changes the idea with a cue ("want", "start").
 *  - Assets are not extracted by core/nlu; a small keyword list below maps the chip options.
 *  - The optional name is kept on the user's chat message (vars.name); the store has no name field.
 */
import { rankActivities } from "../../core/discovery";
import { resolveLocation } from "../../core/geo";
import { affordableProjectCost, catalogActivity, MARGIN_SHARE, SCHEME_MAX_PROJECT_COST } from "../../core/intel/catalog";
import { classifyIntent, detectScript, extract } from "../../core/nlu";
import { mergeExtraction, mergeIntent, type ModelReading } from "../../core/nluModel";
import type { Intent, LocationCandidate, ProfileInput, Slot } from "../../core/types";
import { buildPlan } from "../../engine/finance";
import { rupees } from "../../lib/format";
import { uid, type CaseEvent, type ChatLang, type ChatMessage } from "../../state/store";

export const CORE_SLOTS: Slot[] = ["location", "capital", "activity", "reason", "skills", "premises", "category"];
export type PendingSlot = Slot | "name" | "location_choice";

export type JumpIntent = "grievance" | "application" | "scheme" | "monitoring" | "community" | "languages" | "noViable" | "report" | "review" | "plan";
const INTENT_JUMP: Partial<Record<Intent, JumpIntent>> = {
  raise_grievance: "grievance",
  application_status: "application",
  scheme_inquiry: "scheme",
  monitoring: "monitoring",
  community: "community",
  change_language: "languages",
};

export const ASSET_OPTIONS = ["foot_pedal_machine", "electric_machine", "cattle", "none"] as const;
const ASSET_WORDS: [string, RegExp][] = [
  ["foot_pedal_machine", /pedal|paddle|पैर वाली|पैडल/iu],
  ["electric_machine", /electric|motor machine|बिजली की मशीन|इलेक्ट्रिक/iu],
  ["cattle", /\b(cow|cows|buffalo|cattle|goats?)\b|गाय|भैंस|बकरी/iu],
];
const SKILL_CUE = /\b(know|skill|skills|can do|good at|experience|trained|expert)\b|आता|आती|जानत|हुनर|hunar|aata|aati|कौशल/iu;
const ACTIVITY_CUE = /(want|start|open|business|plan to|instead)|शुरू|चाहत|धंधा|व्यवसाय|dhanda|shuru/iu;
const NONE = /^\s*(none|no|nothing|nope|nahi|nahin|kuch nahi|कुछ नहीं|कोई नहीं|नहीं|না|இல்லை|काही नाही)\s*[.!।]?\s*$/iu;
const NAME_PREFIX = /^(?:hi|hello|namaste|नमस्ते)?[\s,!]*(?:my name is|i am|i'm|call me|this is|mera naam|मेरा नाम|मैं)\s+/iu;
const NAME_SUFFIX = /\s+(?:hai|hoon|hun|है|हूँ|हूं)\s*[.!।]?$/iu;

/* ------------------------------------------------------------------ helpers */

export const bi = (b: { en: string; hi: string }) => JSON.stringify({ en: b.en, hi: b.hi });
export const actVar = (id: string) => `~act:${id}`;
const a = (text: string, vars?: ChatMessage["vars"], card?: string): ChatMessage => ({ id: uid(), from: "assistant", text, ...(vars ? { vars } : {}), ...(card ? { card } : {}) });

/** Slots answered in chat (user messages carry vars.answered = "skills,premises"). */
export function answeredSlots(chat: ChatMessage[]): Set<string> {
  const out = new Set<string>();
  for (const m of chat) if (m.from === "user" && typeof m.vars?.answered === "string") m.vars.answered.split(",").filter(Boolean).forEach((s) => out.add(s));
  return out;
}

/** Name the user gave in chat, if any (latest wins). */
export function chatName(chat: ChatMessage[]): string | null {
  for (let i = chat.length - 1; i >= 0; i--) {
    const v = chat[i].vars?.name;
    if (chat[i].from === "user" && typeof v === "string" && v.trim()) return v.trim();
  }
  return null;
}

/** The place the case uses: the chosen candidate, or the only one. */
export function placeOf(profile: ProfileInput): LocationCandidate | null {
  if (!profile.locationText.trim()) return null;
  const r = resolveLocation(profile.locationText, profile.locationCode);
  return r.chosen ?? (r.candidates.length === 1 ? r.candidates[0] : null);
}

export function missingSlots(profile: ProfileInput, answered: Set<string>): Slot[] {
  const filled: Record<Slot, boolean> = {
    location: placeOf(profile) !== null,
    capital: profile.capital > 0,
    activity: profile.activityId !== null,
    reason: !!profile.reason,
    skills: profile.skills.length > 0 || answered.has("skills"),
    premises: profile.premises !== null || answered.has("premises"),
    category: profile.category !== null || answered.has("category"),
  };
  return CORE_SLOTS.filter((s) => !filled[s]);
}

export const profileComplete = (profile: ProfileInput, chat: ChatMessage[]) => missingSlots(profile, answeredSlots(chat)).length === 0;
export const profileStarted = (profile: ProfileInput) =>
  profile.capital > 0 || !!profile.locationText || profile.activityId !== null || !!profile.reason || profile.skills.length > 0 || profile.premises !== null || profile.category !== null;

/** Stable signature of the inputs the analysis depends on (verdict cards compare it). */
export function profileSig(p: ProfileInput): string {
  let h = 2166136261;
  for (const ch of JSON.stringify([p.capital, p.locationText, p.locationCode, p.activityId, p.reason, p.skills, p.premises, p.category, p.shgMember])) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return (h >>> 0).toString(36);
}

/** Top feasible options for the profile (discovery ranking), for suggestion chips. */
export function suggestedActivities(profile: ProfileInput, n = 3, exclude: string | null = null): string[] {
  const ranked = rankActivities(profile, placeOf(profile)).filter((r) => r.activityId !== exclude);
  const feasible = ranked.filter((r) => r.feasible);
  return (feasible.length ? feasible : profile.capital > 0 ? [] : ranked).slice(0, n).map((r) => r.activityId);
}

/* ------------------------------------------------------------------ turn engine */

export interface ConvInput {
  profile: ProfileInput;
  pendingSlot: string | null;
  chat: ChatMessage[];
  chatLang: ChatLang;
}

export interface ConvResult {
  /** vars for the user's own message (answered slots, name) */
  userVars: Record<string, string>;
  messages: ChatMessage[];
  profilePatch: Partial<ProfileInput>;
  pendingSlot: string | null;
  chatLang?: ChatLang;
  events: Omit<CaseEvent, "at">[];
  /** a core input changed: the previous analysis no longer describes this case */
  changedCore: boolean;
  reset?: boolean;
}

const askMessages = (slot: PendingSlot, profile: ProfileInput): ChatMessage[] => {
  if (slot === "activity" && profile.capital > 0) {
    const ids = suggestedActivities(profile, 3);
    return ids.length ? [a("u1.ask.activity"), a("u1.card.suggest", { ids: ids.join(",") }, "act_suggest")] : [a("u1.ask.activity")];
  }
  return [a(`u1.ask.${slot}`)];
};

/** Assistant messages for a newly stated location. */
function locationTurn(profile: ProfileInput): { messages: ChatMessage[]; code: string | null; pending: PendingSlot | null; confirmed: boolean } {
  const r = resolveLocation(profile.locationText, null);
  const query = profile.locationText.trim();
  if (r.candidates.length === 0) return { messages: [a("u1.loc.notFound", { query })], code: null, pending: "location", confirmed: false };
  if (r.candidates.length > 1) {
    return { messages: [a("u1.loc.choose", { n: r.candidates.length, query }), a("u1.card.locations", { query }, "loc_choice")], code: null, pending: "location_choice", confirmed: false };
  }
  return { messages: [confirmPlace(r.candidates[0])], code: r.candidates[0].lgd, pending: null, confirmed: true };
}

export function confirmPlace(c: LocationCandidate): ChatMessage {
  if (c.method === "village_table" && c.village && c.block && c.lgd?.startsWith("c")) return a("u1.loc.villageCensus", { village: bi(c.village), block: bi(c.block), district: bi(c.district.name) });
  if (c.method === "village_table" && c.village && c.block) return a("u1.loc.village", { village: bi(c.village), block: bi(c.block), district: bi(c.district.name), lgd: c.lgd ?? "" });
  if (c.method === "pincode" && c.village) return a("u1.loc.pincode", { office: bi(c.village), district: bi(c.district.name) });
  if (c.method === "district_table") return a("u1.loc.district", { district: bi(c.district.name) });
  return a("u1.loc.state", { state: bi(c.district.name) });
}

/** Explain the savings with engine numbers (profiling constraint when outside the scheme). */
function capitalTurn(capital: number): ChatMessage {
  const plan = buildPlan(capital);
  if (!plan.eligible) {
    return a("u1.cap.above", { capital: rupees(capital), project: rupees(capital / MARGIN_SHARE), max: rupees(SCHEME_MAX_PROJECT_COST) });
  }
  return a("u1.cap.ok", { capital: rupees(capital), project: rupees(plan.projectCost), loan: rupees(plan.loan), rate: ((plan.tier?.rate ?? 0) * 100).toFixed(1) });
}

/** Can the stated idea start with this capital? Suggest ranked options if not. */
function activityTurn(profile: ProfileInput, changed: boolean): ChatMessage[] {
  const act = profile.activityId ? catalogActivity(profile.activityId) : null;
  if (!act) return [];
  if (profile.capital <= 0) return changed ? [a("u1.act.noted", { idea: actVar(act.id) })] : [];
  const affordable = affordableProjectCost(profile.capital);
  if (act.min_project_cost > affordable) {
    const ids = suggestedActivities(profile, 3, act.id);
    const vars = { idea: actVar(act.id), min: rupees(act.min_project_cost), project: rupees(affordable), need: rupees(Math.ceil(act.min_project_cost * MARGIN_SHARE)) };
    return [a("u1.act.tooBig", vars), ...(ids.length ? [a("u1.card.suggest", { ids: ids.join(",") }, "act_suggest")] : [a("u1.act.noneFits")])];
  }
  return changed ? [a("u1.act.ok", { idea: actVar(act.id), min: rupees(act.min_project_cost), project: rupees(affordable) })] : [];
}

/**
 * Apply a profile patch (from extraction or a chip), acknowledge what changed with computed checks,
 * then ask the next missing slot or show the profile summary.
 */
export function advance(input: ConvInput, patch: Partial<ProfileInput>, answeredNow: string[], pre: ChatMessage[] = []): ConvResult {
  const before = input.profile;
  const profile = { ...before, ...patch };
  const messages = [...pre];
  const events: ConvResult["events"] = [];
  const answered = answeredSlots(input.chat);
  answeredNow.forEach((s) => answered.add(s));
  let pending: PendingSlot | null = null;
  let asked = false;

  const locChanged = patch.locationText !== undefined && patch.locationText !== before.locationText;
  if (locChanged) {
    const turn = locationTurn(profile);
    messages.push(...turn.messages);
    profile.locationCode = turn.code;
    patch = { ...patch, locationCode: turn.code };
    if (turn.pending) {
      pending = turn.pending;
      asked = true;
    }
    if (turn.confirmed) events.push({ type: "location_confirmed", data: { query: profile.locationText, lgd: turn.code } });
  } else if (patch.locationCode !== undefined && patch.locationCode !== before.locationCode) {
    const chosen = resolveLocation(profile.locationText, profile.locationCode).chosen;
    if (chosen) {
      messages.push(confirmPlace(chosen));
      events.push({ type: "location_confirmed", data: { query: profile.locationText, lgd: chosen.lgd } });
    }
  }

  const capChanged = patch.capital !== undefined && patch.capital !== before.capital;
  if (capChanged) messages.push(capitalTurn(profile.capital));
  const actChanged = patch.activityId !== undefined && patch.activityId !== before.activityId;
  if (actChanged || (capChanged && profile.activityId)) messages.push(...activityTurn(profile, actChanged));
  if (patch.reason !== undefined && patch.reason !== before.reason && !locChanged && !capChanged && !actChanged) messages.push(a("u1.reason.ok"));

  const keys = Object.keys(patch) as (keyof ProfileInput)[];
  const changedCore = keys.some((k) => JSON.stringify(patch[k]) !== JSON.stringify(before[k]));
  if (messages.length === pre.length && (changedCore || answeredNow.length)) messages.push(a("u1.noted"));

  if (!asked) {
    const missing = missingSlots(profile, answered);
    if (missing.length) {
      pending = missing[0];
      messages.push(...askMessages(pending, profile));
    } else if (changedCore || answeredNow.length) {
      messages.push(a("u1.summary"), a("u1.card.summary", undefined, "profile_summary"));
      pending = null;
    }
  }
  return { userVars: answeredNow.length ? { answered: answeredNow.join(",") } : {}, messages, profilePatch: patch, pendingSlot: pending, events, changedCore };
}

/** Re-ask whatever is pending (after an intent detour). */
function reask(input: ConvInput): ChatMessage[] {
  const p = input.pendingSlot as PendingSlot | null;
  if (!p) return [];
  if (p === "location_choice") return [a("u1.loc.pickAbove")];
  return askMessages(p, input.profile);
}

export function jumpMessages(jump: JumpIntent): ChatMessage[] {
  return [a(`u1.intent.${jump}`), a("u1.card.jump", { intent: jump }, "jump")];
}

const empty = (input: ConvInput, messages: ChatMessage[], extra: Partial<ConvResult> = {}): ConvResult => ({
  userVars: {}, messages, profilePatch: {}, pendingSlot: input.pendingSlot, events: [], changedCore: false, ...extra,
});

/** One user message through the rule pipeline. */
/** One user turn. `reading` is the on-device message model's reading of the text (null: rules only). */
export function respond(text: string, input: ConvInput, reading: ModelReading | null = null): ConvResult {
  const message = text.trim();
  const pending = input.pendingSlot as PendingSlot | null;
  const coreSlot = pending === "location_choice" ? "location" : pending && (CORE_SLOTS as string[]).includes(pending) ? (pending as Slot) : null;
  const pre: ChatMessage[] = [];
  let chatLang: ChatLang | undefined;

  // Language follows the script the user writes in (orchestrator/language.detect_language)
  const script = detectScript(message);
  if (script !== "en" && script !== input.chatLang) {
    chatLang = script;
    pre.push(a("u1.lang.switched", { lang: `@u1.langName.${script}` }));
  }

  const merged = mergeExtraction(extract(message, coreSlot), reading, coreSlot);
  const ext = merged.ext;
  const intent = mergeIntent(classifyIntent(message), reading, ext);
  // A name mentioned in passing ("I am Meena, from Coimbatore …") is kept when no name was given yet
  const knownName = chatName(input.chat);
  const withName = (r: ConvResult): ConvResult =>
    merged.name && !knownName && !r.reset && !r.userVars.name
      ? {
          ...r,
          userVars: { ...r.userVars, answered: [r.userVars.answered, "name"].filter(Boolean).join(","), name: merged.name },
          messages: [a("u1.name.ok", { name: merged.name }), ...r.messages],
        }
      : r;
  const withLang = (r: ConvResult): ConvResult => withName({ ...r, chatLang: r.chatLang ?? chatLang });

  if (intent === "new_case") return withLang(empty(input, [...pre, a("u1.newCase")], { reset: true, pendingSlot: null }));
  if (intent === "change_language" && ext.language) {
    return withLang(empty(input, [...pre, a("u1.lang.switched", { lang: `@u1.langName.${ext.language}` }), ...jumpMessages("languages"), ...reask(input)], { chatLang: ext.language }));
  }
  const jump = INTENT_JUMP[intent];
  if (jump) return withLang(empty(input, [...pre, ...jumpMessages(jump), ...reask(input)]));

  const patch: Partial<ProfileInput> = {};
  const answered: string[] = [];
  const p = input.profile;
  // A place phrase replaces a known location only if it is a real place ("not in any SHG" must not move the case).
  if (ext.locationText && ext.locationText !== p.locationText && (!placeOf(p) || resolveLocation(ext.locationText, null).candidates.length > 0)) {
    patch.locationText = ext.locationText;
  }
  if (ext.capital !== undefined) patch.capital = ext.capital;
  // While skills / work place / category are being asked, "stitching" names a skill, not a new business idea
  const guarded = coreSlot === "skills" || coreSlot === "premises" || coreSlot === "category";
  if (ext.activityId && (!guarded || ACTIVITY_CUE.test(message))) patch.activityId = ext.activityId;
  if (ext.reason) patch.reason = ext.reason;
  if (ext.skills && (coreSlot === "skills" || SKILL_CUE.test(message))) patch.skills = [...new Set([...p.skills, ...ext.skills])];
  if (ext.premises) patch.premises = ext.premises;
  if (ext.category) patch.category = ext.category;
  if (ext.shgMember !== undefined) patch.shgMember = ext.shgMember;
  const assets = ASSET_WORDS.filter(([, re]) => re.test(message)).map(([id]) => id);
  if (assets.length) patch.assets = [...new Set([...p.assets, ...assets])];
  if (coreSlot === "skills" && NONE.test(message)) answered.push("skills");
  if (coreSlot === "category" && NONE.test(message)) answered.push("category");
  if (coreSlot === "premises" && NONE.test(message)) answered.push("premises");
  if (Object.keys(patch).length || answered.length) return withLang(advance(input, patch, answered, pre));

  // Name (optional): free text with no profile information
  if (pending === "name" && (intent === "unknown" || intent === "greeting")) {
    const name = message.replace(NAME_PREFIX, "").replace(NAME_SUFFIX, "").replace(/[.!।]+$/u, "").trim().slice(0, 40);
    if (name && intent === "unknown") {
      const skipped = skipName(input);
      return withLang({ ...skipped, userVars: { answered: "name", name }, messages: [...pre, a("u1.name.ok", { name }), ...skipped.messages] });
    }
  }
  if (intent === "greeting") return withLang(empty(input, [...pre, a("u1.greetBack"), ...reask(input)]));

  // Nothing understood: be honest about what failed
  if (coreSlot === "capital" && /\d/.test(message)) return withLang(empty(input, [...pre, a("u1.cap.invalid")]));
  if (coreSlot === "location") return withLang(empty(input, [...pre, a("u1.loc.notFound", { query: message.slice(0, 60) })]));
  if (coreSlot === "activity") {
    const ids = suggestedActivities(p, 4);
    return withLang(empty(input, [...pre, a("u1.act.unknown"), ...(ids.length ? [a("u1.card.suggest", { ids: ids.join(",") }, "act_suggest")] : [])]));
  }
  if (pending) return withLang(empty(input, [...pre, a("u1.didntGet"), ...reask(input)]));
  return withLang(empty(input, [...pre, a("u1.help")]));
}

/** Skip the optional name question. */
export function skipName(input: ConvInput): ConvResult {
  const missing = missingSlots(input.profile, answeredSlots(input.chat));
  const messages = missing.length ? askMessages(missing[0], input.profile) : [a("u1.summary"), a("u1.card.summary", undefined, "profile_summary")];
  return { userVars: { answered: "name" }, messages, profilePatch: {}, pendingSlot: missing[0] ?? null, events: [], changedCore: false };
}

/** Opening turn: a new chat, or a case that already has inputs (presenter checkpoint, returning user). */
export function opening(input: ConvInput): { messages: ChatMessage[]; pendingSlot: string | null } {
  if (!profileStarted(input.profile)) return { messages: [a("u1.greet"), a("u1.ask.name")], pendingSlot: "name" };
  const missing = missingSlots(input.profile, answeredSlots(input.chat));
  if (missing.length) return { messages: [a("u1.greetCase"), ...askMessages(missing[0], input.profile)], pendingSlot: missing[0] };
  return { messages: [a("u1.greetCase"), a("u1.summary"), a("u1.card.summary", undefined, "profile_summary")], pendingSlot: null };
}

export const verdictMessage = (sig: string): ChatMessage => a("u1.card.verdict", { sig }, "verdict");

/* ------------------------------------------------------------------ presenter sample, typed through the same pipeline */

const PREMISES_TEXT: Record<NonNullable<ProfileInput["premises"]>, string> = { home: "I will work from home", rented_shop: "I will work in a shop on rent", own_land: "I will work on my own land" };
const ASSET_TEXT: Record<string, string> = { foot_pedal_machine: "a foot pedal machine", electric_machine: "an electric machine", cattle: "cattle" };

/** What a presenter "types" for the pending slot, built from the sample inputs. */
export function sampleText(sample: ProfileInput, slot: PendingSlot | null): string | null {
  const name = sample.activityId ? catalogActivity(sample.activityId)?.name.en.toLowerCase() : null;
  switch (slot) {
    case "location":
      return `I live in ${sample.locationText}`;
    case "capital":
      return `I have ${rupees(sample.capital)} saved`;
    case "activity":
    case "reason":
      return name ? `I want to start ${name}${sample.reason ? ` because ${sample.reason.charAt(0).toLowerCase()}${sample.reason.slice(1)}` : ""}` : null;
    case "skills":
      return sample.skills.length ? `I know ${sample.skills.join(" and ")}` : "none";
    case "premises": {
      const assets = sample.assets.map((x) => ASSET_TEXT[x]).filter(Boolean);
      return `${sample.premises ? PREMISES_TEXT[sample.premises] : "none"}${assets.length ? ` and I have ${assets.join(" and ")}` : ""}`;
    }
    case "category":
      return `${sample.category ? `${sample.category.toUpperCase()} category` : "none"}, ${sample.shgMember ? "member of a self help group" : "not in a self help group"}`;
    default:
      return null;
  }
}
