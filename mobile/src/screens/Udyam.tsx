import { CheckCircle2, CircleAlert, FileCheck2, Loader2, RotateCcw, Send } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { tap } from "../App";
import { validateField } from "../core/documents";
import { useI18n } from "../i18n";
import { useNav } from "../nav";
import { useStore } from "../state/store";
import { Button, Card, Note, Progress, Screen, Section, Segmented } from "../ui";
import { useApplicant } from "./g3/applicant";
import { PackNote } from "./g3/bits";
import { placeOf, udyamNumber } from "./g3/model";
import { activityDisplay } from "./g3/util";
import { LoanForm } from "./w3/LoanForm";
import { shownValue, udyamTab, useUdyamFields } from "./w3/udyamFields";
import { UdyamQuestion } from "./w3/UdyamQuestion";
import { UdyamReview, UdyamSuccess } from "./w3/UdyamReview";

type Tab = "register" | "form";
type Phase = "ask" | "review" | "submitting" | "done";
const DOC_ID = "udyam_certificate";

/** Conversational Udyam registration (simulated portal) + loan application form preview (TDD 6.5). */
export default function Udyam() {
  const { t, tm } = useI18n();
  const { state, dispatch, view } = useStore();
  const { pop, switchTab } = useNav();
  const fields = useUdyamFields();
  const [applicant, update] = useApplicant();
  const registered = state.documents[DOC_ID] === "complete";
  const place = placeOf(view);

  const [tab, setTab] = useState<Tab>(udyamTab.initial);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [phase, setPhase] = useState<Phase>(registered ? "done" : "ask");
  const [fresh, setFresh] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    udyamTab.initial = "register"; // one-shot deep link
  }, []);
  useEffect(() => {
    if (!registered && phase === "done") setPhase("ask");
  }, [registered, phase]);

  const current = fields.find((f) => !answers[f.id]);
  const answered = fields.filter((f) => answers[f.id]).length;

  const answer = useCallback(
    (value: string) => {
      if (!current) return;
      tap();
      if (current.id === "name") update({ enterpriseName: value });
      if (current.id === "ifsc" && current.kind === "text") update({ ifsc: value });
      const next = { ...answers, [current.id]: value };
      setAnswers(next);
      if (fields.every((f) => next[f.id])) setPhase("review");
    },
    [answers, current, fields, update],
  );

  useEffect(() => {
    if (phase !== "submitting") return;
    const id = setTimeout(() => {
      if (!place || !view.activityId || !applicant.aadhaarLast4 || !answers.name) {
        setSubmitError(t("g3.udyam.cannotSubmit"));
        setPhase("review");
        return;
      }
      const number = udyamNumber({
        districtId: place.district.id, stateName: place.district.state, nic: activityDisplay(view.activityId).nic,
        enterpriseName: answers.name, aadhaarLast4: applicant.aadhaarLast4, capital: state.profile.capital,
      });
      const check = validateField("udyam_registration_number", number);
      if (!check.ok) {
        setSubmitError(tm(check.error));
        setPhase("review");
        return;
      }
      update({ udyamNumber: check.value });
      dispatch({ type: "doc", id: DOC_ID, status: "complete" });
      setFresh(true);
      setPhase("done");
    }, 1600);
    return () => clearTimeout(id);
  }, [phase, dispatch, place, view.activityId, applicant.aadhaarLast4, answers.name, state.profile.capital, update, t, tm]);

  if (!view.activityId || fields.length === 0) {
    return (
      <Screen title={t("udyam.title")} subtitle={t("udyam.subtitle")}>
        <Card tone="marigold" className="mt-2">
          <p className="text-[17px] font-semibold">{t("g3.app.empty.title")}</p>
          <p className="mt-1 text-[15px] leading-snug text-ink-2">{t("g3.udyam.empty")}</p>
          <Button size="md" className="mt-3" onClick={() => switchTab("plan")}>
            {t("g3.docs.empty.toPlan")}
          </Button>
        </Card>
      </Screen>
    );
  }

  const footer =
    tab !== "register" ? undefined : phase === "review" ? (
      <Button className="w-full" icon={Send} disabled={!place} onClick={() => { setSubmitError(null); setPhase("submitting"); }}>
        {t("udyam.submit")}
      </Button>
    ) : phase === "submitting" ? (
      <Button className="w-full" disabled icon={Loader2}>
        {t("udyam.submitting")}
      </Button>
    ) : phase === "done" ? (
      <Button className="w-full" icon={FileCheck2} onClick={() => setTab("form")}>
        {t("udyam.toForm")}
      </Button>
    ) : undefined;

  return (
    <Screen title={t("udyam.title")} subtitle={t("udyam.subtitle")} footer={footer}>
      <div className="mt-2 flex justify-center">
        <Segmented<Tab>
          value={tab}
          onChange={setTab}
          options={[
            { value: "register", label: t("udyam.tab.register") },
            { value: "form", label: t("udyam.tab.form") },
          ]}
        />
      </div>

      {tab === "form" ? (
        <Section title={t("loanform.section")}>
          <LoanForm />
        </Section>
      ) : phase === "done" ? (
        <div className="mt-4 space-y-4">
          <UdyamSuccess fresh={fresh} number={applicant.udyamNumber ?? null} />
          <Note tone="azure" icon={CheckCircle2}>
            {t("udyam.success.docNote")}
          </Note>
          <Button variant="ghost" className="w-full" onClick={() => pop()}>
            {t("udyam.backDocs")}
          </Button>
        </div>
      ) : phase === "ask" && current ? (
        <>
          <div className="mt-4 px-1">
            <div className="mb-1.5 flex justify-between text-[12px] font-semibold text-ink-3">
              <span>{t("udyam.progress", { n: answered + 1, total: fields.length })}</span>
              <span>{t("g3.udyam.left", { n: fields.length - answered })}</span>
            </div>
            <Progress value={(answered / fields.length) * 100} />
          </div>
          <div className="mt-4">
            <UdyamQuestion field={current} onAnswer={answer} />
          </div>
          {answered > 0 && (
            <Section title={t("udyam.soFar")}>
              <ul className="space-y-1.5">
                {fields
                  .filter((f) => answers[f.id])
                  .map((f) => (
                    <motion.li key={f.id} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-[13px] shadow-[var(--shadow-card)]">
                      <CheckCircle2 className="size-4 shrink-0 text-azure-600" />
                      <span className="shrink-0 text-ink-3">{t(`udyam.label.${f.id}`)}</span>
                      <span className="tabular min-w-0 flex-1 truncate text-right font-semibold">{shownValue(f, answers[f.id], t, applicant)}</span>
                    </motion.li>
                  ))}
              </ul>
            </Section>
          )}
        </>
      ) : (
        <>
          <div className="mt-4 space-y-2">
            <Note tone="azure">{t("udyam.review.intro")}</Note>
            {!place && (
              <Note tone="clay" icon={CircleAlert}>
                {t("g3.form.noPlace")}
              </Note>
            )}
            {submitError && (
              <Note tone="clay" icon={CircleAlert}>
                {submitError}
              </Note>
            )}
          </div>
          <div className="mt-3">
            <UdyamReview fields={fields} answers={answers} />
          </div>
          <Button
            variant="ghost"
            className="mt-3 w-full"
            icon={RotateCcw}
            disabled={phase === "submitting"}
            onClick={() => {
              setAnswers({});
              setPhase("ask");
            }}
          >
            {t("udyam.review.edit")}
          </Button>
        </>
      )}

      <p className="mt-6 px-2 text-center text-[11px] leading-snug text-ink-3">{t("g3.udyam.simulated")}</p>
      <PackNote uses="rules" />
    </Screen>
  );
}
