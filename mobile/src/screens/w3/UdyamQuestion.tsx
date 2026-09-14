import { Check, KeyRound, ShieldCheck, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { maskAadhaar } from "../../core/documents";
import type { ProfileInput } from "../../core/types";
import { useI18n } from "../../i18n";
import { todayOf, useStore } from "../../state/store";
import { Badge, Button, Card, Chip } from "../../ui";
import { useApplicant } from "../g3/applicant";
import { FieldInput } from "../g3/AutoFill";
import { simulatedOtp } from "../g3/model";
import type { Field } from "./udyamFields";

/** One Udyam question at a time: confirm a computed value, a validated input, or chips. */
export function UdyamQuestion({ field, onAnswer }: { field: Field; onAnswer: (value: string) => void }) {
  const { t } = useI18n();
  const { dispatch } = useStore();

  return (
    <AnimatePresence mode="wait">
      <motion.div key={field.id} initial={{ opacity: 0, x: 28 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -28 }} transition={{ duration: 0.25 }}>
        <Card>
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold tracking-wide text-azure-700 uppercase">{t(`udyam.section.${field.section}`)}</p>
            {field.source !== "ask" && (
              <Badge tone="info" icon={Sparkles}>
                {t(`udyam.auto.${field.source}`)}
              </Badge>
            )}
          </div>
          <p className="mt-1.5 text-[19px] leading-snug font-semibold">{t(`g3.udyam.q.${field.id}`)}</p>

          {field.kind === "otp" ? (
            <OtpStep onDone={() => onAnswer("verified")} />
          ) : field.kind === "auto" ? (
            <>
              <div className="mt-3 rounded-2xl bg-azure-50 p-3.5 ring-1 ring-azure-100">
                <p className="tabular text-[20px] leading-snug font-bold break-words text-azure-800">{field.auto}</p>
                {field.hint && <p className="mt-1 text-[13px] leading-snug text-ink-2">{field.hint}</p>}
              </div>
              <Button className="mt-4 w-full" icon={Check} onClick={() => onAnswer("auto")}>
                {t("udyam.confirm")}
              </Button>
            </>
          ) : field.kind === "text" && field.validator ? (
            <FieldInput key={field.id} field={field.validator} inputMode="text" label={t(`udyam.label.${field.id}`)} suggestions={field.suggestions} voice={field.id === "name"} onSave={onAnswer} saveLabel={t("udyam.confirm")} />
          ) : (
            <div className="mt-3 flex flex-wrap gap-2">
              {field.options?.map((o) => (
                <Chip
                  key={o.value}
                  onClick={() => {
                    if (field.id === "category") dispatch({ type: "profile", patch: { category: o.value as ProfileInput["category"] } });
                    onAnswer(o.value);
                  }}
                >
                  {o.label}
                </Chip>
              ))}
            </div>
          )}
        </Card>
      </motion.div>
    </AnimatePresence>
  );
}

/** Aadhaar check: number validated on the device (Verhoeff), only the last 4 digits kept; the OTP is simulated. */
function OtpStep({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const { state } = useStore();
  const [applicant, update] = useApplicant();
  const [sent, setSent] = useState(false);
  const last4 = applicant.aadhaarLast4;

  if (!last4) {
    return (
      <>
        <p className="mt-1 text-[13px] text-ink-3">{t("g3.udyam.aadhaarAsk")}</p>
        <FieldInput field="aadhaar_number" inputMode="numeric" label={t("udyam.otp.aadhaar")} onSave={(v) => update({ aadhaarLast4: v.slice(-4) })} />
        <p className="mt-2 flex items-center gap-1.5 text-[12px] text-ink-3">
          <ShieldCheck className="size-4 text-azure-700" />
          {t("udyam.otp.privacy")}
        </p>
      </>
    );
  }

  const digits = simulatedOtp(last4, todayOf(state)).split("");
  return (
    <div className="mt-3">
      <div className="space-y-2 rounded-2xl bg-sand p-3 text-[13px]">
        <div className="flex justify-between gap-2">
          <span className="text-ink-3">{t("udyam.otp.aadhaar")}</span>
          <span className="tabular font-semibold">{maskAadhaar(last4)}</span>
        </div>
        <div className="flex justify-between gap-2">
          <span className="text-ink-3">{t("udyam.otp.mobile")}</span>
          <span className="tabular font-semibold">{applicant.phoneMasked ?? t("g3.udyam.noPhone")}</span>
        </div>
      </div>
      <button onClick={() => update({ aadhaarLast4: undefined })} className="mt-1 min-h-9 text-[12px] font-semibold text-sky-700">
        {t("g3.udyam.changeAadhaar")}
      </button>
      {sent ? (
        <>
          <div className="mt-2 flex justify-between gap-1.5">
            {digits.map((d, i) => (
              <motion.span
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 + i * 0.12 }}
                className="tabular grid h-12 flex-1 place-items-center rounded-xl bg-white text-xl font-bold ring-1 ring-azure-200"
              >
                {d}
              </motion.span>
            ))}
          </div>
          <p className="mt-2 text-[12px] text-ink-3">{t("udyam.otp.simulated")}</p>
          <Button className="mt-3 w-full" icon={Check} onClick={onDone}>
            {t("udyam.otp.verify")}
          </Button>
        </>
      ) : (
        <Button className="mt-3 w-full" icon={KeyRound} onClick={() => setSent(true)}>
          {t("udyam.otp.send")}
        </Button>
      )}
    </div>
  );
}
