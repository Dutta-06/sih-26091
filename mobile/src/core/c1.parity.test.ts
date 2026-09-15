import { describe, expect, it } from "vitest";
import fixtures from "./__fixtures__/c1.json";
import { classifyIntent, detectLanguageCode, detectScript, extract } from "./nlu";
import { retrieve } from "./retrieval";
import type { PackDoc, Slot } from "./types";

type NluCase = (typeof fixtures.nlu)[number];

/** Intentional, documented divergences from the backend (extensions listed in nlu.ts). */
const OVERRIDES: Record<string, Partial<Record<"intent" | "locationText", string | null>>> = {
  hello: { intent: "greeting" },
  "fish farming in Prayagraj kyunki talab hai": { locationText: "Prayagraj" },
};

describe("retrieval parity with rag/vector_store.retrieve", () => {
  for (const c of fixtures.retrieval) {
    it(`${c.collection}: ${c.query}`, () => {
      const got = retrieve(c.collection as PackDoc["collection"], c.query);
      expect(got.length).toBe(c.results.length);
      expect(got.slice(0, 3).map((r) => r.source)).toEqual(c.results.slice(0, 3).map((r) => r.source));
      expect(got.slice(0, 3).map((r) => r.heading)).toEqual(c.results.slice(0, 3).map((r) => r.heading));
      got.forEach((r, i) => expect(Math.abs(r.score - c.results[i].score)).toBeLessThanOrEqual(0.02));
    });
  }
});

describe("nlu parity with orchestrator/router + language", () => {
  for (const c of fixtures.nlu as NluCase[]) {
    it(`${JSON.stringify(c.text.slice(0, 60))} (pending ${c.pending})`, () => {
      const e = extract(c.text, c.pending as Slot | null);
      const o = OVERRIDES[c.text] ?? {};
      expect(e.capital ?? null).toBe(c.capital);
      // Languages beyond English/Hindi are understood through the app's lexicons (the backend has none):
      // parity is only required where the backend found an activity.
      if (c.activityId !== null || !/[ঀ-෿]/.test(c.text)) expect(e.activityId ?? null).toBe(c.activityId);
      expect(e.locationText ?? null).toBe("locationText" in o ? o.locationText : c.locationText);
      expect(e.reason ?? null).toBe(c.reason);
      const lexiconLanguage = /[ঀ-෿]/.test(c.text); // understood via app lexicons, not the backend
      if (!lexiconLanguage || c.intent !== "unknown") expect(classifyIntent(c.text)).toBe(o.intent ?? c.intent);
      expect(detectLanguageCode(c.text)).toBe(c.language);
      expect(detectScript(c.text)).toBe(["hi", "bn", "ta", "te", "pa", "kn"].includes(c.language) ? c.language : "en");
    });
  }
});
