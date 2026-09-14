import { motion } from "motion/react";
import type { ScoreBreakdown } from "../../core/types";
import { useI18n } from "../../i18n";
import { cx } from "../../ui";

/** Maximum points per component, as documented in core/discovery.ts (the ranking rule, not a result). */
export const COMPONENT_MAX: Record<keyof ScoreBreakdown, number> = { capitalFit: 20, repayment: 30, skills: 20, localDemand: 20, outcomes: 10 };
export const COMPONENTS = Object.keys(COMPONENT_MAX) as (keyof ScoreBreakdown)[];

export const COMPONENT_COLOR: Record<keyof ScoreBreakdown, string> = {
  capitalFit: "bg-forest-800",
  repayment: "bg-forest-500",
  skills: "bg-sky-700",
  localDemand: "bg-marigold-500",
  outcomes: "bg-forest-200",
};

/** Stacked breakdown bar: each segment's width is its points out of 100. */
export function ScoreBar({ parts, muted }: { parts: ScoreBreakdown; muted?: boolean }) {
  return (
    <div className={cx("flex h-2.5 overflow-hidden rounded-full bg-ink-3/15", muted && "grayscale")}>
      {COMPONENTS.map((c, i) => (
        <motion.div
          key={c}
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(0, parts[c])}%` }}
          transition={{ duration: 0.6, delay: 0.05 * i, ease: "easeOut" }}
          className={cx("h-full border-r border-white last:border-r-0", COMPONENT_COLOR[c])}
        />
      ))}
    </div>
  );
}

export function ScoreLegend() {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1.5">
      {COMPONENTS.map((c) => (
        <span key={c} className="flex items-center gap-1.5 text-xs text-ink-2">
          <span className={cx("size-2.5 rounded-full", COMPONENT_COLOR[c])} />
          {t(`shortlist.c.${c}`)} <span className="tabular text-ink-3">/{COMPONENT_MAX[c]}</span>
        </span>
      ))}
    </div>
  );
}
