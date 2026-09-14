import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { common } from "./strings/common";

export type Lang = "en" | "hi";

/** A string table: every key must exist in both languages. */
export type Strings = { en: Record<string, string>; hi: Record<string, string> };

/** Inline bilingual text, used in mock data. */
export type Bi = { en: string; hi: string };

const modules = import.meta.glob<{ default: Strings }>("./strings/*.ts", { eager: true });

const dictionaries: Record<Lang, Record<string, string>> = { en: { ...common.en }, hi: { ...common.hi } };
for (const mod of Object.values(modules)) {
  if (!mod.default) continue;
  Object.assign(dictionaries.en, mod.default.en);
  Object.assign(dictionaries.hi, mod.default.hi);
}

interface I18n {
  lang: Lang;
  setLang: (lang: Lang) => void;
  /** Translate a key; {name} placeholders are replaced from vars. Missing keys fall back to English, then the key. */
  t: (key: string, vars?: Record<string, string | number>) => string;
  /** Pick the current language from inline bilingual text. */
  pick: (text: Bi | string) => string;
  /** Render a core `Msg` ({ key, vars }); Bi values inside vars are picked, numbers pass through. */
  tm: (msg: { key: string; vars?: Record<string, unknown> } | null | undefined) => string;
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ lang, setLang, children }: { lang: Lang; setLang: (l: Lang) => void; children: ReactNode }) {
  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      let s = dictionaries[lang][key] ?? dictionaries.en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    },
    [lang],
  );
  const pick = useCallback((text: Bi | string) => (typeof text === "string" ? text : text[lang]), [lang]);
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
