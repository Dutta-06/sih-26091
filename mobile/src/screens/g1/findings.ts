/**
 * One-line findings for the six analyses of a feasibility attempt, built from the computed intel
 * (no figure is typed here; each line is an i18n key with values read from `Intel`).
 */
import type { Confidence, Intel, Saturation } from "../../core/types";

export type AgentId = keyof Intel;
export const AGENT_ORDER: AgentId[] = ["marketReach", "opportunity", "competitor", "pricing", "risk", "supplyChain"];

const sat = (s: Saturation) => (s === "unknown" ? "@u1.sat.unknown" : `@level.${s}`);
const km = (v: number) => Math.round(v * 10) / 10;

export type Line = { key: string; vars?: Record<string, unknown> };

export function findingLine(intel: Intel, id: AgentId): Line {
  switch (id) {
    case "marketReach": {
      const r = intel.marketReach;
      return r.population !== null
        ? { key: "u1.an.reach", vars: { pop: r.population, base: r.consumerBase ?? r.population, km: r.radiusKm } }
        : { key: "u1.an.reachUnknown" };
    }
    case "opportunity": {
      const o = intel.opportunity;
      return o.niches.length ? { key: "u1.an.opp", vars: { n: o.niches.length, sat: sat(o.saturation) } } : { key: "u1.an.oppNone" };
    }
    case "competitor": {
      const c = intel.competitor;
      if (c.count === null) return { key: "u1.an.compUnknown" };
      // scope is replaced before km, so the radius text can carry {km}
      return { key: "u1.an.comp", vars: { n: c.count, sat: sat(c.saturation), scope: c.tier === "udyam" ? "@u1.an.scope.district" : "@u1.an.scope.radius", km: intel.marketReach.radiusKm } };
    }
    case "pricing": {
      const p = intel.pricing;
      const point = p.points[0];
      return point
        ? { key: "u1.an.price", vars: { label: point.label, low: Math.round(point.low), high: Math.round(point.high), unit: point.unit, basis: `@u1.an.basis.${p.basis}` } }
        : { key: "u1.an.priceNone" };
    }
    case "risk": {
      const r = intel.risk;
      return r.hubKm !== null ? { key: "u1.an.risk", vars: { level: `@level.${r.overall}`, km: km(r.hubKm) } } : { key: "u1.an.riskNoHub", vars: { level: `@level.${r.overall}` } };
    }
    case "supplyChain": {
      const s = intel.supplyChain;
      return s.suppliers.length ? { key: "u1.an.supply", vars: { n: s.suppliers.length, km: km(s.suppliers[0].km) } } : { key: "u1.an.supplyNone" };
    }
  }
}

export const confidenceOf = (intel: Intel, id: AgentId): Confidence => intel[id].confidence;
