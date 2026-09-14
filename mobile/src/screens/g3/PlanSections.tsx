import { CircleAlert, FileSearch, MessageCircle, Table2 } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import type { FinancialResult } from "../../core/types";
import type { Plan } from "../../engine/finance";
import { useI18n } from "../../i18n";
import { rupees, rupeesShort } from "../../lib/format";
import { BarChart } from "../../ui/charts";
import { Button, Card, Note, Sheet, Stat } from "../../ui";
import { RulesChip, TierBadge } from "./bits";
import { activityDisplay, ratePct } from "./util";

export function PlanHero({ plan, activityId, whatIf }: { plan: Plan; activityId: string; whatIf: boolean }) {
  const { t, pick, lang } = useI18n();
  const tier = plan.tier;
  const act = activityDisplay(activityId);
  return (
    <Card tone="forest" className="relative overflow-hidden">
      <div className="pointer-events-none absolute -top-14 -right-12 size-44 rounded-full bg-white/5" />
      <div className="relative flex items-start justify-between gap-2">
        <p className="min-w-0 text-sm break-words text-forest-100">
          {act.emoji} {t("plan.hero.title", { activity: pick(act.name) })}
        </p>
        {whatIf && <span className="shrink-0 rounded-full bg-marigold-500 px-2 py-0.5 text-[11px] font-bold text-forest-950">{t("g3.plan.whatIfBadge")}</span>}
      </div>
      {plan.eligible && tier ? (
        <>
          <p className="mt-3 text-xs text-forest-100">{t("plan.hero.loanLabel")}</p>
          <motion.p key={plan.loan} initial={{ opacity: 0.4, y: 4 }} animate={{ opacity: 1, y: 0 }} className="tabular text-[40px] leading-tight font-bold">
            {rupees(plan.loan)}
          </motion.p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <TierBadge tier={tier.name} light />
            <RulesChip light />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-white/15 pt-4">
            <Stat tone="light" label={t("plan.rate")} value={ratePct(tier.rate)} hint={t("plan.rateHint")} />
            <Stat tone="light" label={t("plan.tenure")} value={t("unit.years", { n: tier.tenureYears })} />
            <Stat tone="light" label={t("plan.moratorium")} value={t("unit.months", { n: tier.moratoriumMonths })} hint={t("plan.moratoriumHint")} />
            <Stat tone="light" label={t("plan.instalment")} value={rupees(plan.regularInstallment)} hint={t("unit.perQuarter")} />
          </div>
        </>
      ) : plan.projectCost <= 0 ? (
        <div className="mt-3 flex items-start gap-2 text-[15px]">
          <CircleAlert className="mt-0.5 size-5 shrink-0 text-marigold-500" />
          <p>{t("g3.plan.noCapital")}</p>
        </div>
      ) : (
        <div className="mt-3 flex items-start gap-2 text-[15px]">
          <CircleAlert className="mt-0.5 size-5 shrink-0 text-marigold-500" />
          <p>{t("plan.outside.hero", { cost: rupeesShort(plan.projectCost, lang) })}</p>
        </div>
      )}
    </Card>
  );
}

export function EmptyPlan({ onAsk, onReport, hasProfile }: { onAsk: () => void; onReport: () => void; hasProfile: boolean }) {
  const { t } = useI18n();
  return (
    <Card tone="marigold">
      <p className="text-[17px] font-semibold">{t(hasProfile ? "g3.plan.emptyProfiled.title" : "plan.empty.title")}</p>
      <p className="mt-1 text-[15px] leading-snug text-ink-2">{t(hasProfile ? "g3.plan.emptyProfiled.body" : "plan.empty.body")}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="primary" size="md" icon={MessageCircle} onClick={onAsk}>
          {t("plan.empty.cta")}
        </Button>
        {hasProfile && (
          <Button variant="secondary" size="md" icon={FileSearch} onClick={onReport}>
            {t("g3.plan.empty.report")}
          </Button>
        )}
      </div>
    </Card>
  );
}

