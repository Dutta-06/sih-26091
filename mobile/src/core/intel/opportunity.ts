/**
 * Opportunity (port of module1_feasibility/opportunity_agent.py).
 * TF-IDF retrieval over the sector_reports collection restricted to the documents about this activity; sub-niches
 * from `Sub-niche:` headings or `- Name: description` bullets; local feedback (TDD 5.6) attached as evidence ids and
 * used as a saturation signal. Otherwise niche saturation stays "unknown" until swot.crossCheckSaturation.
 */
import { feedback } from "../pack";
import { retrieve } from "../retrieval";
import type { LocationCandidate, OpportunityIntel, PackDoc, Saturation, SubNicheIntel } from "../types";
import { type CatalogActivity, isAscii, msg, src } from "./catalog";

export const MIN_RETRIEVAL_SCORE = 0.02;
export const OPPORTUNITY_TOP_K = 5;
const HIGH_CUES = ["saturated", "too many", "overcrowded", "crowded", "many sellers", "price war", "stiff competition"];
const LOW_CUES = ["unserved", "no one sells", "nobody sells", "shortage", "few sellers", "no shop", "have to travel", "demand exceeds"];
const STOPWORDS = new Set(["local", "village", "supply", "sale", "sales", "services", "products", "direct", "small", "farmers"]);

const stem = (source: string) => source.replace(/^.*[\\/]/, "").replace(/\.[^.]+$/, "").toLowerCase();

/** 2 = document about this activity, 1 = same sector with a keyword in its topic, 0 = unrelated. */
export function docRelevance(source: string, activity: CatalogActivity): number {
  const s = stem(source);
  const i = s.indexOf("__");
  const prefix = i >= 0 ? s.slice(0, i) : s;
  const topic = i >= 0 ? s.slice(i + 2) : "";
  const cid = activity.id;
  if (prefix === cid || (topic && (cid.includes(topic) || topic.includes(cid)))) return 2;
  const keywords = activity.keywords.filter(isAscii).map((k) => k.toLowerCase());
  const topicWords = topic.replace(/_/g, " ");
  const kwInTopic = keywords.some((k) => new RegExp(`\\b${k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(topicWords));
  if (keywords.includes(prefix) || (prefix === activity.sector && kwInTopic)) return 1;
  return 0;
}

export function extractSubNiches(chunk: Pick<PackDoc, "heading" | "text">): [string, string][] {
  const m = /^\s*sub[- ]?niche\s*[:-]\s*(.+)/i.exec(chunk.heading);
  if (m) return [[m[1].trim(), chunk.text.split(/\s+/).filter(Boolean).join(" ")]];
  const pairs: [string, string][] = [];
  for (const line of chunk.text.split(/\r?\n/)) {
    const b = /^\s*[-*•]\s+\**([^:*\n]{3,70}?)\**\s*[:–—]\s+(.+)/.exec(line);
    if (b) pairs.push([b[1].trim(), b[2].trim()]);
  }
  return pairs;
}

export function feedbackSignal(text: string): Saturation | null {
  const t = text.toLowerCase();
  const high = HIGH_CUES.some((c) => t.includes(c));
  const low = LOW_CUES.some((c) => t.includes(c));
  return high && !low ? "high" : low && !high ? "low" : null;
}

const mentions = (name: string, text: string) => {
  const tokens = (name.toLowerCase().match(/[a-z]{5,}/g) ?? []).filter((t) => !STOPWORDS.has(t));
  const lowered = text.toLowerCase();
  return tokens.some((t) => lowered.includes(t));
};

export function opportunityIntel(activity: CatalogActivity, location: LocationCandidate | null): OpportunityIntel {
  const intel: OpportunityIntel = { confidence: "estimated", sources: [], limitations: [], niches: [], saturation: "unknown" };
  const query = [activity.category, activity.sector.replace(/_/g, " "), ...activity.keywords.filter(isAscii)].join(" ");
  const chunks = retrieve("sector_reports", query, 60, MIN_RETRIEVAL_SCORE);
  const scored = chunks.map((c) => [c, docRelevance(c.source, activity)] as const);
  const best = Math.max(0, ...scored.map(([, r]) => r));
  const relevant = scored.filter(([, r]) => r > 0 && r === best).map(([c]) => c);

  const niches = new Map<string, SubNicheIntel>();
  for (const chunk of relevant) {
    for (const [name, detail] of extractSubNiches(chunk)) {
      const key = name.toLowerCase();
      const existing = niches.get(key);
      if (existing) {
        existing.relevance = Math.max(existing.relevance, chunk.score);
        continue;
      }
      niches.set(key, { name, detail: detail.slice(0, 400), source: chunk.source, relevance: chunk.score, saturation: "unknown", evidenceIds: [] });
    }
  }
  const list = [...niches.values()].sort((a, b) => b.relevance - a.relevance).slice(0, OPPORTUNITY_TOP_K);
  const docs = [...new Set(list.map((n) => n.source))].sort();
  intel.sources.push(src(`Sector reference documents (sample): ${docs.join(", ") || "none"}`, `क्षेत्र संदर्भ दस्तावेज़ (नमूना): ${docs.join(", ") || "कोई नहीं"}`, "estimated"));
  intel.limitations.push(msg(list.length ? "c2.opp.sampleDocs" : "c2.opp.noDocs"));

  const rows = location ? feedback(location.district.id, activity.id) : [];
  const overall = new Set<Saturation>();
  const conflicted = new Set<string>();
  for (const row of rows) {
    const text = `${row.topic}: ${row.text.en}`;
    for (const niche of list) if (mentions(niche.name, text)) niche.evidenceIds.push(row.id);
    const signal = feedbackSignal(text);
    if (!signal) continue;
    overall.add(signal);
    for (const niche of list) {
      if (!mentions(niche.name, text) || conflicted.has(niche.name)) continue;
      if (niche.saturation === "unknown" || niche.saturation === signal) niche.saturation = signal;
      else {
        conflicted.add(niche.name);
        niche.saturation = "unknown";
      }
    }
  }
  if (overall.size === 1) {
    intel.saturation = [...overall][0];
    intel.limitations.push(msg("c2.opp.feedbackOnlySaturation"));
  }
  if (rows.length) intel.sources.push(src(`Local feedback records: ${rows.length}`, `स्थानीय प्रतिक्रिया रिकॉर्ड: ${rows.length}`, "real"));
  else intel.limitations.push(msg("c2.opp.noFeedback"));
  intel.niches = list;
  return intel;
}
