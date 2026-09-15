/**
 * Open data bundled with the app, loaded once at start-up (public/data, built by scripts/build_open_villages.py and
 * scripts/build_open_places.py):
 *  - every Census 2011 village (645k: name, sub-district, district, point, population) — CC0 via datameet / Census of India;
 *  - real places from Overture Maps (433k shops, banks, schools, bus/train stations, post offices, suppliers) — CDLA-P-2.0;
 *  - India Post PIN code areas (19k) — CC0 via data.gov.in; bank branches by IFSC (183k) — MIT, Razorpay IFSC.
 *
 * Villages and places stay in typed arrays; a first-word hash index serves name lookups and a 0.1° grid serves radius
 * queries, so a lookup touches only a few hundred rows. Everything is optional: before loading, or if loading fails,
 * the app falls back to the detailed pack districts and generated local tables.
 */
import type { PackPoi, PackVillage } from "./types";
import categoryMap from "./data/open_place_categories.json";

const CELL = 10; // cells per degree (≈11 km)
const DEG = 1e5;

interface VillageTable {
  n: number;
  names: Uint8Array;
  offsets: Uint32Array;
  sub: Uint16Array;
  dist: Uint16Array;
  lat: Int32Array;
  lon: Int32Array;
  pop: Uint32Array;
  districts: string[];
  subdistricts: string[];
  byFirstWord: Map<number, number[]>;
  grid: Map<number, number[]>;
  byDistrict: Map<string, [number, number]>; // first index, end (villages are sorted by district)
}

interface PlaceTable {
  n: number;
  names: Uint8Array;
  offsets: Uint32Array;
  lat: Int32Array;
  lon: Int32Array;
  cat: Uint16Array;
  dist: Uint16Array;
  categories: string[];
  districts: string[];
  grid: Map<number, number[]>;
}

export interface BankBranch {
  ifsc: string;
  bank: string;
  branch: string;
  district: string;
  state: string;
  upi: boolean;
}

export interface PinArea {
  pin: string;
  lat: number;
  lon: number;
  district: string | null;
  office: string;
}

let villagesT: VillageTable | null = null;
let placesT: PlaceTable | null = null;
let pins: Record<string, [number, number, string | null, string]> | null = null;
let ifsc: Record<string, [string, [string, string, string, string, 0 | 1][]]> | null = null;

const decoder = new TextDecoder();
const cellKey = (latCell: number, lonCell: number) => latCell * 4000 + lonCell;

