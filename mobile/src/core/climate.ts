/**
 * Rainfall climate at the case location, fetched online from Open-Meteo (ERA5 reanalysis, no key; lib/online.ts) and
 * kept in the case state, so the analysis stays deterministic and works offline once fetched.
 *
 * Summary over ten calendar years of daily precipitation:
 *  - monsoonShare: share of the yearly rain falling in June–September;
 *  - dryMonths: months whose average rain is under 10 mm;
 *  - yearToYearCv: coefficient of variation of the yearly totals (how much one year differs from the next).
 */
export interface ClimateSummary {
  lat: number;
  lon: number;
  years: string; // e.g. "2016–2025"
  monthlyMm: number[]; // 12 average monthly totals
  annualMm: number;
  monsoonShare: number;
  dryMonths: number;
  yearToYearCv: number;
  fetchedOn: string; // YYYY-MM-DD
}

/** Cache key: the 0.25° ERA5 cell of a point. */
export const climateKey = (lat: number, lon: number) => `${(Math.round(lat * 4) / 4).toFixed(2)},${(Math.round(lon * 4) / 4).toFixed(2)}`;

let current: Record<string, ClimateSummary> = {};

/** Make the fetched climates of the case available to the analysis (called by computeCase). */
export function useClimates(map: Record<string, ClimateSummary> | undefined): void {
  current = map ?? {};
}

export const climateAt = (lat: number, lon: number): ClimateSummary | null => current[climateKey(lat, lon)] ?? null;

const r2 = (v: number) => Math.round(v * 100) / 100;

/** Summarise Open-Meteo archive daily precipitation (dates YYYY-MM-DD, mm) into a ClimateSummary. */
export function summariseDaily(lat: number, lon: number, dates: string[], mm: (number | null)[], fetchedOn: string): ClimateSummary | null {
  const byYearMonth = new Map<string, number>();
  const years = new Set<string>();
  dates.forEach((d, i) => {
    const v = mm[i];
    if (v === null || v === undefined) return;
    const key = d.slice(0, 7);
    byYearMonth.set(key, (byYearMonth.get(key) ?? 0) + v);
    years.add(d.slice(0, 4));
  });
  const yearList = [...years].sort();
  if (yearList.length < 3) return null;
  const monthly = Array.from({ length: 12 }, (_, m) => {
    const vals = yearList.map((y) => byYearMonth.get(`${y}-${String(m + 1).padStart(2, "0")}`)).filter((v): v is number => v !== undefined);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
  });
  const annual = monthly.reduce((a, b) => a + b, 0);
  const totals = yearList.map((y) => Array.from({ length: 12 }, (_, m) => byYearMonth.get(`${y}-${String(m + 1).padStart(2, "0")}`) ?? 0).reduce((a, b) => a + b, 0));
  const mean = totals.reduce((a, b) => a + b, 0) / totals.length;
  const sd = Math.sqrt(totals.reduce((a, v) => a + (v - mean) ** 2, 0) / totals.length);
  return {
    lat, lon, years: `${yearList[0]}–${yearList[yearList.length - 1]}`,
    monthlyMm: monthly.map((v) => Math.round(v)),
    annualMm: Math.round(annual),
    monsoonShare: annual > 0 ? r2((monthly[5] + monthly[6] + monthly[7] + monthly[8]) / annual) : 0,
    dryMonths: monthly.filter((v) => v < 10).length,
    yearToYearCv: mean > 0 ? r2(sd / mean) : 0,
    fetchedOn,
  };
}

/** Rain-fed activities for which rainfall concentration and year-to-year swings are a business risk. */
export const RAIN_SENSITIVE = new Set(["dairy_farming", "goat_rearing", "poultry_backyard", "poultry_layer", "fisheries_pond", "beekeeping", "agri_input_depot", "flour_mill", "mustard_oil_mill"]);

/** Severity of rainfall risk for a rain-fed activity. */
export function rainRisk(c: ClimateSummary): "low" | "medium" | "high" {
  let level = c.monsoonShare >= 0.8 || c.dryMonths >= 6 ? 2 : c.monsoonShare >= 0.65 || c.dryMonths >= 4 ? 1 : 0;
  if (c.yearToYearCv >= 0.25) level = Math.min(2, level + 1);
  return (["low", "medium", "high"] as const)[level];
}
