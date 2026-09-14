import { Activity, Calculator, Database, FileCheck2, Mic, RefreshCcw, ShieldAlert, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { ACTIVITIES } from "../data/activities";
import { districts, docs, feedback, outcomeSeed, pois, priceSeriesAll, villages } from "../core/pack";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useStore } from "../state/store";
import { ConfidenceBadge, CountUp, cx, Reveal, Screen, Section } from "../ui";
import { profileComplete } from "./g1/conversation";
import { AGENT_ORDER } from "./g1/findings";

const SOURCES = ["census", "lgd", "osm", "overture", "indiapost", "ifsc", "openmeteo", "agmarknet", "udyam", "secc", "osrm"];

/** Counts over the bundled data pack, computed from the loaders (not typed). */
function packCounts() {
  return [
    { k: "villages", v: villages().length },
    { k: "districts", v: districts().length },
    { k: "pois", v: pois().length },
    { k: "docs", v: docs("sector_reports").length + docs("risk_taxonomy").length + docs("scheme_guidelines").length },
    { k: "prices", v: priceSeriesAll().length },
    { k: "outcomes", v: outcomeSeed().length },
    { k: "feedback", v: districts().reduce((n, d) => n + feedback(d.id, null).length, 0) },
  ];
}

export default function Architecture() {
  const { t, pick } = useI18n();
  const { state, view } = useStore();
  const f = view.feasibility;
  const hasCase = profileComplete(state.profile, state.chat) || f.attempts.length > 0;
  const shown = f.selected ?? f.attempts.at(-1) ?? null;
  const rules = f.attempts.reduce((n, a) => n + a.findings.length, 0);
  const real = shown ? AGENT_ORDER.filter((id) => shown.intel[id].confidence === "real").length : 0;
  const plan = view.financial?.plan ?? null;

  return (
    <Screen title={t("arch.title")} subtitle={t("arch.subtitle")}>
      <p className="mt-2 text-[15px] leading-relaxed text-ink-2">{t("arch.lead")}</p>

      <div className="relative mt-5">
        <Step i={0} n={1} icon={Mic} title={t("arch.s1")} body={t("arch.s1b")} />
        <Step i={1} n={2} icon={Database} title={t("arch.s2")} body={t("arch.s2b")}>
          <div className="mt-2.5 grid grid-cols-2 gap-1.5">
            {AGENT_ORDER.map((id) => (
              <div key={id} className="flex min-h-9 items-center justify-between gap-1.5 rounded-xl bg-sand px-2.5 py-1.5">
                <span className="truncate text-[12px] font-medium">{t(`u1.agent.${id}`)}</span>
                {shown && <ConfidenceBadge value={shown.intel[id].confidence} compact />}
              </div>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <ConfidenceBadge value="real" />
            <ConfidenceBadge value="estimated" />
          </div>
        </Step>
        <Step i={2} n={3} icon={ShieldAlert} tone="clay" title={t("arch.s3")} body={t("arch.s3b")} />
        <Step i={3} n={4} icon={Calculator} tone="azure" title={t("arch.s4")} body={t("arch.s4b")}>
          {plan?.eligible && (
            <>
              <div className="mt-2.5 rounded-xl bg-white/10 px-3 py-2 text-[13px] leading-snug">
                {t("u1.arch.s4ex", { savings: rupees(plan.capital), loan: rupees(plan.loan), rate: ((plan.tier?.rate ?? 0) * 100).toFixed(1) })}
              </div>
              <p className="mt-1.5 text-[11px] font-medium text-azure-100">{t("g1.rulesNotAi")}</p>
            </>
          )}
        </Step>
        <Step i={4} n={5} icon={FileCheck2} title={t("arch.s5")} body={t("arch.s5b")} />
        <Step i={5} n={6} icon={Activity} tone="marigold" title={t("arch.s6")} body={t("arch.s6b")} />
        <Step i={6} n={7} icon={RefreshCcw} title={t("arch.s7")} body={t("arch.s7b")} last />
      </div>

      <Section title={t("u1.arch.case")}>
        {hasCase ? (
          <Reveal i={0}>
            <div className="rounded-[var(--radius-card)] bg-white p-3.5 shadow-[var(--shadow-card)]">
              <div className="grid grid-cols-3 gap-2">
                {[
                  { v: f.attempts.length, k: "attempts" },
                  { v: rules, k: "rules" },
                  { v: real, k: "real" },
                ].map((s) => (
                  <div key={s.k}>
                    <p className="tabular text-2xl font-bold text-azure-800">
                      <CountUp value={s.v} />
                    </p>
                    <p className="mt-0.5 text-[12px] leading-snug text-ink-2">{t(`u1.arch.case.${s.k}`)}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 border-t border-line pt-2 text-[14px] font-semibold">
                {f.selected
                  ? t("u1.arch.case.selected", { idea: `${ACTIVITIES[f.selected.activityId]?.emoji ?? ""} ${ACTIVITIES[f.selected.activityId] ? pick(ACTIVITIES[f.selected.activityId].name) : f.selected.activityId}` })
                  : f.exhausted
                    ? t("u1.arch.case.exhausted")
                    : t("u1.arch.case.constraint")}
              </p>
            </div>
          </Reveal>
        ) : (
          <p className="rounded-[var(--radius-card)] bg-sand p-3.5 text-[14px] leading-snug text-ink-2">{t("u1.arch.case.none")}</p>
        )}
      </Section>

      <Section title={t("u1.arch.pack")}>
        <p className="-mt-1 mb-2 px-1 text-xs text-ink-3">{t("u1.arch.packSub")}</p>
        <div className="grid grid-cols-2 gap-2">
          {packCounts().map((s, i) => (
            <Reveal key={s.k} i={i}>
              <div className="h-full rounded-[var(--radius-card)] bg-white p-3 shadow-[var(--shadow-card)]">
                <p className="tabular text-2xl font-bold text-azure-800">
                  <CountUp value={s.v} />
                </p>
                <p className="mt-1 text-[12px] leading-snug text-ink-2">{t(`u1.arch.stat.${s.k}`)}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </Section>

      <Section title={t("arch.sources")}>
        <div className="flex flex-wrap gap-2">
          {SOURCES.map((s) => (
            <span key={s} className="inline-flex min-h-9 items-center gap-1.5 rounded-full bg-white px-3 text-[13px] font-medium ring-1 ring-line">
              <span className="size-1.5 rounded-full bg-azure-600" />
              {t(`arch.src.${s}`)}
            </span>
          ))}
        </div>
        <p className="mt-2 px-1 text-xs text-ink-3">{t("arch.offline")}</p>
      </Section>

    </Screen>
  );
}

function Step({ i, n, icon: Icon, title, body, tone = "white", last, children }: { i: number; n: number; icon: LucideIcon; title: string; body: string; tone?: "white" | "azure" | "clay" | "marigold"; last?: boolean; children?: ReactNode }) {
  const { t } = useI18n();
  const tones = {
    white: "bg-white shadow-[var(--shadow-card)]",
    azure: "bg-azure-800 text-white shadow-[var(--shadow-float)]",
    clay: "bg-clay-50 ring-1 ring-clay-100",
    marigold: "bg-marigold-50 ring-1 ring-marigold-200",
  };
  const bubble = { white: "bg-azure-100 text-azure-800", azure: "bg-marigold-500 text-azure-950", clay: "bg-clay-600 text-white", marigold: "bg-marigold-500 text-azure-950" };
  return (
    <Reveal i={i} className="relative flex gap-3 pb-3">
      <div className="flex w-10 shrink-0 flex-col items-center">
        <span className={cx("grid size-10 place-items-center rounded-full", bubble[tone])}>
          <Icon className="size-5" />
        </span>
        {!last && <span className="mt-1 w-0.5 flex-1 rounded-full bg-azure-200" />}
        {last && (
          <svg viewBox="0 0 40 60" className="mt-1 h-12 w-10 text-azure-600" aria-hidden>
            <path d="M20 0 V30 Q20 50 36 50" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />
          </svg>
        )}
      </div>
      <div className={cx("min-w-0 flex-1 rounded-[var(--radius-card)] p-3.5", tones[tone])}>
        <p className={cx("text-[11px] font-semibold tracking-wide uppercase", tone === "azure" ? "text-azure-100" : "text-ink-3")}>{t("arch.step", { n })}</p>
        <p className="text-[16px] leading-snug font-semibold">{title}</p>
        <p className={cx("mt-0.5 text-[13px] leading-snug", tone === "azure" ? "text-azure-100" : "text-ink-2")}>{body}</p>
        {children}
      </div>
    </Reveal>
  );
}
