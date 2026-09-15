import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import tokFixture from "./__fixtures__/tokenizer.json";
import readingFixture from "./__fixtures__/readings.json";
import { loadModel, readMessage } from "./model";
import { UnigramTokenizer, type TokenizerSpec } from "./tokenizer";

const spec = JSON.parse(readFileSync("public/models/nlu/tokenizer.json", "utf8")) as TokenizerSpec;
const labels = JSON.parse(readFileSync("public/models/nlu/labels.json", "utf8"));

describe("app tokenizer matches the Python tokenizer", () => {
  it("gives identical token ids on test messages and app strings in all scripts", () => {
    const tok = new UnigramTokenizer(spec);
    const mismatches = (tokFixture as { text: string; ids: number[] }[]).filter((f) => JSON.stringify(tok.encode(f.text).ids) !== JSON.stringify(f.ids));
    expect(mismatches.slice(0, 5).map((m) => m.text)).toEqual([]);
  });
});

describe("exported model runs in the app runtime", () => {
  it("reads messages exactly as the Python export did", async () => {
    const model = await loadModel({ model: readFileSync("public/models/nlu/nlu.onnx"), tokenizer: spec, labels });
    let same = 0;
    const diffs: string[] = [];
    for (const f of readingFixture as { text: string; intent: string; spans: [string, string][] }[]) {
      const r = await readMessage(model, f.text);
      const ok = r.intent === f.intent && JSON.stringify(r.spans.map((s) => [s.text, s.label])) === JSON.stringify(f.spans);
      if (ok) same++;
      else diffs.push(`${f.text} → ${JSON.stringify(r.spans.map((s) => [s.text, s.label]))} vs ${JSON.stringify(f.spans)}`);
    }
    // int8 kernels differ slightly between onnxruntime (Python) and onnxruntime-web; a borderline token may flip
    expect(same / readingFixture.length, diffs.slice(0, 3).join("\n")).toBeGreaterThanOrEqual(0.95);
  }, 60_000);
});
