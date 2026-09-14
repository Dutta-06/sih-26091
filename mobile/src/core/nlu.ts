/**
 * Offline language understanding — port of orchestrator/router.py (extract_capital, extract_location,
 * extract_reason, match_activity, parse_intent without a case state) and orchestrator/language.detect_language.
 *
 * Extensions over the backend (not in the parity fixtures): Hindi/Hinglish number words before
 * हज़ार/लाख ("बारह हज़ार", "पचास हजार", "dedh lakh"), negative amounts rejected, Bengali digits, Devanagari
 * after "in/at", "कारण" as a reason cue, skills / premises / category / SHG keywords, language names,
 * greeting / change_language / community intents, Marathi detection within Devanagari.
 */
import { ACTIVITIES } from "../data/activities";
import catalog from "../../../data/reference/business_catalog.json";
import { asciiDigits, districtNamesByScript, keyed, LEXICONS, numberWords, words } from "./lexicon";
import type { Extraction, Intent, ProfileInput, Slot } from "./types";

type Lang = NonNullable<Extraction["language"]>;

const W = "[\\p{L}\\p{N}_]"; // Python str \w
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/* ------------------------------------------------------------------ activity (router.match_activity) */

const CATALOG = (catalog as { activities: { id: string; category: string; keywords: string[] }[] }).activities;
const KEYWORDS: { kw: string; id: string; re: RegExp }[] = CATALOG.flatMap((a) =>
  [...a.keywords, a.category.toLowerCase()].map((k) => {
    const kw = k.toLowerCase();
    return { kw, id: a.id, re: new RegExp(`(?<!${W})${esc(kw)}(?:s|es)?(?!${W})`, "u") };
  }),
);

const isAscii = (s: string) => /^[\x00-\x7F]+$/.test(s);
/** Whole word for Latin keywords; word-start prefix for Indic keywords (case endings attach to the word). */
const keywordRe = (kw: string) =>
  isAscii(kw) ? new RegExp(`(?<!${W})${esc(kw)}(?:s|es)?(?!${W})`, "u") : new RegExp(`(?<![\\p{L}\\p{M}])${esc(kw)}`, "u");
for (const [id, list] of Object.entries(keyed((l) => l.activities))) {
  for (const kw of list) KEYWORDS.push({ kw, id, re: keywordRe(kw) });
}

/** Catalog id whose longest whole-word keyword occurs in text (catalog order breaks ties). */
export function matchActivity(text: string | null | undefined): string | null {
  if (!text) return null;
  const lowered = text.toLowerCase();
  let best: [number, string | null] = [0, null];
  for (const { kw, id, re } of KEYWORDS) if (kw.length > best[0] && re.test(lowered)) best = [kw.length, id];
  return best[1];
}

/* ------------------------------------------------------------------ capital (router.extract_capital + words) */

const DIGITS: Record<string, string> = {};
"०१२३४५६७८९".split("").forEach((c, i) => (DIGITS[c] = String(i)));
"০১২৩৪৫৬৭৮৯".split("").forEach((c, i) => (DIGITS[c] = String(i)));
const NUM = "(\\d+(?:[.,]\\d+)*)";
const B = `(?!${W})`; // Python \b after a word character

