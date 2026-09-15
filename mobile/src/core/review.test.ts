import { describe, expect, it } from "vitest";
import { previewDebtService } from "../engine/finance";
import fixture from "./__fixtures__/c2.json";
import { catalogActivity } from "./intel/catalog";
import { classifySaturation, poissonZ } from "./intel/competitor";
import { lowSeasonMonths, overallSeverity, structuralRules, variation } from "./intel/risk";
import { seasonalDecomposition } from "./intel/seasonal";
import { evaluate } from "./review";
import type { Intel, Level, Saturation } from "./types";

type Stub = { sat: Saturation; z: number | null; count: number | null; niches: Saturation[]; flags: [string, string, Level][]; estimated: string[] } | null;
const BRANCH: Record<string, keyof Intel> = {
  market_reach: "marketReach", opportunity: "opportunity", risk: "risk", competitor: "competitor", pricing: "pricing", supply_chain: "supplyChain",
};

function intelFromStub(stub: Stub): Intel | null {
  if (!stub) return null;
  const meta = (branch: string) => ({ confidence: stub.estimated.some((e) => BRANCH[e] === branch) ? "estimated" as const : "real" as const, sources: [], limitations: [] });
  return {
    marketReach: { ...meta("marketReach"), radiusKm: 10, population: null, consumerBase: null, households: null, places: [] },
    opportunity: { ...meta("opportunity"), saturation: "unknown", niches: stub.niches.map((s, i) => ({ name: `n${i}`, detail: "", source: "", relevance: 0, saturation: s, evidenceIds: [] })) },
    competitor: { ...meta("competitor"), tier: "none", tiersAttempted: [], count: stub.count, nearby: [], densityPer10k: null, districtPer10k: null, statePer10k: null, zScore: stub.z, saturation: stub.sat },
    pricing: { ...meta("pricing"), basis: "unavailable", points: [], targetPrice: null, purchasingPowerIndex: null, history: [] },
    risk: {
      ...meta("risk"), overall: "low", hubKm: null, hubName: null, routeMethod: "unavailable", seasonalIndex: [], seasonalBasis: "catalog_profile", lowMonths: [],
      flags: stub.flags.map(([id, category, severity]) => ({ id, category: category as "route", severity, title: { key: id }, detail: { key: id }, mitigation: null, confidence: "estimated" })),
    },
    supplyChain: { ...meta("supplyChain"), nodes: [], edges: [], singlePointsOfFailure: [], suppliers: [] },
  };
}

describe("adversarial review parity (adversarial_review.evaluate)", () => {
  for (const c of fixture.review) {
    it(`${c.activity} @ ${c.capital} / ${c.stub}`, () => {
      const a = catalogActivity(c.activity)!;
      const r = evaluate(c.capital, a, intelFromStub((fixture.stubs as unknown as Record<string, Stub>)[c.stub]), previewDebtService(c.capital, a));
      expect(r.verdict).toBe(c.verdict);
      expect(r.findings.map((f) => f.rule)).toEqual(c.rules);
      expect(r.notes.length).toBe(c.notes);
    });
  }
});

describe("seasonal decomposition parity (risk_agent.seasonal_decomposition)", () => {
  for (const [name, series] of Object.entries(fixture.series)) {
    it(name, () => {
      const expected = (fixture.seasonal as Record<string, number[] | null>)[name];
      const got = seasonalDecomposition(series);
      if (expected === null) expect(got).toBeNull();
      else got!.forEach((v, i) => expect(v).toBeCloseTo(expected[i], 4));
    });
  }
});

describe("structural rules and severity parity", () => {
  it("structural_rules", () => {
    for (const c of fixture.structural) {
      const a = catalogActivity(c.activity)!;
      const mean = a.seasonal_profile.reduce((x, y) => x + y, 0) / 12;
      const index = a.seasonal_profile.map((v) => Math.round((v / mean) * 10000) / 10000);
      expect(variation(index)).toBe(c.variation);
      expect(lowSeasonMonths(index)).toEqual(c.low);
      const rules = structuralRules(a, { km: c.km }, { index, variation: variation(index), low: lowSeasonMonths(index) });
      expect(rules.map(([id, sev]) => [id, sev]), `${c.activity} km=${c.km}`).toEqual(c.rules);
    }
  });
  it("overall_severity", () => {
    fixture.severityCases.forEach((c, i) => expect(overallSeverity(c.map((severity) => ({ severity: severity as Level })))).toBe(fixture.overall[i]));
  });
  it("poisson z and saturation", () => {
    for (const [c, p, b, z] of fixture.stats.poisson) expect(poissonZ(c as number, p as number | null, b as number)).toBe(z);
    for (const [d, b, s] of fixture.stats.saturation) expect(classifySaturation(d as number | null, b as number)).toBe(s);
  });
});
