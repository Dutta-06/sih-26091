import { describe, expect, it } from "vitest";
import { buildPlan } from "../engine/finance";
import catalog from "../../../data/reference/business_catalog.json";
import fixture from "./__fixtures__/c3.json";
import { aggregatePeriod, creditworthinessIndex, monthlySnapshots, scoreRecords, type PeriodRecord } from "./health";
import { buildFinancial } from "./financial";
import { parseNotifications, simulateBankAlerts } from "./sms";
import type { ProfileInput, Transaction } from "./types";

const act = (id: string) => catalog.activities.find((a) => a.id === id)!;
const close = (a: number | null, b: number | null, tol = 0.02) => {
  if (a === null || b === null) return expect(a).toBe(b);
  expect(Math.abs(a - b)).toBeLessThanOrEqual(tol);
};

describe("monitoring aggregation + health scoring parity (ongoing_monitoring_agent + health_score_agent)", () => {
  it.each(fixture.monitoring)("$name", (sc) => {
    const plan = buildPlan(sc.capital);
    const a = act(sc.activity);
    const ctx = { plan, annualRevenue: plan.projectCost * a.annual_revenue_to_project_cost, seasonalIndex: a.seasonal_profile, disbursedOn: sc.disbursedOn };
    const records = sc.batches.map((b) => aggregatePeriod(b as Transaction[], ctx, "2026-09-14")!);
    const scored = scoreRecords(records, 1 - a.operating_margin);
    sc.expected.forEach((e, i) => {
      const g = scored[i];
      expect(g.days).toBe(e.days);
      close(g.revenue, e.revenue);
      close(g.baseline, e.baseline);
      close(g.expenses, e.expenses);
      close(g.installmentDue, e.installmentDue);
      expect(g.status).toBe(e.status);
      close(g.creditIndex, e.creditIndex, 0.1);
      close(g.score, e.score, 0.1);
      expect(g.band).toBe(e.band);
      expect(g.earlyWarning).toBe(e.earlyWarning);
      expect(g.intervention).toBe(e.intervention);
    });
  });

  it("scores fixed snapshots like health_score_agent (bands, warnings, persistent at-risk)", () => {
    const records: PeriodRecord[] = fixture.scoring.map((s, i) => ({
      start: `2026-${String(i + 1).padStart(2, "0")}-01`, end: "", days: s.days, transactionsParsed: s.transactionsParsed,
      revenue: s.revenue, baseline: s.baseline, expenses: s.expenses, surplus: s.surplus, installmentDue: s.installmentDue,
      status: s.status as PeriodRecord["status"], creditIndex: null,
    }));
    const scored = scoreRecords(records, 1 - act("tailoring").operating_margin);
    fixture.scoring.forEach((e, i) => {
      close(scored[i].score, e.score, 0.1);
      expect(scored[i].band).toBe(e.band);
      expect(scored[i].earlyWarning).toBe(e.earlyWarning);
      expect(scored[i].intervention).toBe(e.intervention);
    });
  });

  it("credit index is null under two weeks and uses the repayment factor", () => {
    expect(creditworthinessIndex([], "2026-01-01", 7, "paid")).toBeNull();
    // no credits: regularity 0, consistency 0 → 30 × repayment factor
    expect(creditworthinessIndex([], "2026-01-01", 28, "paid")).toBe(30);
  });
});

const sunita: ProfileInput = {
  capital: 12_000, locationText: "Sitapur", locationCode: null, activityId: "tailoring", reason: null, skills: ["stitching"],
  assets: [], premises: "home", category: "obc", womanOwned: true, shgMember: true,
};

describe("storyline: Sunita's tailoring unit, Jan–Jul 2026 with a July monsoon shock", () => {
  const fin = buildFinancial(sunita, "tailoring", null);
  const alerts = simulateBankAlerts(fin, "tailoring", "2026-01", 7, 26091, { month: "2026-07", revenueDropPct: 40 });
  const txns = parseNotifications(alerts, new Date("2026-09-14T00:00:00Z"));
  const months = monthlySnapshots(txns, fin, "tailoring", { disbursedOn: "2026-01-01" });

  it("plan matches the scheme figures", () => {
    expect(fin.plan.loan).toBe(108_000);
    expect(Math.round(fin.plan.regularInstallment)).toBe(10_801);
  });

  it("every simulated alert parses back with its date", () => {
    expect(txns.length).toBe(alerts.length);
    expect(txns.every((t) => t.at.startsWith("2026-0"))).toBe(true);
    const emis = txns.filter((t) => t.isLoanRepayment);
    expect(emis.map((t) => t.at.slice(0, 7))).toEqual(["2026-03", "2026-06"]);
    expect(Math.round(emis[1].amount)).toBe(10_801);
  });

  it("normal months stay healthy and July raises an early warning with an intervention", () => {
    expect(months.map((m) => m.month)).toEqual(["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]);
    for (const m of months.slice(0, 6)) {
      expect(m.band).toBe("healthy");
      expect(m.earlyWarning).toBe(false);
    }
    expect(months[5].status).toBe("paid");
    const july = months[6];
    expect(july.earlyWarning).toBe(true);
    expect(july.intervention).not.toBeNull();
    expect(july.revenue / july.planned).toBeLessThan(0.7);
  });

  it("edge cases: no transactions, only debits, overdue repayment", () => {
    expect(monthlySnapshots([], fin, "tailoring")).toEqual([]);
    const debits: Transaction[] = [{ at: "2026-04-05T00:00:00+00:00", direction: "debit", amount: 3000, channel: "upi", isLoanRepayment: false }];
    const [d] = monthlySnapshots(debits, fin, "tailoring", { disbursedOn: "2026-01-01" });
    expect(d.revenue).toBe(0);
    expect(d.band).toBe("at_risk");
    expect(d.intervention).toBe("repayment_counselling");
    // zero surplus: sales exactly cover costs → coverage 0 → repayment counselling
    const flat: Transaction[] = [
      { at: "2026-05-02T00:00:00+00:00", direction: "credit", amount: 5000, channel: "upi", isLoanRepayment: false },
      { at: "2026-05-09T00:00:00+00:00", direction: "debit", amount: 5000, channel: "upi", isLoanRepayment: false },
    ];
    const [z] = monthlySnapshots(flat, fin, "tailoring", { disbursedOn: "2026-01-01" });
    expect(z.surplus).toBe(0);
    expect(z.components.coverage).toBe(0);
    expect(z.intervention).toBe("repayment_counselling");
    // June (quarter 2 due month) without the EMI → overdue
    const noEmi = txns.filter((t) => !t.isLoanRepayment);
    const june = monthlySnapshots(noEmi, fin, "tailoring", { disbursedOn: "2026-01-01" })[5];
    expect(june.status).toBe("overdue");
    expect(june.components.repayment).toBe(0);
  });
});
