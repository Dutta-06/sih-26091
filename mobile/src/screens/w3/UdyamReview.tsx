import { BadgeCheck, CheckCircle2, Copy } from "lucide-react";
import { motion } from "motion/react";
import { maskAadhaar } from "../../core/documents";
import { useI18n } from "../../i18n";
import { useCase } from "../../state/store";
import { Card, Note, toast } from "../../ui";
import { useApplicant } from "../g3/applicant";
import { placeOf } from "../g3/model";
import { shownValue, type Field, type Section } from "./udyamFields";

const SECTIONS: Section[] = ["identity", "enterprise", "money", "bank"];

/** The filled form, laid out like the portal's sections with a tick on every field. */
export function UdyamReview({ fields, answers }: { fields: Field[]; answers: Record<string, string> }) {
  const { t, pick } = useI18n();
  const [applicant] = useApplicant();
  const place = placeOf(useCase());
  const address = place ? [place.village && pick(place.village), place.block && pick(place.block), pick(place.district.name), place.district.state, applicant.pincode].filter(Boolean).join(", ") : "—";
  const extra: Partial<Record<Section, [string, string][]>> = {
    identity: [
      [t("udyam.form.owner"), applicant.fullName ?? t("g3.udyam.nameMissing")],
      [t("udyam.otp.aadhaar"), applicant.aadhaarLast4 ? maskAadhaar(applicant.aadhaarLast4) : "—"],
    ],
    enterprise: [[t("udyam.form.address"), address]],
  };
  return (
    <div className="overflow-hidden rounded-[var(--radius-card)] bg-white shadow-[var(--shadow-card)]">
      <div className="border-b-4 border-marigold-500 bg-forest-800 px-4 py-3 text-white">
        <p className="text-[11px] tracking-wide text-forest-100 uppercase">{t("udyam.form.ministry")}</p>
        <p className="text-[17px] font-bold">{t("udyam.form.heading")}</p>
      </div>
      {SECTIONS.map((s, si) => {
        const rows: [string, string][] = [...(extra[s] ?? []), ...fields.filter((f) => f.section === s).map((f) => [t(`udyam.label.${f.id}`), shownValue(f, answers[f.id], t, applicant)] as [string, string])];
        return (
          <section key={s} className="px-4 pt-3 pb-1">
            <p className="text-[12px] font-bold tracking-wide text-ink-3 uppercase">
              {si + 1}. {t(`udyam.section.${s}`)}
            </p>
            <ul className="mt-1 divide-y divide-dashed divide-line">
              {rows.map(([k, v]) => (
                <li key={k} className="flex items-start gap-2.5 py-2">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-forest-600" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] text-ink-3">{k}</p>
                    <p className="tabular text-[15px] leading-snug font-medium break-words">{v}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      <div className="px-4 pt-2 pb-4">
        <Note>{t("udyam.form.declaration")}</Note>
      </div>
    </div>
  );
}

/** Registration success card (also shown when the Udyam document is already complete). */
export function UdyamSuccess({ fresh, number }: { fresh: boolean; number: string | null }) {
  const { t } = useI18n();
  return (
    <Card tone="forest" className="relative overflow-hidden text-center">
      <motion.div initial={fresh ? { scale: 0.4, rotate: -20 } : false} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 260, damping: 14 }} className="mx-auto grid size-16 place-items-center rounded-full bg-marigold-500 text-forest-950">
        <BadgeCheck className="size-9" />
      </motion.div>
      <p className="mt-3 text-[20px] font-bold">{t(fresh ? "udyam.success.title" : "udyam.success.already")}</p>
      <p className="mt-1 text-[13px] text-forest-100">{t("udyam.success.numberLabel")}</p>
      {number ? (
        <button
          onClick={() => navigator.clipboard?.writeText(number).then(() => toast(t("g3.udyam.copied")), () => undefined)}
          className="tabular mt-1 inline-flex max-w-full items-center gap-2 rounded-xl bg-white/12 px-3 py-2 text-[16px] font-bold tracking-wide break-all"
        >
          {number}
          <Copy className="size-4 shrink-0 text-forest-100" />
        </button>
      ) : (
        <p className="mt-1 text-[15px] font-semibold">{t("g3.udyam.numberElsewhere")}</p>
      )}
      <p className="mt-3 text-[13px] leading-snug text-forest-100">{t("g3.udyam.successBody")}</p>
    </Card>
  );
}
