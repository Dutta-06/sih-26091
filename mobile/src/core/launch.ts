/**
 * Business launch roadmap (port of module3_monitoring/launch_copilot.py). The launch is fitted before the first
 * principal repayment: within max(6, round(moratorium_months × 4.33) − 2) weeks, or 12 weeks without a moratorium.
 * Bilingual names are passed as {name} (English) and {name_hi} (Hindi) variables.
 */
import { catalogHi } from "./catalogHi";
import type { Bi } from "../i18n";
import { catalogEntry } from "./financial";
import type { FinancialResult, Intel, Msg, ProfileInput } from "./types";

export const DEFAULT_WINDOW_WEEKS = 12;

export interface Milestone {
  id: string;
  theme: "licensing" | "supplier_discovery" | "inventory" | "customer_acquisition" | "operations";
  week: number;
  tasks: Msg[];
  amount?: number;
}

/** Python's round(): half to even. */
export function pyRound(v: number): number {
  const f = Math.floor(v);
  const diff = v - f;
  if (Math.abs(diff - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1;
  return Math.round(v);
}

const bi = (name: Bi | string) => (typeof name === "string" ? { name, name_hi: name } : { name: name.en, name_hi: name.hi });

export function launchWindowWeeks(financial: FinancialResult): number {
  const m = financial.plan.tier?.moratoriumMonths ?? 0;
  return m ? Math.max(6, pyRound(m * 4.33) - 2) : DEFAULT_WINDOW_WEEKS;
}

export function roadmap(input: ProfileInput, activityId: string, financial: FinancialResult, intel: Intel | null): Milestone[] {
  const act = catalogEntry(activityId);
  const weeks = launchWindowWeeks(financial);
  const { plan } = financial;
  const inputs = act.key_inputs;

  const licensing: Msg[] = act.licences.length
    ? act.licences.map((l) => ({ key: "c3.launch.obtain", vars: { name: l, name_hi: catalogHi(l) } }))
    : [{ key: "c3.launch.udyam" }];
  if (input.premises === "rented_shop") licensing.push({ key: "c3.launch.rent_agreement" });

  const suppliers: Msg[] = inputs.map((i) => ({ key: "c3.launch.two_sources", vars: { name: i, name_hi: catalogHi(i) } }));
  if (intel) {
    const sc = intel.supplyChain;
    suppliers.push(...sc.suppliers.slice(0, 3).map((s) => ({ key: "c3.launch.contact_supplier", vars: { ...bi(s.poi.name), km: Math.round(s.km), confidence: sc.confidence } })));
    for (const id of sc.singlePointsOfFailure.slice(0, 2)) {
      const node = sc.nodes.find((n) => n.id === id);
      suppliers.push({ key: "c3.launch.backup", vars: bi(node?.label ?? id) });
    }
  }

  const inventory: Msg[] = [];
  if (plan.workingCapital > 0) inventory.push({ key: "c3.launch.first_stock", vars: { items: { en: inputs.slice(0, 3).join(", "), hi: inputs.slice(0, 3).map(catalogHi).join(", ") } as unknown as string, amount: plan.workingCapital } });
  else inventory.push({ key: "c3.launch.stock_after_sanction" });
  if (plan.capex > 0) inventory.push({ key: "c3.launch.capex", vars: { amount: plan.capex } });
  if (act.perishable) inventory.push({ key: "c3.launch.perishable" });

  const customers: Msg[] = act.buyers.map((b) => ({ key: "c3.launch.approach", vars: { name: b, name_hi: catalogHi(b) } }));
  if (intel) {
    customers.push(...intel.marketReach.places.slice(0, 3).map((p) => ({ key: "c3.launch.visit", vars: { ...bi(p.poi.name), km: Math.round(p.km) } })));
    if (intel.pricing.targetPrice) {
      customers.push({ key: "c3.launch.price", vars: { price: Math.round(intel.pricing.targetPrice), unit: act.price_unit ?? "", confidence: intel.pricing.confidence } });
    }
  }

  const operations: Msg[] = [plan.tier?.moratoriumMonths
    ? { key: "c3.launch.window", vars: { weeks, months: plan.tier.moratoriumMonths } }
    : { key: "c3.launch.window_default", vars: { weeks } }];
  if (intel) {
    for (const f of intel.risk.flags.filter((x) => x.mitigation).slice(0, 3)) operations.push({ key: "c3.launch.mitigation", vars: { text: f.mitigation! } });
  }
  operations.push({ key: "c3.launch.consent" });

  const phases: [Milestone["theme"], Msg[], number, number?][] = [
    ["licensing", licensing, 0.25],
    ["supplier_discovery", suppliers, 0.4],
    ["inventory", inventory, 0.6, plan.workingCapital > 0 ? plan.workingCapital : undefined],
    ["customer_acquisition", customers, 0.8],
    ["operations", operations, 1.0],
  ];
  return phases.map(([theme, tasks, frac, amount], i) => ({
    id: `m${i + 1}_${theme}`,
    theme,
    week: Math.max(1, pyRound(weeks * frac)),
    tasks,
    ...(amount !== undefined ? { amount } : {}),
  }));
}
