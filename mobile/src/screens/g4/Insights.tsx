import { ArrowDownLeft, ArrowUpRight, Copy, PauseCircle, Sparkles, TrendingDown } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import type { Anomaly, AnomalyKind } from "../../core/anomalies";
import type { Forecast } from "../../core/forecast";
import type { Msg } from "../../core/types";
import { useI18n, type Lang } from "../../i18n";
import { rupees } from "../../lib/format";
import { Badge, Button, Card, ConfidenceBadge, cx, IconBubble, Progress } from "../../ui";
import { ForecastChart } from "../../ui/charts";
import { dateLabel, monthLabel } from "./model";

const HISTORY_SHOWN = 4;

/** Month-valued vars (YYYY-MM) and rupee amounts formatted for display before translation. */
function localize(msg: Msg, lang: Lang): Msg {
  const vars = Object.fromEntries(
    Object.entries(msg.vars ?? {}).map(([k, v]) => [
      k,
      k === "month" && typeof v === "string" ? monthLabel(v, lang) : ["amount", "usual", "actual", "expected"].includes(k) && typeof v === "number" ? rupees(v) : v,
    ]),
  );
  return { ...msg, vars };
}

/** Next three months learned from this business's own months (core/forecast). */
export function ForecastCard({ forecast, history }: { forecast: Forecast; history: { month: string; revenue: number }[] }) {
  const { t, tm, lang } = useI18n();
  const [how, setHow] = useState(false);
  const recent = history.slice(-HISTORY_SHOWN);
  const next = forecast.months[0];
  const inst = forecast.installment;
  const chance = inst ? Math.round(inst.chance * 100) : null;
  const tone = chance === null ? "azure" : chance >= 75 ? "azure" : chance >= 45 ? "marigold" : "clay";

  return (
    <Card>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[15px] font-semibold">
            <Sparkles className="size-4 shrink-0 text-azure-700" />
            {t("u4.fc.title")}
          </p>
          <p className="text-[12px] text-ink-3">{t("u4.fc.basedOn", { n: forecast.basedOn })}</p>
        </div>
        <ConfidenceBadge value="estimated" />
      </div>

      <ForecastChart
        actual={recent.map((h) => h.revenue)}
        forecast={forecast.months.map((m) => ({ mid: m.sales, low: m.low, high: m.high }))}
        labels={[...recent.map((h) => monthLabel(h.month, lang, "short")), ...forecast.months.map((m) => monthLabel(m.month, lang, "short"))]}
      />
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
        <span className="flex items-center gap-1.5"><span className="h-1 w-4 rounded-full bg-azure-700" />{t("monitoring.chart.actual")}</span>
        <span className="flex items-center gap-1.5"><span className="h-0 w-4 border-t-2 border-dashed border-azure-900" />{t("u4.fc.legend.forecast")}</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-azure-600/20" />{t("u4.fc.legend.range")}</span>
      </div>

      <div className="mt-3 rounded-xl bg-sand/70 px-3 py-2.5">
        <p className="text-[13px] text-ink-3">{t("u4.fc.nextMonth", { month: monthLabel(next.month, lang) })}</p>
        <p className="tabular text-[20px] leading-tight font-bold text-azure-800">{rupees(next.sales)}</p>
        <p className="tabular text-[12px] text-ink-2">{t("u4.fc.range", { low: rupees(next.low), high: rupees(next.high) })}</p>
      </div>

      {inst && chance !== null && (
        <div className="mt-3">
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-[14px] font-semibold">{t("u4.fc.installment", { amount: rupees(inst.amount), month: monthLabel(inst.month, lang) })}</p>
            <p className={cx("tabular shrink-0 text-lg font-bold", tone === "azure" ? "text-azure-700" : tone === "marigold" ? "text-marigold-600" : "text-clay-700")}>{chance}%</p>
          </div>
          <Progress value={chance} tone={tone} className="mt-1.5" />
          <p className="mt-1.5 text-[12px] leading-snug text-ink-3">{t(chance >= 75 ? "u4.fc.chance.good" : chance >= 45 ? "u4.fc.chance.mid" : "u4.fc.chance.low", { surplus: rupees(inst.expectedSurplus) })}</p>
        </div>
      )}

      <ul className="mt-3 space-y-1.5 border-t border-line pt-3 text-[13px] leading-snug text-ink-2">
        {forecast.reasons.map((r, i) => (
          <li key={i} className="flex gap-2">
            <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-azure-600" />
            <span>{tm(localize(r, lang))}</span>
          </li>
        ))}
      </ul>

      <button onClick={() => setHow((v) => !v)} className="mt-2 min-h-10 text-[13px] font-semibold text-azure-700">
        {t(how ? "u4.fc.how.hide" : "u4.fc.how.show")}
      </button>
      {how && (
        <div className="rounded-xl bg-azure-50 p-3 text-[12px] leading-snug text-azure-900">
          <p>{t("u4.fc.how.body")}</p>
          <p className="mt-1.5 font-semibold">
            {forecast.backtestError !== null ? t("u4.fc.accuracy", { pct: Math.round(forecast.backtestError * 100), n: forecast.backtests }) : t("u4.fc.accuracy.none")}
          </p>
        </div>
      )}
    </Card>
  );
}

