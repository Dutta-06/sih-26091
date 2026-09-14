import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { LANGS, type Lang } from "./languages";
import { common } from "./strings/common";

export { LANG_INFO, LANGS, isLang, type Lang, type LangInfo } from "./languages";

/**
 * Authored string tables carry English and Hindi (`src/i18n/strings/*.ts`). The other languages live in
 * `src/i18n/locales/<lang>.json` (optionally split as `<lang>.partN.json`), keyed exactly like the English table.
 * Missing keys fall back to English, then to the key itself.
 */
export type Strings = { en: Record<string, string>; hi: Record<string, string> };

/** Inline multilingual text used in data. English and Hindi are always present; other languages are optional. */
export type Bi = { en: string; hi: string } & Partial<Record<Lang, string>>;

const modules = import.meta.glob<{ default: Strings }>("./strings/*.ts", { eager: true });
const locales = import.meta.glob<Record<string, string>>("./locales/*.json", { eager: true, import: "default" });

export const DICTIONARIES: Record<Lang, Record<string, string>> = Object.fromEntries(LANGS.map((l) => [l, {}])) as Record<Lang, Record<string, string>>;
Object.assign(DICTIONARIES.en, common.en);
Object.assign(DICTIONARIES.hi, common.hi);
for (const mod of Object.values(modules)) {
  if (!mod.default) continue;
  Object.assign(DICTIONARIES.en, mod.default.en);
  Object.assign(DICTIONARIES.hi, mod.default.hi);
}
for (const [file, table] of Object.entries(locales)) {
  const name = file.split("/").pop()!;
  if (name.includes(".nlu.")) continue; // message-understanding lexicons are loaded by core/lexicon.ts
  const code = name.split(".")[0] as Lang;
  if (DICTIONARIES[code]) Object.assign(DICTIONARIES[code], table);
}

/** Translate outside React (core formatting, tests). */
export function translate(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  let s = DICTIONARIES[lang]?.[key] ?? DICTIONARIES.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

/** Pick one language from multilingual text: exact language, then Hindi for Marathi (same script), then English. */
export function pickText(text: Bi | string, lang: Lang): string {
  if (typeof text === "string") return text;
  return text[lang] ?? (lang === "mr" ? text.hi : undefined) ?? text.en;
}

/** Multilingual text for a translation key (used for catalog, activity and place names), with authored fallbacks. */
export function biFromKey(key: string, fallback: Bi | string): Bi {
  const base: Bi = typeof fallback === "string" ? { en: fallback, hi: fallback } : fallback;
  const out: Bi = { ...base };
  for (const l of LANGS) {
    const v = DICTIONARIES[l][key];
    if (v && !(l === "en" && base.en)) out[l] = v;
  }
  return out;
}

interface I18n {
  lang: Lang;
  setLang: (lang: Lang) => void;
  /** Translate a key; {name} placeholders are replaced from vars. Missing keys fall back to English, then the key. */
  t: (key: string, vars?: Record<string, string | number>) => string;
  /** Pick the current language from inline multilingual text. */
  pick: (text: Bi | string) => string;
  /** Render a core `Msg` ({ key, vars }); multilingual values inside vars are picked, numbers pass through. */
  tm: (msg: { key: string; vars?: Record<string, unknown> } | null | undefined) => string;
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ lang, setLang, children }: { lang: Lang; setLang: (l: Lang) => void; children: ReactNode }) {
  const t = useCallback((key: string, vars?: Record<string, string | number>) => translate(lang, key, vars), [lang]);
  const pick = useCallback((text: Bi | string) => pickText(text, lang), [lang]);
  const tm = useCallback(
    (msg: { key: string; vars?: Record<string, unknown> } | null | undefined) => {
      if (!msg) return "";
      const vars: Record<string, string | number> = {};
      for (const [k, v] of Object.entries(msg.vars ?? {})) {
        if (v && typeof v === "object" && "en" in (v as object)) vars[k] = pick(v as Bi);
        else if (typeof v === "string" && v.startsWith("@")) vars[k] = t(v.slice(1));
        else vars[k] = v as string | number;
      }
      return t(msg.key, vars);
    },
    [t, pick],
  );
  const value = useMemo(() => ({ lang, setLang, t, pick, tm }), [lang, setLang, t, pick, tm]);
  return (
    <Ctx.Provider value={value}>
      <div lang={lang} className="h-full">
        {children}
      </div>
    </Ctx.Provider>
  );
}

export function useI18n(): I18n {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}
