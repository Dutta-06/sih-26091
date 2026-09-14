import { Lock } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { TierName } from "../../engine/finance";
import { useI18n } from "../../i18n";
import { cx } from "../../ui";

/** "Calculated by fixed rules, not AI" cue shown next to money figures. */
export function RulesChip({ light }: { light?: boolean }) {
  const { t } = useI18n();
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold", light ? "bg-white/12 text-azure-50 ring-1 ring-white/20" : "bg-azure-50 text-azure-800 ring-1 ring-azure-100")}>
      <Lock className="size-3" />
      {t("plan.rulesChip")}
    </span>
  );
}

/** Reminder that loan figures follow fixed scheme rules. */
export function RulesNote() {
  const { t } = useI18n();
  return <p className="mt-6 px-2 text-center text-[11px] leading-snug text-ink-3">{t("g3.pack.rules")}</p>;
}

/** Scheme tier badge that springs when the tier switches. */
export function TierBadge({ tier, light }: { tier: TierName | null; light?: boolean }) {
  const { t } = useI18n();
  const key = tier ?? "outside";
  const tone = tier === "micro_finance" ? (light ? "bg-marigold-500 text-azure-950" : "bg-azure-100 text-azure-800") : tier === "term_loan" ? "bg-sky-100 text-sky-700" : "bg-clay-100 text-clay-700";
  return (
    <span className="relative inline-grid overflow-hidden">
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={key}
          initial={{ y: 14, opacity: 0, scale: 0.9 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          exit={{ y: -14, opacity: 0 }}
          transition={{ type: "spring", stiffness: 420, damping: 26 }}
          className={cx("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold", tone)}
        >
          {t(`plan.tier.${key}`)}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}
