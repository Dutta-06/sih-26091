/**
 * Supply chain (port of module1_feasibility/supply_chain_agent.py).
 * Graph: catalog key inputs → enterprise ← located suppliers; enterprise → logistics → catalog buyers.
 * Located suppliers: pack supplier/market POIs within 25 km whose name or tags match a key-input keyword ("real").
 * Single points of failure: articulation points of the undirected view (except the enterprise), a single buyer
 * channel, or exactly one located supplier.
 */
import { poisNear } from "../pack";
import type { LocationCandidate, PackPoi, SupplyChainIntel } from "../types";
import { type CatalogActivity, msg, src, usableCoords } from "./catalog";

export const SUPPLIER_RADIUS_KM = 25;
export const LOCAL_KM = 10;
export const MAX_SUPPLIERS = 5;
export const ENTERPRISE = "enterprise";
export const LOGISTICS = "logistics";
const INPUT_STOPWORDS = new Set(["services", "service", "material", "materials", "basic", "local", "small", "other", "supply", "with", "and", "for"]);

/** Lower-case keywords (≥ 4 letters) from the catalog key inputs. */
export const inputKeywords = (activity: CatalogActivity) =>
  [...new Set(activity.key_inputs.flatMap((i) => i.toLowerCase().match(/[a-z]{4,}/g) ?? []).filter((w) => !INPUT_STOPWORDS.has(w)))];

const poiText = (p: PackPoi) => `${p.name.en} ${p.tags.map(([k, v]) => `${k} ${v}`).join(" ")}`.toLowerCase().replace(/_/g, " ");

/** Tarjan articulation points on an undirected adjacency map. */
export function articulationPoints(adj: Map<string, Set<string>>): Set<string> {
  const disc = new Map<string, number>();
  const low = new Map<string, number>();
  const out = new Set<string>();
  let time = 0;
  const dfs = (u: string, parent: string | null) => {
    disc.set(u, time);
    low.set(u, time++);
    let children = 0;
    for (const v of adj.get(u) ?? []) {
      if (!disc.has(v)) {
        children++;
        dfs(v, u);
        low.set(u, Math.min(low.get(u)!, low.get(v)!));
        if (parent !== null && low.get(v)! >= disc.get(u)!) out.add(u);
      } else if (v !== parent) low.set(u, Math.min(low.get(u)!, disc.get(v)!));
    }
    if (parent === null && children > 1) out.add(u);
  };
  for (const n of adj.keys()) if (!disc.has(n)) dfs(n, null);
  return out;
}

export function supplyChainIntel(activity: CatalogActivity, location: LocationCandidate | null): SupplyChainIntel {
  const intel: SupplyChainIntel = { confidence: "estimated", sources: [], limitations: [], nodes: [], edges: [], singlePointsOfFailure: [], suppliers: [] };
  intel.sources.push(src("Catalog inputs and buyers (generic roles, planning assumption)", "कैटलॉग इनपुट और खरीदार (सामान्य भूमिकाएँ, योजना अनुमान)", "estimated"));
  const coords = usableCoords(location);
  if (!coords) {
    intel.limitations.push(msg("c2.supply.coarse"));
  } else {
    const kws = inputKeywords(activity);
    intel.suppliers = poisNear(coords.lat, coords.lon, SUPPLIER_RADIUS_KM, (p) => (p.kind === "supplier" || p.kind === "market") && kws.some((k) => poiText(p).includes(k))).slice(0, MAX_SUPPLIERS);
    intel.sources.push(src(`Mapped supplier places within ${SUPPLIER_RADIUS_KM} km: ${intel.suppliers.length}`, `${SUPPLIER_RADIUS_KM} किमी में आपूर्तिकर्ता स्थान: ${intel.suppliers.length}`, "real"));
    if (!intel.suppliers.length) intel.limitations.push(msg("c2.supply.noSuppliers", { km: SUPPLIER_RADIUS_KM }));
  }

  const adj = new Map<string, Set<string>>();
  const edge = (from: string, to: string) => {
    intel.edges.push({ from, to });
    for (const [a, b] of [[from, to], [to, from]]) {
      if (!adj.has(a)) adj.set(a, new Set());
      adj.get(a)!.add(b);
    }
  };
  intel.nodes.push({ id: ENTERPRISE, label: activity.name, role: "enterprise", km: null, confidence: "estimated" });
  adj.set(ENTERPRISE, new Set());
  activity.key_inputs.forEach((label, i) => {
    const id = `input:${i}`;
    intel.nodes.push({ id, label, role: "input", km: null, confidence: "estimated" });
    edge(id, ENTERPRISE);
  });
  for (const s of intel.suppliers) {
    const id = `supplier:${s.poi.id}`;
    intel.nodes.push({ id, label: s.poi.name, role: "input", km: s.km, confidence: "real" });
    edge(id, ENTERPRISE);
  }
  intel.nodes.push({ id: LOGISTICS, label: { en: "Road transport to buyers", hi: "खरीदारों तक सड़क परिवहन" }, role: "logistics", km: null, confidence: "estimated" });
  edge(ENTERPRISE, LOGISTICS);
  activity.buyers.forEach((label, i) => {
    const id = `buyer:${i}`;
    intel.nodes.push({ id, label, role: "buyer", km: null, confidence: "estimated" });
    edge(LOGISTICS, id);
  });

  const spof = new Set([...articulationPoints(adj)].filter((n) => n !== ENTERPRISE));
  const buyers = intel.nodes.filter((n) => n.role === "buyer");
  if (buyers.length === 1) spof.add(buyers[0].id);
  const real = intel.nodes.filter((n) => n.role === "input" && n.confidence === "real");
  if (real.length === 1) spof.add(real[0].id);
  intel.singlePointsOfFailure = [...spof].sort();
  intel.limitations.push(msg("c2.supply.noLeadTimes"));
  return intel;
}

/** "locally_available" | "regionally_available" | "unknown", as SupplyChainIntelligence.raw_material_availability. */
export const rawMaterialAvailability = (intel: SupplyChainIntel) =>
  intel.suppliers.length ? (intel.suppliers[0].km <= LOCAL_KM ? "locally_available" : "regionally_available") : "unknown";
