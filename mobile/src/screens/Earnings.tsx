import { LANG_INFO } from "../i18n";
import { Calculator, MessageCircleHeart, Scale } from "lucide-react";
import { Fragment } from "react";
import { useI18n } from "../i18n";
import { catalogEntry, PRICE_FACTOR_BOUNDS, REACH_FACTOR_BOUNDS, REFERENCE_CONSUMER_BASE } from "../core/financial";
import type { EarningsStep } from "../core/types";
import { dscr, quarterFactors } from "../engine/finance";
import { ratio, rupees } from "../lib/format";
import { useNav } from "../nav";
import { useCase } from "../state/store";
import { Badge, Button, Card, Note, Reveal, Screen, Section } from "../ui";
import { RulesChip } from "./g3/bits";
import { seasonView } from "./g3/model";
import { activityDisplay, coverageTone } from "./g3/util";
import { Rows, SeasonBars, StepCard } from "./w3/EarningsSteps";

const f2 = (v: number) => `${v.toFixed(2)}×`;
const num = new Intl.NumberFormat("en-IN");

/** "How we estimated your earnings": the core's earnings build-up (financial.earnings), step by step (TDD 6.2). */
export default function Earnings() {
  const { t, pick, tm, lang } = useI18n();
  const view = useCase();
  const { switchTab } = useNav();
  const { activityId, financial, intel } = view;

  if (!activityId || !financial) {
    return (
      <Screen title={t("earn.title")}>
        <Card tone="marigold" className="mt-2">
          <p className="text-[17px] font-semibold">{t("g3.earn.empty.title")}</p>
          <p className="mt-1 text-[15px] leading-snug text-ink-2">{t("g3.earn.empty.body")}</p>
          <Button size="md" className="mt-3" icon={Calculator} onClick={() => switchTab("plan")}>
            {t("g3.earn.empty.cta")}
          </Button>
        </Card>
      </Screen>
    );
  }

  const act = activityDisplay(activityId);
  const entry = catalogEntry(activityId);
  const { preview, plan, earnings } = financial;
  const season = seasonView(view);
  const inst = plan.regularInstallment;
  const drop = preview.breakEvenDropPct;
  const monthName = new Intl.DateTimeFormat(LANG_INFO[lang].dateLocale, { month: "long", timeZone: "UTC" });
  const months = (idx: number[]) => idx.map((m) => monthName.format(new Date(Date.UTC(2000, m, 1)))).join(", ");

  // Shown-only adjustments: the last applied=false value is the "more hopeful" local figure.
  const adjustedStep = [...earnings].reverse().find((s) => !s.applied);
  const adjustedDscr = adjustedStep && plan.eligible ? dscr((adjustedStep.value * entry.operating_margin) / 4, inst) : null;
  const ref = entry.reference_price;
  const refMid = ref ? (ref.low + ref.high) / 2 : null;
  const consumers = intel?.marketReach.consumerBase ?? null;
  const bestMonths = season ? season.values.map((v, i) => [v, i] as const).sort((a, b) => b[0] - a[0]).slice(0, 3).map(([, i]) => i).sort((a, b) => a - b) : [];

  const render = (s: EarningsStep, i: number) => {
    const common = { i, n: i + 1, confidence: s.confidence };
    const tag = (
      <span className="mt-1.5 inline-block">
        <Badge tone={s.applied ? "good" : "info"}>{t(s.applied ? "g3.earn.applied" : "g3.earn.shownOnly")}</Badge>
      </span>
    );
    switch (s.id) {
      case "project":
        return (
          <StepCard {...common} title={t("earn.s1.title")} value={rupees(s.value)} explain={t("earn.s1.explain", { v: rupees(plan.capital) })}>
            {tag}
          </StepCard>
        );
      case "base":
        return (
          <StepCard {...common} title={t("earn.s2.title")} value={t("earn.perYear", { v: rupees(s.value) })} explain={t("earn.s2.explain", { r: s.factor ?? 0 })}>
            <Rows rows={[[t("earn.s2.ratio"), f2(s.factor ?? 0)], [t("earn.s2.calc"), `${rupees(plan.projectCost)} × ${s.factor}`]]} />
            {tag}
          </StepCard>
        );
      case "pricing":
        return (
          <StepCard
            {...common}
            title={t("earn.s3.title")}
            value={f2(s.factor ?? 1)}
            explain={t((s.factor ?? 1) < 1 ? "g3.earn.pricingLow" : "g3.earn.pricingHigh")}
          >
            <Rows
              rows={[
                [t("g3.earn.targetPrice"), intel?.pricing.targetPrice != null ? rupees(intel.pricing.targetPrice) : "—"],
                [t("earn.s3.ref"), ref ? `${rupees(ref.low)}–${rupees(ref.high)}` : "—"],
                [t("earn.s3.mid"), intel?.pricing.targetPrice != null && refMid ? `${rupees(intel.pricing.targetPrice)} ÷ ${rupees(refMid)}` : "—"],
                [t("g3.earn.bounds", { lo: PRICE_FACTOR_BOUNDS[0], hi: PRICE_FACTOR_BOUNDS[1] }), t(s.factor === PRICE_FACTOR_BOUNDS[0] || s.factor === PRICE_FACTOR_BOUNDS[1] ? "earn.capped" : "earn.withinBound")],
                [t("g3.earn.ifUsed"), t("earn.perYear", { v: rupees(s.value) })],
              ]}
            />
            {tag}
          </StepCard>
        );
      case "reach":
        return (
          <StepCard {...common} title={t("earn.s4.title")} value={f2(s.factor ?? 1)} explain={t("g3.earn.reachExplain", { n: consumers != null ? num.format(consumers) : "—", lo: REACH_FACTOR_BOUNDS[0], hi: REACH_FACTOR_BOUNDS[1] })}>
            <Rows
              rows={[
                [t("earn.s4.customers"), consumers != null ? num.format(consumers) : "—"],
                [t("earn.s4.formula"), consumers != null ? `√(${num.format(consumers)} ÷ ${num.format(REFERENCE_CONSUMER_BASE)}) = ${Math.sqrt(Math.max(consumers, 0) / REFERENCE_CONSUMER_BASE).toFixed(2)}` : "—"],
                [t("g3.earn.bounds", { lo: REACH_FACTOR_BOUNDS[0], hi: REACH_FACTOR_BOUNDS[1] }), t(s.factor === REACH_FACTOR_BOUNDS[0] || s.factor === REACH_FACTOR_BOUNDS[1] ? "earn.capped" : "earn.withinBound")],
                [t("g3.earn.ifUsed"), t("earn.perYear", { v: rupees(s.value) })],
              ]}
            />
            {tag}
          </StepCard>
        );
      case "surplus":
        return (
          <StepCard {...common} title={t("earn.s5.title")} value={t("earn.perQuarter", { v: rupees(preview.quarterlySurplus) })} explain={t("g3.earn.surplusExplain", { m: Math.round((s.factor ?? 0) * 100) })}>
            <Rows rows={[[t("g3.earn.perYearKept"), rupees(s.value)], [t("earn.s5.calc"), `${rupees(preview.annualRevenue)} × ${Math.round((s.factor ?? 0) * 100)}% ÷ 4`]]} />
            {tag}
          </StepCard>
        );
      case "coverage":
        return (
          <StepCard {...common} title={t("earn.s6.title")} value={ratio(s.value)} explain={drop !== null && drop > 0 ? t("earn.s6.safety", { p: drop.toFixed(0) }) : t("earn.s6.short")}>
            <Rows
              rows={[
                [t("earn.s6.surplus"), rupees(preview.quarterlySurplus)],
                [t("earn.s6.inst"), rupees(inst)],
                [t("earn.s6.band"), <Badge key="b" tone={coverageTone(s.value)}>{t(`earn.band.${coverageTone(s.value)}`)}</Badge>],
              ]}
            />
            {tag}
          </StepCard>
        );
      case "seasons":
        return (
          <StepCard {...common} title={t("earn.s7.title")} value={ratio(s.value)} explain={t("g3.earn.seasonsExplain", { n: season?.low.length ?? 0 })}>
            {season && (
              <>
                <SeasonBars values={season.values} low={season.low} />
                <div className="mt-3 grid grid-cols-4 gap-1.5 text-center">
                  {quarterFactors(season.values).map((q, qi) => (
                    <div key={qi} className="rounded-xl bg-sand px-1 py-1.5">
                      <p className="text-[11px] text-ink-3">Q{qi + 1}</p>
                      <p className={q < 1 ? "tabular text-[13px] font-bold text-clay-700" : "tabular text-[13px] font-bold"}>{f2(q)}</p>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-[12px] text-ink-3">{t(season.basis === "price_history" ? "g3.earn.basis.price_history" : "g3.earn.basis.catalog_profile")}</p>
              </>
            )}
            {tag}
          </StepCard>
        );
    }
  };

  return (
    <Screen title={t("earn.title")} subtitle={`${act.emoji} ${pick(act.name)}`}>
      <Card tone="azure" className="mt-2">
        <p className="text-sm text-azure-100">{t("earn.hero.label")}</p>
        <p className="tabular text-[34px] leading-tight font-bold">{rupees(preview.annualRevenue)}</p>
        <p className="text-[13px] text-azure-100">{t("earn.hero.sub", { surplus: rupees(preview.quarterlySurplus) })}</p>
        <div className="mt-2">
          <RulesChip light />
        </div>
      </Card>

      {financial.limitations.length > 0 && (
        <div className="mt-4 space-y-2">
          {financial.limitations.map((l) => (
            <Note key={l.key} tone={l.key === "c3.fin.lim.outside_scheme" || l.key === "c3.fin.lim.no_capital" ? "clay" : "sand"}>
              {tm(l)}
            </Note>
          ))}
        </div>
      )}

      <Section title={t("earn.steps")}>
        <div className="space-y-3">{earnings.map((s, i) => <Fragment key={s.id}>{render(s, i)}</Fragment>)}</div>
      </Section>

      {plan.eligible && preview.baseDscr !== null && (
        <Section title={t("earn.used.title")}>
          <Reveal>
            <Card tone="sand">
              <div className="flex items-center gap-2">
                <Scale className="size-5 text-azure-700" />
                <p className="text-[15px] font-semibold">{t("earn.used.head")}</p>
              </div>
              <Rows
                rows={[
                  [t("earn.used.base"), `${rupees(preview.annualRevenue)} · ${ratio(preview.baseDscr)}`],
                  [t("earn.used.adjusted"), adjustedStep && adjustedDscr !== null ? `${rupees(adjustedStep.value)} · ${ratio(adjustedDscr)}` : "—"],
                ]}
              />
              <p className="mt-2.5 text-[13px] leading-snug text-ink-2">{t("earn.used.body")}</p>
            </Card>
          </Reveal>
        </Section>
      )}

      <Section title={t("earn.friend.title")}>
        <Card>
          <div className="flex items-center gap-2">
            <MessageCircleHeart className="size-5 text-marigold-600" />
            <Badge tone="warn">{t("earn.friend.badge")}</Badge>
          </div>
          <p className="mt-2 text-[15px] leading-relaxed text-ink-2">
            {plan.eligible
              ? t("g3.earn.friend.p1", { sales: rupees(preview.annualRevenue / 12), keep: rupees(preview.quarterlySurplus), inst: rupees(inst) })
              : t("g3.earn.friend.noLoan", { sales: rupees(preview.annualRevenue / 12), keep: rupees(preview.quarterlySurplus) })}{" "}
            {plan.eligible && (drop !== null && drop > 0 ? t("earn.friend.p2", { p: drop.toFixed(0) }) : t("earn.friend.p2short"))}{" "}
            {season && season.low.length > 0 && bestMonths.length > 0 ? t("g3.earn.friend.p3", { slow: months(season.low), best: months(bestMonths) }) : ""}
          </p>
        </Card>
      </Section>

    </Screen>
  );
}
