import { describe, expect, it } from "vitest";
import { resolveLocation } from "./geo";
import { extract } from "./nlu";
import { bankBranch, openPlacesNear, openVillagesNear, pinArea } from "./openData";
import { poisNear, settlementsNear } from "./pack";

describe("bundled open data", () => {
  it("reads a PIN code as a place, not an amount", () => {
    const e = extract("my pin code is 641001, I want to open a tailoring shop", null);
    expect(e.capital).toBeUndefined();
    expect(resolveLocation(e.locationText!).chosen?.district.name.en).toMatch(/Coimbatore/);
    expect(extract("20000 rupees, PIN 221303", null).capital).toBe(20000);
  });
  it("resolves real Census villages anywhere in India", () => {
    const r = resolveLocation("Pollachi, Coimbatore");
    expect(r.chosen?.method ?? r.candidates[0]?.method).toBeDefined();
    const k = resolveLocation("Kandi, Murshidabad");
    const c = k.chosen ?? k.candidates[0];
    expect(c?.district.id).toBe("murshidabad");
  });
  it("keeps a district name as the district", () => {
    expect(resolveLocation("Nashik").chosen?.district.id).toBe("nashik");
    expect(resolveLocation("Coimbatore").chosen?.method).toBe("district_table");
  });
  it("offers a few choices for very common village names", () => {
    const r = resolveLocation("Kishanpur");
    expect(r.chosen).toBeNull();
    expect(r.candidates.length).toBeLessThanOrEqual(6);
  });
  it("finds a place by PIN code", () => {
    expect(pinArea("221303")?.district).toBe("bhadohi");
    const r = resolveLocation("my pin is 641001");
    expect(r.chosen?.method).toBe("pincode");
    expect(r.chosen?.district.name.en).toBe("Coimbatore");
  });
  it("looks up bank branches by IFSC", () => {
    const b = bankBranch("SBIN0000001");
    expect(b?.bank).toBe("State Bank of India");
    expect(bankBranch("ZZZZ0000000")).toBeNull();
  });
  it("serves real villages and mapped places near a point", () => {
    const vs = openVillagesNear(10.66, 77.0, 10);
    expect(vs.length).toBeGreaterThan(10);
    expect(vs.every((v) => v.population >= 0)).toBe(true);
    expect(openPlacesNear(11.0, 76.96, 5).length).toBeGreaterThan(100);
    const near = poisNear(11.1, 77.34, 10);
    expect(near.some((p) => p.poi.id.startsWith("o"))).toBe(true);
    expect(settlementsNear(11.1, 77.34, 10).some((v) => v.lgd.startsWith("c"))).toBe(true);
  });
});
