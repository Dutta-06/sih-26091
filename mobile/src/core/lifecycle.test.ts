import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/c3.json";
import en from "../i18n/strings/core_c3";
import { checklist, maskAadhaar, maskAccount, requiredDocuments, validateField, verhoeffDigit, verhoeffValid, type Field } from "./documents";
import { buildFinancial } from "./financial";
import { classifyIssue, createTicket, routeTicket } from "./grievance";
import { roadmap } from "./launch";
import { categoryPrior, interventionOptions } from "./outcomes";
import { discountFor, pool } from "./procurement";
import { nextEvents, transition } from "./tracker";
import type { Intel, LocationCandidate, OutcomeRecord, ProfileInput } from "./types";

const profile = (capital: number, extra: Partial<ProfileInput> = {}): ProfileInput => ({
  capital, locationText: "Sitapur", locationCode: null, activityId: "tailoring", reason: null, skills: [], assets: [],
  premises: null, category: null, womanOwned: true, shgMember: false, ...extra,
});

describe("documents", () => {
  const micro = buildFinancial(profile(12_000), "tailoring", null);
  const term = buildFinancial(profile(50_000), "dairy_farming", null);

  it("category certificate only for SC/ST/OBC; scheme documents merged without duplicates", () => {
    const ids = (p: ProfileInput, f = micro) => requiredDocuments(p, f).map((d) => d.id);
    expect(ids(profile(12_000, { category: "obc" }))).toContain("caste_or_category_certificate");
    for (const c of ["general", null] as const) expect(ids(profile(12_000, { category: c }))).not.toContain("caste_or_category_certificate");
    const microIds = ids(profile(12_000));
    expect(microIds).toContain("recent_passport_size_photographs");
    expect(microIds).toContain("income_certificate");
    expect(microIds).not.toContain("identity_proof_aadhaar_card_or_voter_id");
    expect(microIds.some((i) => i.startsWith("self_help_group"))).toBe(false);
    expect(ids(profile(12_000, { shgMember: true })).some((i) => i.startsWith("self_help_group"))).toBe(true);
    const termIds = ids(profile(50_000), term);
    expect(termIds).toContain("licences_applicable_to_the_activity");
    expect(termIds.filter((i) => i === "udyam_certificate")).toHaveLength(1);
    expect(new Set(termIds).size).toBe(termIds.length);
  });

  it("checklist completeness", () => {
    const docs = requiredDocuments(profile(12_000), micro);
    expect(checklist(docs, {}).complete).toBe(false);
    const all = Object.fromEntries(docs.map((d) => [d.id, "complete" as const]));
    expect(checklist(docs, all).complete).toBe(true);
    expect(checklist(docs, { ...all, address_proof: "pending" }).outstanding).toEqual(["address_proof"]);
    expect(checklist([], {}).complete).toBe(false);
  });

  it.each(fixture.validators)("validator parity $field '$value'", ({ field, value, ok, result }) => {
    const got = validateField(field as Field, value);
    if (field === "aadhaar_number" && ok) {
      // backend checks format only; the device adds the Verhoeff checksum
      expect(got.ok).toBe(verhoeffValid(String(result)));
      return;
    }
    expect(got.ok).toBe(ok);
    if (ok) expect(got.value).toBe(String(result));
    else expect(en.en[got.error!.key]).toBeTruthy();
  });

  it("Verhoeff checksum and masking", () => {
    const base = "23456789012";
    const full = base + verhoeffDigit(base);
    expect(verhoeffValid(full)).toBe(true);
    expect(validateField("aadhaar_number", full).ok).toBe(true);
    const wrong = base + ((verhoeffDigit(base) + 1) % 10);
    expect(validateField("aadhaar_number", wrong).error?.key).toBe("c3.doc.err.aadhaar_checksum");
    expect(maskAadhaar(full)).toBe(`XXXX-XXXX-${full.slice(-4)}`);
    expect(maskAccount("123456789012")).toBe("XXXXXXXX9012");
  });
});

describe("tracker", () => {
  it("follows the backend transition table", () => {
    const ok = { allDocsComplete: true };
    let s = transition("not_started", "request_documents", ok);
    s = transition(s, "submit", ok);
    expect(transition(s, "return_documents", ok)).toBe("documents_pending");
    s = transition(transition(transition(s, "start_verification", ok), "sanction", ok), "disburse", ok);
    expect(s).toBe("disbursed");
    expect(nextEvents("disbursed")).toEqual([]);
    expect(nextEvents("sanctioned")).toEqual(["disburse", "reject"]);
  });
  it("throws on illegal moves and incomplete submission", () => {
    expect(() => transition("documents_pending", "submit", { allDocsComplete: false })).toThrow(/documents/);
    expect(() => transition("not_started", "sanction", { allDocsComplete: true })).toThrow(/Illegal/);
    expect(() => transition("rejected", "submit", { allDocsComplete: true })).toThrow(/Illegal/);
  });
});

