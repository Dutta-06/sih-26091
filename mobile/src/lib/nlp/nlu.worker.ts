/// <reference lib="webworker" />
/** Loads the message model once and reads messages off the main thread. */
import wasm from "onnxruntime-web/ort-wasm-simd-threaded.wasm?url";
import mjs from "onnxruntime-web/ort-wasm-simd-threaded.mjs?url";
import { loadModel, readMessage, type LoadedModel } from "./model";

export type NluRequest = { id: number; base: string; text: string | null };
export type NluResponse = { id: number; reading?: import("../../core/nluModel").ModelReading; ready?: boolean; error?: string };

let model: Promise<LoadedModel> | null = null;

function ensure(base: string): Promise<LoadedModel> {
  return (model ??= Promise.all([
    fetch(`${base}nlu.onnx`).then((r) => r.arrayBuffer()),
    fetch(`${base}tokenizer.json`).then((r) => r.json()),
    fetch(`${base}labels.json`).then((r) => r.json()),
  ]).then(([m, tokenizer, labels]) => loadModel({ model: m, tokenizer, labels }, { wasm, mjs })));
}

self.onmessage = async (e: MessageEvent<NluRequest>) => {
  const { id, base, text } = e.data;
  try {
    const m = await ensure(base);
    const reply: NluResponse = text === null ? { id, ready: true } : { id, reading: await readMessage(m, text) };
    (self as DedicatedWorkerGlobalScope).postMessage(reply);
  } catch (err) {
    model = null;
    (self as DedicatedWorkerGlobalScope).postMessage({ id, error: String((err as Error)?.message ?? err) } satisfies NluResponse);
  }
};