const NUMBER_WORDS: Record<string, number> = {
  ...numberWords(),
  एक: 1, दो: 2, तीन: 3, चार: 4, पांच: 5, पाँच: 5, छह: 6, छः: 6, सात: 7, आठ: 8, नौ: 9, दस: 10, ग्यारह: 11, बारह: 12,
  तेरह: 13, चौदह: 14, पंद्रह: 15, पन्द्रह: 15, सोलह: 16, सत्रह: 17, अठारह: 18, उन्नीस: 19, बीस: 20, पच्चीस: 25, तीस: 30,
  पैंतीस: 35, चालीस: 40, पैंतालीस: 45, पचास: 50, साठ: 60, सत्तर: 70, अस्सी: 80, नब्बे: 90, डेढ़: 1.5, डेढ: 1.5, ढाई: 2.5,
  ek: 1, do: 2, teen: 3, char: 4, chaar: 4, paanch: 5, panch: 5, chhe: 6, saat: 7, aath: 8, nau: 9, das: 10,
  gyarah: 11, barah: 12, baarah: 12, pandrah: 15, bees: 20, pachchis: 25, tees: 30, chalis: 40, pachas: 50, pachaas: 50,
  saath: 60, sattar: 70, assi: 80, nabbe: 90, dedh: 1.5, dhai: 2.5,
};
const alt = (xs: string[]) => (xs.length ? "|" + xs.map(esc).join("|") : "");
const LAKH_WORDS = words((l) => l.lakh);
const WORD_RE = new RegExp(
  `(?<![\\p{L}\\p{M}\\p{N}_])(${Object.keys(NUMBER_WORDS).sort((a, b) => b.length - a.length).map(esc).join("|")})\\s*(लाख|lakhs?|हज़ार|हजार|hazaa?r|hajar${alt(LAKH_WORDS)}${alt(words((l) => l.thousand))})(?![\\p{L}\\p{M}_])`,
  "u",
);

const num = (raw: string) => Number(raw.replace(/,/g, ""));
/** "-500" / "₹-500": a minus sign directly before the number (and not a range like "1-2"). */
const negativeAt = (t: string, m: RegExpExecArray) => {
  const i = m.index + m[0].indexOf(m[1]);
  return t[i - 1] === "-" && !/\d/.test(t[i - 2] ?? "");
};

export function extractCapital(text: string, expecting = false): number | null {
  const t = asciiDigits(text.replace(/[०-९০-৯]/g, (c) => DIGITS[c])).normalize("NFC").toLowerCase();
  const accept = (v: number) => (Number.isFinite(v) && v > 0 ? v : null);
  for (const [pattern, mult] of [
    [`${NUM}\\s*(?:crore|cr${B}|करोड़|करोड${alt(words((l) => l.crore))})`, 10_000_000],
    [`${NUM}\\s*(?:lakhs?|lacs?|lac${B}|lakh|लाख${alt(LAKH_WORDS)})`, 100_000],
    [`${NUM}\\s*(?:thousand|hazaa?r|hajar|हज़ार|हजार|k${B}${alt(words((l) => l.thousand))})`, 1_000],
  ] as const) {
    const m = new RegExp(pattern, "u").exec(t);
    if (m) return negativeAt(t, m) ? null : accept(num(m[1]) * mult);
  }
  const w = WORD_RE.exec(t);
  if (w) return NUMBER_WORDS[w[1]] * (/लाख|lakh/.test(w[2]) || LAKH_WORDS.includes(w[2]) ? 100_000 : 1_000);
  const m =
    new RegExp(`(?:₹|rs\\.?|inr|rupees?)\\s*${NUM}`, "u").exec(t) ??
    new RegExp(`${NUM}\\s*(?:rupees?|rs${B}|₹|रुपये|रुपए|rupaye${alt(words((l) => l.rupee))})`, "u").exec(t);
  if (m) return negativeAt(t, m) ? null : accept(num(m[1]));
  for (const mm of t.matchAll(/\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?/g)) {
    if (t[mm.index - 1] === "-" && !/\d/.test(t[mm.index - 2] ?? "")) continue; // negative amount
    const value = num(mm[0]);
    if (value >= 5_000 || (expecting && value > 0)) return value;
  }
  return null;
}

/* ------------------------------------------------------------------ location (router.extract_location) */