describe("outcomes parity (outcome_learning_loop.category_prior)", () => {
  it.each(fixture.priors)("$activity / $district", (p) => {
    const got = categoryPrior(p.activity, p.district, p.real as OutcomeRecord[]);
    expect(got.prior).toBe(p.prior);
    expect(got.realRecords).toBe(p.realRecords);
    expect(got.syntheticRecords).toBe(p.syntheticRecords);
    expect(got.isSyntheticDominant).toBe(p.dominant);
  });

  it("intervention options weight real records above synthetic ones", () => {
    const real = fixture.priors[1].real as OutcomeRecord[];
    const base = interventionOptions("tailoring", "Sitapur", []);
    const withReal = interventionOptions("tailoring", "Sitapur", real);
    expect(base).toHaveLength(4);
    const pricing = (xs: typeof base) => xs.find((x) => x.type === "pricing_adjustment")!;
    expect(pricing(withReal).real).toBe(2);
    expect(pricing(withReal).synthetic).toBe(6);
    expect(pricing(withReal).successRate).toBeGreaterThan(pricing(base).successRate);
    for (const o of withReal) expect(o.successRate).toBeGreaterThanOrEqual(0.1), expect(o.successRate).toBeLessThanOrEqual(0.9);
    expect(interventionOptions("unknown_activity", null, []).every((o) => o.successRate === 0.5 && o.total === 0)).toBe(true);
  });
});

describe("grievance parity (grievance_engine)", () => {
  it.each(fixture.grievances)("classify '$text'", ({ text, issue }) => expect(classifyIssue(text)).toBe(issue));
  it.each(fixture.routes)("route $issue / $sector", ({ issue, sector, role }) => {
    const r = routeTicket(issue as never, sector);
    expect(r.roleEn).toBe(role);
    expect(en.en[r.routedTo.key]).toBe(role);
    expect(r.responseHours).toBeGreaterThan(0);
  });
  it("creates deterministic tickets", () => {
    const a = createTicket("machine kharab", "2026-07-20T10:00:00Z", "textiles_apparel");
    expect(a).toEqual(createTicket("machine kharab", "2026-07-20T10:00:00Z", "textiles_apparel"));
    expect(a.issue).toBe("machinery_breakdown");
    expect(a.status).toBe("mentor_assigned");
  });
});

describe("launch roadmap parity (launch_copilot, no Module 1 intel)", () => {
  it.each(fixture.launch)("$activity at $capital", (l) => {
    const f = buildFinancial(profile(l.capital), l.activity, null);
    const ms = roadmap(profile(l.capital), l.activity, f, null);
    expect(ms.map((m) => m.week)).toEqual(l.weeks);
    expect(ms.map((m) => m.theme)).toEqual(l.themes);
    expect(ms.map((m) => m.tasks.length)).toEqual(l.taskCounts);
    for (const m of ms) for (const t of m.tasks) expect(en.en[t.key]).toBeTruthy();
  });
  it("inventory milestone carries the working capital", () => {
    const f = buildFinancial(profile(12_000), "tailoring", null);
    expect(roadmap(profile(12_000), "tailoring", f, null).find((m) => m.theme === "inventory")!.amount).toBe(24_000);
  });
});

describe("procurement pool", () => {
  it("documented discount tiers", () => {
    expect([0, 2, 3, 5, 6, 9, 10, 40].map(discountFor)).toEqual([0, 0, 8, 8, 12, 12, 15, 15]);
  });
  it("counts competitor POIs from intel and is ready at 3 peers", () => {
    const nearby = Array.from({ length: 4 }, (_, i) => ({ poi: { id: `p${i}` }, km: i }));
    const intel = { competitor: { nearby, confidence: "real" }, marketReach: { radiusKm: 5 } } as unknown as Intel;
    const p = pool("tailoring", null, intel);
    expect(p).toMatchObject({ peers: 4, ready: true, discountPct: 8, target: 3, source: "competitor_intel" });
    expect(p.items.map((i) => (typeof i === "string" ? i : i.en))).toEqual(["Sewing machines", "Thread and accessories", "Fabric (customer-supplied or bought)"]);
    expect(p.items.map((i) => (typeof i === "string" ? i : i.hi))[0]).toBe("सिलाई मशीनें");
  });
  it("without location or intel: no peers, estimated, limitation", () => {
    const p = pool("tailoring", null, null);
    expect(p).toMatchObject({ peers: 0, ready: false, discountPct: 0, confidence: "estimated", source: "none" });
    expect(p.limitations.map((l) => l.key)).toContain("c3.pool.no_location");
  });
  it("falls back to pack POIs around the location", () => {
    const loc = { lat: 27.57, lon: 80.68 } as LocationCandidate;
    const p = pool("tailoring", loc, null);
    expect(p.source).toBe("pack_pois");
    expect(p.confidence).toBe("real");
    expect(p.peers).toBeGreaterThanOrEqual(0);
  });
});

describe("strings", () => {
  it("every C3 key exists in Hindi", () => {
    for (const k of Object.keys(en.en)) expect(en.hi[k], k).toBeTruthy();
  });
});
