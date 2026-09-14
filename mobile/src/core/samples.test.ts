import { describe, expect, it } from "vitest";
import { computeCase } from "./session";
import { initialState, reducerForTests, SAMPLE_PEOPLE, sessionInputs, type DemoCheckpoint } from "../state/store";

describe("example people across states", () => {
  for (const [i, p] of SAMPLE_PEOPLE.entries()) {
    it(`${p.name} (${p.profile.locationText}) runs the whole journey`, { timeout: 30_000 }, () => {
      const at = (to: DemoCheckpoint) =>
        computeCase(sessionInputs(reducerForTests({ ...initialState(), sampleIndex: i }, { type: "jump", to })));
      const report = at("report");
      expect(report.location.chosen, "location").not.toBeNull();
      expect(report.feasibility.attempts.length).toBeGreaterThan(0);
      const plan = at("plan");
      expect(plan.activityId).not.toBeNull();
      expect(plan.financial?.plan.eligible, "loan plan").toBe(true);
      const mon = at("monitoring");
      expect(mon.health.length, "monitoring months").toBeGreaterThan(2);
      expect(mon.forecast).not.toBeNull();
    });
  }
});
