/** Animated number: tweens between values by writing text directly (no React re-render per frame). */
import { animate, useReducedMotion } from "motion/react";
import { useEffect, useLayoutEffect, useRef } from "react";

export const defaultCountFormat = (n: number) => Math.round(n).toLocaleString("en-IN");

export function CountUp({
  value,
  format = defaultCountFormat,
  duration = 0.7,
  from,
  className,
}: {
  value: number;
  /** formatting callback applied every frame (e.g. rupees) */
  format?: (n: number) => string;
  duration?: number;
  /** start value on first mount (default 0; pass `value` to skip the mount animation) */
  from?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const shown = useRef(from ?? 0);
  const fmt = useRef(format);
  fmt.current = format;
  const reduced = useReducedMotion();
  const safe = Number.isFinite(value) ? value : 0;

  // Keep the text right when only the formatter changes (e.g. language switch).
  useLayoutEffect(() => {
    if (ref.current) ref.current.textContent = fmt.current(shown.current);
  });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced || shown.current === safe) {
      shown.current = safe;
      el.textContent = fmt.current(safe);
      return;
    }
    const controls = animate(shown.current, safe, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => {
        shown.current = v;
        el.textContent = fmt.current(v);
      },
    });
    return () => controls.stop();
  }, [safe, duration, reduced]);

  return (
    // text is owned by the effects above (set before first paint) so React never fights the per-frame writes
    <span ref={ref} className={className ? `tabular ${className}` : "tabular"} />
  );
}
