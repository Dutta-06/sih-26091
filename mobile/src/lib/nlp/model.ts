/**
 * On-device message model (ml/nlu/train.py): multilingual-e5-small fine-tuned to tag NAME / LOC / AMT / ACT / REASON
 * spans and classify the intent, int8 ONNX run by onnxruntime-web. Span decoding mirrors train.py.decode_spans.
 */
import * as ort from "onnxruntime-web/wasm";
import type { ModelReading, SpanLabel } from "../../core/nluModel";
import { UnigramTokenizer, type TokenizerSpec } from "./tokenizer";

export interface ModelAssets {
  model: ArrayBuffer | Uint8Array;
  tokenizer: TokenizerSpec;
  labels: { tags: string[]; intents: string[]; maxLen: number };
}

export interface LoadedModel {
  session: ort.InferenceSession;
  tokenizer: UnigramTokenizer;
  labels: ModelAssets["labels"];
}

export async function loadModel(a: ModelAssets, wasm?: { wasm: string; mjs: string }): Promise<LoadedModel> {
  ort.env.wasm.numThreads = 1;
  if (wasm) ort.env.wasm.wasmPaths = wasm;
  const session = await ort.InferenceSession.create(a.model instanceof Uint8Array ? a.model : new Uint8Array(a.model), { executionProviders: ["wasm"] });
  return { session, tokenizer: new UnigramTokenizer(a.tokenizer), labels: a.labels };
}

const EDGE = /[\s,.;:!?।"'()]/u;

const softmax =(xs: Float32Array | number[]): number[] => {
  const max = Math.max(...xs);
  const e = Array.from(xs, (x) => Math.exp(x - max));
  const s = e.reduce((a, b) => a + b, 0);
  return e.map((x) => x / s);
};

/** Token tags → character spans; same-label pieces split by at most one short word are joined, 1–2 letter pieces dropped. */
export function decodeSpans(text: string, offsets: [number, number][], tags: string[], probs: number[]): { start: number; end: number; label: SpanLabel; confidence: number }[] {
  const spans: { start: number; end: number; label: SpanLabel; conf: number[] }[] = [];
  let cur: (typeof spans)[number] | null = null;
  offsets.forEach(([a, b], i) => {
    if (a === b) return;
    const tag = tags[i];
    const seg = text.slice(a, b);
    const a2 = a + (seg.length - seg.trimStart().length);
    if (tag === "O") {
      if (cur) spans.push(cur);
      cur = null;
      return;
    }
    const [kind, label] = tag.split("-") as ["B" | "I", SpanLabel];
    if (kind === "B" || !cur || cur.label !== label) {
      if (cur) spans.push(cur);
      cur = { start: a2, end: b, label, conf: [probs[i]] };
    } else {
      cur.end = b;
      cur.conf.push(probs[i]);
    }
  });
  if (cur) spans.push(cur);
  const merged: typeof spans = [];
  for (const s of spans) {
    const last = merged[merged.length - 1];
    if (last && last.label === s.label) {
      const gap = text.slice(last.end, s.start);
      if (gap.trim().length <= 4 && gap.trim().split(/\s+/).filter(Boolean).length <= 1) {
        last.end = s.end;
        last.conf.push(...s.conf);
        continue;
      }
    }
    merged.push({ ...s, conf: [...s.conf] });
  }
  // punctuation at the edges is not part of a name, place, amount, business or reason
  for (const s of merged) {
    while (s.start < s.end && EDGE.test(text[s.start])) s.start++;
    while (s.end > s.start && EDGE.test(text[s.end - 1])) s.end--;
  }
  return merged
    .filter((s) => text.slice(s.start, s.end).trim().length > 2 || (s.label === "AMT" && s.end > s.start))
    .map((s) => ({ start: s.start, end: s.end, label: s.label, confidence: s.conf.reduce((a, b) => a + b, 0) / s.conf.length }));
}

export async function readMessage(m: LoadedModel, text: string): Promise<ModelReading> {
  const clean = text.normalize("NFC").slice(0, 400);
  const enc = m.tokenizer.encode(clean);
  let ids = enc.ids;
  let offsets = enc.offsets;
  if (ids.length > m.labels.maxLen) {
    ids = [...ids.slice(0, m.labels.maxLen - 1), ids[ids.length - 1]];
    offsets = [...offsets.slice(0, m.labels.maxLen - 1), [0, 0]];
  }
  const n = ids.length;
  const feeds = {
    input_ids: new ort.Tensor("int64", BigInt64Array.from(ids.map(BigInt)), [1, n]),
    attention_mask: new ort.Tensor("int64", new BigInt64Array(n).fill(1n), [1, n]),
  };
  const out = await m.session.run(feeds);
  const tagLogits = out.tags.data as Float32Array;
  const classes = m.labels.tags.length;
  const tags: string[] = [];
  const probs: number[] = [];
  for (let i = 0; i < n; i++) {
    const p = softmax(tagLogits.subarray(i * classes, (i + 1) * classes));
    const best = p.indexOf(Math.max(...p));
    tags.push(m.labels.tags[best]);
    probs.push(p[best]);
  }
  const ip = softmax(out.intent.data as Float32Array);
  const bi = ip.indexOf(Math.max(...ip));
  return {
    intent: m.labels.intents[bi],
    intentConfidence: ip[bi],
    spans: decodeSpans(clean, offsets, tags, probs).map((s) => ({ label: s.label, text: clean.slice(s.start, s.end), confidence: s.confidence })),
  };
}
