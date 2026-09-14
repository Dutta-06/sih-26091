import { CalendarCheck, CheckCircle2, CloudRain, Database, HeartPulse, LifeBuoy, ShieldCheck, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { tap } from "../App";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useNav } from "../nav";
import { Badge, Button, Card, ConfidenceBadge, cx, IconBubble, Progress, Reveal, Screen, Section } from "../ui";
import { INTERVENTION_LOOK } from "./g4/look";
import { monthLabel, pctOfPlan, useLifecycle, type InterventionType } from "./g4/model";


const COMPONENTS = ["revenueVsPlan", "coverage", "repayment"] as const;

export default function Warning() {
  const { t, tm, lang } = useI18n();
  const { state, view, lc, set, dispatch } = useLifecycle();
  const { push } = useNav();
  const { warning } = lc;
  const [choice, setChoice] = useState<InterventionType | null>(null);
  const [changing, setChanging] = useState(false);

  if (!warning) {
    return (
      <Screen title={t("warning.title")}>
        <Reveal>
          <div className="mt-10 grid place-items-center text-center">
            <IconBubble icon={ShieldCheck} tone="forest" size="lg" />
            <p className="mt-3 text-lg font-semibold">{t("u4.warning.none.title")}</p>
            <p className="mt-1 max-w-80 text-[15px] leading-snug text-ink-3">
              {lc.latest ? t("u4.warning.none.body", { n: lc.done.length, month: monthLabel(lc.latest.month, lang) }) : t("u4.warning.none.noData")}
            </p>
            <Button className="mt-5" variant="secondary" icon={HeartPulse} onClick={() => push({ name: "monitoring" })}>
              {t("warning.backToHealth")}
            </Button>
          </div>
        </Reveal>
      </Screen>
    );
  }

  const month = monthLabel(warning.month, lang);
  const pct = pctOfPlan(warning);
  const options = view.interventions;
  const chosen = state.interventionChosen?.month === warning.month ? state.interventionChosen : null;

  if (chosen && !changing) {
    const opt = options.find((o) => o.type === chosen.type);
    return (
      <Screen
        title={t("warning.title")}
        footer={
          <div className="grid gap-1">
            <Button className="w-full" onClick={() => push({ name: lc.followUpDue ? "outcome" : "monitoring" })} icon={lc.followUpDue ? CalendarCheck : undefined}>
              {lc.followUpDue ? t("w4.warning.followUp") : t("warning.backToHealth")}
            </Button>
            {!state.followUp && (
              <Button variant="ghost" size="md" onClick={() => setChanging(true)}>
                {t("u4.warning.change")}
              </Button>
            )}
          </div>
        }
      >
        <div className="grid min-h-[70%] place-items-center text-center">
          <div>
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 14 }} className="mx-auto grid size-20 place-items-center rounded-full bg-forest-100">
              <CheckCircle2 className="size-10 text-forest-700" />
            </motion.div>
            <Reveal i={2}>
              <h2 className="mt-5 text-xl font-bold">{t("warning.success.title")}</h2>
              <p className="mt-1 text-[15px] font-medium text-forest-800">{t(`u4.intervention.${chosen.type}`)}</p>
              <p className="mx-auto mt-3 max-w-80 text-[15px] leading-snug text-ink-2">
                {lc.afterSnap ? t("u4.warning.success.ready", { month: monthLabel(lc.afterSnap.month, lang) }) : t("u4.warning.success.wait", { month })}
              </p>
            </Reveal>
            {opt && (
              <Reveal i={4}>
                <p className="mx-auto mt-4 max-w-80 rounded-2xl bg-sand px-3 py-2.5 text-[13px] leading-snug text-ink-2">
                  {t("u4.warning.success.learn", { real: opt.real, synthetic: opt.synthetic })}
                </p>
              </Reveal>
            )}
          </div>
        </div>
      </Screen>
    );
  }

  const risk = view.intel?.risk;
  const monthIdx = +warning.month.slice(5, 7) - 1;
  const seasonal = risk ? risk.flags.find((f) => f.category === "seasonal") ?? null : null;
  const flaggedBefore = !!risk && (risk.lowMonths.includes(monthIdx) || !!seasonal);
  const totalReal = options.reduce((s, o) => s + o.real, 0);
  const totalSynthetic = options.reduce((s, o) => s + o.synthetic, 0);

  const confirm = () => {
    if (!choice) return;
    tap();
    set({ interventionChosen: { type: choice, month: warning.month }, followUp: null });
    dispatch({ type: "event", event: { type: "intervention", data: { intervention: choice, month: warning.month } } });
    setChanging(false);
  };

  return (
    <Screen
      title={t("warning.title")}
      footer={
        <div className="grid gap-1">
          <Button className="w-full" disabled={!choice} onClick={confirm}>
            {choice ? t("warning.tryThis") : t("warning.pickOne")}
          </Button>
          <Button variant="ghost" size="md" icon={LifeBuoy} onClick={() => push({ name: "grievance" })}>
            {t("warning.raise")}
          </Button>
        </div>
      }
    >
      <Reveal>
        <Card tone="clay" className="mt-2">
          {warning.band && <Badge tone="risk">{t("u4.warning.badge", { band: t(`u4.band.${warning.band}`), score: Math.round(warning.score ?? 0) })}</Badge>}
          <h2 className="mt-2 text-xl font-bold leading-snug text-clay-700">{t("u4.warning.headline", { month, pct: pct ?? "—" })}</h2>
          <div className="mt-3 grid grid-cols-2 gap-2 text-[13px]">
            <div className="rounded-xl bg-white/70 p-2.5">
              <p className="text-ink-3">{t("warning.planned")}</p>
              <p className="tabular text-lg font-bold">{rupees(warning.planned)}</p>
            </div>
            <div className="rounded-xl bg-white/70 p-2.5">
              <p className="text-ink-3">{t("warning.actual")}</p>
              <p className="tabular text-lg font-bold text-clay-700">{rupees(warning.revenue)}</p>
            </div>
          </div>
          {warning.reasons.length > 0 && (
            <ul className="mt-3 space-y-1 text-[13px] leading-snug text-clay-700">
              {warning.reasons.map((r, i) => (
                <li key={i}>• {tm(r)}</li>
              ))}
            </ul>
          )}
        </Card>
      </Reveal>

      <Section title={t("u4.warning.components")}>
        <Reveal i={1}>
          <Card className="grid gap-3">
            {COMPONENTS.map((c) => {
              const v = warning.components[c];
              return (
                <div key={c}>
                  <div className="flex items-baseline justify-between gap-2 text-[13px]">
                    <span className="text-ink-2">{t(`u4.component.${c}`)}</span>
                    <span className="tabular font-semibold">{v === null ? t("u4.component.na") : `${Math.round(v * 100)}%`}</span>
                  </div>
                  {v !== null && <Progress value={v * 100} tone={v >= 0.8 ? "forest" : v >= 0.5 ? "marigold" : "clay"} className="mt-1" />}
                </div>
              );
            })}
            <p className="text-xs leading-snug text-ink-3">{t("u4.warning.componentsNote")}</p>
          </Card>
        </Reveal>
      </Section>

      {flaggedBefore && risk && (
        <Section title={t("warning.cause")}>
          <Reveal i={2}>
            <Card>
              <div className="flex items-start gap-3">
                <IconBubble icon={CloudRain} tone="sky" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[15px] font-semibold">{seasonal ? tm(seasonal.title) : t("u4.warning.lowMonth", { month: monthLabel(warning.month, lang, "short") })}</p>
                    <ConfidenceBadge value={seasonal?.confidence ?? risk.confidence} />
                  </div>
                  {seasonal && <p className="mt-1 text-[13px] leading-snug text-ink-2">{tm(seasonal.detail)}</p>}
                  <p className="mt-1.5 text-[13px] leading-snug text-ink-3">{t("warning.causeLink")}</p>
                </div>
              </div>
            </Card>
          </Reveal>
        </Section>
      )}

      <Section title={t("warning.options")}>
        <p className="-mt-1 mb-2.5 px-1 text-[13px] leading-snug text-ink-3">{t("u4.warning.ranked", { real: totalReal, synthetic: totalSynthetic })}</p>
        <div className="grid gap-3">
          {options.map((o, i) => {
            const active = choice === o.type;
            const look = INTERVENTION_LOOK[o.type];
            const recommended = warning.intervention === o.type;
            return (
              <Reveal key={o.type} i={i + 3}>
                <motion.button
                  whileTap={{ scale: 0.98 }}
                  aria-pressed={active}
                  onClick={() => {
                    tap();
                    setChoice(o.type);
                  }}
                  className={cx("block w-full rounded-[var(--radius-card)] bg-white p-4 text-left shadow-[var(--shadow-card)] ring-2 transition-colors", active ? "ring-forest-600" : "ring-transparent")}
                >
                  <div className="flex items-start gap-3">
                    <IconBubble icon={look.icon} tone={look.tone} size="sm" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap gap-1.5">
                        {recommended && <Badge tone="info" icon={Sparkles}>{t("u4.warning.recommended")}</Badge>}
                        {i === 0 && <Badge tone="good">{t("u4.warning.bestRate")}</Badge>}
                      </div>
                      <p className="mt-1.5 text-[15px] font-semibold leading-snug">{t(`u4.intervention.${o.type}`)}</p>
                      <p className="mt-0.5 text-[13px] leading-snug text-ink-3">{t(`u4.intervention.${o.type}.body`)}</p>
                      <div className="mt-2.5 rounded-xl bg-sand/70 px-2.5 py-2">
                        <p className={cx("text-[13px] font-semibold", i === 0 ? "text-forest-700" : "text-ink-2")}>
                          {t("u4.evidence.rate", { pct: Math.round(o.successRate * 100), n: o.improved, total: o.total })}
                        </p>
                        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-3/15">
                          <div className={cx("h-full rounded-full", i === 0 ? "bg-forest-600" : "bg-ink-3/60")} style={{ width: `${Math.round(o.successRate * 100)}%` }} />
                        </div>
                        <p className="mt-1.5 flex items-start gap-1 text-[11px] font-medium leading-snug text-marigold-600">
                          <Database className="mt-px size-3 shrink-0" />
                          {t("u4.evidence.status", { real: o.real, synthetic: o.synthetic })}
                        </p>
                      </div>
                    </div>
                    <span className={cx("mt-1 grid size-6 shrink-0 place-items-center rounded-full ring-2", active ? "bg-forest-600 ring-forest-600" : "ring-line")}>
                      {active && <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} className="size-2.5 rounded-full bg-white" />}
                    </span>
                  </div>
                  {o.type === "supply_chain_change" && view.pool && (
                    <span
                      role="link"
                      onClick={(e) => {
                        e.stopPropagation();
                        push({ name: "community" });
                      }}
                      className="mt-2 ml-12 inline-flex min-h-9 items-center text-[13px] font-semibold text-forest-700"
                    >
                      {t("u4.warning.poolLink", { n: view.pool.peers })}
                    </span>
                  )}
                </motion.button>
              </Reveal>
            );
          })}
        </div>
      </Section>
    </Screen>
  );
}
