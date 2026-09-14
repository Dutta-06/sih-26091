/**
 * Conversation-language translation (TDD 4.3). The app UI is English or Hindi; the assistant conversation can also run in
 * Bengali, Marathi and Tamil. Messages store keys; `tc` renders them in `state.chatLang`, falling back to the UI language.
 *
 * Var values: "@key" (or "@a|@b", a comma-joined list) are i18n keys · "~act:<id>" is an activity name ·
 * a JSON string starting with {"en" is bilingual pack text · numbers ≥ 1,000 get Indian digit grouping.
 */
import { useCallback, useMemo } from "react";
import { ACTIVITIES } from "../../data/activities";
import { CHAT_STRINGS } from "../../data/w1";
import { useI18n, type Bi, type Lang, type Strings } from "../../i18n";
import { useStore, type ChatLang } from "../../state/store";

const modules = import.meta.glob<{ default: Strings }>("../../i18n/strings/*.ts", { eager: true });
const BASE: Record<Lang, Record<string, string>> = { en: {}, hi: {} };
for (const mod of Object.values(modules)) {
  if (!mod.default) continue;
  Object.assign(BASE.en, mod.default.en);
  Object.assign(BASE.hi, mod.default.hi);
}

export const CHAT_LANGS: ChatLang[] = ["en", "hi", "bn", "mr", "ta"];
export const CHAT_LANG_LABEL: Record<ChatLang, string> = { en: "English", hi: "हिंदी", bn: "বাংলা", mr: "मराठी", ta: "தமிழ்" };
export const CHAT_LANG_SHORT: Record<ChatLang, string> = { en: "EN", hi: "हिं", bn: "বাং", mr: "मरा", ta: "தமி" };

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

function lookup(cl: ChatLang, ui: Lang, key: string): string {
  if (cl === "en" || cl === "hi") return BASE[cl][key] ?? BASE.en[key] ?? key;
  return CHAT_STRINGS[cl][key] ?? BASE[ui][key] ?? BASE.en[key] ?? key;
}

/** Activity display name in the conversation language (bn/mr/ta tables where present, else the UI language). */
export function activityLabel(cl: ChatLang, ui: Lang, id: string): string {
  const a = ACTIVITIES[id];
  if (!a) return id;
  if (cl === "en" || cl === "hi") return a.name[cl];
  return CHAT_STRINGS[cl][`u1.act.${id}`] ?? a.name[ui];
}

export function renderVar(cl: ChatLang, ui: Lang, v: unknown): string {
  if (typeof v === "number") return Math.abs(v) >= 1000 ? inr.format(v) : String(v);
  if (v && typeof v === "object" && "en" in (v as object)) return (v as Bi)[cl === "hi" ? "hi" : cl === "en" ? "en" : ui];
  if (typeof v !== "string") return String(v ?? "");
  if (v.startsWith("@")) return v.split("|").map((p) => lookup(cl, ui, p.replace(/^@/, ""))).join(", ");
  if (v.startsWith("~act:")) return activityLabel(cl, ui, v.slice(5));
  if (v.startsWith('{"en"')) {
    try {
      return renderVar(cl, ui, JSON.parse(v));
    } catch {
      return v;
    }
  }
  return v;
}

export function translateChat(cl: ChatLang, ui: Lang, key: string, vars?: Record<string, unknown>): string {
  let s = lookup(cl, ui, key);
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, renderVar(cl, ui, v));
  return s;
}

/** Translator for conversation content in the chosen conversation language. */
export function useChatI18n() {
  const { lang } = useI18n();
  const { state } = useStore();
  const cl: ChatLang = state.chatLang ?? lang;
  const tc = useCallback((key: string, vars?: Record<string, unknown>) => translateChat(cl, lang, key, vars), [cl, lang]);
  /** Render a core Msg in the conversation language. */
  const tmc = useCallback((m: { key: string; vars?: Record<string, unknown> } | null | undefined) => (m ? translateChat(cl, lang, m.key, m.vars) : ""), [cl, lang]);
  const actName = useCallback((id: string) => activityLabel(cl, lang, id), [cl, lang]);
  /** Bilingual pack text in the conversation language. */
  const pickc = useCallback((b: Bi | string) => renderVar(cl, lang, b), [cl, lang]);
  return useMemo(() => ({ cl, tc, tmc, actName, pickc }), [cl, tc, tmc, actName, pickc]);
}

/** UI-language renderer for core Msgs with grouped numbers (the shared `tm` passes numbers through raw). */
export function useFmt() {
  const { lang } = useI18n();
  return useCallback((m: { key: string; vars?: Record<string, unknown> } | null | undefined) => (m ? translateChat(lang, lang, m.key, m.vars) : ""), [lang]);
}

/** Change the app (UI) language; the conversation follows when it was in English or Hindi. */
export function useSetAppLang() {
  const { state, set } = useStore();
  return useCallback(
    (l: Lang) => set(state.chatLang === "en" || state.chatLang === "hi" ? { lang: l, chatLang: l } : { lang: l }),
    [state.chatLang, set],
  );
}
