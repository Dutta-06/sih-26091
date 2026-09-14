/**
 * Module 2 on the device: loan plan + coverage preview (engine/finance.ts), stress scenarios
 * (scenario_digital_twin), the transparent earnings build-up (operating_model / financial_analyst_agent),
 * an indicative budget split and the scheme explanation lists (policy_scheme_agent over scheme_guidelines).
 */
import catalog from "../../../data/reference/business_catalog.json";
import type { Bi } from "../i18n";
import { dscr, previewDebtService, quarterFactors, stressScenario, type ActivityEconomics } from "../engine/finance";
import { catalogBi } from "./catalogHi";
import { retrieve } from "./retrieval";
import type { EarningsStep, FinancialResult, Intel, Msg, PackDoc, ProfileInput } from "./types";

export interface CatalogActivity extends ActivityEconomics {
  id: string;
  category: string;
  sector: string;
  nic_class: string;
  min_project_cost: number;
  perishable: boolean;
  price_unit?: string;
  reference_price?: { low: number; high: number };
  key_inputs: string[];
  buyers: string[];
  licences: string[];
  osm_tags: [string, string][];
  adjacent: string[];
}

export function catalogEntry(id: string): CatalogActivity {
  const a = (catalog.activities as unknown as CatalogActivity[]).find((x) => x.id === id);
  if (!a) throw new Error(`Unknown activity ${id}`);
  return a;
}

export const PRICE_FACTOR_BOUNDS = [0.8, 1.2] as const;
export const REACH_FACTOR_BOUNDS = [0.85, 1.1] as const;
export const REFERENCE_CONSUMER_BASE = 10_000;
export const PRICE_DROP_PCT = 15;
export const MARGIN_SHOCK_PTS = 5;

/**
 * Budget weights over the catalog key inputs (capital expenditure = 80% of project cost):
 * the first key input is the principal asset (machines / animals / shed) and takes 60% of capex;
 * the remaining 40% is shared equally by the other inputs. With a single input it takes all capex.
 * Working capital is the engine's 20%; amounts are whole rupees and always sum to the project cost.
 */
export const PRIMARY_INPUT_SHARE = 0.6;

export type FinancialOutput = FinancialResult & {
  seasonalBasis: "risk_analysis" | "catalog_profile";
  limitations: Msg[];
};

const clamp = (v: number, [lo, hi]: readonly [number, number]) => Math.max(lo, Math.min(hi, v));
const r2 = (v: number) => Math.round((v + Number.EPSILON) * 100) / 100;
const r4 = (v: number) => Math.round(v * 10000) / 10000;

export function budgetSplit(projectCost: number, workingCapital: number, inputs: string[]): FinancialResult["budget"] {
  if (projectCost <= 0) return [];
  const total = Math.round(projectCost);
  const wc = Math.round(workingCapital);
  const capex = total - wc;
  const weights = inputs.length <= 1 ? [1] : inputs.map((_, i) => (i === 0 ? PRIMARY_INPUT_SHARE : (1 - PRIMARY_INPUT_SHARE) / (inputs.length - 1)));
  const names: (Bi | string)[] = inputs.length ? inputs.map(catalogBi) : [{ en: "Equipment and setup", hi: "उपकरण और सेटअप" }];
  const amounts = weights.map((w) => Math.round(capex * w));
  amounts[0] += capex - amounts.reduce((a, b) => a + b, 0);
  return [
    ...names.map((item, i) => ({ item, amount: amounts[i] })),
    { item: { en: "Working capital (raw material, running costs)", hi: "कार्यशील पूंजी (कच्चा माल, चालू खर्च)" }, amount: wc },
  ];
}

/* ------------------------------------------------------------------ policy (policy_scheme_agent) */

const TIER_DOC: Record<string, string> = { micro_finance: "micro_finance.md", term_loan: "term_loan.md" };
const TIER_LABEL: Record<string, string> = { micro_finance: "Micro Finance Scheme", term_loan: "Term Loan Scheme" };
const ITEM = /^\s*(?:[-*]|\d+\.)\s+(.*\S)/;

function items(chunks: PackDoc[]): string[] {
  const out: string[] = [];
  for (const c of chunks) {
    for (const line of c.text.split(/\r?\n/)) {
      const m = ITEM.exec(line);
      if (m && !out.includes(m[1])) out.push(m[1]);
    }
  }
  return out;
}

const sameSource = (src: string, file: string) => src === file || src.endsWith(`/${file}`) || src.endsWith(`\\${file}`);

function search(query: string, file: string, headingOk: (h: string) => boolean = () => true): PackDoc[] {
  return retrieve("scheme_guidelines", query, 20, 0.02)
    .filter((c) => sameSource(c.source, file) && headingOk(c.heading.toLowerCase()))
    .map(({ score: _score, ...doc }) => doc);
}

