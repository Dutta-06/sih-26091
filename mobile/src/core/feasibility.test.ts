import { describe, expect, it } from "vitest";
import strings from "../i18n/strings/core_c2";
import { rankActivities } from "./discovery";
import { runFeasibility, runIntel } from "./feasibility";
import { district, villages } from "./pack";
import type { FeasibilityAttempt, LocationCandidate, Msg, ProfileInput } from "./types";

const profile = (over: Partial<ProfileInput>): ProfileInput => ({
  capital: 12_000, locationText: "", locationCode: null, activityId: null, reason: null, skills: [], assets: [], premises: null,
  category: null, womanOwned: true, shgMember: false, ...over,
});

function villageLocation(lgd: string): LocationCandidate {
  const v = villages().find((x) => x.lgd === lgd)!;
  return { lgd, village: v.name, block: v.block, district: district(v.district)!, lat: v.lat, lon: v.lon, method: "village_table" };
}
function districtLocation(id: string): LocationCandidate {
  const d = district(id)!;
  return { lgd: null, village: null, block: null, district: d, lat: d.lat, lon: d.lon, method: "district_table" };
}

const GOPIGANJ = () => villageLocation("184512");
const SUNITA = profile({ capital: 12_000, locationText: "Gopiganj", locationCode: "184512", activityId: "handloom_weaving", skills: ["stitching", "embroidery"], reason: "My mother wove sarees" });

function collectMsgs(a: FeasibilityAttempt): Msg[] {
  const i = a.intel;
  return [
    ...a.findings.map((f) => f.msg), ...a.notes, ...a.swot.strengths, ...a.swot.weaknesses, ...a.swot.opportunities, ...a.swot.threats,
    ...[i.marketReach, i.opportunity, i.competitor, i.pricing, i.risk, i.supplyChain].flatMap((x) => x.limitations),
    ...i.risk.flags.flatMap((f) => [f.title, f.detail]),
  ];
}

describe("Sunita storyline emerges from the data pack", () => {
  const result = runFeasibility(SUNITA, GOPIGANJ());

  it("assesses the stated preference first and rejects handloom on coverage and crowding", () => {
    const first = result.attempts[0];
    expect(first.activityId).toBe("handloom_weaving");
    expect(first.verdict).toBe("not_recommended");
    const r2 = first.findings.find((f) => f.rule === "R2");
    expect(r2?.msg.vars?.dscr).toBe(0.72);
    expect(first.intel.competitor.saturation).toBe("high");
    expect(first.findings.some((f) => f.rule === "R3" || f.rule === "M2")).toBe(true);
    expect(first.intel.competitor.count).toBeGreaterThan(0);
  });

  it("then tries the adjacent tailoring unit, which is viable", () => {
    const second = result.attempts[1];
    expect(second.activityId).toBe("tailoring");
    expect(second.verdict).toBe("viable");
    expect(result.selected?.activityId).toBe("tailoring");
    expect(result.exhausted).toBe(false);
    expect(result.attempts).toHaveLength(2);
    expect(second.notes.some((n) => n.key === "c2.feas.adjacentTo")).toBe(true);
  });

  it("uses real local data where the pack has it", () => {
    const intel = result.attempts[1].intel;
    expect(intel.marketReach.population).toBeGreaterThan(0);
    expect(intel.marketReach.confidence).toBe("real");
    expect(intel.marketReach.places.length).toBeGreaterThan(0);
    expect(intel.opportunity.niches.map((n) => n.name)).toContain("School uniform orders");
    expect(intel.risk.hubKm).not.toBeNull();
    expect(intel.risk.seasonalIndex).toHaveLength(12);
    expect(intel.supplyChain.singlePointsOfFailure).toContain("logistics");
  });

  it("every Msg key exists in EN and HI strings", () => {
    for (const attempt of result.attempts) {
      for (const m of collectMsgs(attempt)) {
        expect(strings.en[m.key], m.key).toBeTypeOf("string");
        expect(strings.hi[m.key], m.key).toBeTypeOf("string");
      }
    }
    expect(Object.keys(strings.en).sort()).toEqual(Object.keys(strings.hi).sort());
  });

  it("ranks with a 100-point breakdown and marks unaffordable options", () => {
    const ranked = rankActivities(SUNITA, GOPIGANJ());
    expect(ranked[0].activityId).toBe("handloom_weaving");
    for (const r of ranked) {
      const b = r.breakdown;
      expect(r.score).toBeCloseTo(b.capitalFit + b.repayment + b.skills + b.localDemand + b.outcomes, 1);
      expect(r.score).toBeLessThanOrEqual(100);
    }
    const carpet = ranked.find((r) => r.activityId === "carpet_weaving")!;
    expect(carpet.feasible).toBe(false);
    expect(carpet.infeasibleReason?.key).toBe("c2.infeasible.projectMin");
    const tailoring = ranked.find((r) => r.activityId === "tailoring")!;
    expect(tailoring.breakdown.skills).toBe(20);
    expect(ranked.find((r) => r.activityId === "handloom_weaving")!.breakdown.skills).toBe(12);
    const after = rankActivities(SUNITA, GOPIGANJ(), { rejected: ["handloom_weaving"], adjacentTo: "handloom_weaving" });
    expect(after[0].activityId).toBe("tailoring");
    expect(after[0].adjacentTo).toBe("handloom_weaving");
  });
});

