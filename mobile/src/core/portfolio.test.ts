import { describe, expect, it } from "vitest";
import { completedMonths, computePortfolio, computePortfolioChunked, evaluateApplicant, generateCohort, summarize, COHORT_CAPITAL_RANGE } from "./portfolio";
import { district, villages } from "./pack";

const TODAY = "2026-09-14";

describe("synthetic lender portfolio", () => {
  it("generates a deterministic cohort from the pack", () => {
    const a = generateCohort(30, 7);
    const b = generateCohort(30, 7);
    expect(a).toEqual(b);
    expect(generateCohort(30, 8)).not.toEqual(a);
    for (const x of a) {
      expect(district(x.districtId)).not.toBeNull();
      expect(villages().some((v) => v.lgd === x.profile.locationCode && v.district === x.districtId)).toBe(true);
      expect(x.profile.capital).toBeGreaterThanOrEqual(COHORT_CAPITAL_RANGE[0] - 250);
      expect(x.profile.capital).toBeLessThanOrEqual(COHORT_CAPITAL_RANGE[1] + 250);
      expect(x.profile.activityId).toBeTruthy();
    }
  });

  it("classifies applicants and aggregates consistently", () => {
    const m = computePortfolio(TODAY, 24, 3);
    expect(m.total).toBe(24);
    expect(m.byClass.viable + m.byClass.redirected + m.byClass.no_option).toBe(24);
    expect(m.districts.reduce((s, d) => s + d.total, 0)).toBe(24);
    expect(m.districts.reduce((s, d) => s + d.loan, 0)).toBe(m.loanVolume);
    expect(m.warned).toBeLessThanOrEqual(m.monitored);
    expect(m.monitored).toBeLessThanOrEqual(m.disbursed);
    if (m.warningRate !== null) expect(m.warningRate).toBeGreaterThanOrEqual(0);
    expect(computePortfolio(TODAY, 24, 3)).toBe(m); // cached
  }, 60_000);

  it("gives no loan and no monitoring to applicants without a viable option", () => {
    const [a] = generateCohort(1, 11);
    const r = evaluateApplicant({ ...a, profile: { ...a.profile, capital: 0 }, disbursedMonthsAgo: 6 }, TODAY);
    expect(r.cls).toBe("no_option");
    expect(r.loan).toBe(0);
    expect(r.disbursed).toBe(false);
    expect(summarize([r]).avgCoverage).toBeNull();
  });

  it("chunked computation matches the synchronous one", async () => {
    const sync = summarize(generateCohort(8, 5).map((a) => evaluateApplicant(a, TODAY)));
    const chunked = await computePortfolioChunked("2027-01-01", undefined, undefined, 8, 5);
    const again = summarize(generateCohort(8, 5).map((a) => evaluateApplicant(a, "2027-01-01")));
    expect(chunked).toEqual(again);
    expect(sync.total).toBe(8);
  }, 60_000);
});

describe("completedMonths", () => {
  it("drops the month in progress unless today is its last day", () => {
    const h = [{ month: "2026-08" }, { month: "2026-09" }];
    expect(completedMonths(h, "2026-09-14")).toEqual([{ month: "2026-08" }]);
    expect(completedMonths(h, "2026-09-30")).toEqual(h);
  });
});
