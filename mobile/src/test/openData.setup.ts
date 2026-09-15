/** Tests read the same bundled open data as the app (public/data), from disk. */
import { existsSync, readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { loadIfsc, loadPincodes, loadPlaces, loadVillages } from "../core/openData";

const buf = (path: string): ArrayBuffer => {
  const b = gunzipSync(readFileSync(path));
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
};

if (existsSync("public/data/villages.dat")) {
  loadVillages(buf("public/data/villages.dat"));
  loadPlaces(buf("public/data/places.dat"));
  loadPincodes(JSON.parse(gunzipSync(readFileSync("public/data/pincodes.dat")).toString("utf8")));
  loadIfsc(JSON.parse(gunzipSync(readFileSync("public/data/ifsc.dat")).toString("utf8")));
}
