import { Database } from "lucide-react";
import { motion } from "motion/react";
import { INTERVENTIONS } from "../../core/outcomes";
import { outcomeSeed } from "../../core/pack";
import { useI18n } from "../../i18n";
import { useStore } from "../../state/store";
import { Card, Note, Progress, Section, Stat } from "../../ui";

/** Lender view: outcome learning over the bundled synthetic seed plus real follow-ups recorded on this device (TDD 7.5). */
export function OutcomeLearning() {
  const { t } = useI18n();
  const { state } = useStore();
  const records = [...outcomeSeed(), ...state.realOutcomes];
  const real = records.filter((r) => !r.is_synthetic).length;
  const synthetic = records.length - real;
  const share = records.length ? Math.round((synthetic / records.length) * 100) : 0;
  const rows = INTERVENTIONS.map((type) => {
    const rs = records.filter((r) => r.intervention_type === type);
    const improved = rs.filter((r) => r.health_after > r.health_before).length;
    return { type, n: rs.length, real: rs.filter((r) => !r.is_synthetic).length, pct: rs.length ? Math.round((improved / rs.length) * 100) : null };
  }).sort((a, b) => (b.pct ?? -1) - (a.pct ?? -1));

  return (
    <Section title={t("w4.agency.learning")}>
      <Card>
        <div className="grid grid-cols-2 gap-3">
          <Stat label={t("w4.agency.real")} value={real} tone="forest" />
          <Stat label={t("w4.agency.synthetic")} value={synthetic} />
        </div>

        <p className="mt-4 text-[13px] font-semibold text-ink-2">{t("u4.agency.share")}</p>
        <div className="mt-2 flex items-center gap-2 text-[13px]">
          <div className="flex h-3.5 flex-1 overflow-hidden rounded-full bg-forest-600">
            <motion.div initial={{ width: 0 }} animate={{ width: `${share}%` }} transition={{ duration: 0.6, ease: "easeOut" }} className="h-full bg-marigold-500" />
          </div>
          <span className="tabular w-10 shrink-0 text-right font-semibold">{share}%</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-marigold-500" />{t("w4.agency.legend.synthetic")}</span>
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-forest-600" />{t("w4.agency.legend.real")}</span>
        </div>

        <p className="mt-4 text-[13px] font-semibold text-ink-2">{t("u4.agency.success")}</p>
        <div className="mt-2 grid gap-3">
          {rows.map((p) => (
            <div key={p.type}>
              <div className="flex items-baseline justify-between gap-2">
                <p className="min-w-0 text-[15px] font-medium">
                  {t(`u4.intervention.${p.type}`)} <span className="text-[13px] font-normal text-ink-3">· {t("u4.agency.records", { n: p.n, real: p.real })}</span>
                </p>
                <span className="tabular text-[15px] font-semibold">{p.pct === null ? "—" : `${p.pct}%`}</span>
              </div>
              {p.pct !== null && <Progress value={p.pct} tone={p.pct >= 65 ? "forest" : "marigold"} className="mt-1.5" />}
            </div>
          ))}
        </div>
        <div className="mt-3">
          <Note tone="marigold" icon={Database}>{t("w4.agency.learning.note")}</Note>
        </div>
      </Card>
    </Section>
  );
}
