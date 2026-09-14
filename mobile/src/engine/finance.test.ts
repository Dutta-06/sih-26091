import { describe, expect, it } from "vitest";
import catalog from "../../../data/reference/business_catalog.json";
import { buildPlan, previewDebtService } from "./finance";
import golden from "./golden.json";

const activity = (id: string) => catalog.activities.find((a) => a.id === id)!;

describe("TypeScript engine matches the Python deterministic engine", () => {
  it.each(golden.plans)("plan for capital $capital", (g) => {
    const p = buildPlan(g.capital);
    expect(p.eligible).toBe(g.eligible);
    expect(p.projectCost).toBeCloseTo(g.projectCost, 2);
    expect(p.loan).toBeCloseTo(g.loan, 2);
    expect(p.tier?.name ?? null).toBe(g.tier);
    expect(p.capApplied).toBe(g.capApplied);
    expect(Math.abs(p.regularInstallment - g.regularInstallment)).toBeLessThanOrEqual(0.02);
    expect(Math.abs(p.totalInterest - g.totalInterest)).toBeLessThanOrEqual(0.1);
    expect(p.schedule.length).toBe(g.quarters);
    if (p.eligible) expect(p.schedule.at(-1)!.closing).toBe(0);
  });

  it.each(golden.previews)("coverage preview $activity at $capital", (g) => {
    const v = previewDebtService(g.capital, activity(g.activity));
    expect(v.baseDscr).toBeCloseTo(g.baseDscr!, 2);
    expect(v.minSeasonalDscr).toBeCloseTo(g.minSeasonalDscr!, 2);
  });
});
