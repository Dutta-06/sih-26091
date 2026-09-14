import { describe, expect, it } from "vitest";
import { computeCase, type SessionInputs } from "./session";
import type { ProfileInput } from "./types";

const sunita: ProfileInput = {
  capital: 12_000, locationText: "Gopiganj", locationCode: "184512", activityId: "handloom_weaving",
  reason: "My neighbour earns well from handloom", skills: ["stitching", "embroidery"], assets: [], premises: "home",
  category: "obc", womanOwned: true, shgMember: false,
};

const base = (patch: Partial<SessionInputs> = {}): SessionInputs => ({
  profile: sunita, chosenActivity: null, appStage: "not_started", documents: {}, disbursedOn: null, smsConsent: false,
  inbox: "monsoon_disruption", dataDeletedOn: null, interventionChosen: null, realOutcomes: [], grievances: [], today: "2025-10-06",
  ...patch,
});

describe("computeCase: the whole journey is derived, not scripted", () => {
  it("rejects handloom and selects tailoring for Sunita", () => {
    const c = computeCase(base());
    expect(c.location.chosen?.lgd).toBe("184512");
    expect(c.feasibility.attempts[0].activityId).toBe("handloom_weaving");
    expect(c.feasibility.attempts[0].verdict).toBe("not_recommended");
    expect(c.activityId).toBe("tailoring");
    expect(c.financial?.plan.loan).toBe(108_000);
    expect(c.documents?.items.length).toBeGreaterThan(3);
    expect(c.roadmap.length).toBeGreaterThan(0);
  });

  it("monitoring reads consented alerts and raises a July warning in a monsoon-disrupted inbox", () => {
    const c = computeCase(base({ chosenActivity: "tailoring", appStage: "disbursed", disbursedOn: "2025-12-15", smsConsent: true, today: "2026-07-31" }));
    expect(c.transactions.length).toBeGreaterThan(50);
    expect(c.health.map((h) => h.month)).toContain("2026-07");
    expect(c.warning?.month).toBe("2026-07");
    expect(c.interventions.length).toBeGreaterThan(0);
  });

  it("no consent means no transactions; a typical inbox has no July warning", () => {
    expect(computeCase(base({ chosenActivity: "tailoring", disbursedOn: "2025-12-15", today: "2026-07-31" })).transactions).toHaveLength(0);
    const typical = computeCase(base({ chosenActivity: "tailoring", disbursedOn: "2025-12-15", smsConsent: true, inbox: "typical", today: "2026-07-31" }));
    expect(typical.warning?.month).not.toBe("2026-07");
  });

  it("handles edge inputs without throwing", () => {
    for (const capital of [0, -5, 2_500, 6_000_000]) {
      expect(() => computeCase(base({ profile: { ...sunita, capital } }))).not.toThrow();
    }
    expect(() => computeCase(base({ profile: { ...sunita, locationText: "zzzz", locationCode: null, activityId: null } }))).not.toThrow();
  });
});
