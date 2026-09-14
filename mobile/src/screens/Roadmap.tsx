import { Check, Flag, Milestone as MilestoneIcon, Wallet } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { tap } from "../App";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useNav } from "../nav";
import { useStore } from "../state/store";
import { Button, Card, cx, IconBubble, Note, Reveal, Screen } from "../ui";
import { addMonthsIso, dateLabel, fmtMsg } from "./g4/model";

/** Launch roadmap computed by core/launch.ts from the plan, catalog inputs and the location's intelligence. */
export default function Roadmap() {
  const { t, tm, lang } = useI18n();
  const { state, view, dispatch } = useStore();
  const { push } = useNav();
  const milestones = view.roadmap;
  const plan = view.financial?.plan;

  if (!milestones.length || !plan) {
    return (
      <Screen title={t("roadmap.title")}>
        <Reveal>
          <div className="mt-10 grid place-items-center text-center">
            <IconBubble icon={MilestoneIcon} tone="sand" size="lg" />
            <p className="mt-3 text-lg font-semibold">{t("u4.roadmap.empty.title")}</p>
            <p className="mt-1 max-w-80 text-[15px] leading-snug text-ink-3">{t("u4.roadmap.empty.body")}</p>
            <Button className="mt-5" icon={Wallet} onClick={() => push({ name: "plan" })}>
              {t("u4.roadmap.empty.cta")}
            </Button>
          </div>
        </Reveal>
      </Screen>
    );
  }

  const done = milestones.filter((m) => state.milestonesDone.includes(m.id)).length;
  const total = milestones.length;
  const windowWeeks = milestones[total - 1].week;
  const moratorium = plan.tier?.moratoriumMonths ?? 0;
  const firstFull = plan.schedule.find((q) => !q.isMoratorium) ?? null;
  const firstFullDate = firstFull && state.disbursedOn ? addMonthsIso(state.disbursedOn, 3 * firstFull.quarter) : null;
  const toggle = (id: string) => {
    tap();
    dispatch({ type: "milestone", id });
  };

  return (
    <Screen title={t("roadmap.title")} subtitle={t("roadmap.subtitle")}>
      <Reveal>
        <Card tone="azure" className="mt-2">
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-[13px] text-azure-100">{t("roadmap.progress")}</p>
              <p className="tabular mt-0.5 text-3xl font-bold">
                {done}
                <span className="text-lg text-azure-100"> / {total}</span>
              </p>
            </div>
            <AnimatePresence>
              {done === total && (
                <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={{ type: "spring", stiffness: 400, damping: 15 }} className="rounded-full bg-marigold-500 px-3 py-1 text-xs font-bold text-azure-950">
                  {t("roadmap.allDone")}
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/20">
            <motion.div animate={{ width: `${(done / total) * 100}%` }} transition={{ type: "spring", stiffness: 120, damping: 20 }} className="h-full rounded-full bg-marigold-500" />
          </div>
          <p className="mt-3 text-[13px] leading-snug text-azure-100">
            {moratorium ? t("roadmap.deadline", { week: windowWeeks, months: moratorium }) : t("u4.roadmap.deadlineNoBreak", { week: windowWeeks })}
          </p>
          {state.appStage !== "disbursed" && <p className="mt-2 text-xs font-medium text-marigold-200">{t("u4.roadmap.preview")}</p>}
        </Card>
      </Reveal>

      <div className="mt-5">
        {milestones.map((m, i) => {
          const isDone = state.milestonesDone.includes(m.id);
          const last = i === total - 1;
          const from = i === 0 ? 1 : Math.min(m.week, milestones[i - 1].week + 1);
          return (
            <Reveal key={m.id} i={i + 1}>
              <div className="relative flex gap-3">
                <div className="flex flex-col items-center">
                  <motion.button
                    whileTap={{ scale: 0.85 }}
                    aria-label={t(`u4.theme.${m.theme}`)}
                    aria-pressed={isDone}
                    onClick={() => toggle(m.id)}
                    className={cx("relative z-[1] grid size-11 place-items-center rounded-full ring-2 transition-colors", isDone ? "bg-azure-600 ring-azure-600" : "bg-white ring-line")}
                  >
                    <AnimatePresence mode="wait" initial={false}>
                      {isDone ? (
                        <motion.span key="c" initial={{ scale: 0, rotate: -45 }} animate={{ scale: [0, 1.3, 1], rotate: 0 }} exit={{ scale: 0 }} transition={{ duration: 0.4 }}>
                          <Check className="size-6 text-white" strokeWidth={3} />
                        </motion.span>
                      ) : (
                        <motion.span key="n" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="tabular text-[15px] font-bold text-ink-2">
                          {i + 1}
                        </motion.span>
                      )}
                    </AnimatePresence>
                    {isDone && <motion.span key={`ping-${m.id}`} initial={{ scale: 1, opacity: 0.5 }} animate={{ scale: 1.8, opacity: 0 }} transition={{ duration: 0.6 }} className="absolute inset-0 rounded-full bg-azure-600" />}
                  </motion.button>
                  {!last && <div className={cx("w-0.5 flex-1 transition-colors", isDone ? "bg-azure-600" : "bg-line")} />}
                </div>
                <div className="min-w-0 flex-1 pb-5">
                  <Card onClick={() => toggle(m.id)} className={cx("transition-opacity", isDone && "opacity-80")}>
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs font-semibold text-marigold-600">{from === m.week ? t("u4.roadmap.week", { week: m.week }) : t("roadmap.weeks", { from, to: m.week })}</p>
                      {m.amount !== undefined && <span className="tabular text-xs font-semibold text-ink-2">{rupees(m.amount)}</span>}
                    </div>
                    <p className={cx("mt-0.5 text-[15px] font-semibold leading-snug", isDone && "text-ink-3 line-through decoration-azure-600/60")}>{t(`u4.theme.${m.theme}`)}</p>
                    <ul className="mt-2 space-y-1.5">
                      {m.tasks.map((task, k) => (
                        <li key={`${task.key}-${k}`} className="flex gap-2 text-[13px] leading-snug text-ink-2 [overflow-wrap:anywhere]">
                          <span className={cx("mt-1.5 size-1.5 shrink-0 rounded-full", isDone ? "bg-azure-600" : "bg-ink-3/50")} />
                          {tm(fmtMsg(task))}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-2.5 text-xs font-medium text-azure-700">{isDone ? t("roadmap.tapUndo") : t("roadmap.tapDone")}</p>
                  </Card>
                </div>
              </div>
            </Reveal>
          );
        })}
      </div>

      {firstFull && (
        <div className="flex items-center gap-3 px-1">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-marigold-100 text-marigold-600">
            <Flag className="size-5" />
          </span>
          <div className="min-w-0">
            <p className="text-[15px] font-semibold">
              {firstFullDate ? t("u4.roadmap.firstFullOn", { date: dateLabel(firstFullDate, lang) }) : t("u4.roadmap.firstFullAfter", { months: 3 * firstFull.quarter })}
            </p>
            <p className="text-[13px] text-ink-3">{t("roadmap.repayAmount", { amount: rupees(firstFull.payment) })}</p>
          </div>
        </div>
      )}
      <div className="mt-5">
        <Note tone="azure">{t("u4.roadmap.note")}</Note>
      </div>
    </Screen>
  );
}
