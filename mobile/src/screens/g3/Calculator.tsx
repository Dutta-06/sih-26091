import { CircleAlert, RotateCcw, Save } from "lucide-react";
import { motion } from "motion/react";
import { MARGIN_SHARE, MICRO_MAX_PROJECT, TERM_MAX_PROJECT, type Plan } from "../../engine/finance";
import { useI18n } from "../../i18n";
import { rupees, rupeesShort } from "../../lib/format";
import { Button, Card, Note, Stat } from "../../ui";
import { RulesChip, TierBadge } from "./bits";
import { SavingsSlider, SLIDER_MAX, SLIDER_MIN } from "./SavingsSlider";

/**
 * What-if savings → loan calculator. The slider is local (nothing changes until the user commits); every figure
 * is recomputed by the deterministic engine. `onCommit` saves the amount to the profile so the whole case re-runs.
 */
export function Calculator({ plan, capital, savedCapital, onChange, onCommit }: { plan: Plan; capital: number; savedCapital: number; onChange: (v: number) => void; onCommit: (v: number) => void }) {
  const { t, lang } = useI18n();
  const microCapital = MICRO_MAX_PROJECT * MARGIN_SHARE;
  const termCapital = TERM_MAX_PROJECT * MARGIN_SHARE;

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[13px] text-ink-3">{t("plan.calc.savings")}</p>
          <p className="tabular text-[32px] leading-tight font-bold text-azure-900">{rupees(capital)}</p>
        </div>
        <div className="pt-1">
          <TierBadge tier={plan.tier?.name ?? null} />
        </div>
      </div>

      <div className="mt-3">
        <SavingsSlider
          value={capital}
          onChange={onChange}
          label={t("plan.calc.savings")}
          minLabel={rupeesShort(SLIDER_MIN, lang)}
          maxLabel={rupeesShort(SLIDER_MAX, lang)}
          marks={[
            { value: microCapital, label: t("plan.calc.markTerm", { v: rupeesShort(microCapital, lang) }) },
            { value: termCapital, label: t("plan.calc.markLimit", { v: rupeesShort(termCapital, lang) }) },
          ]}
        />
      </div>

      {capital !== savedCapital && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button size="md" icon={Save} onClick={() => onCommit(capital)}>
            {t("g3.plan.commit", { v: rupees(capital) })}
          </Button>
          {savedCapital > 0 && (
            <button onClick={() => onChange(savedCapital)} className="inline-flex min-h-11 items-center gap-1.5 px-2 text-sm font-semibold text-azure-700 active:opacity-70">
              <RotateCcw className="size-4" />
              {t("g3.plan.backToSaved", { v: rupees(savedCapital) })}
            </button>
          )}
        </div>
      )}

      {plan.eligible ? (
        <>
          <UnlockBar plan={plan} />
          <div className="mt-4 grid grid-cols-3 gap-3 border-t border-line pt-4">
            <Stat label={t("plan.projectCost")} value={rupeesShort(plan.projectCost, lang)} />
            <Stat label={t("plan.loan")} value={rupeesShort(plan.loan, lang)} tone="azure" />
            <Stat label={t("plan.instalmentShort")} value={rupeesShort(plan.regularInstallment, lang)} />
          </div>
          <div className="mt-3">
            <RulesChip />
          </div>
        </>
      ) : (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-4">
          <Note tone="clay" icon={CircleAlert}>
            <p className="font-semibold">{t("plan.outside.title")}</p>
            <p className="mt-0.5">{t("plan.outside.body", { cost: rupeesShort(plan.projectCost, lang), limit: rupeesShort(TERM_MAX_PROJECT, lang) })}</p>
          </Note>
        </motion.div>
      )}
    </Card>
  );
}

/** "Your ₹12,000 unlocks ₹1,20,000" stacked bar. */
function UnlockBar({ plan }: { plan: Plan }) {
  const { t, lang } = useI18n();
  const you = plan.marginPct;
  return (
    <div className="mt-4 rounded-2xl bg-sand p-3.5">
      <p className="text-[15px] leading-snug font-semibold">
        {t("plan.unlock.title", { capital: rupees(plan.capital), project: rupees(plan.projectCost) })}
      </p>
      <div className="mt-3 flex h-9 overflow-hidden rounded-xl text-xs font-bold">
        <motion.div animate={{ width: `${you}%` }} transition={{ type: "spring", stiffness: 200, damping: 30 }} className="grid min-w-9 place-items-center bg-marigold-500 text-azure-950">
          {Math.round(you)}%
        </motion.div>
        <div className="grid flex-1 place-items-center bg-azure-700 text-white">{Math.round(plan.loanPct)}%</div>
      </div>
      <div className="mt-2 flex justify-between gap-3 text-[13px]">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-marigold-500" />
          {t("plan.unlock.you", { v: rupeesShort(plan.projectCost - plan.loan, lang) })}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-azure-700" />
          {t("plan.unlock.loan", { v: rupeesShort(plan.loan, lang) })}
        </span>
      </div>
      {plan.capApplied && plan.tier && (
        <p className="mt-2 text-xs leading-snug text-marigold-600">
          {t("plan.unlock.capped", { cap: rupees(plan.tier.maxLoan), loanPct: plan.loanPct.toFixed(1), youPct: plan.marginPct.toFixed(1) })}
        </p>
      )}
    </div>
  );
}
