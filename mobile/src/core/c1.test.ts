import { describe, expect, it } from "vitest";
import fixtures from "./__fixtures__/c1.json";
import { resolveLocation, haversineKm } from "./geo";
import { classifyIntent, detectScript, extract } from "./nlu";
import {
  district, districts, docs, feedback, healthThresholds, isDetailed, outcomeSeed, packMeta, poisNear, priceSeries, settlementsNear,
  stateRef, udyam, udyamState, villages,
} from "./pack";
import { retrieve } from "./retrieval";
import catalog from "../../../data/reference/business_catalog.json";

describe("all-India coverage", () => {
  it("reads a place with a language word in it as a place, not a language request", () => {
    const e = extract("I am Meena, I live in Coimbatore, Tamil Nadu and have 15000 rupees saved, I want to start a tea stall", null);
    expect(e.locationText).toBe("Coimbatore, Tamil Nadu");
    expect(e.language).toBeUndefined();
    expect(resolveLocation(e.locationText!).chosen?.district.name.en).toBe("Coimbatore");
    expect(extract("tamil mein baat karo", null).language).toBe("ta");
  });

  it("resolves districts anywhere and generates consistent local tables", () => {
    for (const [q, state] of [["Tiruppur, Tamil Nadu", "Tamil Nadu"], ["Murshidabad", "West Bengal"], ["Hyderabad", "Telangana"], ["Central Delhi", "Delhi"], ["Kamrup, Assam", "Assam"]] as const) {
      const r = resolveLocation(q);
      expect(r.chosen?.method, q).toBe("district_table");
      expect(r.chosen!.district.state).toBe(state);
      const near = settlementsNear(r.chosen!.lat, r.chosen!.lon, 10);
      expect(near.length).toBeGreaterThan(5);
      expect(poisNear(r.chosen!.lat, r.chosen!.lon, 10).some((p) => p.poi.kind === "bank")).toBe(true);
      expect(udyam(r.chosen!.district.id, "1410")).toBeGreaterThan(0);
    }
    // deterministic: the same district always gets the same tables
    const a = poisNear(11.1, 77.34, 5).map((p) => p.poi.id).join();
    expect(poisNear(11.1, 77.34, 5).map((p) => p.poi.id).join()).toBe(a);
    // states missing from the repository reference are completed from the district table
    expect(stateRef("Goa")?.density).toBeGreaterThan(100);
  });
});

describe("pack", () => {
  it("is flagged as a synthetic sample, covers every Census 2011 district and details nine of them", () => {
    expect(packMeta().synthetic_sample).toBe(true);
    expect(districts().filter((d) => isDetailed(d.id)).map((d) => d.id).sort()).toEqual(
      ["bhadohi", "dharwad", "gaya", "jaunpur", "mirzapur", "muzaffarpur", "nashik", "prayagraj", "varanasi"],
    );
    expect(districts().length).toBeGreaterThan(630);
    expect(new Set(districts().map((d) => d.id)).size).toBe(districts().length);
    expect(districts().filter((d) => /allahabad|bhadohi/i.test(d.name.en))).toHaveLength(1); // merged into the detailed rows
    for (const d of districts().filter((x) => isDetailed(x.id))) {
      const n = villages().filter((v) => v.district === d.id).length;
      expect(n).toBeGreaterThanOrEqual(25);
      expect(n).toBeLessThanOrEqual(40);
    }
  });

  it("has Gopiganj (Bhadohi) with its LGD code and repeats the name elsewhere", () => {
    const g = villages().filter((v) => v.name.en === "Gopiganj");
    expect(g.map((v) => v.district).sort()).toEqual(["bhadohi", "gaya", "jaunpur"]);
    const b = g.find((v) => v.district === "bhadohi")!;
    expect([b.lgd, b.lat, b.lon, b.name.hi]).toEqual(["184512", 25.279, 82.458, "गोपीगंज"]);
    expect(new Set(villages().map((v) => v.lgd)).size).toBe(villages().length);
  });

  it("makes handloom crowded and tailoring thin around Gopiganj, Bhadohi (from benchmark densities)", () => {
    const tagged = (k: string, v: string) => (p: { tags: [string, string][] }) => p.tags.some(([a, b]) => a === k && b === v);
    const near = (f: (p: { tags: [string, string][] }) => boolean) => poisNear(25.279, 82.458, 10, f).length;
    const handloom = near(tagged("craft", "weaver")) + near(tagged("shop", "fabric"));
    const tailoring = near(tagged("shop", "tailor")) + near(tagged("craft", "tailor"));
    const cat = Object.fromEntries(catalog.activities.map((a) => [a.id, a.typical_density_per_10k]));
    // relative to the benchmark, handloom is far denser than tailoring
    expect(handloom / cat.handloom_weaving).toBeGreaterThan(3 * (tailoring / cat.tailoring));
    const hits = poisNear(25.279, 82.458, 5);
    expect(hits.every((h, i) => i === 0 || hits[i - 1].km <= h.km)).toBe(true);
    expect(hits.some((h) => h.poi.kind === "haat" || h.poi.kind === "market")).toBe(true);
  });

  it("serves Udyam counts, prices, feedback, docs, seed, state reference and thresholds", () => {
    for (const a of catalog.activities) expect(udyam("bhadohi", a.nic_class)).toBeGreaterThanOrEqual(0);
    expect(udyam("bhadohi", "1312")!).toBeGreaterThan(udyam("varanasi", "1312")! * 0.3);
    expect(udyam("nowhere", "1410")).toBeNull();
    const up = udyamState("Uttar Pradesh", "1410")!;
    expect(up.population).toBeGreaterThan(10_000_000);
    expect(udyamState("Kerala", "1410")!.population).toBeGreaterThan(30_000_000); // generated for every district
    const wheat = priceSeries("Wheat", "Uttar Pradesh")!;
    expect(wheat.months).toHaveLength(36);
    expect(wheat.months[35].month).toBe("2026-06");
    expect(wheat.months[0].month).toBe("2023-07");
    expect(priceSeries("Wheat", "Kerala")).toBeNull();
    for (const d of districts().filter((x) => isDetailed(x.id))) {
      const f = feedback(d.id, null);
      expect(f.length).toBeGreaterThanOrEqual(3);
      expect(f.length).toBeLessThanOrEqual(6);
    }
    expect(feedback("bhadohi", "tailoring").length).toBeGreaterThan(0);
    expect(docs("risk_taxonomy").length).toBeGreaterThan(5);
    expect(outcomeSeed().every((r) => r.is_synthetic)).toBe(true);
    expect(stateRef("UP")?.purchasing_power).toBe("low");
    expect(stateRef("Atlantis")).toBeNull();
    expect(healthThresholds().bands.healthy_min_score).toBe(70);
    expect(district("Bhadohi")?.id).toBe("bhadohi");
  });
});

