import type { Lang } from "../i18n";

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** ₹1,20,000 (Indian digit grouping). */
export const rupees = (value: number) => `₹${inr.format(Math.round(value))}`;

/** Compact Indian units: ₹12K, ₹1.2 L, ₹4.5 Cr (Hindi: ₹1.2 लाख). */
export function rupeesShort(value: number, lang: Lang = "en") {
  const abs = Math.abs(value);
  const trim = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(n < 10 ? 2 : 1).replace(/\.?0+$/, ""));
  if (abs >= 1e7) return `₹${trim(value / 1e7)} ${lang === "hi" ? "करोड़" : "Cr"}`;
  if (abs >= 1e5) return `₹${trim(value / 1e5)} ${lang === "hi" ? "लाख" : "L"}`;
  if (abs >= 1e3) return `₹${trim(value / 1e3)}${lang === "hi" ? " हज़ार" : "K"}`;
  return `₹${Math.round(value)}`;
}

export const pct = (value: number, digits = 0) => `${value.toFixed(digits)}%`;

export const ratio = (value: number) => (Number.isFinite(value) ? `${value.toFixed(2)}×` : "—");

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
