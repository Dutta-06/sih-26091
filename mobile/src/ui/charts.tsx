/**
 * Lightweight SVG charts (no chart library; renders offline and animates on mount).
 * Geometry is computed once per data change (useMemo); animations use transform/opacity/stroke-dash only.
 */
import { motion } from "motion/react";
import { memo, useId, useMemo } from "react";

export interface BarDatum {
  label: string;
  value: number;
  /** optional second stacked segment drawn on top */
  stack?: number;
  tone?: "azure" | "marigold" | "clay" | "sand";
  highlight?: boolean;
}

const FILL = { azure: "#0e9bb3", marigold: "#F2A516", clay: "#C2410C", sand: "#C5D7DB" };
const EASE = [0.16, 1, 0.3, 1] as const;

export const BarChart = memo(function BarChart({
  data,
  height = 140,
  formatValue,
  showLabels = true,
  maxLabels = 8,
}: {
  data: BarDatum[];
  height?: number;
  formatValue?: (v: number) => string;
  showLabels?: boolean;
  maxLabels?: number;
}) {
  const bars = useMemo(() => {
    const max = Math.max(1, ...data.map((d) => d.value + (d.stack ?? 0)));
    const w = 100 / Math.max(1, data.length);
    return data.map((d, i) => {
      const h = (d.value / max) * (height - 4);
      const hs = ((d.stack ?? 0) / max) * (height - 4);
      const bw = w * 0.64;
      return { x: i * w + w * 0.18, bw, h, hs, fill: FILL[d.tone ?? "azure"], dim: d.highlight === false, title: formatValue ? formatValue(d.value) : undefined };
    });
  }, [data, height, formatValue]);
  const every = Math.max(1, Math.ceil(data.length / maxLabels));
  const n = Math.max(1, data.length);

  return (
    <div>
      <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" className="w-full" style={{ height }}>
        {bars.map((b, i) => (
          <g key={i}>
            <motion.rect
              x={b.x}
              y={height - b.h}
              width={b.bw}
              height={b.h}
              rx={Math.min(1.2, b.bw / 3)}
              fill={b.fill}
              opacity={b.dim ? 0.45 : 1}
              style={{ transformBox: "fill-box", originY: 1 }}
              initial={{ scaleY: 0 }}
              animate={{ scaleY: 1 }}
              transition={{ delay: Math.min(0.25, (i / n) * 0.25), duration: 0.5, ease: EASE }}
            >
              {b.title && <title>{b.title}</title>}
            </motion.rect>
            {b.hs > 0 && (
              <motion.rect
                x={b.x}
                y={height - b.h - b.hs}
                width={b.bw}
                height={b.hs}
                fill={FILL.marigold}
                style={{ transformBox: "fill-box", originY: 1 }}
                initial={{ scaleY: 0 }}
                animate={{ scaleY: 1 }}
                transition={{ delay: 0.2 + Math.min(0.25, (i / n) * 0.25), duration: 0.45, ease: EASE }}
              />
            )}
          </g>
        ))}
      </svg>
      {showLabels && (
        <div className="mt-1.5 flex text-[10px] text-ink-3">
          {data.map((d, i) => (
            <span key={i} className="tabular flex-1 text-center">
              {i % every === 0 ? d.label : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  );
});

/** Actual vs planned line chart with a shaded actual area. */
export const PlanVsActual = memo(function PlanVsActual({
  actual,
  planned,
  labels,
  height = 150,
  warnFrom,
}: {
  actual: number[];
  planned: number[];
  labels: string[];
  height?: number;
  warnFrom?: number;
}) {
  const W = 300;
  const gradId = `actualFill-${useId().replace(/:/g, "")}`;
  const geo = useMemo(() => {
    const max = Math.max(1e-9, ...actual, ...planned) * 1.1;
    const count = Math.max(actual.length, planned.length);
    const x = (i: number) => (count > 1 ? (i / (count - 1)) * (W - 16) + 8 : W / 2);
    const y = (v: number) => height - 8 - (v / max) * (height - 20);
    const line = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ");
    const actualLine = line(actual);
    return {
      x,
      actualLine,
      plannedLine: line(planned),
      area: actual.length ? `${actualLine} L${x(actual.length - 1)},${height} L${x(0)},${height} Z` : "",
      dots: actual.map((v, i) => ({ cx: x(i), cy: y(v), warn: warnFrom !== undefined && i >= warnFrom })),
    };
  }, [actual, planned, height, warnFrom]);

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full" style={{ height }}>
        <defs>
          <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#0e9bb3" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#0e9bb3" stopOpacity="0" />
          </linearGradient>
        </defs>
        {warnFrom !== undefined && <rect x={geo.x(warnFrom) - 10} y={0} width={W - geo.x(warnFrom) + 10} height={height} fill="#FDE3D3" opacity={0.55} rx={6} />}
        {geo.area && <motion.path d={geo.area} fill={`url(#${gradId})`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6 }} />}
        <path d={geo.plannedLine} fill="none" stroke="#7F9297" strokeWidth={2} strokeDasharray="5 5" />
        <motion.path
          d={geo.actualLine}
          fill="none"
          stroke="#0A8AA0"
          strokeWidth={3}
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.9, ease: "easeInOut" }}
        />
        {geo.dots.map((d, i) => (
          <circle key={i} cx={d.cx} cy={d.cy} r={3.5} fill={d.warn ? "#C2410C" : "#0A8AA0"} stroke="white" strokeWidth={1.5} />
        ))}
      </svg>
      <div className="mt-1 flex justify-between px-1 text-[10px] text-ink-3">
        {labels.map((l, i) => (
          <span key={i}>{l}</span>
        ))}
      </div>
    </div>
  );
});

/** Semi-circular gauge for coverage ratios (DSCR). 0 → 2.0×, bands at 1.0 and 1.25. */
export const CoverageGauge = memo(function CoverageGauge({ value, size = 180 }: { value: number; size?: number }) {
  const clamped = Math.max(0, Math.min(2, Number.isFinite(value) ? value : 2));
  const r = size / 2 - 14;
  const cx = size / 2;
  const cy = size / 2;
  const bands = useMemo(() => {
    const arc = (from: number, to: number) => {
      const a0 = Math.PI * (1 - from / 2);
      const a1 = Math.PI * (1 - to / 2);
      return `M${cx + r * Math.cos(a0)},${cy - r * Math.sin(a0)} A${r},${r} 0 0 1 ${cx + r * Math.cos(a1)},${cy - r * Math.sin(a1)}`;
    };
    return { low: arc(0, 1), mid: arc(1, 1.25), high: arc(1.25, 2) };
  }, [cx, cy, r]);
  // Needle is drawn pointing right and rotated about the hub (transform only, no attribute tweening).
  const deg = -180 * (1 - clamped / 2);
  const len = r - 18;
  return (
    <svg viewBox={`0 0 ${size} ${size / 2 + 12}`} className="w-full" style={{ maxWidth: size }}>
      <path d={bands.low} stroke="#F7C6A8" strokeWidth={14} fill="none" strokeLinecap="round" />
      <path d={bands.mid} stroke="#FBDC9C" strokeWidth={14} fill="none" />
      <path d={bands.high} stroke="#B3E3EA" strokeWidth={14} fill="none" strokeLinecap="round" />
      <motion.g style={{ transformBox: "fill-box", originX: 0.5, originY: 0.5 }} initial={{ rotate: -180 }} animate={{ rotate: deg }} transition={{ type: "spring", stiffness: 60, damping: 12 }}>
        {/* invisible counterweight keeps the group's box centred on the hub */}
        <line x1={cx - len} y1={cy} x2={cx} y2={cy} stroke="transparent" strokeWidth={4} />
        <line x1={cx} y1={cy} x2={cx + len} y2={cy} stroke="#00596A" strokeWidth={4} strokeLinecap="round" />
      </motion.g>
      <circle cx={cx} cy={cy} r={7} fill="#00596A" />
    </svg>
  );
});
