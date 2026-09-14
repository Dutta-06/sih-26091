/**
 * TypeScript port of the deterministic financial core
 * (module2_financial/financial_engine.py and operating_model.py).
 * Golden values exported from the Python engine are checked in finance.test.ts.
 */

export const MARGIN_SHARE = 0.1;
export const LOAN_SHARE = 0.9;
export const WORKING_CAPITAL_SHARE = 0.2;
export const MICRO_MAX_PROJECT = 140_000;
export const TERM_MAX_PROJECT = 5_000_000;

export type TierName = "micro_finance" | "term_loan";

export interface SchemeTier {
  name: TierName;
  maxProjectCost: number;
  maxLoan: number;
  rate: number;
  tenureYears: number;
  moratoriumMonths: number;
}

export interface Installment {
  quarter: number;
  isMoratorium: boolean;
  opening: number;
  interest: number;
  principal: number;
  payment: number;
  closing: number;
}

export interface Plan {
  eligible: boolean;
  capital: number;
  projectCost: number;
  loan: number;
  loanPct: number;
  marginPct: number;
  capApplied: boolean;
  tier: SchemeTier | null;
  workingCapital: number;
  capex: number;
  schedule: Installment[];
  regularInstallment: number;
  moratoriumInstallment: number;
  totalInterest: number;
  totalRepayment: number;
}

export interface ActivityEconomics {
  annual_revenue_to_project_cost: number;
  operating_margin: number;
  seasonal_profile: number[];
}

const r2 = (v: number) => Math.round((v + Number.EPSILON) * 100) / 100;

export const TIERS: Record<TierName, SchemeTier> = {
  micro_finance: { name: "micro_finance", maxProjectCost: MICRO_MAX_PROJECT, maxLoan: 125_000, rate: 0.065, tenureYears: 3, moratoriumMonths: 3 },
  term_loan: { name: "term_loan", maxProjectCost: TERM_MAX_PROJECT, maxLoan: 4_500_000, rate: 0.08, tenureYears: 7, moratoriumMonths: 6 },
};

export function routeTier(projectCost: number): SchemeTier | null {
  if (projectCost <= 0) return null;
  if (projectCost <= MICRO_MAX_PROJECT) return TIERS.micro_finance;
  if (projectCost <= TERM_MAX_PROJECT) return TIERS.term_loan;
  return null;
}

export function quarterlySchedule(loan: number, rate: number, tenureYears: number, moratoriumMonths: number): Installment[] {
  const total = tenureYears * 4;
  const moratorium = Math.floor(moratoriumMonths / 3);
  const repaying = total - moratorium;
  const q = rate / 4;
  let balance = r2(loan);
  const out: Installment[] = [];
  for (let n = 1; n <= moratorium; n++) {
    const interest = r2(balance * q);
    out.push({ quarter: n, isMoratorium: true, opening: balance, interest, principal: 0, payment: interest, closing: balance });
  }
  if (repaying > 0 && balance > 0) {
    const growth = Math.pow(1 + q, repaying);
    const installment = q > 0 ? r2((balance * q * growth) / (growth - 1)) : r2(balance / repaying);
    for (let n = moratorium + 1; n <= total; n++) {
      const interest = r2(balance * q);
      const last = n === total;
      const principal = last ? balance : r2(installment - interest);
      const payment = last ? r2(principal + interest) : installment;
      const closing = Math.max(0, r2(balance - principal));
      out.push({ quarter: n, isMoratorium: false, opening: balance, interest, principal, payment, closing });
      balance = closing;
    }
  }
  return out;
}

export function buildPlan(capital: number): Plan {
  const empty: Plan = {
    eligible: false, capital, projectCost: 0, loan: 0, loanPct: 0, marginPct: 0, capApplied: false, tier: null,
    workingCapital: 0, capex: 0, schedule: [], regularInstallment: 0, moratoriumInstallment: 0, totalInterest: 0, totalRepayment: 0,
  };
  if (capital <= 0) return empty;
  const projectCost = r2(capital / MARGIN_SHARE);
  const workingCapital = r2(projectCost * WORKING_CAPITAL_SHARE);
  const capex = r2(projectCost - workingCapital);
  const tier = routeTier(projectCost);
  if (!tier) return { ...empty, projectCost, workingCapital, capex, marginPct: 10 };
  const uncapped = r2(projectCost * LOAN_SHARE);
  const loan = Math.min(uncapped, tier.maxLoan);
  const loanPct = Math.round((loan / projectCost) * 10000) / 100;
  const schedule = quarterlySchedule(loan, tier.rate, tier.tenureYears, tier.moratoriumMonths);
  return {
    eligible: true, capital, projectCost, loan, loanPct, marginPct: r2(100 - loanPct), capApplied: uncapped > tier.maxLoan, tier,
    workingCapital, capex, schedule,
    regularInstallment: schedule.find((i) => !i.isMoratorium)?.payment ?? 0,
    moratoriumInstallment: schedule.find((i) => i.isMoratorium)?.payment ?? 0,
    totalInterest: r2(schedule.reduce((s, i) => s + i.interest, 0)),
    totalRepayment: r2(schedule.reduce((s, i) => s + i.payment, 0)),
  };
}

