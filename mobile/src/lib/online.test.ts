import { afterEach, describe, expect, it, vi } from "vitest";
import { rainRisk, summariseDaily } from "../core/climate";
import { fetchClimate, geocode, placeTextFor } from "./online";

afterEach(() => vi.unstubAllGlobals());

describe("online sources (no key)", () => {
  it("summarises ten years of daily rain into monsoon share, dry months and year-to-year swing", () => {
    const dates: string[] = [];
    const mm: number[] = [];
    for (let y = 2016; y <= 2025; y++) {
      for (let m = 1; m <= 12; m++) {
        for (let d = 1; d <= 28; d++) {
          dates.push(`${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`);
          mm.push(m >= 6 && m <= 9 ? 8 * (1 + ((y % 3) - 1) * 0.3) : m === 1 ? 0.1 : 0.5);
        }
      }
    }
    const c = summariseDaily(25, 82, dates, mm, "2026-09-15")!;
    expect(c.years).toBe("2016–2025");
    expect(c.monsoonShare).toBeGreaterThan(0.8);
    expect(c.dryMonths).toBeGreaterThanOrEqual(1);
    expect(c.yearToYearCv).toBeGreaterThan(0.1);
    expect(rainRisk(c)).toBe("high");
  });

  it("returns null instead of failing when the service is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    expect(await fetchClimate(25, 82)).toBeNull();
    expect(await geocode("Kandi")).toBeNull();
  });

  it("snaps a geocoded point to the nearest Census village and its district", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ features: [{ geometry: { coordinates: [88.03, 23.95] }, properties: { name: "Kandi", countrycode: "IN", state: "West Bengal" } }] }) }));
    const hit = await geocode("Kandi town");
    expect(hit?.source).toBe("photon");
    expect(placeTextFor(hit!, "Kandi")).toMatch(/Murshidabad$/);
  });
});
