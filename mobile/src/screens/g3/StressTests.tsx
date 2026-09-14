import { Calculator as CalcIcon, CloudRain, Factory, TrendingDown } from "lucide-react";
import { motion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import { MARGIN_SHOCK_PTS, PRICE_DROP_PCT } from "../../core/financial";
import type { FinancialResult } from "../../core/types";
import { coverageBand, type DebtServicePreview } from "../../engine/finance";
import { useI18n } from "../../i18n";
import { ratio, rupees } from "../../lib/format";
import { CoverageGauge } from "../../ui/charts";
import { Badge, Card, IconBubble, Reveal, cx } from "../../ui";
import { RulesChip } from "./bits";
import { coverageTone } from "./util";

const ICONS: Record<FinancialResult["scenarios"][number]["id"], LucideIcon> = { low_season: CloudRain, price_drop: TrendingDown, input_cost: Factory };

const BUBBLE = { good: "azure", warn: "marigold", risk: "clay" } as const;

export function CoverageCard({ preview, onExplain }: { preview: DebtServicePreview; onExplain?: () => void }) {
  const { t } = useI18n();
  const base = preview.baseDscr ?? 0;
  const surplusShort = preview.quarterlySurplus <= 0;
  const tone = coverageTone(base);
  return (
    <Card>
      <div className="flex flex-col items-center text-center">
        <CoverageGauge value={base} size={200} />
        <p className="tabular -mt-1 text-[34px] leading-none font-bold">{ratio(base)}</p>
        <div className="mt-2">
          <Badge tone={tone}>{t(`plan.band.${coverageBand(base)}`)}</Badge>
        </div>
        <p className="mt-3 text-[15px] leading-snug text-ink-2">
          {t("plan.coverage.explain", { surplus: rupees(preview.quarterlySurplus), inst: rupees(preview.plan.regularInstallment) })}
        </p>
        {surplusShort ? (
          <p className="mt-2 text-[13px] font-semibold text-clay-700">{t("g3.plan.zeroSurplus")}</p>
        ) : (
          preview.breakEvenDropPct !== null && (
            <p className="mt-2 text-[13px] text-ink-2">
              {preview.breakEvenDropPct > 0 ? t("earn.s6.safety", { p: preview.breakEvenDropPct.toFixed(0) }) : t("earn.s6.short")}
            </p>
          )
        )}
        <div className="mt-3 flex w-full justify-between px-2 text-[11px] text-ink-3">
          <span>{t("plan.coverage.scaleLow")}</span>
          <span>{t("plan.coverage.scaleMid")}</span>
          <span>{t("plan.coverage.scaleHigh")}</span>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
          <RulesChip />
        </div>
        {onExplain && (
          <button onClick={onExplain} className="mt-2 inline-flex min-h-11 items-center gap-1.5 rounded-full px-3 text-sm font-semibold text-azure-800 underline underline-offset-2 active:bg-azure-50">
            <CalcIcon className="size-4" />
            {t("earn.link")}
          </button>
        )}
      </div>
    </Card>
  );
}

/** The three stress scenarios computed by the core (financial.scenarios). */
export function StressTests({ scenarios }: { scenarios: FinancialResult["scenarios"] }) {
  const { t } = useI18n();
  const season = scenarios.find((s) => s.id === "low_season")?.result ?? null;
  const vars = { p: PRICE_DROP_PCT, m: MARGIN_SHOCK_PTS };
  return (
    <div className="space-y-3">
      {scenarios.map(({ id, result }, i) => {
        const icon = ICONS[id];
        const tone = coverageTone(result.minDscr);
        return (
          <Reveal key={id} i={i}>
            <Card>
              <div className="flex items-start gap-3">
                <IconBubble icon={icon} tone={BUBBLE[tone]} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] font-semibold">{t(`g3.stress.${id}.title`, vars)}</p>
                  <p className="text-[13px] leading-snug text-ink-3">{t(`g3.stress.${id}.desc`, vars)}</p>
                </div>
                <div className="text-right">
                  <p className={cx("tabular text-xl font-bold", tone === "good" ? "text-azure-700" : tone === "warn" ? "text-marigold-600" : "text-clay-600")}>{ratio(result.minDscr)}</p>
                  <p className="text-[11px] text-ink-3">{t("plan.stress.worst")}</p>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-[13px]">
                <div className="rounded-xl bg-sand px-3 py-2">
                  <p className="text-[11px] text-ink-3">{t("plan.stress.deficitLabel")}</p>
                  <p className="font-semibold">{result.deficitQuarters === 0 ? t("plan.stress.noDeficit") : t("plan.stress.deficit", { n: result.deficitQuarters })}</p>
                </div>
                <div className="rounded-xl bg-sand px-3 py-2">
                  <p className="text-[11px] text-ink-3">{t("plan.stress.bufferLabel")}</p>
                  <p className="font-semibold">{result.bufferNeeded === 0 ? t("plan.stress.noBuffer") : t("plan.stress.buffer", { v: rupees(result.bufferNeeded) })}</p>
                </div>
              </div>
              <p className="mt-2.5 text-[13px] leading-snug text-ink-2">{t(`plan.stress.verdict.${tone}`)}</p>
            </Card>
          </Reveal>
        );
      })}
      {season && (
        <Card>
          <p className="text-[15px] font-semibold">{t("plan.quarters.title")}</p>
          <p className="text-[13px] text-ink-3">{t("plan.quarters.sub")}</p>
          <QuarterBars values={season.quarterlyDscr} />
        </Card>
      )}
    </div>
  );
}

function QuarterBars({ values }: { values: number[] }) {
  const { t } = useI18n();
  const max = Math.max(2, ...values.filter(Number.isFinite));
  const h = (v: number) => (Math.max(0, Math.min(Number.isFinite(v) ? v : max, max)) / max) * (H - 20);
  const H = 120;
  return (
    <div className="relative mt-4" style={{ height: H + 36 }}>
      <div className="absolute inset-x-0 border-t border-dashed border-clay-600/60" style={{ top: H - (1 / max) * (H - 20) }}>
        <span className="absolute -top-4 right-0 text-[10px] font-semibold text-clay-600">{t("plan.quarters.line")}</span>
      </div>
      <div className="absolute inset-x-0 top-0 flex items-end justify-around gap-3" style={{ height: H }}>
        {values.map((v, i) => {
          const tone = coverageTone(v);
          return (
            <div key={i} className="flex h-full flex-1 flex-col items-center justify-end">
              <span className="tabular mb-1 text-xs font-bold">{ratio(v)}</span>
              <motion.div
                initial={{ height: 0 }}
                animate={{ height: h(v) }}
                transition={{ delay: i * 0.08, type: "spring", stiffness: 140, damping: 20 }}
                className={cx("w-full max-w-12 rounded-t-lg", tone === "good" ? "bg-azure-600" : tone === "warn" ? "bg-marigold-500" : "bg-clay-600")}
              />
            </div>
          );
        })}
      </div>
      <div className="absolute inset-x-0 flex justify-around gap-3 text-center text-[11px] text-ink-3" style={{ top: H + 6 }}>
        {values.map((_, i) => (
          <span key={i} className="flex-1">
            <span className="block font-semibold text-ink-2">Q{i + 1}</span>
            {t(`plan.quarters.q${i + 1}`)}
          </span>
        ))}
      </div>
    </div>
  );
}
