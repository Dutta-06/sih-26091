import { ACTIVITIES } from "../../data/activities";
import { catalogEntry } from "../../core/financial";
import { coverageBand } from "../../engine/finance";
import type { Bi } from "../../i18n";

/** 0.065 → "6.5%", 0.08 → "8%". */
export const ratePct = (rate: number) => `${Number((rate * 100).toFixed(2))}%`;

/** Display name/emoji for a catalog activity (display copy), falling back to the catalog category. */
export function activityDisplay(id: string): { name: Bi | string; emoji: string; nic: string; category: string } {
  const entry = catalogEntry(id);
  const d = ACTIVITIES[id];
  return { name: d?.name ?? entry.category, emoji: d?.emoji ?? "🏪", nic: entry.nic_class, category: entry.category };
}

export type Tone = "good" | "warn" | "risk";
const BAND_TONE = { does_not_cover: "risk", thin: "warn", comfortable: "good" } as const;
/** Tone from the engine's coverage band (same thresholds as the plan). */
export const coverageTone = (v: number): Tone => BAND_TONE[coverageBand(v)];
