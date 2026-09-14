/**
 * Location resolution over the bundled village / district / state tables — the offline counterpart of
 * data_connectors/geocoding.resolve_location (LGD/Census table → district HQ → state centroid; no Nominatim).
 *
 * Matching is whole-token on normalised text in any script (lower-case, NFC, nukta and chandrabindu folded,
 * punctuation as separators). Repeated village names yield several candidates; a district, block or state named
 * in the same text narrows them, otherwise the user chooses (chosenLgd). Only a village-table match is "real".
 */
import { district as packDistrict, districts, stateReference, villages } from "./pack";
import type { LocationCandidate, Msg, PackDistrict, PackVillage, ResolvedLocation } from "./types";

const R = 6371.0088;
const rad = (d: number) => (d * Math.PI) / 180;

/** Great-circle distance in km (common.reference.haversine_km). */
export function haversineKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const h = Math.sin(rad(b.lat - a.lat) / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lon - a.lon) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Normalised tokens: NFC, lower-case, Devanagari nukta removed and chandrabindu → anusvara. */
export function tokens(text: string): string[] {
  return (text ?? "")
    .normalize("NFC")
    .toLowerCase()
    .replace(/़/g, "")
    .replace(/ँ/g, "ं")
    .split(/[^\p{L}\p{M}\p{N}]+/u)
    .filter(Boolean);
}

/** Start index of `needle` as a contiguous token run inside `hay`, excluding already-used positions; -1 if absent. */
function findRun(hay: string[], needle: string[], used: Set<number>): number {
  if (!needle.length) return -1;
  outer: for (let i = 0; i + needle.length <= hay.length; i++) {
    for (let j = 0; j < needle.length; j++) if (hay[i + j] !== needle[j] || used.has(i + j)) continue outer;
    return i;
  }
  return -1;
}

/** Words that are also common Hindi words ("गया" = went): only a location with a place cue next to them. */
const CONTEXT_ONLY = new Set(["गया"]);
const PLACE_CUES = new Set(["जिला", "जिले", "जिल", "district", "बिहार", "bihar", "जनपद"]);

interface Hit<T> {
  item: T;
  start: number;
  len: number;
  n: number; // tokens covered
}

function matchNames<T>(hay: string[], raw: string, items: T[], names: (t: T) => string[], used: Set<number>): Hit<T>[] {
  const hits: Hit<T>[] = [];
  for (const item of items) {
    let best: Hit<T> | null = null;
    for (const name of names(item)) {
      // Very short Latin aliases ("UP", "MP") only count when written in capitals in the original text
      if (/^[a-z]{1,2}$/i.test(name) && !new RegExp(`(?<![\\p{L}])${name.toUpperCase()}(?![\\p{L}])`, "u").test(raw)) continue;
      const needle = tokens(name);
      const start = findRun(hay, needle, used);
      if (start < 0) continue;
      if (needle.length === 1 && CONTEXT_ONLY.has(needle[0])) {
        const near = [hay[start - 1], hay[start + 1]].some((t) => t !== undefined && PLACE_CUES.has(t));
        if (!near && hay.length > 1) continue;
      }
      const len = needle.join(" ").length;
      if (!best || len > best.len) best = { item, start, len, n: needle.length };
    }
    if (best) hits.push(best);
  }
  return hits;
}

const longest = <T>(hits: Hit<T>[]) => {
  const max = Math.max(0, ...hits.map((h) => h.len));
  return hits.filter((h) => h.len === max);
};
const markUsed = (used: Set<number>, h: Hit<unknown>) => {
  for (let i = 0; i < h.n; i++) used.add(h.start + i);
};

function villageCandidate(v: PackVillage): LocationCandidate {
  return { lgd: v.lgd, village: v.name, block: v.block, district: packDistrict(v.district)!, lat: v.lat, lon: v.lon, method: "village_table" };
}

function districtCandidate(d: PackDistrict): LocationCandidate {
  return { lgd: null, village: null, block: null, district: d, lat: d.lat, lon: d.lon, method: "district_table" };
}

interface StateInfo {
  name: string;
  hi: string;
  aliases: string[];
  lat: number;
  lon: number;
}
function statesList(): StateInfo[] {
  return Object.entries(stateReference().states).map(([name, s]) => ({
    name,
    hi: (s.aliases ?? []).find((a) => /[ऀ-ॿ]/.test(a)) ?? name,
    aliases: s.aliases ?? [],
    lat: s.lat,
    lon: s.lon,
  }));
}

