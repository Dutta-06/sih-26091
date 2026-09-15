/**
 * Per-language vocabulary for offline message understanding (src/i18n/locales/<lang>.nlu.json).
 * Each file is optional; entries are merged into the English/Hindi rules of nlu.ts, so a missing lexicon only
 * means that language is understood less well — never a behaviour change for the others.
 */
import { DICTIONARIES, LANGS, type Lang } from "../i18n";

export interface Lexicon {
  lakh?: string[];
  thousand?: string[];
  crore?: string[];
  rupee?: string[];
  numberWords?: Record<string, number>;
  because?: string[];
  activities?: Record<string, string[]>;
  skills?: Record<string, string[]>;
  premises?: Partial<Record<"home" | "rented_shop" | "own_land", string[]>>;
  category?: Partial<Record<"sc" | "st" | "obc" | "general", string[]>>;
  shg?: string[];
  negation?: string[];
  intents?: Partial<Record<"raise_grievance" | "application_status" | "scheme_inquiry" | "monitoring" | "community" | "change_language" | "new_case", string[]>>;
  greetings?: string[];
  languageNames?: string[];
}

const files = import.meta.glob<Lexicon>("../i18n/locales/*.nlu.json", { eager: true, import: "default" });

export const LEXICONS: Partial<Record<Lang, Lexicon>> = {};
for (const [file, lex] of Object.entries(files)) {
  const code = file.split("/").pop()!.split(".")[0] as Lang;
  if ((LANGS as readonly string[]).includes(code)) LEXICONS[code] = lex;
}

const lower = (xs: string[] | undefined) => (xs ?? []).map((x) => x.normalize("NFC").toLowerCase()).filter(Boolean);

/** All words of one list across every language lexicon. */
export function words(pick: (l: Lexicon) => string[] | undefined): string[] {
  return [...new Set(Object.values(LEXICONS).flatMap((l) => lower(pick(l!))))];
}

/** Keyword lists keyed by id (activities, skills, premises, category, intents) across all lexicons. */
export function keyed<K extends string>(pick: (l: Lexicon) => Partial<Record<K, string[]>> | undefined): Record<K, string[]> {
  const out = {} as Record<K, string[]>;
  for (const lex of Object.values(LEXICONS)) {
    for (const [id, list] of Object.entries(pick(lex!) ?? {}) as [K, string[]][]) out[id] = [...new Set([...(out[id] ?? []), ...lower(list)])];
  }
  return out;
}

export function numberWords(): Record<string, number> {
  return Object.assign({}, ...Object.values(LEXICONS).map((l) => l!.numberWords ?? {}));
}

/** District name as written in each language (translation keys place.district.<id>) → English name. */
export function districtNamesByScript(): [string, string][] {
  const pairs: [string, string][] = [];
  for (const [key, en] of Object.entries(DICTIONARIES.en)) {
    if (!key.startsWith("place.district.")) continue;
    for (const l of LANGS) {
      const v = DICTIONARIES[l][key];
      if (v && v !== en && !/^[\x00-\x7F]+$/.test(v)) pairs.push([v.normalize("NFC").toLowerCase(), en]);
    }
  }
  return pairs.sort((a, b) => b[0].length - a[0].length);
}

/** Unicode decimal digits of Indic scripts → ASCII (Devanagari, Bengali, Gurmukhi, Tamil, Telugu, Kannada). */
const ZEROS = [0x0966, 0x09e6, 0x0a66, 0x0be6, 0x0c66, 0x0ce6];
export function asciiDigits(text: string): string {
  return text.replace(/\p{Nd}/gu, (ch) => {
    const cp = ch.codePointAt(0)!;
    const z = ZEROS.find((zero) => cp >= zero && cp <= zero + 9);
    return z === undefined ? ch : String(cp - z);
  });
}
