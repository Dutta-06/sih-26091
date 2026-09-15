import { readFileSync, writeFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { loadModel, readMessage } from "../lib/nlp/model";
import { resolveLocation } from "./geo";
import { classifyIntent, extract, extractCapital } from "./nlu";
import { mergeExtraction, mergeIntent, type ModelReading } from "./nluModel";

/**
 * Field-level comparison on the hand-written test messages (ml/nlu/data/*.json "test"/"testIntents", never trained on):
 * what the chat actually keeps — district of the place, parsed amount, catalog business, reason present, name, intent —
 * with the rules alone versus rules + the on-device model.
 */
interface Row { lang: string; text: string; spans: [number, number, string][]; intent: string | null }
const rows: Row[] = readFileSync("src/core/__fixtures__/nlu_test.jsonl", "utf8").trim().split("\n").map((l) => JSON.parse(l));

const districtOf = (t?: string) => (t ? resolveLocation(t, null).candidates[0]?.district.id ?? null : null);
const norm = (s: string) => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
const toApp = (i: string) => (i === "other" ? "unknown" : i);

describe("message model versus rules on hand-written messages", () => {
  it("improves what the chat understands", async () => {
    const model = await loadModel({
      model: readFileSync("public/models/nlu/nlu.onnx"),
      tokenizer: JSON.parse(readFileSync("public/models/nlu/tokenizer.json", "utf8")),
      labels: JSON.parse(readFileSync("public/models/nlu/labels.json", "utf8")),
    });
    const score = { rules: {} as Record<string, [number, number]>, merged: {} as Record<string, [number, number]> };
    const add = (who: "rules" | "merged", field: string, ok: boolean) => {
      const s = (score[who][field] ??= [0, 0]);
      s[0] += ok ? 1 : 0;
      s[1] += 1;
    };
    for (const row of rows) {
      const reading: ModelReading = await readMessage(model, row.text);
      const rules = extract(row.text, null);
      const { ext, name } = mergeExtraction(rules, reading, null);
      const gold = (label: string) => row.spans.filter((s) => s[2] === label).map((s) => row.text.slice(s[0], s[1]));
      const g = { LOC: gold("LOC")[0], AMT: gold("AMT")[0], ACT: gold("ACT")[0], REASON: gold("REASON")[0], NAME: gold("NAME")[0] };
      if (g.LOC && districtOf(g.LOC)) {
        add("rules", "place", districtOf(rules.locationText) === districtOf(g.LOC));
        add("merged", "place", districtOf(ext.locationText) === districtOf(g.LOC));
      }
      const amount = g.AMT ? extractCapital(g.AMT, true) : null;
      if (amount !== null) {
        add("rules", "amount", rules.capital === amount);
        add("merged", "amount", ext.capital === amount);
      }
      const act = g.ACT ? extract(g.ACT, "activity").activityId : undefined;
      if (act) {
        add("rules", "business", rules.activityId === act);
        add("merged", "business", ext.activityId === act);
      }
      if (g.REASON) {
        add("rules", "reason", !!rules.reason);
        add("merged", "reason", !!ext.reason);
      }
      if (g.NAME) {
        add("rules", "name", false); // the rules only take a name as a direct answer to the name question
        add("merged", "name", !!name && (norm(g.NAME).includes(norm(name)) || norm(name).includes(norm(g.NAME))));
      }
      if (row.intent) {
        const ruleIntent = classifyIntent(row.text);
        add("rules", "intent", ruleIntent === toApp(row.intent));
        add("merged", "intent", mergeIntent(ruleIntent, reading, ext) === toApp(row.intent));
      }
    }
    const pct = (s?: [number, number]) => (s ? Math.round((100 * s[0]) / s[1]) : 0);
    const table = Object.keys(score.merged).map((f) => ({ field: f, n: score.merged[f][1], rules: pct(score.rules[f]), withModel: pct(score.merged[f]) }));
    if (process.env.NLU_REPORT) writeFileSync(process.env.NLU_REPORT, JSON.stringify(table, null, 1));
    for (const t of table) expect(t.withModel, t.field).toBeGreaterThanOrEqual(t.rules);
    expect(table.find((t) => t.field === "intent")!.withModel).toBeGreaterThanOrEqual(85);
  }, 240_000);
});
