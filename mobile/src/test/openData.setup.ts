/** Tests read the same bundled open data as the app (public/data), from disk. */
import { existsSync, readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { loadIfsc, loadPincodes, loadPlaces, loadVillages } from "../core/openData";

const buf = (path: string): ArrayBuffer => {
  const b = gunzipSync(readFileSync(path));
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
};

if (existsSync("public/data/villages.bin.gz")) {
  loadVillages(buf("public/data/villages.bin.gz"));
  loadPlaces(buf("public/data/places.bin.gz"));
  loadPincodes(JSON.parse(gunzipSync(readFileSync("public/data/pincodes.json.gz")).toString("utf8")));
  loadIfsc(JSON.parse(gunzipSync(readFileSync("public/data/ifsc.json.gz")).toString("utf8")));
}