const STOP = new Set(
  ("and with for to because i have want rupees rs my the a start business since as but so who where lakh capital invest " +
    "least all home present once time this that our it which what first last one am is" +
    " kyunki kyonki").split(" "), // extension: Hinglish reason cues end a location too
);
const LANGUAGE_NAMES: [RegExp, Lang][] = [
  [/(?<![\p{L}_])(english|angrezi|अंग्रेज़ी|अंग्रेजी|इंग्लिश)(?![\p{L}_])/u, "en"],
  [/(?<![\p{L}_])(hindi|हिंदी|हिन्दी)(?![\p{L}_])/u, "hi"],
  [/(?<![\p{L}_])(bengali|bangla|বাংলা|बंगाली)(?![\p{L}_])/u, "bn"],
  [/(?<![\p{L}_])(marathi|मराठी)(?![\p{L}_])/u, "mr"],
  [/(?<![\p{L}_])(tamil|தமிழ்|तमिल)(?![\p{L}_])/u, "ta"],
  [/(?<![\p{L}_])(telugu|తెలుగు|तेलुगु)(?![\p{L}_])/u, "te"],
  [/(?<![\p{L}_])(punjabi|panjabi|ਪੰਜਾਬੀ|पंजाबी)(?![\p{L}_])/u, "pa"],
  [/(?<![\p{L}_])(kannada|ಕನ್ನಡ|कन्नड़)(?![\p{L}_])/u, "kn"],
];
/** Place names that contain a language name ("Tamil Nadu") are not language requests. */
const withoutPlaceNames = (s: string) => s.replace(/tamil\s*nadu|तमिल\s*नाडु|தமிழ்\s*நாடு/giu, " ");
const isLanguageName = (s: string) => LANGUAGE_NAMES.some(([re]) => re.test(withoutPlaceNames(s.toLowerCase())));

function cleanLocation(candidate: string): string | null {
  const out: string[] = [];
  for (const w of candidate.replace(/^[ ,.]+|[ ,.]+$/g, "").split(/\s+/)) {
    if (STOP.has(w.toLowerCase().replace(/^,+|,+$/g, "")) || /\d/.test(w)) break;
    out.push(w);
  }
  const loc = out.join(" ").replace(/^[ ,.]+|[ ,.]+$/g, "");
  if (!loc || matchActivity(loc) || ["india", "village", "town", "city"].includes(loc.toLowerCase()) || isLanguageName(loc)) return null;
  return loc;
}

const HINGLISH_NON_PLACES = new Set(
  "baare bare baray gaon gaanv shahar ghar dukaan dukan kaam dhande dhandhe vyavsay vyapar jile zile zila jila area yojana scheme loan paise".split(" "),
);
const HINDI_PLACE_WORDS = new Set(["गांव", "गाँव", "शहर", "जिले", "व्यवसाय", "धंधे"]);

export function extractLocation(text: string): string | null {
  for (const m of text.matchAll(/\b(?:in|near|at|from)\s+([A-Za-z][A-Za-z ,.-]{1,60})/gi)) {
    const loc = cleanLocation(m[1]);
    if (loc) return loc;
  }
  for (const m of text.matchAll(/\b(?:in|near|at|from)\s+([ऀ-ॿ]+)/gi)) {
    if (!matchActivity(m[1]) && !HINDI_PLACE_WORDS.has(m[1]) && !isLanguageName(m[1])) return m[1];
  }
  const mein = /([A-Za-z][A-Za-z-]+(?:,?\s+[A-Za-z][A-Za-z-]+)?)\s+mein\b/i.exec(text);
  if (mein) {
    const last = mein[1].split(/\s+/).pop() ?? "";
    const loc = HINGLISH_NON_PLACES.has(last.toLowerCase()) ? null : cleanLocation(last); // extension
    if (loc) return loc;
  }
  for (const m of text.matchAll(/([ऀ-ॿ]+)\s+में/g)) {
    // Python [ऀ-ॿ]+ is greedy over the whole block, so "में" itself never starts a match
    if (!matchActivity(m[1]) && !HINDI_PLACE_WORDS.has(m[1]) && !isLanguageName(m[1])) return m[1];
  }
  // extension: a district named in another script (translation tables) → its English name for the gazetteer
  const hay = text.normalize("NFC").toLowerCase();
  for (const [name, en] of districtNamesByScript()) if (hay.includes(name)) return en;
  return null;
}

/* ------------------------------------------------------------------ reason */

export function extractReason(text: string): string | null {
  const m = new RegExp(`(?:\\bbecause\\b|\\bsince\\b|\\bkyunki\\b|\\bkyonki\\b|क्योंकि|कारण${alt(words((l) => l.because))})\\s*(.+?)(?:[.!?।]|$)`, "iu").exec(text);
  const r = m?.[1]?.replace(/^[ ,]+|[ ,]+$/g, "");
  return m && m[1].trim() && r ? r : null;
}