/** Budget from the core split (catalog key inputs + working capital); amounts always sum to the project cost. */
export function Budget({ plan, budget }: { plan: Plan; budget: FinancialResult["budget"] }) {
  const { t, pick } = useI18n();
  return (
    <Card>
      <ul className="divide-y divide-line">
        {budget.map((r, i) => (
          <li key={i} className="py-2.5">
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 text-[15px] break-words">{pick(r.item)}</span>
              <span className="tabular shrink-0 font-semibold">{rupees(r.amount)}</span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-3/10">
              <motion.div animate={{ width: `${plan.projectCost > 0 ? (r.amount / plan.projectCost) * 100 : 0}%` }} className="h-full rounded-full bg-forest-600" />
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex items-baseline justify-between border-t border-line pt-3">
        <span className="font-semibold">{t("plan.projectCost")}</span>
        <span className="tabular text-lg font-bold text-forest-800">{rupees(plan.projectCost)}</span>
      </div>
      <div className="mt-3">
        <Note>{t("g3.plan.budgetNote", { wc: rupees(plan.workingCapital), capex: rupees(plan.capex) })}</Note>
      </div>
    </Card>
  );
}

export function Repayment({ plan }: { plan: Plan }) {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState(false);
  const data = plan.schedule.map((i) => ({ label: `Q${i.quarter}`, value: i.payment, tone: i.isMoratorium ? ("marigold" as const) : ("forest" as const) }));
  return (
    <Card>
      <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-marigold-500" />
          {t("plan.schedule.legendMoratorium")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-forest-600" />
          {t("plan.schedule.legendRegular")}
        </span>
      </div>
      <BarChart data={data} height={120} maxLabels={7} />
      <p className="mt-2 text-[13px] leading-snug text-ink-3">
        {t("plan.schedule.caption", { mor: rupees(plan.moratoriumInstallment), reg: rupees(plan.regularInstallment), n: plan.schedule.length })}
      </p>
      <div className="mt-3 grid grid-cols-2 gap-3 border-t border-line pt-3">
        <Stat label={t("plan.schedule.totalInterest")} value={rupeesShort(plan.totalInterest, lang)} />
        <Stat label={t("plan.schedule.totalRepayment")} value={rupeesShort(plan.totalRepayment, lang)} tone="forest" />
      </div>
      <Button variant="secondary" size="md" icon={Table2} className="mt-3 w-full" onClick={() => setOpen(true)}>
        {t("plan.schedule.open")}
      </Button>
      <Sheet open={open} onClose={() => setOpen(false)} title={t("plan.schedule.sheetTitle")}>
        <div className="overflow-x-auto rounded-2xl bg-white">
          <table className="tabular w-full text-right text-[13px]">
            <thead className="bg-sand text-[11px] text-ink-3 uppercase">
              <tr>
                <th className="px-2 py-2 text-left">{t("plan.schedule.q")}</th>
                <th className="px-2 py-2">{t("plan.schedule.interest")}</th>
                <th className="px-2 py-2">{t("plan.schedule.principal")}</th>
                <th className="px-2 py-2">{t("plan.schedule.payment")}</th>
                <th className="px-2 py-2">{t("plan.schedule.balance")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {plan.schedule.map((i) => (
                <tr key={i.quarter} className={i.isMoratorium ? "bg-marigold-50" : undefined}>
                  <td className="px-2 py-2 text-left font-medium">Q{i.quarter}</td>
                  <td className="px-2 py-2">{rupees(i.interest)}</td>
                  <td className="px-2 py-2">{rupees(i.principal)}</td>
                  <td className="px-2 py-2 font-semibold">{rupees(i.payment)}</td>
                  <td className="px-2 py-2 text-ink-3">{rupees(i.closing)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-sand font-semibold">
              <tr>
                <td className="px-2 py-2 text-left">{t("plan.schedule.total")}</td>
                <td className="px-2 py-2">{rupees(plan.totalInterest)}</td>
                <td className="px-2 py-2">{rupees(plan.loan)}</td>
                <td className="px-2 py-2">{rupees(plan.totalRepayment)}</td>
                <td className="px-2 py-2" />
              </tr>
            </tfoot>
          </table>
        </div>
        <Button className="mt-4 w-full" onClick={() => setOpen(false)}>
          {t("action.close")}
        </Button>
      </Sheet>
    </Card>
  );
}
