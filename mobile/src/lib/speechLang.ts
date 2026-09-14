/** Pure language-tag matching for the voice engines (unit-tested). */

import { LANG_INFO } from "../i18n/languages";

const PREFERRED: Record<string, string> = Object.fromEntries(Object.values(LANG_INFO).map((l) => [l.code, l.speech]));

/**
 * Pick the best tag an engine reports for an app language: exact Indian locale first, then any regional
 * variant of the language (`hi`, `hi_IN`, `en-GB` ...). Returns null when the engine cannot speak it.
 */
export function pickLanguageTag(lang: string, available: string[]): string | null {
  const norm = (t: string) => t.replace(/_/g, "-").toLowerCase();
  const want = norm(PREFERRED[lang] ?? lang);
  const base = want.split("-")[0];
  let exact: string | null = null;
  let india: string | null = null;
  let any: string | null = null;
  for (const raw of available) {
    const t = norm(raw);
    const b = t.split("-")[0];
    if (b !== base) continue;
    if (t === want) exact ??= raw.replace(/_/g, "-");
    else if (t.endsWith("-in")) india ??= raw.replace(/_/g, "-");
    else any ??= raw.replace(/_/g, "-");
  }
  return exact ?? india ?? any;
}
