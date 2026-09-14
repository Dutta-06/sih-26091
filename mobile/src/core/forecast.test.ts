import { describe, expect, it } from "vitest";
import { detectAnomalies, robustZ } from "./anomalies";
import { backtestError, learnLevel, normalCdf } from "./forecast";
import type { MonthlyHealth } from "./health";
import { computeCase, type SessionInputs } from "./session";
import type { ProfileInput, Transaction } from "./types";

const sunita: ProfileInput = {
  capital: 12_000, locationText: "Gopiganj", locationCode: "184512", activityId: "handloom_weaving",
  reason: "My neighbour earns well from handloom", skills: ["stitching", "embroidery"], assets: [], premises: "home",
  category: "obc", womanOwned: true, shgMember: false,
};
const monitored = (patch: Partial<SessionInputs> = {}): SessionInputs => ({
  profile: sunita, chosenActivity: "tailoring", appStage: "disbursed", documents: {}, disbursedOn: "2025-12-15", smsConsent: true,
  inbox: "monsoon_disruption", dataDeletedOn: null, interventionChosen: null, realOutcomes: [], grievances: [], today: "2026-08-10",
  ...patch,
});

describe("forecast model", () => {
  it("starts at the plan and learns from recent months", () => {
    expect(learnLevel([]).level).toBeCloseTo(1, 5);
    const low = learnLevel([1, 1, 0.6]).level;
    expect(low).toBeLessThan(1);
    expect(low).toBeGreaterThan(0.6); // shrunk toward the plan
    expect(learnLevel([0.6, 1, 1]).level).toBeGreaterThan(low); // recent months weigh more
  });

  it("normal CDF is accurate", () => {
    expect(normalCdf(0)).toBeCloseTo(0.5, 6);
    expect(normalCdf(1.2816)).toBeCloseTo(0.9, 3);
    expect(normalCdf(-1.96)).toBeCloseTo(0.025, 3);
  });

  it("back-tests need at least two predictable months", () => {
    const m = (month: string, revenue: number): MonthlyHealth => ({ month, revenue, planned: 1000 } as MonthlyHealth);
    expect(backtestError([m("2026-01", 1000), m("2026-02", 1000), m("2026-03", 1000)]).error).toBeNull();
    const err = backtestError([m("2026-01", 1000), m("2026-02", 1000), m("2026-03", 1000), m("2026-04", 500)]).error!;
    expect(err).toBeGreaterThan(0.5);
  });

  it("a monitored case forecasts three months with ranges and an instalment outlook", () => {
    const c = computeCase(monitored());
    const f = c.forecast!;
    expect(f.basedOn).toBe(c.health.length);
    expect(f.months.map((x) => x.month)).toEqual(["2026-08", "2026-09", "2026-10"]);
    for (const x of f.months) {
      expect(x.low).toBeLessThanOrEqual(x.sales);
      expect(x.high).toBeGreaterThanOrEqual(x.sales);
    }
    expect(f.installment).not.toBeNull();
    expect(f.installment!.chance).toBeGreaterThan(0);
    expect(f.installment!.chance).toBeLessThan(1);
    expect(f.reasons[0].key).toBe("c3.fc.reason.level");
    expect(f.backtests).toBeGreaterThanOrEqual(2);
  });

  it("no finished month means no forecast", () => {
    expect(computeCase(monitored({ today: "2025-12-20" })).forecast).toBeNull();
  });
});

describe("unusual activity", () => {
  const tx = (at: string, amount: number, direction: Transaction["direction"] = "credit"): Transaction => ({ at: `${at}T00:00:00+00:00`, amount, direction, channel: "upi", isLoanRepayment: false });
  const daily = (from: number, to: number, amount = 500) => Array.from({ length: to - from + 1 }, (_, i) => tx(`2026-03-${String(from + i).padStart(2, "0")}`, amount + (i % 3) * 40));

  it("robust z ignores one earlier outlier", () => {
    expect(robustZ(5000, [400, 420, 450, 480, 500, 20000])).toBeGreaterThan(3.5);
  });

  it("finds a double charge, a large withdrawal and a gap in sales", () => {
    const txns = [
      ...daily(1, 10),
      ...Array.from({ length: 9 }, (_, i) => tx(`2026-03-0${i + 1}`, 900 + i * 25, "debit")),
      tx("2026-03-10", 1200, "debit"), tx("2026-03-10", 1200, "debit"),
      tx("2026-03-11", 15000, "debit"),
      ...daily(25, 31),
    ];
    const kinds = detectAnomalies(txns, "2026-03-31").map((a) => a.kind);
    expect(kinds).toContain("duplicate_debit");
    expect(kinds).toContain("large_debit");
    expect(kinds).toContain("sales_gap");
  });

  it("stays quiet on steady activity", () => {
    expect(detectAnomalies(daily(1, 31), "2026-03-31")).toEqual([]);
  });

  it("the monitored case surfaces the inbox's irregular events", () => {
    const kinds = new Set(computeCase(monitored()).anomalies.map((a) => a.kind));
    expect(kinds.has("duplicate_debit")).toBe(true);
    expect(kinds.has("large_credit")).toBe(true);
    expect(kinds.has("sales_gap")).toBe(true);
    const typical = computeCase(monitored({ inbox: "typical" })).anomalies.map((a) => a.kind);
    expect(typical).not.toContain("sales_gap");
  });
});