/** Retrieve rules, documents and process steps for a tier (null = both tiers, e.g. outside the scheme range). */
export function explainScheme(tierName: string | null): FinancialResult["policy"] {
  const tiers = tierName && TIER_DOC[tierName] ? [tierName] : Object.keys(TIER_DOC);
  const rules: PackDoc[] = [];
  for (const tier of tiers) {
    const label = TIER_LABEL[tier];
    rules.push(...search(`${label} key terms interest rate tenure moratorium maximum loan project cost`, TIER_DOC[tier], (h) => h !== label.toLowerCase()));
  }
  let docChunks: PackDoc[] = [];
  if (tierName && TIER_DOC[tierName]) {
    const label = TIER_LABEL[tierName].toLowerCase();
    docChunks = search(`documents required for all applicants and additional documents for the ${label}`, "required_documents.md",
      (h) => h.includes("all applicants") || h.includes(label));
  }
  const stepChunks = search("application process steps", "application_process.md", (h) => h.includes("steps"));
  return { tier: tierName && TIER_DOC[tierName] ? tierName : null, rules, documents: items(docChunks), steps: items(stepChunks) };
}

/* ------------------------------------------------------------------ build */

export function buildFinancial(input: ProfileInput, activityId: string, intel: Intel | null): FinancialOutput {
  const act = catalogEntry(activityId);
  const preview = previewDebtService(input.capital, act);
  const { plan } = preview;
  const limitations: Msg[] = [];

  const riskIndex = intel?.risk.seasonalIndex;
  const useRisk = !!riskIndex && riskIndex.length === 12 && riskIndex.reduce((a, b) => a + b, 0) > 0;
  const index = useRisk ? riskIndex! : act.seasonal_profile;
  const econ: ActivityEconomics = { ...act, seasonal_profile: index };
  if (!useRisk) limitations.push({ key: "c3.fin.lim.catalog_season" });

  const scenarios: FinancialResult["scenarios"] = plan.eligible
    ? [
        { id: "low_season", result: stressScenario(preview, econ) },
        { id: "price_drop", result: stressScenario(preview, econ, { priceDropPct: PRICE_DROP_PCT }) },
        { id: "input_cost", result: stressScenario(preview, econ, { marginDropPts: MARGIN_SHOCK_PTS }) },
      ]
    : [];
  if (!plan.eligible) limitations.push({ key: plan.projectCost > 0 ? "c3.fin.lim.outside_scheme" : "c3.fin.lim.no_capital" });

  // Earnings build-up. Only the catalog base feeds the plan, coverage and scenarios; pricing and reach
  // factors are shown for transparency (applied: false).
  const base = preview.annualRevenue;
  const earnings: EarningsStep[] = [
    { id: "project", value: plan.projectCost, applied: true, confidence: "real" },
    { id: "base", value: r2(base), factor: act.annual_revenue_to_project_cost, applied: true, confidence: "estimated" },
  ];
  let adjusted = base;
  const target = intel?.pricing.targetPrice ?? null;
  const ref = act.reference_price;
  if (target && ref && (ref.low + ref.high) / 2 > 0) {
    const factor = r4(clamp(target / ((ref.low + ref.high) / 2), PRICE_FACTOR_BOUNDS));
    adjusted *= factor;
    earnings.push({ id: "pricing", value: r2(adjusted), factor, applied: false, confidence: intel!.pricing.confidence });
  } else {
    limitations.push({ key: "c3.fin.lim.no_pricing" });
  }
  const consumers = intel?.marketReach.consumerBase ?? null;
  if (consumers !== null) {
    const factor = r4(clamp(Math.sqrt(Math.max(consumers, 0) / REFERENCE_CONSUMER_BASE), REACH_FACTOR_BOUNDS));
    adjusted *= factor;
    earnings.push({ id: "reach", value: r2(adjusted), factor, applied: false, confidence: intel!.marketReach.confidence });
  } else {
    limitations.push({ key: "c3.fin.lim.no_reach" });
  }
  earnings.push({ id: "surplus", value: r2(base * act.operating_margin), factor: act.operating_margin, applied: true, confidence: "estimated" });
  if (plan.eligible && preview.baseDscr !== null) {
    const inst = plan.regularInstallment;
    earnings.push({ id: "coverage", value: preview.baseDscr, applied: true, confidence: "estimated" });
    const minSeason = Math.min(...quarterFactors(index).map((f) => dscr(preview.quarterlySurplus * f, inst)));
    earnings.push({
      id: "seasons", value: minSeason, applied: true,
      confidence: useRisk && intel!.risk.seasonalBasis === "price_history" ? intel!.risk.confidence : "estimated",
    });
  }

  return {
    plan,
    preview,
    scenarios,
    earnings,
    budget: budgetSplit(plan.projectCost, plan.workingCapital, act.key_inputs),
    policy: explainScheme(plan.eligible && plan.tier ? plan.tier.name : null),
    seasonalBasis: useRisk ? "risk_analysis" : "catalog_profile",
    limitations,
  };
}
