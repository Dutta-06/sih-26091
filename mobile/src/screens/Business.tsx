import { AlertTriangle, BellRing, CalendarCheck, CalendarClock, ChevronRight, Eye, HeartPulse, Hourglass, LifeBuoy, Lock, Milestone, ShieldCheck, TrendingDown, TrendingUp, Users } from "lucide-react";
import { motion } from "motion/react";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useNav } from "../nav";
import { Badge, Button, Card, cx, IconBubble, ListRow, Progress, Reveal, Ring, Section, TabScreen } from "../ui";
import { ConsentCard } from "./g4/Consent";
import { activityLabel, BAND_TONE, dateLabel, monthLabel, pctOfPlan, RING_TONE, STATUS_TONE, useLifecycle } from "./g4/model";

function Locked() {
  const { t } = useI18n();
  const { push } = useNav();
  const items = [
    { icon: Milestone, key: "roadmap" },
    { icon: HeartPulse, key: "cashflow" },
    { icon: BellRing, key: "warning" },
    { icon: Users, key: "community" },
  ];
  return (
    <TabScreen header={<header className="safe-top px-5 pt-5 pb-1"><h1 className="text-2xl font-bold">{t("nav.business")}</h1></header>}>
      <Reveal>
        <Card tone="azure" className="mt-3 p-5">
          <motion.div initial={{ scale: 0.6, rotate: -12 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 260, damping: 14 }} className="grid size-14 place-items-center rounded-2xl bg-white/15">
            <Lock className="size-7" />
          </motion.div>
          <h2 className="mt-4 text-xl font-bold leading-snug">{t("business.locked.title")}</h2>
          <p className="mt-1.5 text-[15px] leading-snug text-azure-100">{t("business.locked.body")}</p>
        </Card>
      </Reveal>
      <Section title={t("business.locked.unlocks")}>
        <Card className="divide-y divide-line py-1">
          {items.map((it, i) => (
            <Reveal key={it.key} i={i + 1}>
              <ListRow icon={it.icon} title={t(`business.locked.${it.key}`)} subtitle={t(`business.locked.${it.key}.sub`)} right={<Lock className="size-4 text-ink-3" />} />
            </Reveal>
          ))}
        </Card>
      </Section>
      <div className="mt-6 grid gap-2">
        <Button onClick={() => push({ name: "application" })} iconRight={ChevronRight}>
          {t("business.locked.cta")}
        </Button>
        <Button variant="ghost" size="md" icon={Eye} onClick={() => push({ name: "roadmap" })}>
          {t("business.locked.preview")}
        </Button>
      </div>
    </TabScreen>
  );
}

