/** Shared motion tuning and the pure maths behind gestures (unit-tested; no DOM). */

/** Page push/pop spring: near-critically damped, visually settles in ~280–320ms. Units are "page widths". */
export const NAV_SPRING = { type: "spring", stiffness: 420, damping: 42, mass: 1, restDelta: 0.0005, restSpeed: 0.02 } as const;
/** Snappy spring for press feedback. */
export const PRESS_SPRING = { type: "spring", stiffness: 700, damping: 32, mass: 0.6 } as const;
/** Sheet open/close spring. */
export const SHEET_SPRING = { type: "spring", stiffness: 380, damping: 38, mass: 1 } as const;
/** Tab cross-fade (tween: short and non-bouncy). */
export const TAB_FADE = { duration: 0.2, ease: [0.2, 0.8, 0.2, 1] } as const;

/** How far (as % of width) the page underneath shifts left while another page covers it. */
export const PARALLAX_PCT = 28;
/** Max dim applied to the page underneath. */
export const UNDER_DIM = 0.16;
/** Width of the left edge that starts a swipe-back, in CSS px. */
export const EDGE_PX = 24;

/** Layer position → translateX. pos 0 = resting on top, 1 = off-screen right, -1 = parallaxed underneath. */
export const layerX = (pos: number): string => (pos >= 0 ? `${pos * 100}%` : `${pos * PARALLAX_PCT}%`);
export const layerDim = (pos: number): number => (pos < 0 ? Math.min(1, -pos) * UNDER_DIM : 0);
/** Edge shadow of a page that is sliding over another (fades as it leaves). */
export const layerShadow = (pos: number): number => (pos > 0 && pos < 1 ? 1 - pos : 0);

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/**
 * Decide whether a released swipe-back completes (pops) or springs back.
 * `dx` is the finger travel in px, `vx` its release velocity in px/s, `width` the page width.
 */
export function swipeCompletes(dx: number, vx: number, width: number): boolean {
  if (width <= 0) return false;
  const progress = dx / width;
  if (vx < -250) return false; // flicked back towards the edge
  if (vx > 550 && progress > 0.05) return true; // quick flick
  return progress > 0.4;
}

/** Decide whether a released sheet drag dismisses the sheet. `dy` px downwards, `vy` px/s, `height` of the sheet. */
export function sheetDismisses(dy: number, vy: number, height: number): boolean {
  if (vy < -200) return false;
  if (vy > 600 && dy > 8) return true;
  return dy > Math.min(160, Math.max(60, height * 0.3));
}

/** Velocity (px/s) from recent pointer samples, ignoring samples older than `windowMs`. */
export function releaseVelocity(samples: { x: number; t: number }[], windowMs = 100): number {
  if (samples.length < 2) return 0;
  const last = samples[samples.length - 1];
  let first = samples[0];
  for (let i = samples.length - 2; i >= 0; i--) {
    first = samples[i];
    if (last.t - samples[i].t > windowMs) break;
  }
  const dt = last.t - first.t;
  return dt > 0 ? ((last.x - first.x) / dt) * 1000 : 0;
}
