import { LANG_INFO } from "../../i18n";
import { BellRing, CalendarDays } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import type { Plan } from "../../engine/finance";
import { useI18n } from "../../i18n";
import { rupees } from "../../lib/format";
import { Badge, Card, Toggle, cx } from "../../ui";
import { addMonthsIso, dueDates } from "../g3/model";

const asDate = (iso: string) => new Date(`${iso}T00:00:00Z`);

/**
 * Due dates from the engine schedule, counted from the real disbursal date, or projected from today when the
 * loan is not disbursed yet. Shows the next six from today, with a local reminder toggle.
 */
export function RepaymentCalendar({ plan, startIso, projected, today }: { plan: Plan; startIso: string; projected: boolean; today: string }) {
  const { t, lang } = useI18n();
  const [remind, setRemind] = useState(false);
  const fmt = new Intl.DateTimeFormat(LANG_INFO[lang].dateLocale, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const fmtShort = new Intl.DateTimeFormat(LANG_INFO[lang].dateLocale, { day: "numeric", month: "short", timeZone: "UTC" });
  const all = dueDates(startIso, plan.schedule);
  const paidCount = all.filter((i) => i.due < today).length;
  const rows = all.slice(Math.min(paidCount, Math.max(0, all.length - 6)), Math.min(paidCount, Math.max(0, all.length - 6)) + 6);
  if (!rows.length) return null;

  return (
    <Card>
      <div className="flex items-center gap-2">
        <CalendarDays className="size-5 text-azure-700" />
        <p className="text-[15px] font-semibold">{t("g3.cal.title", { n: rows.length })}</p>
      </div>
      <p className="mt-0.5 text-[13px] leading-snug text-ink-3">{projected ? t("g3.cal.projected", { d: fmt.format(asDate(startIso)) }) : t("g3.cal.fromDisbursal", { d: fmt.format(asDate(startIso)), paid: paidCount })}</p>
      <ol className="mt-3 divide-y divide-line">
        {rows.map((i) => {
          const due = asDate(i.due);
          const next = i.due >= today && (i.quarter === 1 || all[i.quarter - 2].due < today);
          return (
            <li key={i.quarter} className="flex min-h-14 items-center gap-3 py-2">
              <span className={cx("grid w-12 shrink-0 place-items-center rounded-xl py-1.5 text-center leading-tight", i.isMoratorium ? "bg-marigold-100 text-marigold-600" : "bg-azure-100 text-azure-800")}>
                <span className="tabular text-[17px] font-bold">{due.getUTCDate()}</span>
                <span className="text-[10px] font-semibold">{fmtShort.formatToParts(due).find((p) => p.type === "month")?.value}</span>
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-medium">{fmt.format(due)}</p>
                <p className="text-[12px] text-ink-3">
                  {i.isMoratorium ? t("cal.interestOnly") : t("cal.regular")} · Q{i.quarter}
                  {next && !projected && <span className="ml-1.5 font-semibold text-azure-700">· {t("g3.cal.next")}</span>}
                </p>
                <AnimatePresence>
                  {remind && (
                    <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="flex items-center gap-1 text-[12px] font-semibold text-sky-700">
                      <BellRing className="size-3.5" />
                      {t("cal.reminderOn", { d: fmtShort.format(asDate(addMonthsIso(startIso, i.quarter * 3, 3))) })}
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
              <span className="tabular shrink-0 font-semibold">{rupees(i.payment)}</span>
            </li>
          );
        })}
      </ol>
      <div className="mt-2 flex items-center gap-3 rounded-2xl bg-sand px-3 py-2.5">
        <BellRing className="size-5 shrink-0 text-azure-700" />
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-medium leading-snug">{t("cal.remind")}</p>
          <p className="text-[12px] text-ink-3">{t("cal.remindSub")}</p>
        </div>
        <Toggle checked={remind} onChange={setRemind} label={t("cal.remind")} />
      </div>
      {remind && (
        <div className="mt-2">
          <Badge tone="good">{t("cal.saved")}</Badge>
        </div>
      )}
    </Card>
  );
}
