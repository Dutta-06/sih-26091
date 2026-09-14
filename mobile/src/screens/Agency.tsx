import { AlertTriangle, Shuffle, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { cachedPortfolio, COHORT_CAPITAL_RANGE, computePortfolioChunked, DISBURSED_SHARE, type PortfolioMetrics } from "../core/portfolio";
import { district } from "../core/pack";
import { useI18n } from "../i18n";
import { ratio, rupees, rupeesShort } from "../lib/format";
import { BarChart } from "../ui/charts";
import { Badge, Card, cx, IconBubble, Note, Progress, Reveal, Screen, Section, Skeleton, Stat } from "../ui";
import { activityLabel, useLifecycle } from "./g4/model";
import { OutcomeLearning } from "./w4/AgencyLearning";

const num = new Intl.NumberFormat("en-IN");
const FLAGGED_SHOWN = 5;

function usePortfolio(today: string) {
  const [metrics, setMetrics] = useState<PortfolioMetrics | null>(() => cachedPortfolio(today));
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    const hit = cachedPortfolio(today);
    if (hit) {
      setMetrics(hit);
      return;
    }
    setMetrics(null);
    const signal = { cancelled: false };
    computePortfolioChunked(today, (done, total) => setProgress(done / total), signal).then((m) => m && setMetrics(m));
    return () => {
      signal.cancelled = true;
    };
  }, [today]);
  return { metrics, progress };
}