/** FNV-1a over the lower-cased ASCII letters/digits of a word (bytes). */
function hashWord(bytes: Uint8Array, start: number, end: number): number {
  let h = 2166136261;
  for (let i = start; i < end; i++) {
    let c = bytes[i];
    if (c >= 65 && c <= 90) c += 32;
    h = Math.imul(h ^ c, 16777619);
  }
  return h >>> 0;
}
const isWordByte = (c: number) => (c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c >= 128;

export function hashToken(token: string): number {
  const b = new TextEncoder().encode(token);
  return hashWord(b, 0, b.length);
}

function readHeader(buf: ArrayBuffer, magic: string) {
  const view = new DataView(buf);
  const got = String.fromCharCode(...new Uint8Array(buf, 0, 4));
  if (got !== magic) throw new Error(`bad open-data file ${got}`);
  const n = view.getUint32(4, true);
  const hlen = view.getUint32(8, true);
  const header = JSON.parse(decoder.decode(new Uint8Array(buf, 12, hlen)));
  let o = 12 + hlen;
  const nb = view.getUint32(o, true);
  o += 4;
  const names = new Uint8Array(buf, o, nb);
  o += nb;
  return { view, n, header, names, o };
}

/** Typed-array view at an aligned offset (copies when the offset is not a multiple of the element size). */
function typed<T extends Uint16Array | Uint32Array | Int32Array>(Ctor: { new (b: ArrayBuffer, o: number, n: number): T; new (n: number): T; BYTES_PER_ELEMENT: number }, buf: ArrayBuffer, offset: number, count: number): T {
  if (offset % Ctor.BYTES_PER_ELEMENT === 0) return new Ctor(buf, offset, count);
  const copy = buf.slice(offset, offset + count * Ctor.BYTES_PER_ELEMENT);
  return new Ctor(copy, 0, count);
}

export function loadVillages(buf: ArrayBuffer): void {
  const { n, header, names, o: start } = readHeader(buf, "VIL1");
  let o = start;
  const offsets = typed(Uint32Array, buf, o, n + 1); o += 4 * (n + 1);
  const sub = typed(Uint16Array, buf, o, n); o += 2 * n;
  const dist = typed(Uint16Array, buf, o, n); o += 2 * n;
  const lat = typed(Int32Array, buf, o, n); o += 4 * n;
  const lon = typed(Int32Array, buf, o, n); o += 4 * n;
  const pop = typed(Uint32Array, buf, o, n);
  const byFirstWord = new Map<number, number[]>();
  const grid = new Map<number, number[]>();
  const byDistrict = new Map<string, [number, number]>();
  for (let i = 0; i < n; i++) {
    const a = offsets[i];
    const b = offsets[i + 1];
    let e = a;
    while (e < b && isWordByte(names[e])) e++;
    const h = hashWord(names, a, e);
    const list = byFirstWord.get(h);
    if (list) list.push(i);
    else byFirstWord.set(h, [i]);
    const k = cellKey(Math.floor((lat[i] / DEG) * CELL), Math.floor((lon[i] / DEG) * CELL));
    const cell = grid.get(k);
    if (cell) cell.push(i);
    else grid.set(k, [i]);
    const d = header.districts[dist[i]];
    const span = byDistrict.get(d);
    if (span) span[1] = i + 1;
    else byDistrict.set(d, [i, i + 1]);
  }
  villagesT = { n, names, offsets, sub, dist, lat, lon, pop, districts: header.districts, subdistricts: header.subdistricts, byFirstWord, grid, byDistrict };
}

export function loadPlaces(buf: ArrayBuffer): void {
  const { n, header, names, o: start } = readHeader(buf, "PLC1");
  let o = start;
  const offsets = typed(Uint32Array, buf, o, n + 1); o += 4 * (n + 1);
  const lat = typed(Int32Array, buf, o, n); o += 4 * n;
  const lon = typed(Int32Array, buf, o, n); o += 4 * n;
  const cat = typed(Uint16Array, buf, o, n); o += 2 * n;
  const dist = typed(Uint16Array, buf, o, n);
  const grid = new Map<number, number[]>();
  for (let i = 0; i < n; i++) {
    const k = cellKey(Math.floor((lat[i] / DEG) * CELL), Math.floor((lon[i] / DEG) * CELL));
    const cell = grid.get(k);
    if (cell) cell.push(i);
    else grid.set(k, [i]);
  }
  placesT = { n, names, offsets, lat, lon, cat, dist, categories: header.categories, districts: header.districts, grid };
}

export function loadPincodes(json: Record<string, [number, number, string | null, string]>): void {
  pins = json;
}
export function loadIfsc(json: Record<string, [string, [string, string, string, string, 0 | 1][]]>): void {
  ifsc = json;
}

export const openVillagesLoaded = () => villagesT !== null;
export const openPlacesLoaded = () => placesT !== null;

/* ------------------------------------------------------------------ villages */

function villageAt(t: VillageTable, i: number): PackVillage {
  const name = decoder.decode(t.names.subarray(t.offsets[i], t.offsets[i + 1]));
  const block = t.subdistricts[t.sub[i]];
  return { lgd: `c${i}`, name: { en: name, hi: name }, block: { en: block, hi: block }, district: t.districts[t.dist[i]], lat: t.lat[i] / DEG, lon: t.lon[i] / DEG, population: t.pop[i] };
}

/** Census villages whose name starts with one of the given words (callers check the full name). */
export function villagesStartingWith(words: string[]): PackVillage[] {
  const t = villagesT;
  if (!t) return [];
  const out: PackVillage[] = [];
  const seen = new Set<number>();
  for (const w of new Set(words)) {
    for (const i of t.byFirstWord.get(hashToken(w)) ?? []) {
      if (!seen.has(i)) {
        seen.add(i);
        out.push(villageAt(t, i));
      }
    }
  }
  return out;
}

/** Census village by the id given out in `lgd` ("c<index>"). */
export function villageById(id: string): PackVillage | null {
  const t = villagesT;
  const i = /^c(\d+)$/.exec(id)?.[1];
  return t && i !== undefined && +i < t.n ? villageAt(t, +i) : null;
}

function cellsAround(lat: number, lon: number, radiusKm: number): number[] {
  const dLat = radiusKm / 111;
  const dLon = radiusKm / (111 * Math.max(0.2, Math.cos((lat * Math.PI) / 180)));
  const keys: number[] = [];
  for (let a = Math.floor((lat - dLat) * CELL); a <= Math.floor((lat + dLat) * CELL); a++) {
    for (let b = Math.floor((lon - dLon) * CELL); b <= Math.floor((lon + dLon) * CELL); b++) keys.push(cellKey(a, b));
  }
  return keys;
}

const km = (la1: number, lo1: number, la2: number, lo2: number) => {
  const r = Math.PI / 180;
  const h = Math.sin(((la2 - la1) * r) / 2) ** 2 + Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin(((lo2 - lo1) * r) / 2) ** 2;
  return 2 * 6371.0088 * Math.asin(Math.sqrt(h));
};

/** Census villages within radiusKm, optionally only those of districts accepted by `keep`. */
export function openVillagesNear(lat: number, lon: number, radiusKm: number, keep?: (districtId: string) => boolean): PackVillage[] {
  const t = villagesT;
  if (!t) return [];
  const out: PackVillage[] = [];
  for (const k of cellsAround(lat, lon, radiusKm)) {
    for (const i of t.grid.get(k) ?? []) {
      if (keep && !keep(t.districts[t.dist[i]])) continue;
      if (km(lat, lon, t.lat[i] / DEG, t.lon[i] / DEG) <= radiusKm) out.push(villageAt(t, i));
    }
  }
  return out;
}

/** All Census villages of a district, or null when the table is not loaded. */
export function openVillagesOfDistrict(districtId: string): PackVillage[] | null {
  const t = villagesT;
  if (!t) return null;
  const span = t.byDistrict.get(districtId);
  if (!span) return [];
  const out: PackVillage[] = [];
  for (let i = span[0]; i < span[1]; i++) out.push(villageAt(t, i));
  return out;
}

/* ------------------------------------------------------------------ places */

const CATEGORY = categoryMap as Record<string, { kind: PackPoi["kind"] | "post_office"; activities: string[] }>;

export interface OpenPlace {
  poi: PackPoi;
  category: string;
  activities: string[];
  district: string;
}

/** Real places within radiusKm, with their Overture category and the activities they evidence. */
export function openPlacesNear(lat: number, lon: number, radiusKm: number): OpenPlace[] {
  const t = placesT;
  if (!t) return [];
  const out: OpenPlace[] = [];
  for (const k of cellsAround(lat, lon, radiusKm)) {
    for (const i of t.grid.get(k) ?? []) {
      const pl = t.lat[i] / DEG;
      const po = t.lon[i] / DEG;
      if (km(lat, lon, pl, po) > radiusKm) continue;
      const category = t.categories[t.cat[i]];
      const meta = CATEGORY[category];
      const name = decoder.decode(t.names.subarray(t.offsets[i], t.offsets[i + 1]));
      const kind: PackPoi["kind"] = meta.kind === "post_office" ? "transport" : meta.kind;
      out.push({
        poi: { id: `o${i}`, name: { en: name, hi: name }, kind, tags: [["overture", category], ...(meta.kind === "post_office" ? ([["amenity", "post_office"]] as [string, string][]) : [])], lat: pl, lon: po },
        category,
        activities: meta.activities,
        district: t.districts[t.dist[i]],
      });
    }
  }
  return out;
}

/* ------------------------------------------------------------------ PIN codes and bank branches */

export function pinArea(pin: string): PinArea | null {
  const hit = pins?.[pin];
  return hit ? { pin, lat: hit[0], lon: hit[1], district: hit[2], office: hit[3] } : null;
}

export const pincodesLoaded = () => pins !== null;
export const ifscLoaded = () => ifsc !== null;

export function bankBranch(code: string): BankBranch | null {
  const c = code.trim().toUpperCase();
  const bank = ifsc?.[c.slice(0, 4)];
  const row = bank?.[1].find((b) => b[0] === c.slice(4));
  return bank && row ? { ifsc: c, bank: bank[0], branch: row[1], district: row[2], state: row[3], upi: row[4] === 1 } : null;
}