export default function Business() {
  const { t, pick, lang } = useI18n();
  const { state, view, lc } = useLifecycle();
  const { push } = useNav();
  if (state.appStage !== "disbursed") return <Locked />;

  const act = activityLabel(view.activityId);
  const place = view.location.chosen ?? view.location.candidates[0] ?? null;
  const placeName = place ? pick(place.village ?? place.district.name) : state.profile.locationText;
  const total = view.roadmap.length;
  const done = view.roadmap.filter((m) => state.milestonesDone.includes(m.id)).length;
  const { latest, previous, warning, instalment } = lc;
  const plan = view.financial?.plan;

  const header = (
    <header className="safe-top px-5 pt-5 pb-2">
      <p className="text-[13px] text-ink-3">{t("nav.business")}</p>
      <div className="mt-1 flex items-center gap-3">
        <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-white text-2xl shadow-[var(--shadow-card)]">{act.emoji}</span>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-bold leading-tight">{pick(act.name)}</h1>
          <p className="truncate text-[13px] text-ink-3">{placeName}</p>
        </div>
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <Badge tone="good">{t("business.disbursed")}</Badge>
        {state.disbursedOn && <span className="text-xs text-ink-3">{t("u4.business.disbursedOn", { date: dateLabel(state.disbursedOn, lang) })}</span>}
      </div>
    </header>
  );

  const trend = latest?.score != null && previous?.score != null ? Math.round(latest.score) - Math.round(previous.score) : null;

  return (
    <TabScreen header={header}>
      {warning && !lc.acted && (
        <Reveal>
          <Card tone="clay" className="mt-3" onClick={() => push({ name: "warning" })}>
            <div className="flex items-center gap-3">
              <IconBubble icon={AlertTriangle} tone="clay" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-semibold text-clay-700">{t("business.warning.title")}</p>
                <p className="text-[13px] text-clay-700/80">{t("u4.business.warning.body", { month: monthLabel(warning.month, lang), pct: pctOfPlan(warning) ?? "—" })}</p>
              </div>
              <ChevronRight className="size-5 text-clay-700" />
            </div>
          </Card>
        </Reveal>
      )}

      {lc.followUpDue && state.interventionChosen && lc.afterSnap && (
        <Reveal>
          <Card tone="marigold" className="mt-3" onClick={() => push({ name: "outcome" })}>
            <div className="flex items-center gap-3">
              <IconBubble icon={CalendarCheck} tone="marigold" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-semibold">{t("w4.business.followUp.title")}</p>
                <p className="text-[13px] leading-snug text-ink-2">
                  {t("u4.business.followUp.body", { step: t(`u4.intervention.${state.interventionChosen.type}`), month: monthLabel(lc.afterSnap.month, lang) })}
                </p>
              </div>
              <ChevronRight className="size-5 text-ink-3" />
            </div>
          </Card>
        </Reveal>
      )}

      {total > 0 && (
        <Reveal i={1}>
          <Card className="mt-3" onClick={() => push({ name: "roadmap" })}>
            <div className="flex items-center gap-3">
              <IconBubble icon={Milestone} />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-semibold">{t("business.roadmap.title")}</p>
                <p className="text-[13px] text-ink-3">{t("business.roadmap.sub", { done, total })}</p>
              </div>
              <ChevronRight className="size-5 text-ink-3" />
            </div>
            <Progress className="mt-3" value={(done / total) * 100} />
          </Card>
        </Reveal>
      )}

      <Section title={t("business.health.section")}>
        <Reveal i={2}>
          {!state.smsConsent ? (
            <ConsentCard tabRoot />
          ) : latest?.score != null && latest.band ? (
            <Card onClick={() => push({ name: "monitoring" })}>
              <div className="flex items-center gap-4">
                <Ring value={Math.round(latest.score)} tone={RING_TONE[latest.band]} size={84} stroke={9} sub="/100" />
                <div className="min-w-0 flex-1">
                  <Badge tone={BAND_TONE[latest.band]}>{t(`u4.band.${latest.band}`)}</Badge>
                  <p className="mt-1.5 text-[15px] font-semibold">{t("business.health.title")}</p>
                  <p className={cx("flex items-center gap-1 text-[13px]", trend === null ? "text-ink-3" : trend >= 0 ? "text-azure-700" : "text-clay-700")}>
                    {trend !== null && (trend >= 0 ? <TrendingUp className="size-4 shrink-0" /> : <TrendingDown className="size-4 shrink-0" />)}
                    <span className="min-w-0">
                      {trend === null
                        ? t("u4.health.first", { month: monthLabel(latest.month, lang) })
                        : t(trend > 0 ? "u4.health.up" : trend < 0 ? "u4.health.down" : "u4.health.flat", { from: Math.round(previous!.score!), to: Math.round(latest.score), month: monthLabel(latest.month, lang) })}
                    </span>
                  </p>
                </div>
                <ChevronRight className="size-5 text-ink-3" />
              </div>
            </Card>
          ) : (
            <Card onClick={() => push({ name: "monitoring" })}>
              <div className="flex items-center gap-3">
                <IconBubble icon={Hourglass} tone="sky" />
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] font-semibold">{t("u4.health.waiting.title")}</p>
                  <p className="text-[13px] leading-snug text-ink-3">
                    {lc.current ? t("u4.health.waiting.sofar", { amount: rupees(lc.current.revenue), n: lc.current.transactions }) : t("u4.health.waiting.body")}
                  </p>
                </div>
                <ChevronRight className="size-5 text-ink-3" />
              </div>
            </Card>
          )}
        </Reveal>
      </Section>

      <Section title={t("business.instalment.section")}>
        <Reveal i={3}>
          <Card>
            {!instalment || !plan ? (
              <p className="text-[13px] leading-snug text-ink-3">{t("u4.instalment.none")}</p>
            ) : "done" in instalment ? (
              <div className="flex items-center gap-3">
                <IconBubble icon={CalendarCheck} tone="azure" />
                <p className="text-[15px] font-semibold">{t("u4.instalment.allDone", { n: instalment.total })}</p>
              </div>
            ) : (
              <>
                <div className="flex items-start gap-3">
                  <IconBubble icon={CalendarClock} tone="marigold" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] text-ink-3">{t("business.instalment.due", { date: dateLabel(instalment.due, lang) })}</p>
                    <p className="tabular text-2xl font-bold">{rupees(instalment.payment)}</p>
                    <p className="text-[13px] text-ink-3">{t("u4.instalment.quarter", { n: instalment.quarter, total: instalment.total, days: instalment.inDays })}</p>
                  </div>
                  {latest && <Badge tone={STATUS_TONE[latest.status]}>{t(`u4.status.${latest.status}`)}</Badge>}
                </div>
                {instalment.isMoratorium && (
                  <p className="mt-3 rounded-xl bg-sand px-3 py-2 text-[13px] leading-snug text-ink-2">
                    {t("u4.instalment.interestOnly", { months: plan.tier?.moratoriumMonths ?? 0, amount: rupees(plan.regularInstallment) })}
                  </p>
                )}
                {latest && <p className="mt-2 text-xs leading-snug text-ink-3">{t("u4.instalment.statusFrom", { month: monthLabel(latest.month, lang) })}</p>}
              </>
            )}
            <p className="mt-2 text-[11px] font-medium text-azure-700">{t("business.rulesCue")}</p>
          </Card>
        </Reveal>
      </Section>

      <Section title={t("business.support.section")}>
        <Reveal i={4}>
          <Card className="divide-y divide-line py-1">
            <ListRow icon={LifeBuoy} tone="clay" title={t("business.grievance.title")} subtitle={t("u4.business.grievance.sub")} onClick={() => push({ name: "grievance" })} />
            <ListRow icon={Users} tone="sky" title={t("business.community.title")} subtitle={t("u4.business.community.sub")} onClick={() => push({ name: "community" })} />
            <ListRow icon={CalendarCheck} tone="marigold" title={t("w4.outcome.title")} subtitle={t("w4.business.outcome.sub")} onClick={() => push({ name: "outcome" })} />
            <ListRow icon={ShieldCheck} tone="azure" title={t("w4.privacy.title")} subtitle={t("w4.business.privacy.sub")} onClick={() => push({ name: "privacy" })} />
          </Card>
        </Reveal>
      </Section>
    </TabScreen>
  );
}
