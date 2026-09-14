import { BadgeCheck, ChevronDown, FileText, ScrollText } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import { explainScheme } from "../core/financial";
import type { PackDoc } from "../core/types";
import { buildPlan, TIERS, type TierName } from "../engine/finance";
import { useI18n } from "../i18n";
import { rupeesShort } from "../lib/format";
import { useStore } from "../state/store";
import { Badge, Card, Note, Reveal, Section, Screen, cx } from "../ui";
import { RulesChip } from "./g3/bits";
import { ratePct } from "./g3/util";

const TIER_ORDER = Object.keys(TIERS) as TierName[];
const FAQ = ["monsoon", "prepay", "decides", "reject"];
const DOC_SOURCE = "required_documents.md";
const STEP_SOURCE = "application_process.md";

const fileName = (source: string) => source.split(/[\\/]/).pop() ?? source;

/** Guideline text lines without markdown list / quote markers. */
const lines = (text: string) =>
  text
    .split(/\r?\n/)
    .map((l) => l.replace(/^\s*(?:[-*]|\d+\.|>)\s*/, "").trim())
    .filter(Boolean);

export default function Scheme() {
  const { t, lang } = useI18n();
  const { state, view } = useStore();
  const [openFaq, setOpenFaq] = useState<string | null>(FAQ[0]);
  const [openRule, setOpenRule] = useState<number | null>(null);

  // The case's plan and retrieved policy; before an activity is chosen, the same core call on the saved savings.
  const plan = view.financial?.plan ?? buildPlan(state.profile.capital);
  const policy = useMemo(() => view.financial?.policy ?? explainScheme(plan.eligible && plan.tier ? plan.tier.name : null), [view.financial, plan]);
  const ruleSources = [...new Set(policy.rules.map((r) => fileName(r.source)))];

  const steps = plan.eligible && plan.tier
    ? [
        { title: t("scheme.how.margin"), body: t("scheme.how.marginBody", { v: rupeesShort(plan.projectCost - plan.loan, lang) }) },
        { title: t("scheme.how.project"), body: t("scheme.how.projectBody", { v: rupeesShort(plan.projectCost, lang) }) },
        { title: t("scheme.how.loan"), body: t(plan.capApplied ? "g3.scheme.loanCapped" : "scheme.how.loanBody", { v: rupeesShort(plan.loan, lang), pct: plan.loanPct.toFixed(1) }) },
        { title: t("scheme.how.moratorium"), body: t("scheme.how.moratoriumBody", { n: plan.tier.moratoriumMonths }) },
        { title: t("scheme.how.repay"), body: t("scheme.how.repayBody", { v: rupeesShort(plan.regularInstallment, lang), y: plan.tier.tenureYears }) },
      ]
    : null;

  return (
    <Screen title={t("scheme.title")} subtitle={t("scheme.subtitle")}>
      <p className="mt-2 px-1 text-[15px] leading-snug text-ink-2">{t("scheme.intro")}</p>

      <Section title={t("scheme.tiers")}>
        <div className="space-y-3">
          {TIER_ORDER.map((name, i) => {
            const tier = TIERS[name];
            const applies = plan.tier?.name === name;
            return (
              <Reveal key={name} i={i}>
                <Card className={cx(applies && "ring-2 ring-forest-600")}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[17px] font-bold">{t(`plan.tier.${name}`)}</p>
                    {applies && (
                      <Badge tone="good" icon={BadgeCheck}>
                        {t("scheme.applies")}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-0.5 text-[13px] text-ink-3">{t("scheme.tierFor", { v: rupeesShort(tier.maxProjectCost, lang) })}</p>
                  <dl className="mt-3 grid grid-cols-2 gap-2">
                    {[
                      [t("plan.rate"), ratePct(tier.rate)],
                      [t("plan.tenure"), t("unit.years", { n: tier.tenureYears })],
                      [t("plan.moratorium"), t("unit.months", { n: tier.moratoriumMonths })],
                      [t("scheme.loanCap"), rupeesShort(tier.maxLoan, lang)],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded-xl bg-sand px-3 py-2">
                        <dt className="text-[11px] text-ink-3">{k}</dt>
                        <dd className="tabular text-[15px] font-semibold">{v}</dd>
                      </div>
                    ))}
                  </dl>
                </Card>
              </Reveal>
            );
          })}
          {!plan.eligible && (
            <Note tone="marigold">{plan.projectCost > 0 ? t("g3.scheme.outside", { v: rupeesShort(plan.projectCost, lang) }) : t("g3.scheme.noCapital")}</Note>
          )}
        </div>
      </Section>

      {steps && (
        <Section title={t("scheme.how.title")}>
          <Card>
            <ol className="space-y-3">
              {steps.map((s, i) => (
                <li key={i} className="flex gap-3">
                  <span className="tabular grid size-8 shrink-0 place-items-center rounded-full bg-forest-800 text-sm font-bold text-white">{i + 1}</span>
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold">{s.title}</p>
                    <p className="text-[13px] leading-snug text-ink-2">{s.body}</p>
                  </div>
                </li>
              ))}
            </ol>
            <div className="mt-3">
              <RulesChip />
            </div>
          </Card>
        </Section>
      )}

      {policy.rules.length > 0 && (
        <Section title={t("g3.scheme.rules")}>
          <div className="space-y-2">
            {policy.rules.map((r: PackDoc, i) => {
              const open = openRule === i;
              return (
                <div key={`${r.source}-${r.heading}`} className="overflow-hidden rounded-2xl bg-white shadow-[var(--shadow-card)]">
                  <button onClick={() => setOpenRule(open ? null : i)} className="flex min-h-14 w-full items-center gap-3 px-4 text-left" aria-expanded={open}>
                    <ScrollText className="size-5 shrink-0 text-forest-700" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[15px] font-semibold break-words">{r.heading}</span>
                      <span className="block text-[11px] text-ink-3">{fileName(r.source)}</span>
                    </span>
                    <ChevronDown className={cx("size-5 shrink-0 text-ink-3 transition-transform", open && "rotate-180")} />
                  </button>
                  <AnimatePresence initial={false}>
                    {open && (
                      <motion.ul initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} transition={{ duration: 0.22 }} className="space-y-1 px-4 pb-4 text-[14px] leading-snug text-ink-2">
                        {lines(r.text).map((l, li) => (
                          <li key={li}>{l}</li>
                        ))}
                      </motion.ul>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
          {lang !== "en" && <p className="mt-2 px-1 text-[12px] text-ink-3">{t("g3.scheme.englishSource")}</p>}
        </Section>
      )}

      <Section title={t("scheme.docs")}>
        {policy.documents.length > 0 ? (
          <Card className="py-2">
            <ul className="divide-y divide-line">
              {policy.documents.map((d) => (
                <li key={d} className="flex min-h-11 items-center gap-2.5 py-1.5 text-[15px]">
                  <FileText className="size-4.5 shrink-0 text-forest-700" />
                  <span className="min-w-0 break-words">{d}</span>
                </li>
              ))}
            </ul>
            <p className="pb-1 text-[11px] text-ink-3">{t("g3.scheme.source", { files: DOC_SOURCE })}</p>
          </Card>
        ) : (
          <Note>{t("g3.scheme.docsNeedTier")}</Note>
        )}
      </Section>

      {policy.steps.length > 0 && (
        <Section title={t("scheme.steps")}>
          <Card>
            <ol className="relative">
              {policy.steps.map((s, i) => (
                <li key={s} className="relative flex gap-3 pb-4 last:pb-0">
                  {i < policy.steps.length - 1 && <span className="absolute top-6 bottom-0 left-[11px] w-0.5 bg-forest-100" />}
                  <span className="relative mt-0.5 size-6 shrink-0 rounded-full border-4 border-forest-100 bg-forest-600" />
                  <p className="min-w-0 text-[14px] leading-snug">{s}</p>
                </li>
              ))}
            </ol>
            <p className="mt-2 text-[11px] text-ink-3">{t("g3.scheme.source", { files: STEP_SOURCE })}</p>
          </Card>
        </Section>
      )}

      <Section title={t("scheme.faq")}>
        <div className="space-y-2">
          {FAQ.map((id) => {
            const open = openFaq === id;
            return (
              <div key={id} className="overflow-hidden rounded-2xl bg-white shadow-[var(--shadow-card)]">
                <button onClick={() => setOpenFaq(open ? null : id)} className="flex min-h-14 w-full items-center gap-3 px-4 text-left" aria-expanded={open}>
                  <span className="flex-1 text-[15px] font-semibold">{t(`scheme.faq.${id}.q`)}</span>
                  <ChevronDown className={cx("size-5 shrink-0 text-ink-3 transition-transform", open && "rotate-180")} />
                </button>
                <AnimatePresence initial={false}>
                  {open && (
                    <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} transition={{ duration: 0.22 }}>
                      <p className="px-4 pb-4 text-[15px] leading-snug text-ink-2">{t(`scheme.faq.${id}.a`)}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </Section>

      <p className="mt-6 px-1 text-center text-[11px] leading-snug text-ink-3">{t("g3.scheme.sources", { files: [...new Set([...ruleSources, DOC_SOURCE, STEP_SOURCE])].join(", ") })}</p>
    </Screen>
  );
}