const ICON: Record<AnomalyKind, LucideIcon> = {
  duplicate_debit: Copy,
  large_debit: ArrowUpRight,
  large_credit: ArrowDownLeft,
  sales_gap: PauseCircle,
  sales_slowdown: TrendingDown,
};

/** Findings from core/anomalies, newest first, each with its evidence and a suggested check. */
export function UnusualActivity({ anomalies, limit = 5 }: { anomalies: Anomaly[]; limit?: number }) {
  const { t, lang } = useI18n();
  const [all, setAll] = useState(false);
  const shown = all ? anomalies : anomalies.slice(0, limit);
  if (!anomalies.length) {
    return (
      <Card>
        <div className="flex items-center gap-3">
          <IconBubble icon={Sparkles} tone="azure" size="sm" />
          <p className="text-[14px] leading-snug text-ink-2">{t("u4.anomaly.none")}</p>
        </div>
      </Card>
    );
  }
  return (
    <>
      <Card className="divide-y divide-line py-1">
        {shown.map((a, i) => {
          const vars = localize({ key: "", vars: a.vars }, lang).vars ?? {};
          return (
            <div key={`${a.kind}-${a.at}-${i}`} className="flex gap-3 py-3">
              <IconBubble icon={ICON[a.kind]} tone={a.severity === "high" ? "clay" : "marigold"} size="sm" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <p className="text-[15px] font-semibold">{t(`u4.anomaly.${a.kind}.title`)}</p>
                  <Badge tone={a.severity === "high" ? "risk" : "warn"}>{t(`u4.anomaly.severity.${a.severity}`)}</Badge>
                </div>
                <p className="mt-0.5 text-[13px] leading-snug text-ink-2">
                  {t(`u4.anomaly.${a.kind}.body${a.kind === "sales_gap" && a.vars.open ? "Open" : ""}`, { ...vars, date: dateLabel(a.at, lang) })}
                </p>
                <p className="mt-1 text-[12px] leading-snug font-medium text-azure-800">{t(`u4.anomaly.${a.kind}.action`)}</p>
              </div>
            </div>
          );
        })}
      </Card>
      {anomalies.length > limit && (
        <Button variant="ghost" size="md" className="mt-2 w-full" onClick={() => setAll((v) => !v)}>
          {all ? t("u4.tx.less") : t("u4.anomaly.all", { n: anomalies.length })}
        </Button>
      )}
      <p className="mt-2 text-[11px] leading-snug text-ink-3">{t("u4.anomaly.how")}</p>
    </>
  );
}
