import { catalogBi } from "./catalogHi";
import type { Bi } from "../i18n";
/**
 * Pooled procurement (Module 3, after module3_monitoring/procurement_coordinator.py).
 *
 * The phone has no cross-case enrolment store, so the pool counts the POTENTIAL peer pool the backend reports
 * alongside enrolment: same-activity enterprises within the market radius — Module 1 competitor POIs when
 * available, else pack POIs matching the catalog OSM tags. A pool is ready at settings.procurement_min_peers = 3.
 *
 * Discount tier rule (indicative bulk-purchase saving on pooled key inputs):
 *   < 3 peers → 0% (not ready) · 3–5 → 8% · 6–9 → 12% · ≥ 10 → 15%.
 */
import { catalogEntry } from "./financial";
import { poisNear } from "./pack";
import type { Confidence, Intel, LocationCandidate, Msg } from "./types";

export const PROCUREMENT_MIN_PEERS = 3;
export const DEFAULT_RADIUS_KM = 10;

export function discountFor(peers: number): number {
  if (peers >= 10) return 15;
  if (peers >= 6) return 12;
  if (peers >= PROCUREMENT_MIN_PEERS) return 8;
  return 0;
}

export interface Pool {
  peers: number;
  target: number;
  items: (Bi | string)[];
  discountPct: number;
  ready: boolean;
  confidence: Confidence;
  source: "competitor_intel" | "pack_pois" | "none";
  limitations: Msg[];
}

export function pool(activityId: string, location: LocationCandidate | null, intel: Intel | null): Pool {
  const act = catalogEntry(activityId);
  const limitations: Msg[] = [{ key: "c3.pool.potential_only" }];
  let peers = 0;
  let source: Pool["source"] = "none";
  const comp = intel?.competitor;
  if (comp && comp.nearby.length > 0) {
    peers = comp.nearby.length;
    source = "competitor_intel";
  } else if (location) {
    const radius = intel?.marketReach.radiusKm ?? DEFAULT_RADIUS_KM;
    const tags = new Set(act.osm_tags.map(([k, v]) => `${k}=${v}`));
    peers = poisNear(location.lat, location.lon, radius, (p) => p.tags.some(([k, v]) => tags.has(`${k}=${v}`))).length;
    source = "pack_pois";
  } else {
    limitations.push({ key: "c3.pool.no_location" });
  }
  return {
    peers,
    target: PROCUREMENT_MIN_PEERS,
    items: act.key_inputs.map(catalogBi),
    discountPct: discountFor(peers),
    ready: peers >= PROCUREMENT_MIN_PEERS,
    confidence: source === "none" ? "estimated" : source === "competitor_intel" ? comp!.confidence : "real",
    source,
    limitations,
  };
}
