/**
 * Risk (port of module1_feasibility/risk_agent.py over the data pack).
 *  - Route: hub = nearest market/haat/transport POI within 30 km, else nearest pack district HQ (≤ 150 km);
 *    distance = haversine × 1.3 (estimate; no routing engine on device); perishable-aware bands.
 *    Only a village-table location is precise enough (district/state centroids leave the route unknown).
 *  - Seasonality: multiplicative decomposition of the pack price series when the activity has a commodity, else the
 *    catalog seasonal profile normalised to mean 1.
 *  - Structural: structural_rules on catalog attributes, taxonomy entries from the risk_taxonomy documents, plus
 *    taxonomy entries retrieved from the entrepreneur's own stated reason.
 *  - Local feedback flags from pack feedback ratings.
 */
import { climateAt, rainRisk, RAIN_SENSITIVE } from "../climate";
import { districts, feedback, docs, poisNear } from "../pack";
import { haversineKm } from "../geo";
import { retrieve } from "../retrieval";
import type { Level, LocationCandidate, PackFeedback, RiskFlagIntel, RiskIntel } from "../types";
import { type CatalogActivity, MONTHS, msg, round, src } from "./catalog";
import { seasonalDecomposition } from "./seasonal";
import { priceSeries } from "../pack";

export const ROAD_FACTOR = 1.3;
export const HUB_SEARCH_RADIUS_KM = 30;
export const MAX_HUB_KM = 150;
export const PROFILE_MATCH_SCORE = 0.12;
const RANK: Record<Level, number> = { low: 0, medium: 1, high: 2 };
const CONCENTRATED_BUYERS = ["exporter", "master weaver", "cooperative", "processor", "wholesaler"];
const CREDIT_BUYERS = ["wholesaler", "retailer", "retail", "exporter", "processor", "cooperative", "kirana", "master weaver", "bakeries"];

export const routeBand = (km: number, perishable: boolean): Level => {
  const [low, medium] = perishable ? [10, 25] : [15, 40];
  return km <= low ? "low" : km <= medium ? "medium" : "high";
};

export const variation = (index: number[]): Level => {
  const amp = Math.max(...index) - Math.min(...index);
  return amp < 0.25 ? "low" : amp < 0.5 ? "medium" : "high";
};

/** common.reference.low_season_months as 0-based month indices. */
export const lowSeasonMonths = (index: number[], threshold = 0.92) => index.slice(0, 12).flatMap((v, i) => (v < threshold ? [i] : []));

export interface RouteInfo { km: number | null }
export interface SeasonInfo { index: number[]; variation: Level; low: number[] }
export type StructuralRule = [id: string, severity: Level, reason: string];

/** risk_agent.structural_rules (reason text kept in English for parity; UI text comes from Msg keys). */
export function structuralRules(activity: CatalogActivity, route: RouteInfo, seasonal: SeasonInfo): StructuralRule[] {
  const buyers = (activity.buyers ?? []).map((b) => b.toLowerCase());
  const infra = activity.infrastructure_needs ?? [];
  const rules: StructuralRule[] = [];
  if (buyers.length <= 1) rules.push(["single_buyer_dependency", "high", `Only ${buyers.length} typical buyer channel listed.`]);
  else if (buyers.length === 2) {
    const concentrated = buyers.some((b) => CONCENTRATED_BUYERS.some((k) => b.includes(k)));
    rules.push(["single_buyer_dependency", concentrated ? "high" : "medium", `Only two buyer channels (${activity.buyers.join(", ")}).`]);
  }
  if (activity.perishable) {
    const far = route.km !== null && route.km > 25;
    rules.push(["perishability_cold_chain", far ? "high" : "medium", "Perishable product"]);
  }
  const inputs = (activity.key_inputs ?? []).join(" ").toLowerCase();
  if (activity.commodity || /feed|fodder|seed|grain|oil/.test(inputs)) rules.push(["input_price_volatility", "medium", "Main inputs are agricultural commodities or feed."]);
  if (infra.includes("three_phase_power")) rules.push(["power_reliability", "high", "Machinery needs a three-phase power connection."]);
  else if (infra.includes("electricity")) rules.push(["power_reliability", "low", "Operations depend on grid electricity."]);
  if (buyers.some((b) => CREDIT_BUYERS.some((k) => b.includes(k)))) rules.push(["credit_receivables", "medium", "Sales to traders/retailers usually involve credit periods."]);
  const extra = (activity.licences ?? []).filter((l) => !l.toLowerCase().includes("udyam"));
  if (extra.length) rules.push(["regulatory_licensing", "medium", `Needs: ${extra.join("; ")}.`]);
  if (activity.sector === "animal_husbandry" || activity.sector === "fisheries") {
    rules.push(["climate_disease_livestock_fisheries", activity.sector === "fisheries" ? "high" : "medium", "Live animals/stock exposed to disease and weather losses."]);
  }
  const index = seasonal.index;
  if (index.length && Math.max(...index) >= 1.2) {
    const peak = index.flatMap((v, i) => (v >= 1.15 ? [MONTHS[i]] : []));
    rules.push(["festival_season_concentration", "medium", `Demand concentrated in ${peak.join(", ")}.`]);
  }
  if (seasonal.low.length >= 3 || seasonal.variation === "high") {
    rules.push(["working_capital_strain", seasonal.low.length >= 5 ? "high" : "medium", `${seasonal.low.length} low-season months to finance.`]);
  }
  return rules;
}

