import { describe, expect, it } from "vitest";
import { computeCase, type SessionInputs } from "../../core/session";
import { EMPTY_PROFILE, SAMPLE_PROFILE } from "../../state/store";
import type { ProfileInput } from "../../core/types";
import { adjacency, cheapestViable, confidenceCounts, firstRejected, placeOf, reportAttempt } from "./feasibility";
import { evidenceFor, tallies } from "../w2/evidence";

const inputs = (profile: ProfileInput, chosenActivity: string | null = null): SessionInputs => ({
  profile, chosenActivity, appStage: "not_started", documents: {}, disbursedOn: null, smsConsent: false, inbox: "typical",
  dataDeletedOn: null, interventionChosen: null, realOutcomes: [], grievances: [], today: "2026-09-14",
});

describe("g2 view-model over the computed case", () => {
  it("sample case: rejected first idea, selected alternative, report/evidence computed", () => {
    const view = computeCase(inputs(SAMPLE_PROFILE));
    const rej = firstRejected(view);
    expect(rej?.activityId).toBe("handloom_weaving");
    expect(rej!.findings.length).toBeGreaterThan(0);
    const att = reportAttempt(view, SAMPLE_PROFILE)!;
    expect(att.activityId).toBe(view.activityId);
    const c = confidenceCounts(att.intel);
    expect(c.real + c.estimated).toBe(6);
    if (view.feasibility.selected) expect(["listed", "sector", "none"]).toContain(adjacency(rej!.activityId, view.feasibility.selected.activityId));
    const place = placeOf(view);
    expect(place).not.toBeNull();
    const ev = evidenceFor(place!.district.id, att.activityId, att.intel, []);
    expect(ev.pack.every((p) => p.record.district === place!.district.id)).toBe(true);
    expect(tallies(place!.district.id, []).packCount).toBeGreaterThanOrEqual(ev.pack.length);
  });

  it("changing capital changes the numbers", () => {
    const a = reportAttempt(computeCase(inputs(SAMPLE_PROFILE)), SAMPLE_PROFILE)!;
    const p2 = { ...SAMPLE_PROFILE, capital: 40_000 };
    const b = reportAttempt(computeCase(inputs(p2)), p2)!;
    expect(a.preview.quarterlySurplus).not.toBe(b.preview.quarterlySurplus);
  });

  it("an activity chosen outside the loop still gets a report attempt", () => {
    const view = computeCase(inputs(SAMPLE_PROFILE, "dairy_farming"));
    const att = reportAttempt(view, SAMPLE_PROFILE);
    expect(att?.activityId).toBe("dairy_farming");
  });

  it("no-viable case: savings target is computed and confirmed", () => {
    const profile = { ...SAMPLE_PROFILE, capital: 2_500, activityId: "flour_mill" };
    const view = computeCase(inputs(profile));
    const t0 = Date.now();
    const target = cheapestViable(profile, placeOf(view));
    const ms = Date.now() - t0;
    expect(ms).toBeLessThan(3000);
    if (target) {
      expect(target.capital).toBeGreaterThan(profile.capital);
      expect(target.more).toBe(target.capital - profile.capital);
    }
    // eslint-disable-next-line no-console
    console.log("no-viable", view.feasibility.exhausted, view.feasibility.attempts.map((a) => `${a.activityId}:${a.verdict}`), target, `${ms}ms`);
  });

  it("empty profile: constraints, no attempt, no report", () => {
    const view = computeCase(inputs(EMPTY_PROFILE));
    expect(view.feasibility.attempts).toHaveLength(0);
    expect(view.feasibility.constraints.length).toBeGreaterThan(0);
    expect(reportAttempt(view, EMPTY_PROFILE)).toBeNull();
    expect(firstRejected(view)).toBeNull();
    expect(placeOf(view)).toBeNull();
  });
});
