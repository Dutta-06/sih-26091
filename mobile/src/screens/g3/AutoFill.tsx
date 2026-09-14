import { Check, Mic, Pencil, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { tap } from "../../App";
import { canListen, listen } from "../../lib/speech";
import { maskAccount, validateField, type Field } from "../../core/documents";
import { useI18n } from "../../i18n";
import { rupees } from "../../lib/format";
import { useStore } from "../../state/store";
import { Badge, Button, Card, Chip } from "../../ui";
import { maskPhone, useApplicant, type Applicant } from "./applicant";
import { placeOf } from "./model";
import { activityDisplay } from "./util";

type QuestionId = "fullName" | "phone" | "pincode" | "ifsc" | "account" | "premises";

interface TextQuestion {
  id: Exclude<QuestionId, "premises">;
  field: Field;
  inputMode: "text" | "numeric" | "tel";
  /** What is kept on the phone after validation (masked where sensitive). */
  store: (value: string) => Partial<Applicant>;
  shown: (a: Applicant) => string | undefined;
}

const TEXT_QUESTIONS: TextQuestion[] = [
  { id: "fullName", field: "full_name", inputMode: "text", store: (v) => ({ fullName: v }), shown: (a) => a.fullName },
  { id: "phone", field: "phone_number", inputMode: "tel", store: (v) => ({ phoneMasked: maskPhone(v) }), shown: (a) => a.phoneMasked },
  { id: "pincode", field: "pincode", inputMode: "numeric", store: (v) => ({ pincode: v }), shown: (a) => a.pincode },
  { id: "ifsc", field: "ifsc_code", inputMode: "text", store: (v) => ({ ifsc: v }), shown: (a) => a.ifsc },
  { id: "account", field: "bank_account_number", inputMode: "numeric", store: (v) => ({ accountMasked: maskAccount(v) }), shown: (a) => a.accountMasked },
];

const PREMISES = ["home", "rented_shop", "own_land"] as const;

/** One validated text answer (core validateField); shows the core's error message. */
export function FieldInput({ field, inputMode, label, onSave, initial = "", suggestions = [], voice = false, saveLabel }: { field: Field; inputMode: "text" | "numeric" | "tel"; label: string; onSave: (value: string) => void; initial?: string; suggestions?: string[]; voice?: boolean; saveLabel?: string }) {
  const { t, tm, lang } = useI18n();
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const stopRef = useRef<(() => void) | null>(null);
  useEffect(() => () => stopRef.current?.(), []);
  const mic = async () => {
    if (listening) return stopRef.current?.();
    tap();
    setListening(true);
    stopRef.current = await listen({
      lang,
      onPartial: (text) => setValue(text),
      onFinal: (text) => {
        setValue(text);
        setListening(false);
      },
      onError: (e) => {
        setListening(false);
        if (e !== "aborted") setError(t(`g3.voice.${e === "unavailable" || e === "permission" ? e : "failed"}`));
      },
    });
  };
  const save = () => {
    const r = validateField(field, value);
    if (!r.ok) return setError(tm(r.error));
    setError(null);
    onSave(r.value ?? value);
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
      className="mt-3"
    >
      {suggestions.length > 0 && (
        <div className="mb-2.5 flex flex-wrap gap-2">
          {suggestions.map((sg) => (
            <Chip key={sg} active={value === sg} onClick={() => setValue(sg)}>
              {sg}
            </Chip>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
      <input
        aria-label={label}
        inputMode={inputMode}
        autoComplete="off"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          if (error) setError(null);
        }}
        aria-invalid={!!error}
        className={`tabular min-h-12 w-full min-w-0 flex-1 rounded-xl bg-white px-3 text-[16px] ring-1 outline-none focus:ring-2 ${error ? "ring-clay-600" : "ring-line focus:ring-azure-600"}`}
      />
      {voice && canListen() && (
        <motion.button
          type="button"
          whileTap={{ scale: 0.92 }}
          onClick={mic}
          aria-label={t("udyam.mic")}
          className={`relative grid size-12 shrink-0 place-items-center rounded-full text-white ${listening ? "bg-clay-600" : "bg-azure-800"}`}
        >
          {listening && <motion.span className="absolute inset-0 rounded-full bg-clay-600/40" animate={{ scale: [1, 1.5], opacity: [0.7, 0] }} transition={{ repeat: Infinity, duration: 1 }} />}
          <Mic className="relative size-5" />
        </motion.button>
      )}
      </div>
      <AnimatePresence>
        {error && (
          <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} role="alert" className="mt-1.5 text-[13px] font-medium text-clay-700">
            {error}
          </motion.p>
        )}
      </AnimatePresence>
      <Button type="submit" size="md" icon={Check} className="mt-2.5 w-full">
        {saveLabel ?? t("g3.form.save")}
      </Button>
    </form>
  );
}

/** Application form pre-filled from the case (location, activity, plan); asks only what is still unknown, validated on the device. */
export function AutoFill() {
  const { t, pick } = useI18n();
  const { state, view, dispatch } = useStore();
  const [applicant, update] = useApplicant();
  const [editing, setEditing] = useState<QuestionId | null>(null);
  const place = placeOf(view);
  const plan = view.financial?.plan ?? null;
  const act = view.activityId ? activityDisplay(view.activityId) : null;
  const dash = "—";

  const filled: [string, string][] = [
    [t("docs.form.village"), place?.village ? pick(place.village) : dash],
    [t("g3.form.block"), place?.block ? pick(place.block) : dash],
    [t("docs.form.district"), place ? `${pick(place.district.name)}, ${place.district.state}` : dash],
    [t("docs.form.activity"), act ? pick(act.name) : dash],
    [t("docs.form.nic"), act ? act.nic : dash],
    [t("docs.form.projectCost"), plan && plan.projectCost > 0 ? rupees(plan.projectCost) : dash],
    [t("docs.form.loan"), plan?.eligible ? rupees(plan.loan) : dash],
  ];
  const autoCount = filled.filter(([, v]) => v !== dash).length;

  const answered = (id: QuestionId) => (id === "premises" ? state.profile.premises !== null : !!TEXT_QUESTIONS.find((q) => q.id === id)!.shown(applicant));
  const order: QuestionId[] = [...TEXT_QUESTIONS.map((q) => q.id), "premises"];
  const next = editing ?? order.find((id) => !answered(id)) ?? null;
  const answeredCount = order.filter(answered).length;
  const shownOf = (id: QuestionId) => (id === "premises" ? (state.profile.premises ? t(`g3.form.premises.${state.profile.premises}`) : "") : TEXT_QUESTIONS.find((q) => q.id === id)!.shown(applicant) ?? "");

  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[17px] font-semibold">{t("docs.form.title")}</p>
        <Badge tone="info" icon={Sparkles}>
          {t("docs.form.count", { n: autoCount + answeredCount, total: filled.length + order.length })}
        </Badge>
      </div>
      {!place && <p className="mt-1 text-[13px] text-marigold-600">{t("g3.form.noPlace")}</p>}
      <ul className="mt-2 divide-y divide-line">
        {filled.map(([k, v]) => (
          <li key={k} className="flex min-h-11 items-center justify-between gap-3 py-1.5">
            <div className="min-w-0">
              <p className="text-[11px] text-ink-3">{k}</p>
              <p className="text-[15px] font-medium break-words">{v}</p>
            </div>
            {v !== dash && (
              <span className="flex shrink-0 items-center gap-1 text-[11px] font-semibold text-azure-700">
                <Check className="size-3.5" />
                {t("docs.form.auto")}
              </span>
            )}
          </li>
        ))}
        {order.filter((id) => answered(id) && id !== editing).map((id) => (
          <li key={id} className="flex min-h-11 items-center justify-between gap-3 py-1.5">
            <div className="min-w-0">
              <p className="text-[11px] text-ink-3">{t(`g3.form.q.${id}.label`)}</p>
              <p className="tabular text-[15px] font-medium break-words">{shownOf(id)}</p>
            </div>
            <button onClick={() => setEditing(id)} aria-label={t("g3.form.edit")} className="flex min-h-11 shrink-0 items-center gap-1 px-1 text-[11px] font-semibold text-sky-700">
              <Pencil className="size-3.5" />
              {t("g3.form.edit")}
            </button>
          </li>
        ))}
      </ul>
      <AnimatePresence mode="wait">
        {next ? (
          <motion.div key={next} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} className="mt-3 rounded-2xl bg-azure-50 p-3.5 ring-1 ring-azure-100">
            <p className="text-[11px] font-semibold tracking-wide text-azure-700 uppercase">{t("g3.form.left", { n: order.length - answeredCount })}</p>
            <p className="mt-1 text-[15px] font-semibold">{t(`g3.form.q.${next}`)}</p>
            {next === "premises" ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {PREMISES.map((p) => (
                  <Chip
                    key={p}
                    active={state.profile.premises === p}
                    onClick={() => {
                      dispatch({ type: "profile", patch: { premises: p } });
                      setEditing(null);
                    }}
                  >
                    {t(`g3.form.premises.${p}`)}
                  </Chip>
                ))}
              </div>
            ) : (
              (() => {
                const q = TEXT_QUESTIONS.find((x) => x.id === next)!;
                return (
                  <>
                    <p className="mt-0.5 text-[12px] text-ink-3">{t(`g3.form.q.${next}.hint`)}</p>
                    <FieldInput
                      key={next}
                      field={q.field}
                      inputMode={q.inputMode}
                      label={t(`g3.form.q.${next}.label`)}
                      initial={q.id === "fullName" || q.id === "ifsc" || q.id === "pincode" ? q.shown(applicant) ?? "" : ""}
                      onSave={(v) => {
                        update(q.store(v));
                        setEditing(null);
                      }}
                    />
                  </>
                );
              })()
            )}
          </motion.div>
        ) : (
          <motion.p key="ready" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 flex items-center gap-2 rounded-2xl bg-azure-50 p-3 text-[15px] font-semibold text-azure-800">
            <Check className="size-5" />
            {t("docs.form.ready")}
          </motion.p>
        )}
      </AnimatePresence>
      <p className="mt-2 text-[11px] leading-snug text-ink-3">{t("g3.form.privacy")}</p>
    </Card>
  );
}