describe("other paths", () => {
  it("capital 2500 → exhausted with no feasible activity", () => {
    const r = runFeasibility(profile({ capital: 2_500 }), GOPIGANJ());
    expect(r.attempts).toHaveLength(0);
    expect(r.selected).toBeNull();
    expect(r.exhausted).toBe(true);
    expect(r.shortlist.every((s) => !s.feasible)).toBe(true);
  });

  it("capital 100000 dairy in Jaunpur → viable or with explicit findings", () => {
    const r = runFeasibility(profile({ capital: 100_000, activityId: "dairy_farming", skills: ["livestock"] }), districtLocation("jaunpur"));
    const first = r.attempts[0];
    expect(first.activityId).toBe("dairy_farming");
    if (first.verdict !== "viable") expect(first.findings.length).toBeGreaterThan(0);
    expect(first.intel.risk.routeMethod).toBe("unavailable"); // district centroid is not precise enough for a route
  });

  it("unknown location → still runs with estimated labels", () => {
    const r = runFeasibility(profile({ capital: 12_000, skills: ["stitching"] }), null);
    expect(r.attempts.length).toBeGreaterThan(0);
    const intel = r.attempts[0].intel;
    for (const x of [intel.marketReach, intel.competitor, intel.pricing, intel.risk, intel.supplyChain]) expect(x.confidence).toBe("estimated");
    expect(intel.marketReach.population).toBeNull();
    expect(intel.competitor.saturation).toBe("unknown");
    expect(r.constraints.map((c) => c.key)).toContain("c2.constraint.noLocation");
  });

  it("capital 600000 (project above the Rs 50 lakh ceiling) → profiling constraint, no attempts", () => {
    const r = runFeasibility(profile({ capital: 600_000 }), GOPIGANJ());
    expect(r.attempts).toHaveLength(0);
    expect(r.exhausted).toBe(false);
    expect(r.constraints[0].key).toBe("c2.constraint.aboveScheme");
    expect(r.shortlist.every((s) => s.infeasibleReason?.key === "c2.infeasible.outsideScheme")).toBe(true);
  });

  it("is deterministic and bounded by maxAttempts", () => {
    const a = runFeasibility(SUNITA, GOPIGANJ(), 1);
    expect(a.attempts).toHaveLength(1);
    expect(a.exhausted).toBe(true);
    expect(JSON.stringify(runIntel("tailoring", SUNITA, GOPIGANJ()))).toBe(JSON.stringify(runIntel("tailoring", SUNITA, GOPIGANJ())));
  });

  it("commodity activity uses the real price series and its seasonal decomposition", () => {
    const intel = runIntel("goat_rearing", profile({ capital: 10_000 }), GOPIGANJ());
    expect(intel.pricing.basis).toBe("direct_market_data");
    expect(intel.pricing.confidence).toBe("real");
    expect(intel.risk.seasonalBasis).toBe("price_history");
  });
});