export function quarterFactors(monthly: number[]): number[] {
  const mean = monthly.reduce((a, b) => a + b, 0) / 12;
  const norm = monthly.map((v) => v / mean);
  return [0, 1, 2, 3].map((k) => Math.round(((norm[k * 3] + norm[k * 3 + 1] + norm[k * 3 + 2]) / 3) * 10000) / 10000);
}

export const dscr = (surplus: number, installment: number) => (installment <= 0 ? Infinity : r2(surplus / installment));

export type CoverageBand = "does_not_cover" | "thin" | "comfortable";
export const coverageBand = (ratio: number): CoverageBand => (ratio < 1 ? "does_not_cover" : ratio < 1.25 ? "thin" : "comfortable");

export interface DebtServicePreview {
  plan: Plan;
  annualRevenue: number;
  quarterlySurplus: number;
  baseDscr: number | null;
  quarterlyDscr: number[];
  minSeasonalDscr: number | null;
  breakEvenDropPct: number | null;
}

/** Mirrors operating_model.preview_debt_service (catalog economics, no Module 1 adjustments). */
export function previewDebtService(capital: number, activity: ActivityEconomics): DebtServicePreview {
  const plan = buildPlan(capital);
  const annualRevenue = plan.projectCost * activity.annual_revenue_to_project_cost;
  const quarterlySurplus = r2((annualRevenue * activity.operating_margin) / 4);
  if (!plan.eligible) {
    return { plan, annualRevenue, quarterlySurplus, baseDscr: null, quarterlyDscr: [], minSeasonalDscr: null, breakEvenDropPct: null };
  }
  const inst = plan.regularInstallment;
  const quarterlyDscr = quarterFactors(activity.seasonal_profile).map((f) => dscr(quarterlySurplus * f, inst));
  return {
    plan, annualRevenue, quarterlySurplus,
    baseDscr: dscr(quarterlySurplus, inst),
    quarterlyDscr,
    minSeasonalDscr: Math.min(...quarterlyDscr),
    breakEvenDropPct: annualRevenue > 0 ? r2(((quarterlySurplus - inst) / (annualRevenue / 4)) * 100) : null,
  };
}

export interface Scenario {
  quarterlyDscr: number[];
  minDscr: number;
  deficitQuarters: number;
  /** Cash buffer (rounded up to Rs 500) that covers every quarterly shortfall in the stressed year. */
  bufferNeeded: number;
}

/**
 * Stressed year over calendar quarters (mirrors scenario_digital_twin):
 *  - seasonal: surplus scales with the quarter factor (costs move with sales)
 *  - priceDropPct: revenue falls, operating costs unchanged
 *  - marginDropPts: input-cost shock lowers the operating margin
 */
export function stressScenario(
  preview: DebtServicePreview,
  activity: ActivityEconomics,
  { priceDropPct = 0, marginDropPts = 0 }: { priceDropPct?: number; marginDropPts?: number } = {},
): Scenario {
  const inst = preview.plan.regularInstallment;
  const quarterlyRevenue = preview.annualRevenue / 4;
  const surpluses = quarterFactors(activity.seasonal_profile).map((f) => {
    const revenue = quarterlyRevenue * f;
    const margin = activity.operating_margin - marginDropPts / 100;
    return revenue * margin - revenue * (priceDropPct / 100);
  });
  const quarterlyDscr = surpluses.map((s) => dscr(s, inst));
  const shortfall = surpluses.reduce((sum, s) => sum + Math.max(0, inst - s), 0);
  return {
    quarterlyDscr,
    minDscr: Math.min(...quarterlyDscr),
    deficitQuarters: quarterlyDscr.filter((d) => d < 1).length,
    bufferNeeded: Math.ceil(shortfall / 500) * 500,
  };
}