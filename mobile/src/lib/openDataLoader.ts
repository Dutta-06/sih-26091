/**
 * Loads the bundled open data (villages, places, PIN codes, bank branches) at start-up. Files are gzip-compressed and
 * unpacked with the WebView's native DecompressionStream. Failures are tolerated: the app then works from the
 * detailed pack districts and generated local tables alone.
 */
import { loadIfsc, loadPincodes, loadPlaces, loadVillages } from "../core/openData";

async function gunzip(path: string): Promise<ArrayBuffer> {
  const res = await fetch(new URL(path, document.baseURI));
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  const buf = await res.arrayBuffer();
  // Files are gzip data named .dat (Android packaging unpacks and renames .gz assets); a server may also have unpacked them
  const bytes = new Uint8Array(buf, 0, Math.min(2, buf.byteLength));
  if (bytes[0] !== 0x1f || bytes[1] !== 0x8b) return buf;
  return new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
}

const json = async (path: string) => JSON.parse(new TextDecoder().decode(await gunzip(path)));

export async function loadOpenData(): Promise<void> {
  const tasks: [string, Promise<void>][] = [
    ["villages", gunzip("data/villages.dat").then(loadVillages)],
    ["places", gunzip("data/places.dat").then(loadPlaces)],
    ["pincodes", json("data/pincodes.dat").then(loadPincodes)],
    ["ifsc", json("data/ifsc.dat").then(loadIfsc)],
  ];
  const results = await Promise.allSettled(tasks.map(([, p]) => p));
  results.forEach((r, i) => {
    if (r.status === "rejected") console.warn(`open data ${tasks[i][0]} not loaded:`, r.reason);
  });
}