export default function Agency() {
  const { t, pick, lang } = useI18n();
  const { lc } = useLifecycle();
  const { metrics: m, progress } = usePortfolio(lc.today);

  const disclosure = (
    <Reveal>
      <div className="mt-2">
        <Badge tone="info" icon={Users}>{t("u4.agency.synthetic")}</Badge>
      </div>
    </Reveal>
  );

  if (!m) {
    return (
      <Screen title={t("agency.title")} subtitle={t("u4.agency.subtitleLoading")}>
        {disclosure}
        <Card tone="azure" className="mt-3">
          <p className="text-[13px] text-azure-100">{t("u4.agency.computing", { pct: Math.round(progress * 100) })}</p>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/20">
            <div className="h-full rounded-full bg-marigold-500 transition-[width]" style={{ width: `${progress * 100}%` }} />
          </div>
        </Card>
        <div className="mt-3 grid gap-3">
          <Skeleton rounded="card" className="h-24 w-full" />
          <Skeleton rounded="card" className="h-40 w-full" />
          <Skeleton rounded="card" className="h-56 w-full" />
        </div>
      </Screen>
    );
  }

  const pipeline = [
    { key: "viable", value: m.byClass.viable, tone: "azure" as const },
    { key: "redirected", value: m.byClass.redirected, tone: "marigold" as const },
    { key: "no_option", value: m.byClass.no_option, tone: "clay" as const },
  ];
  const DOT = { azure: "bg-azure-600", marigold: "bg-marigold-500", clay: "bg-clay-600" };
  const maxDistrict = Math.max(1, ...m.districts.map((d) => d.total));

  return (
    <Screen title={t("agency.title")} subtitle={t("u4.agency.subtitle", { n: m.total, d: m.districts.length })}>
      {disclosure}
      <Reveal>
        <Card tone="azure" className="mt-3 grid grid-cols-2 gap-x-4 gap-y-4">
          <Stat tone="light" label={t("u4.agency.applicants")} value={num.format(m.total)} />
          <Stat tone="light" label={t("u4.agency.loanVolume")} value={rupeesShort(m.loanVolume, lang)} />
          <Stat tone="light" label={t("u4.agency.avgCoverage")} value={m.avgCoverage === null ? "—" : ratio(m.avgCoverage)} />
          <Stat tone="light" label={t("u4.agency.warningRate")} value={m.warningRate === null ? "—" : `${Math.round(m.warningRate * 100)}%`} hint={t("u4.agency.warningRateHint", { w: m.warned, n: m.monitored })} />
        </Card>
      </Reveal>

      <Reveal i={1}>
        <Card tone="marigold" className="mt-3">
          <div className="flex items-start gap-3">
            <IconBubble icon={Shuffle} tone="marigold" />
            <div className="min-w-0">
              <p className="tabular text-2xl font-bold text-azure-950">{num.format(m.byClass.redirected)}</p>
              <p className="text-[15px] font-semibold leading-snug">{t("u4.agency.redirected")}</p>
              <p className="mt-1 text-[13px] leading-snug text-ink-2">{t("u4.agency.redirected.sub")}</p>
            </div>
          </div>
        </Card>
      </Reveal>

      <Section title={t("u4.agency.pipeline")}>
        <Reveal i={2}>
          <Card>
            <BarChart data={pipeline.map((p) => ({ label: t(`u4.agency.class.${p.key}`), value: p.value, tone: p.tone }))} height={120} />
            <div className="mt-3 grid gap-2">
              {pipeline.map((p) => (
                <div key={p.key} className="flex items-center gap-2 text-[13px]">
                  <span className={cx("size-2.5 shrink-0 rounded-full", DOT[p.tone])} />
                  <span className="min-w-0 text-ink-2">{t(`u4.agency.class.${p.key}`)}</span>
                  <span className="tabular ml-auto font-semibold">{p.value}</span>
                </div>
              ))}
            </div>
          </Card>
        </Reveal>
      </Section>

      {m.flagged.length > 0 && (
        <Section title={t("u4.agency.flagged", { n: m.warned })}>
          <Reveal i={3}>
            <Card className="divide-y divide-line py-1">
              {m.flagged.slice(0, FLAGGED_SHOWN).map((f) => {
                const act = activityLabel(f.selected);
                const d = district(f.districtId);
                return (
                  <div key={f.id} className="flex min-h-16 items-center gap-3 py-2.5">
                    <span className="grid size-10 shrink-0 place-items-center rounded-full bg-clay-100 text-lg">{act.emoji}</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[15px] font-medium">
                        {pick(act.name)} · {d ? pick(d.name) : f.districtId}
                      </p>
                      <p className="flex items-center gap-1 text-[13px] leading-snug text-clay-700">
                        <AlertTriangle className="size-3.5 shrink-0" />
                        <span className="truncate">{t("u4.agency.flaggedRow", { id: f.id, months: f.monitoredMonths })}</span>
                      </p>
                    </div>
                    {f.worstScore !== null && (
                      <span className="shrink-0 text-right">
                        <span className="tabular block text-[15px] font-bold text-clay-700">{Math.round(f.worstScore)}</span>
                        {f.latestScore !== null && <span className="tabular block text-[11px] text-ink-3">{t("u4.agency.nowScore", { n: Math.round(f.latestScore) })}</span>}
                      </span>
                    )}
                  </div>
                );
              })}
            </Card>
          </Reveal>
        </Section>
      )}

      <Section title={t("agency.districts")}>
        <Reveal i={4}>
          <Card>
            <div className="grid gap-3">
              {m.districts.map((d) => {
                const info = district(d.id);
                return (
                  <div key={d.id}>
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="min-w-0 text-[15px] font-medium">
                        {info ? pick(info.name) : d.id} <span className="text-[13px] font-normal text-ink-3">· {t("agency.casesN", { n: d.total })}</span>
                      </p>
                      <span className="tabular shrink-0 text-[13px] font-semibold">{rupeesShort(d.loan, lang)}</span>
                    </div>
                    <div className="mt-1.5 flex h-2 overflow-hidden rounded-full bg-line" style={{ width: `${(d.total / maxDistrict) * 100}%` }}>
                      <div className="h-full bg-azure-600" style={{ width: `${(d.viable / d.total) * 100}%` }} />
                      <div className="h-full bg-marigold-500" style={{ width: `${(d.redirected / d.total) * 100}%` }} />
                      <div className="h-full bg-clay-600" style={{ width: `${(d.noOption / d.total) * 100}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-3 text-xs leading-snug text-ink-3">{t("u4.agency.districtsNote")}</p>
          </Card>
        </Reveal>
      </Section>

      <Reveal i={5}>
        <Card className="mt-3">
          <p className="text-[15px] font-semibold">{t("u4.agency.monitoring")}</p>
          <p className="mt-1 text-[13px] leading-snug text-ink-3">{t("u4.agency.monitoring.sub", { disbursed: m.disbursed, monitored: m.monitored, health: m.avgHealth === null ? "—" : Math.round(m.avgHealth) })}</p>
          {m.disbursed > 0 && <Progress value={(m.warned / Math.max(1, m.monitored)) * 100} tone="clay" className="mt-3" />}
        </Card>
      </Reveal>

      <Reveal i={6}>
        <OutcomeLearning />
      </Reveal>

      <div className="mt-4 grid gap-2">
        <Note tone="sand">{t("u4.agency.method", { n: m.total, lo: rupees(COHORT_CAPITAL_RANGE[0]), hi: rupees(COHORT_CAPITAL_RANGE[1]), share: Math.round(DISBURSED_SHARE * 100) })}</Note>
        <Note tone="azure">{t("agency.note")}</Note>
      </div>
    </Screen>
  );
}
