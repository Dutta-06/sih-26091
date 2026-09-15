/**
 * Classical multiplicative seasonal decomposition — port of risk_agent.seasonal_decomposition (the pandas path used
 * when statsmodels is absent; both give the same factors):
 *   series by month (price > 0, last value per month wins) → reindex to a continuous monthly range →
 *   linear interpolation filling at most 2 consecutive missing months per gap → drop remaining gaps →
 *   centred 2×12 moving average trend → ratio = price / trend → mean ratio per calendar month → normalise to mean 1.
 */
export interface MonthlyPrice {
  month: string; // YYYY-MM
  modal: number;
}

const toIdx = (m: string) => {
  const [y, mo] = m.split("-").map(Number);
  return y * 12 + (mo - 1);
};

export function seasonalDecomposition(prices: MonthlyPrice[]): number[] | null {
  if (prices.length < 24) return null;
  const byMonth = new Map<number, number>();
  for (const p of prices) if (p.modal > 0) byMonth.set(toIdx(p.month), p.modal);
  if (byMonth.size < 24) return null;
  const keys = [...byMonth.keys()].sort((a, b) => a - b);
  const start = keys[0];
  const n = keys[keys.length - 1] - start + 1;
  const raw: (number | null)[] = Array.from({ length: n }, (_, i) => byMonth.get(start + i) ?? null);
  // pandas Series.interpolate(limit=2): linear between valid neighbours, forward direction, ≤ 2 per gap.
  const filled = [...raw];
  for (let i = 0; i < n; i++) {
    if (raw[i] !== null) continue;
    let j = i;
    while (j < n && raw[j] === null) j++;
    const prev = i - 1;
    if (prev >= 0 && j < n) {
      for (let k = i; k < Math.min(j, i + 2); k++) filled[k] = raw[prev]! + ((raw[j]! - raw[prev]!) * (k - prev)) / (j - prev);
    }
    i = j - 1;
  }
  const s: { idx: number; v: number }[] = [];
  filled.forEach((v, i) => v !== null && s.push({ idx: start + i, v }));
  if (s.length < 24) return null;
  const len = s.length;
  // rolling(12, center=True).mean() at position i covers [i-6, i+5]; rolling(2).mean().shift(-1) averages i and i+1.
  const ma12 = (i: number) => {
    if (i - 6 < 0 || i + 5 >= len) return null;
    let sum = 0;
    for (let k = i - 6; k <= i + 5; k++) sum += s[k].v;
    return sum / 12;
  };
  const sums = new Array(12).fill(0);
  const counts = new Array(12).fill(0);
  for (let i = 0; i < len; i++) {
    const a = ma12(i);
    const b = i + 1 < len ? ma12(i + 1) : null;
    if (a === null || b === null) continue;
    const trend = (a + b) / 2;
    const month = ((s[i].idx % 12) + 12) % 12;
    sums[month] += s[i].v / trend;
    counts[month] += 1;
  }
  if (counts.some((c) => c === 0)) return null;
  const factors = sums.map((sum, m) => sum / counts[m]);
  const mean = factors.reduce((a, b) => a + b, 0) / 12;
  return factors.map((f) => Math.round((f / mean) * 10000) / 10000);
}
