import { expect, it } from "vitest";
it("hindi coverage", () => {
  const mods = import.meta.glob("./i18n/strings/*.ts", { eager: true }) as Record<string, { default: { en: Record<string,string>; hi: Record<string,string> } }>;
  const missing: string[] = [];
  for (const [f, m] of Object.entries(mods)) {
    if (!m.default) continue;
    for (const k of Object.keys(m.default.en)) if (!(k in m.default.hi)) missing.push(`${f.split("/").pop()}:${k}`);
  }
  expect(missing).toEqual([]);
});
