/**
 * Pricing (port of module1_feasibility/pricing_agent.py).
 * Commodity activities with a pack price series: 25th/50th/75th percentiles (numpy linear) of the latest 12 monthly
 * modal prices ("real"). Otherwise catalog reference price × purchasing-power index from the state tier
 * (low 0.85 / medium 1.0 / high 1.15, documented placeholder) — "estimated". No SECC extract ships in the pack.
 */
import { catalogHi } from "../catalogHi";
import { priceSeries, stateRefEntry } from "../pack";
import type { Level, LocationCandidate, PricingIntel } from "../types";
import { type CatalogActivity, msg, percentile, round, src } from "./catalog";

export const STATE_TIER_INDEX: Record<Level, number> = { low: 0.85, medium: 1.0, high: 1.15 };
export const AGMARKNET_UNIT = { en: "INR per quintal (mandi modal price)", hi: "रुपये प्रति क्विंटल (मंडी मॉडल भाव)" };

export const indexLevel = (index: number): Level => (index < 0.925 ? "low" : index <= 1.075 ? "medium" : "high");

export function pricingIntel(activity: CatalogActivity, location: LocationCandidate | null): PricingIntel {
  const state = location?.district.state ?? null;
  const base: PricingIntel = {
    confidence: "estimated", sources: [], limitations: [], basis: "unavailable", points: [], targetPrice: null,
    purchasingPowerIndex: null, history: [],
  };
  if (activity.commodity) {
    const series = state ? priceSeries(activity.commodity, state) : null;
    if (series && series.months.length) {
      const recent = series.months.slice(-12).map((m) => m.modal);
      const [low, mid, high] = [25, 50, 75].map((q) => round(percentile(recent, q), 2));
      base.basis = "direct_market_data";
      base.confidence = "real";
      base.history = series.months;
      base.targetPrice = mid;
      base.points = [
        { label: { en: "Typical low (12 months)", hi: "सामान्य कम भाव (12 महीने)" }, low, high: mid, unit: AGMARKNET_UNIT, confidence: "real" },
        { label: { en: "Typical range (12 months)", hi: "सामान्य दायरा (12 महीने)" }, low, high, unit: AGMARKNET_UNIT, confidence: "real" },
      ];
      base.sources.push(src(`Mandi price series for ${activity.commodity}, ${state}: ${series.months.length} months`, `${activity.commodity} का मंडी भाव, ${state}: ${series.months.length} महीने`, "real"));
      if (series.months.length < 12) base.limitations.push(msg("c2.price.shortHistory", { n: series.months.length }));
      base.limitations.push(msg("c2.price.wholesale"));
      if (activity.price_unit && !/quintal/i.test(activity.price_unit)) base.limitations.push(msg("c2.price.unitMismatch", { unit: activity.price_unit }));
      return base;
    }
    base.limitations.push(msg("c2.price.noSeries", { commodity: activity.commodity }));
  } else {
    base.limitations.push(msg("c2.price.noCommodity"));
  }
  const ref = activity.reference_price;
  if (!ref) {
    base.limitations.push(msg("c2.price.unavailable"));
    return base;
  }
  const hit = state ? stateRefEntry(state) : null;
  const index = hit ? STATE_TIER_INDEX[hit[1].purchasing_power] ?? null : null;
  const factor = index ?? 1;
  const low = round(ref.low * factor, 2);
  const high = round(ref.high * factor, 2);
  const mid = round((low + high) / 2, 2);
  base.basis = "purchasing_power_proxy";
  base.purchasingPowerIndex = index;
  base.targetPrice = mid;
  base.points = [
    { label: { en: "Estimated local range", hi: "अनुमानित स्थानीय दायरा" }, low, high, unit: { en: displayUnit(activity.price_unit), hi: catalogHi(activity.price_unit) }, confidence: "estimated" },
    { label: { en: "Estimated target price", hi: "अनुमानित लक्ष्य कीमत" }, low: mid, high: mid, unit: { en: displayUnit(activity.price_unit), hi: catalogHi(activity.price_unit) }, confidence: "estimated" },
  ];
  base.sources.push(src(`Catalog reference price ${ref.low}-${ref.high} (planning assumption)`, `कैटलॉग संदर्भ कीमत ${ref.low}-${ref.high} (योजना अनुमान)`, "estimated"));
  if (hit && index !== null) {
    base.sources.push(src(`State purchasing-power tier: ${hit[0]} ${hit[1].purchasing_power} → ${index}`, `राज्य क्रय-शक्ति स्तर: ${hit[0]} ${hit[1].purchasing_power} → ${index}`, "estimated"));
    base.limitations.push(msg("c2.price.stateTier", { state: hit[0], tier: hit[1].purchasing_power }));
  } else {
    base.limitations.push(msg("c2.price.noState"));
  }
  base.limitations.push(msg("c2.price.estimate"));
  return base;
}

/** Catalog units read "INR per kg"; amounts are already shown with ₹, so drop the currency word. */
function displayUnit(unit: string): string {
  return unit.replace(/^INR\s+/i, "").replace(/,\s*INR\b/i, "");
}
