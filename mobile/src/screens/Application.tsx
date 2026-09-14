import { Banknote, Check, ClipboardList, FileCheck2, FlaskConical, Rocket, ShieldCheck, UserRoundCheck, XCircle } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useState } from "react";
import { tap } from "../App";
import type { AppEvent } from "../core/tracker";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useNav } from "../nav";
import { useStore } from "../state/store";
import { Badge, Button, Card, ListRow, Note, Section, Screen, cx } from "../ui";
import { PackNote, RulesChip } from "./g3/bits";
import { Celebration } from "./g3/Celebration";
import { applicationRef, officerEvents, placeOf, stageDates, stageIndex, STAGE_ORDER } from "./g3/model";
import { activityDisplay } from "./g3/util";
import { udyamTab } from "./w3/udyamFields";

const STEP_ICONS = [FileCheck2, Check, UserRoundCheck, ShieldCheck, Banknote];
const EVENT_TONE: Partial<Record<AppEvent, "accent" | "secondary" | "danger">> = { reject: "danger", return_documents: "secondary", request_documents: "secondary" };

export default function Application() {
  const { t, pick, tm, lang } = useI18n();
  const { state, dispatch, view } = useStore();
  const { push, goto, switchTab } = useNav();
  const [celebrate, setCelebrate] = useState<"sanctioned" | "disbursed" | null>(null);
  const endCelebration = useCallback(() => setCelebrate(null), []);

  const plan = view.financial?.plan ?? null;
  const act = view.activityId ? activityDisplay(view.activityId) : null;
  const stage = state.appStage;
  const idx = stageIndex(stage, state.events);
  const disbursed = stage === "disbursed";
  const rejected = stage === "rejected";
  const submittedYet = idx >= 1;
  const dates = stageDates(state.events);
  const place = placeOf(view);
  const ref = applicationRef(place?.district.id, state.events);
  const allDocsComplete = !!view.documents?.complete;
  const fmt = new Intl.DateTimeFormat(lang === "hi" ? "hi-IN-u-nu-latn" : "en-IN", { day: "numeric", month: "short", year: "numeric" });
  const officer = tm({ key: "c3.role.sca_loan_officer" });

  if (!act || !plan) {
    return (
      <Screen title={t("app.title")} subtitle={t("app.subtitle")}>
        <Card tone="marigold" className="mt-2">
          <p className="text-[17px] font-semibold">{t("g3.app.empty.title")}</p>
          <p className="mt-1 text-[15px] leading-snug text-ink-2">{t("g3.app.empty.body")}</p>
          <Button size="md" className="mt-3" onClick={() => switchTab("plan")}>
            {t("g3.docs.empty.toPlan")}
          </Button>
        </Card>
      </Screen>
    );
  }

  const act_ = (event: AppEvent) => {
    tap();
    dispatch({ type: "application", event, allDocsComplete });
    if (event === "sanction") setCelebrate("sanctioned");
    if (event === "disburse") setCelebrate("disbursed");
  };
  const events = officerEvents(stage);

  return (
    <Screen
      title={t("app.title")}
      subtitle={t("app.subtitle")}
      footer={
        disbursed ? (
          <Button className="w-full" icon={Rocket} onClick={() => goto("business", { name: "roadmap" })}>
            {t("app.cta.launch")}
          </Button>
        ) : undefined
      }
    >
      <Card tone={rejected ? "clay" : "forest"} className="mt-2">
        <p className={cx("text-sm break-words", rejected ? "text-ink-2" : "text-forest-100")}>
          {act.emoji} {pick(act.name)}
        </p>
        <p className={cx("mt-2 text-xs", rejected ? "text-ink-2" : "text-forest-100")}>
          {t(rejected ? "g3.app.amountRejected" : disbursed ? "app.amountDisbursed" : idx >= 3 ? "app.amountSanctioned" : "app.amountRequested")}
        </p>
        <p className="tabular text-[36px] leading-tight font-bold">{plan.eligible ? rupees(plan.loan) : "—"}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className={cx("tabular rounded-full px-2.5 py-1 text-[11px] font-semibold", rejected ? "bg-white/60" : "bg-white/12")}>
            {ref ? t("g3.app.ref", { ref }) : t("g3.app.refPending")}
          </span>
          {!rejected && <RulesChip light />}
        </div>
      </Card>

      {!plan.eligible && (
        <div className="mt-4">
          <Note tone="clay">{t("g3.docs.notEligible")}</Note>
        </div>
      )}

      {!submittedYet && !rejected && (
        <div className="mt-4">
          <Note tone="marigold">
            <p>{t("app.notSubmitted")}</p>
            <button onClick={() => push({ name: "documents" })} className="mt-1.5 min-h-9 font-semibold underline">
              {t("app.openDocs")}
            </button>
          </Note>
        </div>
      )}

      {rejected && (
        <div className="mt-4">
          <Note tone="clay" icon={XCircle}>
            <p className="font-semibold">{t("g3.app.rejected.title", { d: dates.rejected ? fmt.format(new Date(dates.rejected)) : "—" })}</p>
            <p className="mt-0.5">{t("g3.app.rejected.body")}</p>
            <button onClick={() => push({ name: "grievance" })} className="mt-1.5 min-h-9 font-semibold underline">
              {t("g3.app.rejected.grievance")}
            </button>
          </Note>
        </div>
      )}

      <Section>
        <Card className="py-1">
          <ListRow icon={ClipboardList} title={t("app.viewForm")} subtitle={t("app.viewFormSub")} onClick={() => {
              udyamTab.initial = "form";
              push({ name: "udyam" });
            }} />
        </Card>
      </Section>

      <Section title={t("app.tracker")}>
        <Card>
          <ol>
            {STAGE_ORDER.map((s, i) => {
              const Icon = STEP_ICONS[i];
              const isDone = i < idx || (disbursed && i === idx);
              const isCurrent = i === idx && !disbursed && !rejected;
              const isRejectedHere = rejected && i === idx + 1;
              const at = dates[s];
              return (
                <li key={s} className="relative flex gap-3 pb-5 last:pb-0">
                  {i < STAGE_ORDER.length - 1 && <span className={cx("absolute top-10 bottom-0 left-[19px] w-0.5", i < idx ? "bg-forest-600" : "bg-line")} />}
                  <motion.span
                    animate={isCurrent ? { scale: [1, 1.08, 1] } : { scale: 1 }}
                    transition={isCurrent ? { repeat: Infinity, duration: 1.8 } : undefined}
                    className={cx(
                      "relative grid size-10 shrink-0 place-items-center rounded-full",
                      isDone ? "bg-forest-600 text-white" : isCurrent ? "bg-marigold-500 text-forest-950 ring-4 ring-marigold-100" : isRejectedHere ? "bg-clay-600 text-white" : "bg-sand text-ink-3",
                    )}
                  >
                    {isDone ? <Check className="size-5" /> : isRejectedHere ? <XCircle className="size-5" /> : <Icon className="size-5" />}
                  </motion.span>
                  <div className="min-w-0 flex-1 pt-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className={cx("text-[15px] font-semibold", !isDone && !isCurrent && "text-ink-3")}>{t(`app.step.${s}`)}</p>
                      {isCurrent && <Badge tone="warn">{t("app.now")}</Badge>}
                      {isRejectedHere && <Badge tone="risk">{t("g3.app.rejectedBadge")}</Badge>}
                    </div>
                    <p className="text-[13px] leading-snug text-ink-3">
                      {isDone
                        ? at
                          ? t("g3.app.doneOn", { d: fmt.format(new Date(at)) })
                          : t("g3.app.done")
                        : isCurrent
                          ? `${t(`app.current.${s}`)}${at ? ` · ${t("g3.app.since", { d: fmt.format(new Date(at)) })}` : ""}`
                          : t("app.upcoming")}
                    </p>
                    {s === "under_verification" && (isCurrent || isDone) && (
                      <p className="mt-1 flex items-center gap-1.5 text-[13px] text-ink-2">
                        <UserRoundCheck className="size-4 text-forest-700" />
                        {officer}
                        {place ? ` · ${pick(place.district.name)}` : ""}
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </Card>
      </Section>

      {disbursed && plan.eligible ? (
        <div className="mt-4">
          <Note tone="forest" icon={Banknote}>
            {t("app.disbursedNote", { v: rupees(plan.loan) })}
          </Note>
        </div>
      ) : (
        events.length > 0 && (
          <Section>
            <Card tone="marigold">
              <div className="flex items-center gap-2">
                <FlaskConical className="size-5 text-marigold-600" />
                <p className="text-[15px] font-semibold">{t("app.demo.title")}</p>
              </div>
              <p className="mt-1 text-[13px] leading-snug text-ink-2">{t("g3.app.demo.body", { officer })}</p>
              <div className="mt-3 space-y-2">
                {events.map((e) => (
                  <Button key={e} variant={EVENT_TONE[e] ?? "accent"} size="md" className="w-full" onClick={() => act_(e)}>
                    {t(`g3.app.event.${e}`)}
                  </Button>
                ))}
              </div>
            </Card>
          </Section>
        )
      )}

      <PackNote uses="rules" />
      {celebrate && <Celebration kind={celebrate} amount={rupees(plan.loan)} onDone={endCelebration} />}
    </Screen>
  );
}