/** Coarse state-level stand-in district (population/area unknown → 0; always paired with a limitation). */
function stateCandidate(s: StateInfo): LocationCandidate {
  const d: PackDistrict = {
    id: `state:${s.name.toLowerCase().replace(/\s+/g, "_")}`,
    name: { en: s.name, hi: s.hi },
    aliases: [s.name.toLowerCase(), ...s.aliases.map((a) => a.toLowerCase())],
    state: s.name,
    lat: s.lat,
    lon: s.lon,
    population: 0,
    areaSqKm: 0,
  };
  return { lgd: null, village: null, block: null, district: d, lat: s.lat, lon: s.lon, method: "state_centroid" };
}

const districtNames = (d: PackDistrict) => [d.name.en, d.name.hi, ...d.aliases];

export function resolveLocation(text: string, chosenLgd?: string | null): ResolvedLocation {
  const query = text ?? "";
  const hay = tokens(query);
  const limitations: Msg[] = [];
  const used = new Set<number>();
  const done = (candidates: LocationCandidate[], chosen: LocationCandidate | null): ResolvedLocation => ({
    query,
    candidates,
    chosen,
    confidence: chosen?.method === "village_table" ? "real" : "estimated",
    limitations,
  });

  // 1. village table (longest name wins; repeated names give several candidates)
  let vHits = longest(matchNames(hay, query, villages(), (v) => [v.name.en, v.name.hi], used));
  for (const h of vHits) markUsed(used, h);

  // context stated alongside the village: district, block, state
  const dHits = longest(matchNames(hay, query, districts(), districtNames, used));
  const sHits = matchNames(hay, query, statesList(), (s) => [s.name, ...s.aliases], used);
  const statedDistricts = new Set(dHits.map((h) => h.item.id));
  const statedStates = new Set(sHits.map((h) => h.item.name));

  if (vHits.length) {
    let narrowed = vHits;
    if (statedDistricts.size) narrowed = narrowed.filter((h) => statedDistricts.has(h.item.district));
    if (statedStates.size) narrowed = narrowed.filter((h) => statedStates.has(packDistrict(h.item.district)!.state));
    if (narrowed.length > 1) {
      const byBlock = narrowed.filter((h) => findRun(hay, tokens(h.item.block.en), used) >= 0 || findRun(hay, tokens(h.item.block.hi), used) >= 0);
      if (byBlock.length) narrowed = byBlock;
    }
    if (narrowed.length) {
      const candidates = narrowed.map((h) => villageCandidate(h.item)).sort((a, b) => (a.lgd! < b.lgd! ? -1 : 1));
      if (candidates.length === 1) return done(candidates, candidates[0]);
      const pick = chosenLgd ? candidates.find((c) => c.lgd === chosenLgd) ?? null : null;
      if (!pick) {
        if (chosenLgd) limitations.push({ key: "core.c1.geo.choice_invalid", vars: { lgd: chosenLgd } });
        limitations.push({ key: "core.c1.geo.ambiguous", vars: { name: narrowed[0].item.name.en, count: candidates.length } });
      }
      return done(candidates, pick);
    }
    limitations.push({ key: "core.c1.geo.village_not_in_district", vars: { name: vHits[0].item.name.en } });
    vHits = [];
  }

  // chosen code without a text match (e.g. the UI kept the LGD from an earlier turn)
  if (chosenLgd) {
    const v = villages().find((x) => x.lgd === chosenLgd);
    if (v) return done([villageCandidate(v)], villageCandidate(v));
  }

  // 2. district table (HQ coordinates), also reached via a block name
  let dList = dHits.map((h) => h.item);
  if (statedStates.size) dList = dList.filter((d) => statedStates.has(d.state));
  if (!dList.length) {
    const blocks = new Map<string, PackVillage>();
    for (const v of villages()) blocks.set(`${v.district}|${v.block.en}`, v);
    const bHits = longest(matchNames(hay, query, [...blocks.values()], (v) => [v.block.en, v.block.hi], used));
    dList = [...new Set(bHits.map((h) => h.item.district))].map((id) => packDistrict(id)!);
  }
  if (dList.length) {
    const candidates = dList.map(districtCandidate);
    const pick = candidates.length === 1 ? candidates[0] : null;
    limitations.push({ key: "core.c1.geo.district_hq", vars: { district: dList[0].name.en } });
    if (!pick) limitations.push({ key: "core.c1.geo.ambiguous", vars: { name: query.trim(), count: candidates.length } });
    return done(candidates, pick);
  }

  // 3. state centroid
  if (sHits.length) {
    const candidates = sHits.map((h) => stateCandidate(h.item));
    limitations.push({ key: "core.c1.geo.state_centroid", vars: { state: sHits[0].item.name } });
    return done(candidates, candidates.length === 1 ? candidates[0] : null);
  }

  limitations.push({ key: "core.c1.geo.unresolved", vars: { query: query.trim() } });
  return done([], null);
}
