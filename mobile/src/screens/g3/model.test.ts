import { describe, expect, it } from "vitest";
import { validateField } from "../../core/documents";
import { computeCase } from "../../core/session";
import { SAMPLE_PROFILE, initialState, sessionInputs, type CaseEvent } from "../../state/store";
import { addMonthsIso, applicationRef, dueDates, officerEvents, placeOf, seasonView, stageDates, stageIndex, udyamNumber } from "./model";

describe("g3 derivations", () => {
  it("adds months in UTC and clamps the day", () => {
    expect(addMonthsIso("2026-01-31", 1)).toBe("2026-02-28");
    expect(addMonthsIso("2026-11-15", 3)).toBe("2027-02-15");
    expect(addMonthsIso("2026-03-15", 3, 3)).toBe("2026-06-12");
  });

  it("derives due dates from the schedule", () => {
    const d = dueDates("2026-09-14", [{ quarter: 1 }, { quarter: 4 }] as never);
    expect(d.map((x) => x.due)).toEqual(["2026-12-14", "2027-09-14"]);
  });

  it("makes a valid, deterministic Udyam number that changes with inputs", () => {
    const base = { districtId: "bhadohi", stateName: "Uttar Pradesh", nic: "1410", enterpriseName: "Asha Silai", aadhaarLast4: "1234", capital: 12000 };
    const a = udyamNumber(base);
    expect(validateField("udyam_registration_number", a).ok).toBe(true);
    expect(a.startsWith("UDYAM-UP-")).toBe(true);
    expect(udyamNumber(base)).toBe(a);
    expect(udyamNumber({ ...base, enterpriseName: "Other" })).not.toBe(a);
  });

  it("derives the application reference from the first application event", () => {
    expect(applicationRef("bhadohi", [])).toBeNull();
    const events: CaseEvent[] = [{ type: "application", at: "2026-09-01T10:00:00.000Z", data: { event: "submit", stage: "submitted" } }];
    const ref = applicationRef("bhadohi", events)!;
    expect(ref).toMatch(/^ARB-BHA-2026-\d{5}$/);
    expect(applicationRef("varanasi", events)).not.toBe(ref);
  });

  it("places a rejected application where it was rejected and offers only legal events", () => {
    const events: CaseEvent[] = [
      { type: "application", at: "2026-09-01T00:00:00Z", data: { stage: "submitted" } },
      { type: "application", at: "2026-09-03T00:00:00Z", data: { stage: "under_verification" } },
      { type: "application", at: "2026-09-05T00:00:00Z", data: { stage: "rejected" } },
    ];
    expect(stageIndex("rejected", events)).toBe(2);
    expect(stageDates(events).under_verification).toBe("2026-09-03T00:00:00Z");
    expect(officerEvents("rejected")).toEqual([]);
    expect(officerEvents("documents_pending")).toEqual([]);
    expect(officerEvents("sanctioned")).toEqual(["disburse", "reject"]);
  });

  it("uses the season index the financial plan used", () => {
    const view = computeCase(sessionInputs({ ...initialState(), profile: SAMPLE_PROFILE, chosenActivity: "tailoring" }));
    expect(placeOf(view)).not.toBeNull();
    const s = seasonView(view)!;
    expect(s.values).toHaveLength(12);
    expect(s.values.reduce((a, b) => a + b, 0) / 12).toBeCloseTo(1, 5);
  });
});
