import { AlertTriangle, ArrowDownLeft, ArrowUpRight, CheckCircle2, ChevronRight, Clock, FlaskConical, Gauge, Hourglass, Landmark, Lock, PauseCircle, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";
import { useState } from "react";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useNav } from "../nav";
import { PlanVsActual } from "../ui/charts";
import { Badge, Button, Card, cx, IconBubble, ListRow, Note, Progress, Reveal, Ring, Screen, Section, Stat } from "../ui";
import { ConsentCard } from "./g4/Consent";
import { BAND_TONE, consentLog, dateLabel, monthLabel, pctOfPlan, RING_TONE, STATUS_TONE, useLifecycle } from "./g4/model";

const CHART_MONTHS = 6;
const TX_PAGE = 15;

export default function Monitoring() {
  const { t, lang } = useI18n();
  const { state, view, lc } = useLifecycle();
  const { push, switchTab } = useNav();
  const [showAll, setShowAll] = useState(false);

  const manage = (
    <button onClick={() => push({ name: "privacy" })} className="mx-auto mt-4 flex min-h-11 items-center gap-1.5 text-[15px] font-semibold text-azure-700">
      <ShieldCheck className="size-4.5" />
      {t("w4.monitoring.manage")}
    </button>
  );

  if (!state.smsConsent) {
    const log = consentLog(state);
    const last = log[log.length - 1];
    const paused = !!last && !last.granted;
    return (
      <Screen title={t("monitoring.title")}>
        <Reveal>
          <div className="mt-6 grid place-items-center text-center">
            <IconBubble icon={paused ? PauseCircle : Lock} tone={paused ? "marigold" : "sand"} size="lg" />
            <p className="mt-3 text-lg font-semibold">{t(paused ? "w4.monitoring.paused.title" : "monitoring.off.title")}</p>
            <p className="mt-1 max-w-72 text-[15px] leading-snug text-ink-3">{paused ? t("w4.monitoring.paused.body", { date: dateLabel(last.at, lang) }) : t("monitoring.off.body")}</p>
            {state.dataDeletedOn && <p className="mt-2 max-w-72 text-[13px] leading-snug text-clay-700">{t("u4.monitoring.deletedOn", { date: dateLabel(state.dataDeletedOn, lang) })}</p>}
          </div>
        </Reveal>
        <Reveal i={1} className="mt-6">
          <ConsentCard />
        </Reveal>
        {manage}
      </Screen>
    );
  }

  if (!view.health.length) {
    const disbursed = state.appStage === "disbursed";
    return (
      <Screen title={t("monitoring.title")} subtitle={t("monitoring.subtitle")}>
        <Reveal>
          <div className="mt-8 grid place-items-center text-center">
            <IconBubble icon={Hourglass} tone="sky" size="lg" />
            <p className="mt-3 text-lg font-semibold">{t(disbursed ? "u4.monitoring.noData.title" : "u4.monitoring.notDisbursed.title")}</p>
            <p className="mt-1 max-w-80 text-[15px] leading-snug text-ink-3">
              {disbursed ? (state.dataDeletedOn ? t("u4.monitoring.noData.afterDelete", { date: dateLabel(state.dataDeletedOn, lang) }) : t("u4.monitoring.noData.body")) : t("u4.monitoring.notDisbursed.body")}
            </p>
            {disbursed ? (
              <Button className="mt-5" variant="secondary" icon={Clock} onClick={() => switchTab("more")}>
                {t("u4.presenter.advance")}
              </Button>
            ) : (
              <Button className="mt-5" variant="secondary" onClick={() => push({ name: "application" })}>
                {t("business.locked.cta")}
              </Button>
            )}
          </div>
        </Reveal>
        {manage}
      </Screen>
    );
  }

  const { latest, previous, warning, current, done } = lc;
  const trend = latest?.score != null && previous?.score != null ? Math.round(latest.score) - Math.round(previous.score) : null;
  const chart = done.slice(-CHART_MONTHS);
  const warnIdx = warning ? chart.findIndex((h) => h.month === warning.month) : -1;
  const shown = latest ?? current!;
  const txns = [...view.transactions].sort((a, b) => b.at.localeCompare(a.at));
  const visible = showAll ? txns : txns.slice(0, TX_PAGE);

  return (
    <Screen title={t("monitoring.title")} subtitle={t("monitoring.subtitle")}>
      <Reveal>
        <Card className="mt-2">
          {latest?.score != null && latest.band ? (
            <div className="flex items-center gap-4">
              <Ring value={Math.round(latest.score)} tone={RING_TONE[latest.band]} sub="/100" />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] text-ink-3">{t("u4.monitoring.healthFor", { month: monthLabel(latest.month, lang) })}</p>
                <div className="mt-1">
                  <Badge tone={BAND_TONE[latest.band]}>{t(`u4.band.${latest.band}`)}</Badge>
                </div>
                {trend !== null && (
                  <p className={cx("mt-2 flex items-center gap-1 text-[13px] font-medium", trend >= 0 ? "text-azure-700" : "text-clay-700")}>
                    {trend >= 0 ? <TrendingUp className="size-4 shrink-0" /> : <TrendingDown className="size-4 shrink-0" />}
                    {t(trend > 0 ? "u4.health.up" : trend < 0 ? "u4.health.down" : "u4.health.flat", { from: Math.round(previous!.score!), to: Math.round(latest.score), month: monthLabel(latest.month, lang) })}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <IconBubble icon={Hourglass} tone="sky" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-semibold">{t("u4.health.waiting.title")}</p>
                <p className="text-[13px] leading-snug text-ink-3">{latest ? t("u4.monitoring.noScore") : t("u4.health.waiting.body")}</p>
              </div>
            </div>
          )}
          {latest && latest.reasons.length > 0 && latest.score !== null && (
            <ul className="mt-3 space-y-1 text-[13px] leading-snug text-clay-700">
              {latest.reasons.map((r, i) => (
                <li key={i} className="flex gap-1.5">
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                  <ReasonText msg={r} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </Reveal>

      {warning && (
        <Reveal i={1}>
          <Card tone={lc.acted ? "sand" : "clay"} className="mt-3" onClick={() => push({ name: "warning" })}>
            <div className="flex items-center gap-3">
              <IconBubble icon={lc.acted ? CheckCircle2 : AlertTriangle} tone={lc.acted ? "azure" : "clay"} />
              <div className="min-w-0 flex-1">
                <p className={cx("text-[15px] font-semibold", lc.acted ? "text-ink" : "text-clay-700")}>{t("u4.warning.headline", { month: monthLabel(warning.month, lang), pct: pctOfPlan(warning) ?? "—" })}</p>
                <p className={cx("text-[13px]", lc.acted ? "text-ink-3" : "text-clay-700/80")}>
                  {lc.acted && state.interventionChosen ? t("u4.monitoring.acted", { step: t(`u4.intervention.${state.interventionChosen.type}`) }) : t("monitoring.warning.cta")}
                </p>
              </div>
              <ChevronRight className="size-5 text-ink-3" />
            </div>
          </Card>
        </Reveal>
      )}

      <Section title={t("monitoring.chart.title")}>
        <Reveal i={2}>
          <Card>
            {chart.length >= 2 ? (
              <>
                <PlanVsActual
                  actual={chart.map((m) => m.revenue)}
                  planned={chart.map((m) => m.planned)}
                  labels={chart.map((m) => monthLabel(m.month, lang, "short"))}
                  warnFrom={warnIdx === chart.length - 1 ? warnIdx : undefined}
                />
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
                  <span className="flex items-center gap-1.5"><span className="h-1 w-4 rounded-full bg-azure-700" />{t("monitoring.chart.actual")}</span>
                  <span className="flex items-center gap-1.5"><span className="h-0 w-4 border-t-2 border-dashed border-ink-3" />{t("monitoring.chart.planned")}</span>
                </div>
              </>
            ) : (
              <p className="text-[13px] leading-snug text-ink-3">{t("u4.monitoring.chartWait", { n: done.length })}</p>
            )}
            {current && <p className="mt-2 text-xs leading-snug text-ink-3">{t("u4.monitoring.partial", { month: monthLabel(current.month, lang) })}</p>}
          </Card>
        </Reveal>
      </Section>

      <Section title={latest ? monthLabel(latest.month, lang) : t("monitoring.thisMonth", { month: monthLabel(shown.month, lang) })}>
        <Reveal i={3}>
          <Card>
            <div className="grid grid-cols-3 gap-3">
              <Stat label={t("monitoring.revenue")} value={rupees(shown.revenue)} hint={pctOfPlan(shown) !== null && latest ? t("u4.monitoring.ofPlan", { pct: pctOfPlan(shown)! }) : undefined} />
              <Stat label={t("monitoring.expenses")} value={rupees(shown.expenses)} />
              <Stat label={t("monitoring.surplus")} value={rupees(shown.surplus)} tone={shown.surplus >= 0 ? "azure" : "ink"} />
            </div>
            {latest && current && (
              <p className="mt-3 rounded-xl bg-sand px-3 py-2 text-[13px] leading-snug text-ink-2">
                {t("u4.monitoring.sofarLine", { month: monthLabel(current.month, lang), revenue: rupees(current.revenue), expenses: rupees(current.expenses), n: current.transactions })}
              </p>
            )}
          </Card>
        </Reveal>
      </Section>

      {latest && view.financial?.plan.eligible && (
        <Reveal i={4}>
          <Card className="mt-3">
            <div className="flex items-start gap-3">
              <IconBubble icon={Landmark} tone="marigold" size="sm" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-semibold">{t("u4.monitoring.repayment")}</p>
                <p className="mt-0.5 text-[13px] leading-snug text-ink-2">
                  {latest.installmentDue > 0 ? t("u4.monitoring.dueShare", { amount: rupees(latest.installmentDue), surplus: rupees(latest.surplus) }) : t("u4.monitoring.nothingDue")}
                </p>
              </div>
              <Badge tone={STATUS_TONE[latest.status]}>{t(`u4.status.${latest.status}`)}</Badge>
            </div>
            <p className="mt-2 text-[11px] font-medium text-azure-700">{t("business.rulesCue")}</p>
          </Card>
        </Reveal>
      )}

      {latest && (
        <Reveal i={5}>
          <Card className="mt-3">
            <div className="flex items-center gap-3">
              <IconBubble icon={Gauge} tone="sky" size="sm" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-semibold">{t("monitoring.credit")}</p>
                <p className="text-xs text-marigold-600">{t("monitoring.credit.label")}</p>
              </div>
              {latest.creditIndex !== null && (
                <p className="tabular text-xl font-bold">
                  {Math.round(latest.creditIndex)}
                  <span className="text-sm font-medium text-ink-3">/100</span>
                </p>
              )}
            </div>
            {latest.creditIndex !== null ? <Progress value={latest.creditIndex} className="mt-3" /> : null}
            <p className="mt-2 text-xs leading-snug text-ink-3">{latest.creditIndex !== null ? t("u4.monitoring.creditHint") : t("u4.monitoring.creditNone")}</p>
          </Card>
        </Reveal>
      )}

      <Section title={t("u4.monitoring.tx.title", { n: txns.length })}>
        <Card className="divide-y divide-line py-1">
          {visible.map((tx, i) => {
            const credit = tx.direction === "credit";
            return (
              <ListRow
                key={`${tx.at}-${i}`}
                icon={credit ? ArrowDownLeft : ArrowUpRight}
                tone={credit ? "azure" : tx.isLoanRepayment ? "marigold" : "sand"}
                title={tx.isLoanRepayment ? t("u4.tx.loan") : t(credit ? "u4.tx.in" : "u4.tx.out", { channel: t(`u4.channel.${tx.channel}`) })}
                subtitle={dateLabel(tx.at, lang)}
                right={<span className={cx("tabular text-[15px] font-semibold", credit ? "text-azure-700" : "text-ink-2")}>{credit ? "+" : "−"}{rupees(tx.amount)}</span>}
              />
            );
          })}
        </Card>
        {txns.length > TX_PAGE && (
          <Button variant="ghost" size="md" className="mt-2 w-full" onClick={() => setShowAll((v) => !v)}>
            {showAll ? t("u4.tx.less") : t("u4.tx.all", { n: txns.length })}
          </Button>
        )}
        <div className="mt-3 grid gap-2">
          <Note tone="azure">{t("u4.monitoring.parsedNote")}</Note>
          <Note tone="marigold" icon={FlaskConical}>{t("u4.monitoring.sampleInbox", { kind: t(`u4.inbox.${state.inbox}`) })}</Note>
        </div>
        <Button variant="ghost" size="md" icon={Clock} className="mt-2 w-full" onClick={() => switchTab("more")}>
          {t("u4.presenter.advance")}
        </Button>
        {manage}
      </Section>
    </Screen>
  );
}

function ReasonText({ msg }: { msg: { key: string; vars?: Record<string, unknown> } }) {
  const { tm } = useI18n();
  return <span>{tm(msg)}</span>;
}