/* ------------------------------------------------------------------ profile keywords (extension) */

const cue = (words: string[]) => new RegExp(`(?<![\\p{L}\\p{M}_])(?:${words.map(esc).join("|")})(?![\\p{L}\\p{M}_])`, "u");
const SKILLS: [string, RegExp][] = [
  ["stitching", cue(["stitching", "stitch", "sewing", "silai", "सिलाई", "सिलना", "tailoring", "tailor"])],
  ["embroidery", cue(["embroidery", "kadhai", "kadai", "zari", "कढ़ाई", "कढाई", "ज़री"])],
  ["weaving", cue(["weaving", "weave", "loom", "handloom", "बुनाई", "बुनना", "करघा"])],
  ["cooking", cue(["cooking", "cook", "pickle", "papad", "khana banana", "खाना बनाना", "अचार", "पापड़"])],
  ["livestock", cue(["livestock", "cattle", "goats", "goat", "cows", "cow", "buffalo", "pashu", "पशु", "गाय", "भैंस", "बकरी"])],
  ["retail", cue(["retail", "selling", "shopkeeping", "dukandari", "दुकानदारी", "बेचना"])],
  ["repair", cue(["repair", "repairing", "mechanic", "electrician", "मरम्मत", "रिपेयर"])],
  ["beauty", cue(["beauty", "makeup", "mehendi", "mehndi", "parlour", "parlor", "मेहंदी", "ब्यूटी", "पार्लर"])],
];
const PREMISES: [ProfileInput["premises"], RegExp][] = [
  ["rented_shop", cue(["rented shop", "rent a shop", "on rent", "kiraye", "kiraya", "किराए", "किराये", "किराया"])],
  ["own_land", cue(["own land", "my land", "my field", "zameen", "jameen", "khet", "ज़मीन", "जमीन", "खेत"])],
  ["home", cue(["from home", "at home", "my home", "my house", "ghar se", "ghar par", "ghar pe", "घर से", "घर पर", "घर में"])],
];
const CATEGORIES: [ProfileInput["category"], RegExp][] = [
  ["st", cue(["st", "scheduled tribe", "adivasi", "अनुसूचित जनजाति", "जनजाति", "आदिवासी"])],
  ["sc", cue(["sc", "scheduled caste", "dalit", "अनुसूचित जाति"])],
  ["obc", cue(["obc", "other backward", "backward class", "पिछड़ा वर्ग", "पिछड़ा", "ओबीसी"])],
  ["general", cue(["general category", "general caste", "samanya", "सामान्य वर्ग", "सामान्य"])],
];
const SHG = cue(["shg", "self help group", "self-help group", "स्वयं सहायता समूह", "jeevika", "जीविका", "mahila samuh", "महिला समूह", "samuh", "समूह"]);

// extension: other languages' vocabulary (Indic words match at word start, since case endings attach to them)
const lexCue = (list: string[]) => {
  const latin = list.filter(isAscii);
  const indic = list.filter((x) => !isAscii(x));
  const parts = [latin.length ? `(?:${latin.map(esc).join("|")})(?![\\p{L}\\p{M}_])` : "", indic.length ? `(?:${indic.map(esc).join("|")})` : ""].filter(Boolean);
  return parts.length ? new RegExp(`(?<![\\p{L}\\p{M}_])(?:${parts.join("|")})`, "u") : /(?!)/;
};
for (const [id, list] of Object.entries(keyed((l) => l.skills))) SKILLS.push([id, lexCue(list)]);
for (const [id, list] of Object.entries(keyed((l) => l.premises))) PREMISES.push([id as ProfileInput["premises"], lexCue(list)]);
for (const [id, list] of Object.entries(keyed((l) => l.category))) CATEGORIES.push([id as ProfileInput["category"], lexCue(list)]);
const LEX_SHG = lexCue(words((l) => l.shg));
const NEGATION = words((l) => l.negation);

/* ------------------------------------------------------------------ public API */

