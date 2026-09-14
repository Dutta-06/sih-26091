import type { ReactNode } from "react";
import { LANG_INFO, useI18n } from "../../i18n";
import { cx, ConfidenceBadge, Card, Reveal } from "../../ui";

/** One numbered step of the earnings build-up. */
export function StepCard({ n, title, value, confidence, explain, children, i }: { n: number; title: string; value: ReactNode; confidence: "real" | "estimated"; explain: string; children?: ReactNode; i: number }) {
  return (
    <Reveal i={i}>
      <Card>
        <div className="flex items-start gap-3">
          <span className="tabular grid size-8 shrink-0 place-items-center rounded-full bg-azure-100 text-sm font-bold text-azure-800">{n}</span>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <p className="text-[15px] leading-snug font-semibold">{title}</p>
              <ConfidenceBadge value={confidence} />
            </div>
            <p className="tabular mt-1 text-[22px] leading-tight font-bold text-azure-800">{value}</p>
            <p className="mt-1 text-[13px] leading-snug text-ink-2">{explain}</p>
            {children}
          </div>
        </div>
      </Card>
    </Reveal>
  );
}

/** Label / value rows used inside a step. */
export function Rows({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="mt-2.5 divide-y divide-line rounded-xl bg-sand/60 px-3 text-[13px]">
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-baseline justify-between gap-3 py-1.5">
          <dt className="text-ink-3">{k}</dt>
          <dd className="tabular text-right font-semibold">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** 12-month seasonal profile with below-average months highlighted. */
export function SeasonBars({ values, low }: { values: number[]; low: number[] }) {
  const { t, lang } = useI18n();
  const max = Math.max(...values) * 1.08;
  // Twelve columns leave room for about two characters; fall back to the platform's narrow month names
  const narrow = new Intl.DateTimeFormat(LANG_INFO[lang].dateLocale, { month: "narrow", timeZone: "UTC" });
  const monthLabel = (i: number) => {
    const label = t(`earn.month.${i}`);
    return [...label].length > 2 ? narrow.format(Date.UTC(2024, i, 15)) : label;
  };
  const H = 110;
  return (
    <div className="mt-3">
      <div className="relative flex items-end gap-1" style={{ height: H }}>
        <div className="absolute inset-x-0 border-t border-dashed border-ink-3/50" style={{ bottom: (1 / max) * H }} />
        {values.map((v, i) => {
          const isLow = low.includes(i);
          return (
            <div key={i} className="flex h-full flex-1 flex-col items-center justify-end">
              <div className={cx("w-full rounded-t-md", isLow ? "bg-clay-600" : "bg-azure-600")} style={{ height: (v / max) * H }} />
            </div>
          );
        })}
      </div>
      <div className="mt-1 flex gap-1 text-center text-[10px] text-ink-3">
        {values.map((_, i) => (
          <span key={i} className={cx("min-w-0 flex-1 overflow-hidden", low.includes(i) && "font-semibold text-clay-700")}>
            {monthLabel(i)}
          </span>
        ))}
      </div>
    </div>
  );
}
