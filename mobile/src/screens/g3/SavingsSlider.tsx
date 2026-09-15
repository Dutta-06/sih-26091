import { useRef, type KeyboardEvent } from "react";
import { MARGIN_SHARE, TERM_MAX_PROJECT } from "../../engine/finance";
import { clamp } from "../../lib/format";
import { cx } from "../../ui";

export const SLIDER_MIN = 5_000;
export const SLIDER_MAX = 600_000;
const SPAN = Math.log(SLIDER_MAX / SLIDER_MIN);
const LIMIT = TERM_MAX_PROJECT * MARGIN_SHARE;

const stepOf = (v: number) => (v < 20_000 ? 500 : v < 100_000 ? 1_000 : v < 300_000 ? 5_000 : 10_000);
const snap = (v: number) => clamp(Math.round(v / stepOf(v)) * stepOf(v), SLIDER_MIN, SLIDER_MAX);
const toPos = (v: number) => clamp(Math.log(v / SLIDER_MIN) / SPAN, 0, 1);
const fromPos = (p: number) => snap(SLIDER_MIN * Math.exp(clamp(p, 0, 1) * SPAN));

export interface SliderMark {
  value: number;
  label: string;
}

/** Large logarithmic savings slider (₹5,000 → ₹6,00,000) with tier markers. */
export function SavingsSlider({ value, onChange, label, marks, minLabel, maxLabel }: { value: number; onChange: (v: number) => void; label: string; marks: SliderMark[]; minLabel: string; maxLabel: string }) {
  const track = useRef<HTMLDivElement>(null);
  const pos = toPos(value) * 100;
  const outside = value > LIMIT;

  const update = (clientX: number) => {
    const r = track.current?.getBoundingClientRect();
    if (!r || r.width === 0) return;
    const v = fromPos((clientX - r.left) / r.width);
    if (v !== value) onChange(v);
  };
  const onKey = (e: KeyboardEvent) => {
    const delta = e.key === "ArrowRight" || e.key === "ArrowUp" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowDown" ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    onChange(clamp(value + delta * stepOf(delta < 0 ? value - 1 : value), SLIDER_MIN, SLIDER_MAX));
  };

  return (
    <div className="px-3">
      <div className="relative h-5 text-[10px] font-medium text-ink-3">
        {marks.map((m) => {
          const p = toPos(m.value) * 100;
          return (
            <span key={m.value} className="absolute top-0 whitespace-nowrap" style={{ left: `${p}%`, transform: `translateX(${p > 80 ? "-100%" : "-50%"})` }}>
              {m.label}
            </span>
          );
        })}
      </div>
      <div
        ref={track}
        role="slider"
        tabIndex={0}
        aria-label={label}
        aria-valuemin={SLIDER_MIN}
        aria-valuemax={SLIDER_MAX}
        aria-valuenow={value}
        onKeyDown={onKey}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          update(e.clientX);
        }}
        onPointerMove={(e) => {
          if (e.currentTarget.hasPointerCapture(e.pointerId)) update(e.clientX);
        }}
        className="relative h-12 cursor-pointer touch-none outline-none"
      >
        <div className="absolute inset-x-0 top-1/2 h-3 -mt-1.5 overflow-hidden rounded-full bg-ink-3/15">
          <div className="absolute inset-y-0 right-0 bg-clay-100" style={{ left: `${toPos(LIMIT) * 100}%` }} />
          <div className={cx("absolute inset-y-0 left-0 rounded-full transition-colors", outside ? "bg-clay-600" : "bg-azure-600")} style={{ width: `${pos}%` }} />
        </div>
        {marks.map((m) => (
          <span key={m.value} className="absolute top-1/2 -mt-3 h-6 w-0.5 rounded bg-ink-3/40" style={{ left: `${toPos(m.value) * 100}%` }} />
        ))}
        <span
          className={cx("absolute top-1/2 -mt-4 -ml-4 size-8 rounded-full bg-white shadow-[var(--shadow-float)] ring-4 transition-transform active:scale-110", outside ? "ring-clay-600" : "ring-azure-600")}
          style={{ left: `${pos}%` }}
        />
      </div>
      <div className="tabular flex justify-between text-[11px] text-ink-3">
        <span>{minLabel}</span>
        <span>{maxLabel}</span>
      </div>
    </div>
  );
}