describe("retrieval", () => {
  it("returns nothing for empty or out-of-vocabulary queries and respects topK", () => {
    expect(retrieve("sector_reports", "")).toEqual([]);
    expect(retrieve("sector_reports", "🙂 qwertyuiop")).toEqual([]);
    expect(retrieve("sector_reports", "tailoring weaving dairy", 2).length).toBeLessThanOrEqual(2);
  });
  it("parity fixture exists for 8 queries x 3 collections", () => {
    expect(fixtures.retrieval.length).toBe(24);
  });
});

describe("nlu extensions", () => {
  const cap = (t: string, p: "capital" | null = null) => extract(t, p).capital;
  it("reads amounts in words and rejects negatives / zero / unsupported English words", () => {
    expect(cap("बारह हज़ार")).toBe(12_000);
    expect(cap("पचास हजार रुपये")).toBe(50_000);
    expect(cap("dedh lakh")).toBe(150_000);
    expect(cap("1.5 लाख")).toBe(150_000);
    expect(cap("-500", "capital")).toBeUndefined();
    expect(cap("-5 lakh")).toBeUndefined();
    expect(cap("0", "capital")).toBeUndefined();
    expect(cap("twelve thousand", "capital")).toBeUndefined();
    expect(cap("१२००० रुपये")).toBe(12_000);
    expect(cap("between 1-2 lakh")).toBe(200_000);
  });
  it("extracts skills, premises, category, SHG and language", () => {
    const e = extract("I know stitching and embroidery, will work from home, OBC category, member of an SHG", null);
    expect(e.skills).toEqual(["stitching", "embroidery"]);
    expect(e.premises).toBe("home");
    expect(e.category).toBe("obc");
    expect(e.shgMember).toBe(true);
    const h = extract("मुझे सिलाई आती है, घर से काम करूँगी, अनुसूचित जाति, स्वयं सहायता समूह की सदस्य", null);
    expect(h.skills).toContain("stitching");
    expect(h.premises).toBe("home");
    expect(h.category).toBe("sc");
    expect(h.shgMember).toBe(true);
    expect(extract("I am not in any SHG group", null).shgMember).toBe(false);
    expect(extract("sc", "category").category).toBe("sc");
    expect(extract("I will go to the st market", null).category).toBeUndefined();
    expect(extract("Hindi mein baat karo", null)).toEqual({ language: "hi" });
  });
  it("handles Hindi location/reason cues, bare location and very long text", () => {
    expect(extract("भदोही में दुकान", null).locationText).toBe("भदोही");
    expect(extract("in गोपीगंज", null).locationText).toBe("गोपीगंज");
    expect(extract("सिलाई कारण गाँव में दर्ज़ी नहीं है", null).reason).toBe("गाँव में दर्ज़ी नहीं है");
    expect(extract("Gopiganj Bhadohi", "location").locationText).toBe("Gopiganj Bhadohi");
    expect(extract("my savings", "reason").reason).toBe("my savings");
    expect(extract("a".repeat(20000), null)).toEqual({});
    expect(extract("", "location")).toEqual({});
  });
  it("classifies extra intents", () => {
    expect(classifyIntent("नमस्ते")).toBe("greeting");
    expect(classifyIntent("please speak in Hindi")).toBe("change_language");
    expect(classifyIntent("I want to meet other entrepreneurs in the community")).toBe("community");
    expect(classifyIntent("मेरा आवेदन कहाँ तक पहुँचा")).toBe("application_status");
    expect(classifyIntent("yojana ke baare mein batao")).toBe("scheme_inquiry");
    expect(classifyIntent("")).toBe("unknown");
  });
  it("detects scripts", () => {
    expect(detectScript("मला शिवणकाम व्यवसाय करायचा आहे")).toBe("mr");
    expect(detectScript("मुझे सिलाई का काम करना है")).toBe("hi");
    expect(detectScript("আমি দুধ বিক্রি করি")).toBe("bn");
    expect(detectScript("தையல்")).toBe("ta");
    expect(detectScript("ಧಾರವಾಡ")).toBe("kn");
    expect(detectScript("ਪਿੰਡ")).toBe("pa");
    expect(detectScript("గ్రామం")).toBe("te");
    expect(detectScript("ગામ")).toBe("en"); // Gujarati is not an app language
    expect(detectScript("")).toBe("en");
  });
});