/** risk_agent.overall_severity */
export function overallSeverity(flags: Pick<RiskFlagIntel, "severity">[]): Level {
  const highs = flags.filter((f) => f.severity === "high").length;
  if (highs >= 2) return "high";
  return highs || flags.some((f) => f.severity === "medium") ? "medium" : "low";
}

/** Title / Mitigation lines of a data/risk_taxonomy entry from the pack documents. */
export function taxonomyEntry(riskId: string): { title: string; mitigation: string } | null {
  const chunks = docs("risk_taxonomy").filter((d) => d.source.replace(/^.*[\\/]/, "").replace(/\.md$/, "") === riskId);
  if (!chunks.length) return null;
  const all = chunks.map((c) => c.text).join("\n");
  const mitigation = /^Mitigation:\s*(.+)$/m.exec(all)?.[1].trim() ?? "";
  return { title: chunks[0].heading, mitigation };
}

export const feedbackSeverity = (rating: number | null): Level => (rating === null ? "medium" : rating <= 2 ? "high" : rating === 3 ? "medium" : "low");

export function feedbackFlags(rows: PackFeedback[]): RiskFlagIntel[] {
  return rows.map((row) => ({
    id: `local_feedback:${row.id}`, category: "local_feedback", severity: feedbackSeverity(row.rating),
    title: msg("c2.risk.feedback.title", { topic: row.topic }),
    detail: msg(row.kind === "funded_entrepreneur" ? "c2.risk.feedback.funded" : "c2.risk.feedback.survey", { id: row.id, rating: row.rating ?? "-" }),
    mitigation: null, confidence: "real",
  }));
}