export function extract(text: string, pendingSlot: Slot | null): Extraction {
  const message = text ?? "";
  const out: Extraction = {};
  const capital = extractCapital(message, pendingSlot === "capital");
  if (capital !== null) out.capital = capital;
  const activityId = matchActivity(message);
  if (activityId) out.activityId = activityId;
  let location = extractLocation(message);
  if (location === null && pendingSlot === "location" && capital === null && activityId === null) location = cleanLocation(message);
  if (location) out.locationText = location;
  const reason = extractReason(message);
  if (reason) out.reason = reason;
  else if (pendingSlot === "reason" && message.trim() && capital === null) out.reason = message.trim();

  const lower = message.toLowerCase();
  const skills = [...new Set(SKILLS.filter(([, re]) => re.test(lower)).map(([id]) => id))];
  if (skills.length) out.skills = skills;
  const premises = PREMISES.find(([, re]) => re.test(lower));
  if (premises) out.premises = premises[0];
  // "sc"/"st" are only taken as categories with an explicit cue word or when the category was asked for
  const catText = pendingSlot === "category" || /categor|caste|jati|जाति|वर्ग|varg/u.test(lower) ? lower : lower.replace(/\b(sc|st)\b/g, " ");
  const category = CATEGORIES.find(([, re]) => re.test(catText));
  if (category) out.category = category[0];
  if (SHG.test(lower)) out.shgMember = !/\b(not|no)\b[^.]*\b(shg|group)\b|नहीं[^।]*समूह|समूह[^।]*नहीं/u.test(lower);
  else if (LEX_SHG.test(lower)) out.shgMember = !NEGATION.some((n) => lower.includes(n));
  const lang = LANGUAGE_NAMES.find(([re]) => re.test(withoutPlaceNames(lower)));
  if (lang) out.language = lang[1];
  return out;
}

/** router._CUES (exact substrings, lowercase) + extensions. */
const CUES: Record<string, string[]> = {
  raise_grievance: ["complaint", "grievance", "problem with", "not working", "broken", "breakdown", "delay in", "delayed",
    "unable to repay", "can't repay", "cannot repay", "prices crashed", "price crash", "शिकायत", "समस्या", "खराब",
    "shikayat", "samasya", "kharab"],
  consent_monitoring: ["i consent", "i agree to monitoring", "allow monitoring", "consent to monitoring",
    "you can read my sms", "सहमति", "sahmati"],
  jump_monitoring: ["monitoring", "health score", "how is my business doing", "my transactions", "business health"],
  jump_application: ["application status", "my application", "apply now", "loan application", "documents needed",
    "fill the form", "आवेदन", "aavedan"],
  inquire_scheme: ["scheme", "subsidy", "guideline", "interest rate", "eligibility", "moratorium", "योजना", "yojana"],
  new_case: ["new case", "start over", "restart", "start again", "नया केस", "फिर से शुरू"],
};
const LEX_INTENTS = keyed((l) => l.intents);
CUES.raise_grievance.push(...(LEX_INTENTS.raise_grievance ?? []));
CUES.jump_application.push(...(LEX_INTENTS.application_status ?? []));
CUES.inquire_scheme.push(...(LEX_INTENTS.scheme_inquiry ?? []));
CUES.jump_monitoring.push(...(LEX_INTENTS.monitoring ?? []));
CUES.new_case.push(...(LEX_INTENTS.new_case ?? []));
const LEX_CHANGE_LANGUAGE = LEX_INTENTS.change_language ?? [];
const LEX_COMMUNITY = LEX_INTENTS.community ?? [];
const LEX_GREETINGS = words((l) => l.greetings);
const LEX_LANGUAGE_NAMES: [string, Lang][] = [];
for (const [code, lex] of Object.entries(LEXICONS)) for (const n of lex?.languageNames ?? []) LEX_LANGUAGE_NAMES.push([n.toLowerCase(), code as Lang]);
const CHANGE_LANGUAGE = /(?:language|bhasha|भाषा|speak|talk|baat|बात|बोलो|बोलिए)/u;
const COMMUNITY = /(?:community|other entrepreneurs|peer group|mentor|meet others|samudaay|समुदाय|दूसरे उद्यमी|मेंटर)/u;
const GREETING = /^\s*(?:hi+|hello|hey|namaste|namaskar|नमस्ते|नमस्कार|good (?:morning|afternoon|evening)|राम राम|ram ram|pranam|प्रणाम)(?![\p{L}\p{M}])[\s!.,?।]*$/iu;

