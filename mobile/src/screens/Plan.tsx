import { BookOpen, Calculator as CalcIcon, CircleAlert, FileCheck2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { tap } from "../App";
import { buildFinancial, catalogEntry } from "../core/financial";
import { buildPlan, MARGIN_SHARE } from "../engine/finance";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useNav } from "../nav";
import { todayOf, useStore } from "../state/store";
import { Button, Card, ListRow, Note, Reveal, Section, TabScreen, toast } from "../ui";
import { RulesNote } from "./g3/bits";
import { Calculator } from "./g3/Calculator";
import { Budget, EmptyPlan, PlanHero, Repayment } from "./g3/PlanSections";
import { SLIDER_MIN } from "./g3/SavingsSlider";
import { CoverageCard, StressTests } from "./g3/StressTests";
import { RepaymentCalendar } from "./w3/RepaymentCalendar";

export default function Plan() {
  const { t, tm } = useI18n();
  const { state, dispatch, view } = useStore();
  const { push, switchTab } = useNav();
  const saved = state.profile.capital;
  const activityId = view.activityId;

  // What-if savings: local until the user commits. Starts at the saved savings, else the activity's minimum own share.
  const startValue = saved > 0 ? saved : activityId ? Math.max(SLIDER_MIN, Math.round(catalogEntry(activityId).min_project_cost * MARGIN_SHARE)) : SLIDER_MIN;
  const [draft, setDraft] = useState<number | null>(null);
  const value = draft ?? startValue;
  const whatIf = value !== saved;
  useEffect(() => setDraft(null), [saved, activityId]);

  const financial = useMemo(
    () => (!activityId ? null : !whatIf ? view.financial : buildFinancial({ ...state.profile, capital: value }, activityId, view.intel)),
    [activityId, whatIf, value, view.financial, view.intel, state.profile],
  );
  const plan = useMemo(() => financial?.plan ?? buildPlan(value), [financial, value]);

  // light haptic whenever the slider crosses a scheme tier boundary
  const tierKey = plan.tier?.name ?? "outside";
  const lastTier = useRef(tierKey);
  useEffect(() => {
    if (lastTier.current !== tierKey) tap();
    lastTier.current = tierKey;
  }, [tierKey]);

  const commit = (capital: number) => {
    dispatch({ type: "profile", patch: { capital } });
    setDraft(null);
    toast(t("g3.plan.committed", { v: rupees(capital) }));
  };

  const prepare = () => {
    if (state.appStage === "not_started") dispatch({ type: "application", event: "request_documents", allDocsComplete: false });
    push({ name: "documents" });
  };

  const attempt = activityId ? view.feasibility.attempts.find((a) => a.activityId === activityId) : undefined;
  const belowMinimum = activityId && plan.projectCost > 0 ? catalogEntry(activityId).min_project_cost > plan.projectCost : false;
  const committedEligible = !!view.financial?.plan.eligible;
  const committedNotes = (view.financial?.limitations ?? []).filter((l) => l.key === "c3.fin.lim.outside_scheme" || l.key === "c3.fin.lim.no_capital");
  const today = todayOf(state).slice(0, 10);
  const hasProfile = saved > 0 || !!state.profile.locationText || !!state.profile.activityId;

  const header = (
    <header className="safe-top bg-cream px-5 pt-4 pb-2">
      <h1 className="text-[26px] leading-tight font-bold">{t("nav.plan")}</h1>
      <p className="text-sm text-ink-3">{t("plan.subtitle")}</p>
    </header>
  );

  const calculator = (
    <Calculator plan={plan} capital={value} savedCapital={saved} onChange={setDraft} onCommit={commit} />
  );

  if (!activityId || !financial) {
    return (
      <TabScreen header={header}>
        <Reveal className="mt-2">
          <EmptyPlan hasProfile={hasProfile} onAsk={() => switchTab("assistant")} onReport={() => push({ name: view.feasibility.exhausted ? "noViable" : "report" })} />
        </Reveal>
        <Section title={t("plan.calc.titlePreview")}>{calculator}</Section>
        <RulesNote />
      </TabScreen>
    );
  }

  const { preview } = financial;
  return (
    <TabScreen header={header}>
      <Reveal className="mt-2">
        <PlanHero plan={plan} activityId={activityId} whatIf={whatIf} />
      </Reveal>

      {(attempt?.verdict === "not_recommended" || belowMinimum || committedNotes.length > 0) && (
        <div className="mt-3 space-y-2">
          {attempt?.verdict === "not_recommended" && (
            <Note tone="clay" icon={CircleAlert}>
              {t("g3.plan.notRecommended")}{" "}
              <button className="font-semibold underline" onClick={() => push({ name: "report" })}>
                {t("g3.plan.seeReport")}
              </button>
            </Note>
          )}
          {belowMinimum && <Note tone="marigold">{t("g3.plan.belowMinimum", { v: rupees(catalogEntry(activityId).min_project_cost) })}</Note>}
          {committedNotes.map((l) => (
            <Note key={l.key}>{tm(l)}</Note>
          ))}
        </div>
      )}

      <Section title={whatIf ? t("g3.plan.whatIfTitle") : t("plan.calc.title")}>{calculator}</Section>

      {plan.eligible && financial.budget.length > 0 && (
        <Section title={t("plan.budget.title")}>
          <Budget plan={plan} budget={financial.budget} />
        </Section>
      )}

      {plan.eligible && (
        <Section title={t("plan.schedule.title")}>
          <Repayment plan={plan} />
          <div className="mt-3">
            <RepaymentCalendar plan={plan} startIso={!whatIf && state.disbursedOn ? state.disbursedOn : today} projected={whatIf || !state.disbursedOn} today={today} />
          </div>
        </Section>
      )}

      {plan.eligible && preview.baseDscr !== null && (
        <>
          <Section title={t("plan.coverage.title")}>
            <CoverageCard preview={preview} onExplain={whatIf ? undefined : () => push({ name: "earnings" })} />
          </Section>
          {financial.scenarios.length > 0 && (
            <Section title={t("plan.stress.title")}>
              <p className="mb-3 px-1 text-[13px] leading-snug text-ink-3">{t("plan.stress.intro")}</p>
              <StressTests scenarios={financial.scenarios} />
            </Section>
          )}
        </>
      )}

      <Section>
        <Card className="py-1">
          <div className="divide-y divide-line">
            <ListRow icon={CalcIcon} title={t("earn.link")} subtitle={t("g3.plan.link.earningsSub")} onClick={() => push({ name: "earnings" })} />
            <ListRow icon={BookOpen} title={t("plan.link.scheme")} subtitle={t("plan.link.schemeSub")} onClick={() => push({ name: "scheme" })} />
            <ListRow icon={FileCheck2} title={t("docs.title")} subtitle={view.documents ? t("g3.plan.link.docsSub", { done: view.documents.items.length - view.documents.outstanding.length, total: view.documents.items.length }) : undefined} onClick={() => push({ name: "documents" })} />
          </div>
        </Card>
        {whatIf && <p className="mt-3 px-1 text-[13px] leading-snug text-ink-3">{t("g3.plan.whatIfHint")}</p>}
        <Button className="mt-4 w-full" icon={FileCheck2} disabled={!committedEligible || whatIf} onClick={prepare}>
          {state.appStage === "not_started" ? t("plan.cta.prepare") : t("g3.plan.cta.continue")}
        </Button>
      </Section>

    </TabScreen>
  );
}