export function riskIntel(activity: CatalogActivity, location: LocationCandidate | null, reason: string | null): RiskIntel {
  const limitations = [];
  const sources = [];
  // Route
  let hubKm: number | null = null;
  let hubName: RiskIntel["hubName"] = null;
  let routeRisk: Level = "medium";
  if (!location || (location.method !== "village_table" && location.method !== "pincode")) {
    limitations.push(msg("c2.risk.routeCoarse"));
  } else {
    const here = { lat: location.lat, lon: location.lon };
    const poi = poisNear(here.lat, here.lon, HUB_SEARCH_RADIUS_KM, (p) => p.kind === "market" || p.kind === "haat" || p.kind === "transport")[0];
    let hub: { name: RiskIntel["hubName"]; lat: number; lon: number } | null = poi ? { name: poi.poi.name, lat: poi.poi.lat, lon: poi.poi.lon } : null;
    if (!hub) {
      const hq = districts().map((d) => ({ d, km: haversineKm(here, d) })).sort((a, b) => a.km - b.km)[0];
      if (hq && hq.km <= MAX_HUB_KM) {
        hub = { name: { en: `${hq.d.name.en} district HQ`, hi: `${hq.d.name.hi} ज़िला मुख्यालय` }, lat: hq.d.lat, lon: hq.d.lon };
        limitations.push(msg("c2.risk.hubIsHq"));
      }
    }
    if (hub) {
      hubKm = round(haversineKm(here, hub) * ROAD_FACTOR, 1);
      hubName = hub.name;
      routeRisk = routeBand(hubKm, activity.perishable);
      limitations.push(msg("c2.risk.routeEstimate", { factor: ROAD_FACTOR }));
    } else limitations.push(msg("c2.risk.noHub"));
  }
  sources.push(src(hubKm === null ? "Route distance (unavailable)" : "Straight-line × 1.3 estimate", hubKm === null ? "रास्ते की दूरी (उपलब्ध नहीं)" : "सीधी दूरी × 1.3 अनुमान", "estimated"));
  const routeFlag: RiskFlagIntel = hubKm === null
    ? { id: "route_distance", category: "route", severity: "medium", title: msg("c2.risk.route.unknownTitle"), detail: msg("c2.risk.route.unknownDetail"), mitigation: null, confidence: "estimated" }
    : { id: "route_distance", category: "route", severity: routeRisk, title: msg("c2.risk.route.title"), detail: msg(activity.perishable ? "c2.risk.route.detailPerishable" : "c2.risk.route.detail", { km: hubKm, hub: hubName!.en }), mitigation: null, confidence: "estimated" };

  // Seasonality
  let index: number[] | null = null;
  let basis: RiskIntel["seasonalBasis"] = "catalog_profile";
  let seasonalConf: "real" | "estimated" = "estimated";
  if (activity.commodity && location) {
    const series = priceSeries(activity.commodity, location.district.state);
    index = series ? seasonalDecomposition(series.months) : null;
    if (index) {
      basis = "price_history";
      seasonalConf = "real";
      sources.push(src(`Seasonal decomposition of ${activity.commodity} mandi prices, ${series!.months.length} months`, `${activity.commodity} मंडी भाव का मौसमी विश्लेषण, ${series!.months.length} महीने`, "real"));
    } else limitations.push(msg("c2.risk.noPriceHistory", { commodity: activity.commodity }));
  } else if (!activity.commodity) limitations.push(msg("c2.risk.noCommodity"));
  if (!index) {
    const mean = activity.seasonal_profile.reduce((a, b) => a + b, 0) / 12;
    index = activity.seasonal_profile.map((v) => Math.round((v / mean) * 10000) / 10000);
    sources.push(src("Catalog seasonal profile (planning assumption)", "कैटलॉग मौसमी प्रोफ़ाइल (योजना अनुमान)", "estimated"));
  }
  const seasonal: SeasonInfo = { index, variation: variation(index), low: lowSeasonMonths(index) };
  const seasonalFlag: RiskFlagIntel = {
    id: "seasonal_demand_variation", category: "seasonal", severity: seasonal.variation, title: msg("c2.risk.seasonal.title"),
    detail: msg("c2.risk.seasonal.detail", { swing: Math.round(100 * (Math.max(...index) - Math.min(...index))), months: seasonal.low.map((m) => MONTHS[m]).join(", ") }),
    mitigation: null, confidence: seasonalConf,
  };

  // Structural
  const triggered = new Map<string, Level>();
  for (const [id, sev] of structuralRules(activity, { km: hubKm }, seasonal)) triggered.set(id, sev);
  const reasonIds = new Set<string>();
  if (reason?.trim()) {
    for (const chunk of retrieve("risk_taxonomy", reason, 3, PROFILE_MATCH_SCORE)) {
      const rid = chunk.source.replace(/^.*[\\/]/, "").replace(/\.md$/, "");
      if (!triggered.has(rid)) {
        triggered.set(rid, "medium");
        reasonIds.add(rid);
      }
    }
  }
  if (!docs("risk_taxonomy").length) limitations.push(msg("c2.risk.noTaxonomy"));
  const structural: RiskFlagIntel[] = [...triggered].map(([id, severity]) => {
    const entry = taxonomyEntry(id);
    return {
      id, category: "structural", severity, title: msg(`c2.risk.tax.${id}`),
      detail: msg(reasonIds.has(id) ? "c2.risk.structural.fromReason" : `c2.risk.rule.${id}`),
      mitigation: entry?.mitigation || null, confidence: "estimated",
    };
  });
  sources.push(src(`Risk taxonomy: ${structural.length} entries matched`, `जोखिम सूची: ${structural.length} मेल`, "estimated"));

  // Rainfall (Open-Meteo, fetched online and kept with the case) for rain-fed activities
  const climate = location ? climateAt(location.lat, location.lon) : null;
  const rainFlags: RiskFlagIntel[] = [];
  if (climate && RAIN_SENSITIVE.has(activity.id)) {
    rainFlags.push({
      id: "rainfall_dependence", category: "seasonal", severity: rainRisk(climate), title: msg("c2.risk.rain.title"),
      detail: msg("c2.risk.rain.detail", { share: Math.round(climate.monsoonShare * 100), dry: climate.dryMonths, cv: Math.round(climate.yearToYearCv * 100), annual: climate.annualMm }),
      mitigation: null, confidence: "real",
    });
    sources.push(src(`Open-Meteo daily rainfall (ERA5), ${climate.years}, fetched ${climate.fetchedOn}`, `ओपन-मेटियो दैनिक वर्षा (ERA5), ${climate.years}, ${climate.fetchedOn} को लिया`, "real"));
  }

  const fb = location ? feedbackFlags(feedback(location.district.id, activity.id)) : [];
  if (fb.length) sources.push(src(`Local feedback records: ${fb.length}`, `स्थानीय प्रतिक्रिया रिकॉर्ड: ${fb.length}`, "real"));

  const flags = [routeFlag, seasonalFlag, ...rainFlags, ...structural, ...fb].sort((a, b) => RANK[b.severity] - RANK[a.severity]);
  return {
    confidence: "estimated", // route distance is always an estimate on device, so the combined analysis is too
    sources, limitations, overall: overallSeverity(flags), hubKm, hubName,
    routeMethod: hubKm === null ? "unavailable" : "haversine_estimate",
    seasonalIndex: index, seasonalBasis: basis, lowMonths: seasonal.low, flags,
  };
}