const hasSlots = (e: Extraction) =>
  e.capital !== undefined || e.activityId !== undefined || e.locationText !== undefined || e.reason !== undefined;

/** router.parse_intent(message, state=None) mapped to the app's intents, plus greeting/language/community. */
export function classifyIntent(text: string): Intent {
  const lower = (text ?? "").toLowerCase();
  if (!lower.trim()) return "unknown";
  const hits = new Set(Object.entries(CUES).filter(([, cues]) => cues.some((c) => lower.includes(c))).map(([k]) => k));
  if (hits.has("raise_grievance")) return "raise_grievance";
  if (hits.has("consent_monitoring")) return "monitoring";
  if (hits.has("new_case")) return "new_case";
  const e = extract(text, null);
  if (e.language && (CHANGE_LANGUAGE.test(lower) || LEX_CHANGE_LANGUAGE.some((w) => lower.includes(w)))) return "change_language";
  if (hasSlots(e)) return "provide_info"; // no case state → profile incomplete → slots win
  if (hits.has("jump_monitoring")) return "monitoring";
  if (hits.has("jump_application")) return "application_status";
  if (hits.has("inquire_scheme")) return "scheme_inquiry";
  if (COMMUNITY.test(lower) || LEX_COMMUNITY.some((w) => lower.includes(w))) return "community";
  if (GREETING.test(lower) || LEX_GREETINGS.includes(lower.trim().replace(/[\s!.,?।]+$/u, ""))) return "greeting";
  if (e.skills || e.premises || e.category || e.shgMember !== undefined) return "provide_info";
  return "unknown";
}

const SCRIPTS: [number, number, string][] = [
  [0x0900, 0x097f, "hi"], [0x0980, 0x09ff, "bn"], [0x0a00, 0x0a7f, "pa"], [0x0a80, 0x0aff, "gu"], [0x0b00, 0x0b7f, "or"],
  [0x0b80, 0x0bff, "ta"], [0x0c00, 0x0c7f, "te"], [0x0c80, 0x0cff, "kn"], [0x0d00, 0x0d7f, "ml"],
];
const MARATHI = /(?:आहे|आहेत|मला|माझ|आणि|नाही|करायचा|करायची|पाहिजे|व्यवसाय करायचा|ळ)/u;

/** language.detect_language (dominant Indic script; ties → first seen) narrowed to the app's languages.
 * Devanagari with Marathi function words → "mr"; scripts the app does not support → "en". */
export function detectScript(text: string): Lang {
  const counts = new Map<string, number>();
  for (const ch of text ?? "") {
    const cp = ch.codePointAt(0)!;
    const s = SCRIPTS.find(([lo, hi]) => cp >= lo && cp <= hi);
    if (s) counts.set(s[2], (counts.get(s[2]) ?? 0) + 1);
  }
  let best: string | null = null;
  for (const [code, n] of counts) if (best === null || n > counts.get(best)!) best = code;
  if (best === "hi") return MARATHI.test(text) ? "mr" : "hi";
  return best === "bn" || best === "ta" || best === "te" || best === "pa" || best === "kn" ? (best as Lang) : "en";
}

/** Python-parity helper: the backend's detect_language code (all scripts). */
export function detectLanguageCode(text: string): string {
  const counts = new Map<string, number>();
  for (const ch of text ?? "") {
    const cp = ch.codePointAt(0)!;
    const s = SCRIPTS.find(([lo, hi]) => cp >= lo && cp <= hi);
    if (s) counts.set(s[2], (counts.get(s[2]) ?? 0) + 1);
  }
  let best: string | null = null;
  for (const [code, n] of counts) if (best === null || n > counts.get(best)!) best = code;
  return best ?? "en";
}

export const knownActivityIds = (): string[] => Object.keys(ACTIVITIES);
