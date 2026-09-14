import { CalendarCheck, CheckCircle2, ChevronRight, Clock, Database, HeartPulse, Hourglass, Meh, ThumbsDown, ThumbsUp, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { tap } from "../App";
import type { OutcomeRecord } from "../core/types";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useNav } from "../nav";
import { Badge, Button, Card, cx, IconBubble, Note, Reveal, Ring, Screen, Section, Stat } from "../ui";
import { INTERVENTION_LOOK } from "./g4/look";
import { addMonthsIso, monthLabel, pctOfPlan, RING_TONE, useLifecycle } from "./g4/model";
import { OutcomeHistory } from "./w4/OutcomeHistory";

type Answer = "yes" | "little" | "no";
const ANSWERS: { id: Answer; icon: LucideIcon }[] = [
  { id: "yes", icon: ThumbsUp },
  { id: "little", icon: Meh },
  { id: "no", icon: ThumbsDown },
];

/** "Did it help?" — compares health at the warning with the first month that ended after it, and records a real outcome. */
export default function Outcome() {
  const { t, lang } = useI18n();
  const { state, view, lc, set, dispatch } = useLifecycle();
  const { push, switchTab } = useNav();
  const [answer, setAnswer] = useState<Answer | null>(null);
  const chosen = state.interventionChosen;

  const history = (
    <Section title={t("w4.history.title")}>
      <OutcomeHistory />
      <div className="mt-3">
        <Note tone="forest">{t("u4.history.note")}</Note>
      </div>
    </Section>
  );

  if (!chosen) {
    return (
      <Screen title={t("w4.outcome.title")}>
        <Reveal>
          <div className="mt-8 grid place-items-center text-center">
            <IconBubble icon={CalendarCheck} tone="sand" size="lg" />
            <p className="mt-3 text-lg font-semibold">{t("w4.outcome.empty.title")}</p>
            <p className="mt-1 max-w-80 text-[15px] leading-snug text-ink-3">{t("u4.outcome.empty.body")}</p>
            <Button className="mt-5" icon={HeartPulse} onClick={() => push({ name: "monitoring" })}>
              {t("w4.outcome.empty.cta")}
            </Button>
          </div>
        </Reveal>
        {history}
      </Screen>
    );
  }

  const look = INTERVENTION_LOOK[chosen.type];
  const option = view.interventions.find((o) => o.type === chosen.type) ?? null;
  const before = lc.chosenSnap?.score ?? null;
  const after = lc.afterSnap;
  const recorded = !!state.followUp && state.followUp.month === after?.month;

  const chosenCard = (
    <Section title={t("w4.outcome.chosen")}>
      <Reveal i={2}>
        <Card>
          <div className="flex items-start gap-3">
            <IconBubble icon={look.icon} tone={look.tone} size="sm" />
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-semibold leading-snug">{t(`u4.intervention.${chosen.type}`)}</p>
              <p className="text-[13px] text-ink-3">{t("u4.outcome.forMonth", { month: monthLabel(chosen.month, lang) })}</p>
              {option && (
                <p className="mt-2 flex items-start gap-1 text-[11px] font-medium leading-snug text-marigold-600">
                  <Database className="mt-px size-3 shrink-0" />
                  {t("u4.evidence.rateStatus", { pct: Math.round(option.successRate * 100), real: option.real, synthetic: option.synthetic })}
                </p>
              )}
            </div>
          </div>
        </Card>
      </Reveal>
    </Section>
  );

  if (!after || before === null || after.score === null) {
    const next = monthLabel(addMonthsIso(`${chosen.month}-01`, 1).slice(0, 7), lang);
    return (
      <Screen title={t("w4.outcome.title")}>
        <Reveal>
          <Card className="mt-2">
            <div className="flex items-start gap-3">
              <IconBubble icon={Hourglass} tone="sky" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-semibold">{t("u4.outcome.wait.title")}</p>
                <p className="mt-1 text-[13px] leading-snug text-ink-2">
                  {!state.smsConsent ? t("u4.outcome.wait.noConsent") : t("u4.outcome.wait.body", { month: next })}
                </p>
              </div>
            </div>
            {before !== null && <p className="mt-3 rounded-xl bg-sand px-3 py-2 text-[13px] text-ink-2">{t("u4.outcome.beforeWas", { score: Math.round(before), month: monthLabel(chosen.month, lang) })}</p>}
            <Button variant="ghost" size="md" icon={Clock} className="mt-2 w-full" onClick={() => switchTab("more")}>
              {t("u4.presenter.advance")}
            </Button>
          </Card>
        </Reveal>
        {chosenCard}
        {history}
      </Screen>
    );
  }

  const afterScore = Math.round(after.score);
  const beforeScore = Math.round(before);
  const improved = afterScore > beforeScore;
  const pct = pctOfPlan(after);

  const record = () => {
    if (!answer || recorded) return;
    tap();
    const place = view.location.chosen ?? view.location.candidates[0] ?? null;
    const outcome: OutcomeRecord = {
      catalog_id: view.activityId!,
      district: place?.district.id ?? null,
      intervention_type: chosen.type,
      health_before: before,
      health_after: after.score!,
      is_synthetic: false,
    };
    set({ followUp: { answer, before, after: after.score!, month: after.month }, realOutcomes: [...state.realOutcomes, outcome] });
    dispatch({ type: "event", event: { type: "follow_up", data: { intervention: chosen.type, warningMonth: chosen.month, month: after.month, before, after: after.score!, answer } } });
  };

  const footer = recorded ? (
    <Button className="w-full" iconRight={ChevronRight} onClick={() => push({ name: "monitoring" })}>
      {t("warning.backToHealth")}
    </Button>
  ) : (
    <Button className="w-full" disabled={!answer} onClick={record}>
      {answer ? t("w4.outcome.record") : t("w4.outcome.pick")}
    </Button>
  );

  return (
    <Screen title={t("w4.outcome.title")} subtitle={t("u4.outcome.subtitle", { from: monthLabel(chosen.month, lang), to: monthLabel(after.month, lang) })} footer={footer}>
      <Reveal>
        <Card className="mt-2">
          <p className="text-[13px] text-ink-3">{t("w4.outcome.health")}</p>
          <div className="mt-3 flex items-center justify-around gap-3">
            <div className="text-center">
              <Ring value={beforeScore} tone={lc.chosenSnap?.band ? RING_TONE[lc.chosenSnap.band] : "marigold"} size={76} stroke={8} />
              <p className="mt-1.5 text-xs text-ink-3">{monthLabel(chosen.month, lang, "short")}</p>
            </div>
            <ChevronRight className="size-6 text-ink-3" />
            <div className="text-center">
              <Ring value={afterScore} tone={after.band ? RING_TONE[after.band] : "marigold"} size={96} stroke={10} sub="/100" />
              <p className="mt-1.5 text-xs text-ink-3">{monthLabel(after.month, lang, "short")}</p>
            </div>
          </div>
          <div className="mt-3 flex justify-center">
            <Badge tone={improved ? "good" : "risk"}>{t(improved ? "w4.history.improved" : "w4.history.notImproved")}</Badge>
          </div>
        </Card>
      </Reveal>

      <Reveal i={1}>
        <Card className="mt-3 grid grid-cols-2 gap-3">
          <Stat label={t("u4.outcome.revenueIn", { month: monthLabel(after.month, lang, "short") })} value={rupees(after.revenue)} tone="forest" hint={pct !== null ? t("u4.monitoring.ofPlan", { pct }) : undefined} />
          <Stat label={t("w4.outcome.planned")} value={rupees(after.planned)} />
        </Card>
      </Reveal>

      {chosenCard}

      {!recorded ? (
        <Section title={t("w4.outcome.question")}>
          <div className="grid grid-cols-3 gap-2">
            {ANSWERS.map((a, i) => (
              <Reveal key={a.id} i={i + 3}>
                <motion.button
                  whileTap={{ scale: 0.95 }}
                  aria-pressed={answer === a.id}
                  onClick={() => {
                    tap();
                    setAnswer(a.id);
                  }}
                  className={cx("flex min-h-20 w-full flex-col items-center justify-center gap-1.5 rounded-2xl text-[15px] font-semibold ring-2", answer === a.id ? "bg-forest-800 text-white ring-forest-800" : "bg-white text-forest-800 ring-line")}
                >
                  <a.icon className="size-5" />
                  {t(`w4.outcome.answer.${a.id}`)}
                </motion.button>
              </Reveal>
            ))}
          </div>
          <p className="mt-2 px-1 text-[13px] leading-snug text-ink-3">{t("w4.outcome.questionHint")}</p>
        </Section>
      ) : (
        <Reveal i={3}>
          <Card tone="forest" className="mt-6">
            <div className="flex items-center gap-3">
              <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 14 }} className="grid size-11 shrink-0 place-items-center rounded-2xl bg-white/15">
                <CheckCircle2 className="size-6" />
              </motion.span>
              <div className="min-w-0">
                <p className="text-lg font-bold">{t("w4.outcome.recorded")}</p>
                {state.followUp && <p className="text-[13px] text-forest-100">{t("w4.outcome.youSaid", { answer: t(`w4.outcome.answer.${state.followUp.answer}`) })}</p>}
              </div>
            </div>
            <p className="mt-3 text-[15px] leading-snug text-forest-100">{t("u4.outcome.recorded.body")}</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-xl bg-white/10 p-2.5">
                <p className="text-xs text-forest-100">{t("w4.outcome.realRecords")}</p>
                <motion.p key={view.prior?.realRecords} initial={{ y: -8, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="tabular text-2xl font-bold">
                  {view.prior?.realRecords ?? 0}
                </motion.p>
              </div>
              <div className="rounded-xl bg-white/10 p-2.5">
                <p className="text-xs text-forest-100">{t("w4.outcome.syntheticRecords")}</p>
                <p className="tabular text-2xl font-bold">{view.prior?.syntheticRecords ?? 0}</p>
              </div>
            </div>
            {option && <p className="mt-2 text-[13px] text-forest-100">{t("u4.outcome.newRate", { step: t(`u4.intervention.${chosen.type}`), pct: Math.round(option.successRate * 100), real: option.real, synthetic: option.synthetic })}</p>}
            {view.prior?.isSyntheticDominant && (
              <p className="mt-2 flex items-start gap-1.5 text-xs leading-snug text-marigold-200">
                <Database className="mt-px size-3.5 shrink-0" />
                {t("w4.outcome.syntheticNote")}
              </p>
            )}
          </Card>
        </Reveal>
      )}

      {history}
    </Screen>
  );
}
