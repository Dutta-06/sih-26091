/**
 * Main-thread access to the message model worker. `readWithModel` never throws and never blocks the chat for long:
 * if the model is unavailable or slower than the timeout, the rules answer alone (null).
 */
import type { ModelReading } from "../../core/nluModel";
import type { NluRequest, NluResponse } from "./nlu.worker";

let worker: Worker | null = null;
let failed = false;
let nextId = 1;
const pending = new Map<number, (r: NluResponse) => void>();

function nluWorker(): Worker | null {
  if (failed || typeof Worker === "undefined") return null;
  if (!worker) {
    try {
      worker = new Worker(new URL("./nlu.worker.ts", import.meta.url), { type: "module" });
      worker.onmessage = (e: MessageEvent<NluResponse>) => {
        pending.get(e.data.id)?.(e.data);
        pending.delete(e.data.id);
      };
      worker.onerror = () => {
        failed = true;
      };
    } catch {
      failed = true;
      return null;
    }
  }
  return worker;
}

function ask(text: string | null, timeoutMs: number): Promise<NluResponse | null> {
  const w = nluWorker();
  if (!w) return Promise.resolve(null);
  const id = nextId++;
  const base = new URL("models/nlu/", document.baseURI).href;
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      resolve(null);
    }, timeoutMs);
    pending.set(id, (r) => {
      clearTimeout(timer);
      resolve(r);
    });
    w.postMessage({ id, base, text } satisfies NluRequest);
  });
}

/** Start loading the model (call when the assistant opens). */
export function warmUpModel(): void {
  void ask(null, 60_000);
}

export async function readWithModel(text: string, timeoutMs = 2500): Promise<ModelReading | null> {
  const r = await ask(text, timeoutMs);
  return r?.reading ?? null;
}
