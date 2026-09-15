import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/c3.json";
import { budgetSplit, buildFinancial, explainScheme } from "./financial";
import { docs } from "./pack";
import type { Intel, ProfileInput } from "./types";

const profile = (capital: number, extra: Partial<ProfileInput> = {}): ProfileInput => ({
  capital, locationText: "Sitapur", locationCode: null, activityId: "tailoring", reason: null, skills: ["stitching"], assets: [],
  premises: "home", category: "obc", womanOwned: true, shgMember: true, ...extra,
});

/** Minimal intel carrying only the fields buildFinancial reads. */
const intel = (over: { target?: number | null; consumers?: number | null; seasonal?: number[] }): Intel => ({
  pricing: { targetPrice: over.target ?? null, confidence: "real" },
  marketReach: { consumerBase: over.consumers ?? null, confidence: "real" },
  risk: { seasonalIndex: over.seasonal ?? [], seasonalBasis: "price_history", confidence: "real" },
}) as unknown as Intel;

describe("buildFinancial", () => {
  it("Sunita: ₹12,000 tailoring → ₹1,08,000 loan, ₹10,801 instalment, three scenarios", () => {
    const f = buildFinancial(profile(12_000), "tailoring", null);
    expect(f.plan.loan).toBe(108_000);
    expect(Math.round(f.plan.regularInstallment)).toBe(10_801);
    expect(f.scenarios.map((s) => s.id)).toEqual(["low_season", "price_drop", "input_cost"]);
    expect(f.scenarios[1].result.minDscr).toBeLessThan(f.scenarios[0].result.minDscr);
    expect(f.seasonalBasis).toBe("catalog_profile");
    expect(f.policy.tier).toBe("micro_finance");
  });

  it("earnings: only the base is applied; pricing and reach are bounded transparency steps", () => {
    const f = buildFinancial(profile(12_000), "tailoring", intel({ target: 600, consumers: 2_500 }));
    const step = (id: string) => f.earnings.find((e) => e.id === id)!;
    expect(step("base").value).toBe(180_000);
    expect(step("pricing")).toMatchObject({ factor: 1.2, applied: false, confidence: "real" }); // 600 / 285 → capped
    expect(step("reach")).toMatchObject({ factor: 0.85, applied: false }); // √0.25 = 0.5 → floor
    expect(step("reach").value).toBeCloseTo(180_000 * 1.2 * 0.85, 2);
    expect(step("coverage").value).toBe(f.preview.baseDscr);
    expect(f.earnings.filter((e) => e.applied).map((e) => e.id)).toEqual(["project", "base", "surplus", "coverage", "seasons"]);
  });

  it("uses the risk seasonal index for scenarios when available", () => {
    const flat = buildFinancial(profile(12_000), "tailoring", intel({ seasonal: new Array(12).fill(1) }));
    expect(flat.seasonalBasis).toBe("risk_analysis");
    expect(flat.scenarios[0].result.deficitQuarters).toBe(0);
    expect(new Set(flat.scenarios[0].result.quarterlyDscr).size).toBe(1);
  });

  it("budget splits capex over key inputs + 20% working capital and sums exactly", () => {
    for (const capital of [12_000, 13_999, 50_000, 333_333]) {
      const f = buildFinancial(profile(capital), "dairy_farming", null);
      expect(f.budget.reduce((a, b) => a + b.amount, 0)).toBe(Math.round(f.plan.projectCost));
      expect(f.budget.at(-1)!.amount).toBe(Math.round(f.plan.workingCapital));
    }
    expect(budgetSplit(0, 0, ["x"])).toEqual([]);
    expect(budgetSplit(1000, 200, []).map((b) => b.amount)).toEqual([800, 200]);
  });

  it("outside the scheme: no scenarios, no coverage, both tiers explained", () => {
    const f = buildFinancial(profile(600_000), "flour_mill", null);
    expect(f.plan.eligible).toBe(false);
    expect(f.scenarios).toEqual([]);
    expect(f.earnings.find((e) => e.id === "coverage")).toBeUndefined();
    expect(f.policy.tier).toBeNull();
    expect(f.policy.documents).toEqual([]);
    expect(f.limitations.map((l) => l.key)).toContain("c3.fin.lim.outside_scheme");
  });

  it("no capital: zero surplus, no plan, no budget", () => {
    const f = buildFinancial(profile(0), "tailoring", null);
    expect(f.earnings.find((e) => e.id === "surplus")!.value).toBe(0);
    expect(f.budget).toEqual([]);
    expect(f.limitations.map((l) => l.key)).toContain("c3.fin.lim.no_capital");
  });
});

describe.skipIf(docs("scheme_guidelines").length === 0)("policy lists parity with policy_scheme_agent.explain_scheme", () => {
  it.each(fixture.policy)("tier $tier", (p) => {
    const got = explainScheme(p.tier);
    expect(got.documents).toEqual(p.documents);
    expect(got.steps).toEqual(p.steps);
    expect(got.rules.map((r) => r.heading).sort()).toEqual([...p.ruleHeadings].sort());
  });
});