describe("geo.resolveLocation", () => {
  it("returns every Gopiganj for a bare repeated name, and the chosen one is real", () => {
    for (const q of ["Gopiganj", "गोपीगंज", "gopiganj!!"]) {
      const r = resolveLocation(q);
      expect(r.candidates.map((c) => c.district.id).sort()).toEqual(["bhadohi", "gaya", "jaunpur"]);
      expect(r.chosen).toBeNull();
      expect(r.confidence).toBe("estimated");
      expect(r.limitations[0].key).toBe("core.c1.geo.ambiguous");
    }
    const chosen = resolveLocation("गोपीगंज", "184512");
    expect(chosen.chosen?.district.id).toBe("bhadohi");
    expect(chosen.chosen?.method).toBe("village_table");
    expect(chosen.confidence).toBe("real");
    expect(chosen.limitations).toEqual([]);
  });

  it("narrows by stated district, block or state", () => {
    const r = resolveLocation("Gopiganj, Bhadohi, Uttar Pradesh");
    expect(r.candidates).toHaveLength(1);
    expect(r.chosen?.lgd).toBe("184512");
    expect(r.confidence).toBe("real");
    expect(resolveLocation("गोपीगंज, गया जिला").chosen?.district.id).toBe("gaya");
    expect(resolveLocation("Gopiganj, Shahganj block").chosen?.district.id).toBe("jaunpur");
    expect(resolveLocation("Gopiganj Bihar").chosen?.district.id).toBe("gaya");
    expect(resolveLocation("Gopiganj UP").candidates.map((c) => c.district.id).sort()).toEqual(["bhadohi", "jaunpur"]);
    const wrong = resolveLocation("Gopiganj, Nashik");
    expect(wrong.chosen?.method).toBe("district_table");
    expect(wrong.limitations.map((l) => l.key)).toContain("core.c1.geo.village_not_in_district");
  });

  it("falls back to district HQ, then state centroid, then nothing", () => {
    const d = resolveLocation("Bhadohi");
    expect(d.chosen?.method).toBe("district_table");
    expect(d.chosen?.district.id).toBe("bhadohi");
    expect(d.confidence).toBe("estimated");
    expect(resolveLocation("बनारस").chosen?.district.id).toBe("varanasi");
    expect(resolveLocation("Allahabad").chosen?.district.id).toBe("prayagraj");
    const s = resolveLocation("UP");
    expect(s.chosen?.method).toBe("state_centroid");
    expect(s.chosen?.district.state).toBe("Uttar Pradesh");
    expect(s.limitations[0].key).toBe("core.c1.geo.state_centroid");
    expect(resolveLocation("I will pick up the goods").chosen).toBeNull();
    expect(resolveLocation("मैं कल बाज़ार गया था").candidates).toEqual([]);
    for (const q of ["asdfgh qwerty", "", "🙂"]) {
      const n = resolveLocation(q);
      expect(n.candidates).toEqual([]);
      expect(n.chosen).toBeNull();
      expect(n.limitations[0].key).toBe("core.c1.geo.unresolved");
    }
  });

  it("uses a kept LGD code when the text has no place", () => {
    expect(resolveLocation("", "243177").chosen?.district.id).toBe("gaya");
  });

  it("computes haversine distance", () => {
    expect(haversineKm({ lat: 25.39, lon: 82.57 }, { lat: 25.32, lon: 82.97 })).toBeCloseTo(40.97, 0);
  });
});
