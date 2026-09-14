import { CheckCircle2, CircleDashed, Send, Share2 } from "lucide-react";
import { useState } from "react";
import { tap } from "../../App";
import { useI18n } from "../../i18n";
import { rupees } from "../../lib/format";
import { useStore } from "../../state/store";
import { Button, Card, ListRow, Note, Sheet } from "../../ui";
import { useApplicant } from "../g3/applicant";
import { RulesChip } from "../g3/bits";
import { applicationRef, placeOf } from "../g3/model";
import { activityDisplay, ratePct } from "../g3/util";

const SHARE_TARGETS = ["whatsapp", "sms", "portal"] as const;

/** One-page loan application summary with a simulated share to the bank officer (TDD 6.5). */
export function LoanForm() {
  const { t, pick, tm } = useI18n();
  const { state, view } = useStore();
  const [applicant] = useApplicant();
  const [open, setOpen] = useState(false);
  const [sharedTo, setSharedTo] = useState<string | null>(null);
  if (!view.activityId || !view.financial) return null;
  const act = activityDisplay(view.activityId);
  const plan = view.financial.plan;
  const place = placeOf(view);
  const registered = state.documents.udyam_certificate === "complete";
  const cat = state.profile.category;
  const ref = applicationRef(place?.district.id, state.events);
  const officer = tm({ key: "c3.role.sca_loan_officer" });
  const docs = view.documents?.items ?? [];

  const blocks: { title: string; rows: [string, string][] }[] = [
    {
      title: t("loanform.applicant"),
      rows: [
        [t("loanform.name"), applicant.fullName ?? t("g3.udyam.nameMissing")],
        [t("loanform.address"), place ? [place.village && pick(place.village), pick(place.district.name)].filter(Boolean).join(", ") : "—"],
        [t("udyam.label.ifsc"), applicant.ifsc ? `${applicant.ifsc}${applicant.accountMasked ? ` · ${applicant.accountMasked}` : ""}` : "—"],
        [t("udyam.label.category"), cat ? t(`udyam.cat.${cat}`) : "—"],
        [t("udyam.label.women"), t(state.profile.womanOwned ? "udyam.yes" : "udyam.no")],
      ],
    },
    {
      title: t("loanform.business"),
      rows: [
        [t("loanform.activity"), `${act.emoji} ${pick(act.name)}`],
        [t("udyam.label.nic"), act.nic],
        [t("loanform.udyam"), registered ? applicant.udyamNumber ?? t("g3.loanform.udyamOnFile") : t("loanform.udyamPending")],
      ],
    },
    {
      title: t("loanform.money"),
      rows: plan.eligible && plan.tier
        ? [
            [t("plan.projectCost"), rupees(plan.projectCost)],
            [t("loanform.ownShare"), rupees(plan.projectCost - plan.loan)],
            [t("plan.loan"), rupees(plan.loan)],
            [t("loanform.tier"), `${t(`plan.tier.${plan.tier.name}`)} · ${ratePct(plan.tier.rate)}`],
            [t("loanform.moratorium"), t("unit.months", { n: plan.tier.moratoriumMonths })],
            [t("loanform.instalment"), `${rupees(plan.regularInstallment)} ${t("unit.perQuarter")}`],
          ]
        : [[t("plan.projectCost"), plan.projectCost > 0 ? rupees(plan.projectCost) : "—"], [t("plan.loan"), t("plan.tier.outside")]],
    },
  ];

  return (
    <>
      <div className="overflow-hidden rounded-[var(--radius-card)] bg-white shadow-[var(--shadow-card)]">
        <div className="flex items-start justify-between gap-2 border-b border-line bg-sand px-4 py-3">
          <div className="min-w-0">
            <p className="text-[17px] font-bold">{t("loanform.heading")}</p>
            <p className="tabular text-[12px] text-ink-3">{ref ? t("loanform.ref", { ref }) : t("g3.app.refPending")}</p>
          </div>
          <RulesChip />
        </div>
        {blocks.map((b) => (
          <section key={b.title} className="px-4 pt-3">
            <p className="text-[12px] font-bold tracking-wide text-ink-3 uppercase">{b.title}</p>
            <dl className="mt-1 divide-y divide-line text-[14px]">
              {b.rows.map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-3 py-1.5">
                  <dt className="text-ink-3">{k}</dt>
                  <dd className="tabular min-w-0 text-right font-semibold break-words">{v}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
        <section className="px-4 pt-3 pb-4">
          <p className="text-[12px] font-bold tracking-wide text-ink-3 uppercase">{t("loanform.docs")}</p>
          <ul className="mt-1.5 grid grid-cols-1 gap-1">
            {docs.map((d) => {
              const ok = d.status === "complete";
              return (
                <li key={d.id} className="flex items-center gap-2 text-[14px]">
                  {ok ? <CheckCircle2 className="size-4 text-forest-600" /> : <CircleDashed className="size-4 text-marigold-600" />}
                  <span className={ok ? "min-w-0" : "min-w-0 text-ink-3"}>{pick(d.name)}</span>
                  {!ok && <span className="text-[11px] font-semibold text-marigold-600">{t("loanform.notYet")}</span>}
                </li>
              );
            })}
          </ul>
        </section>
      </div>

      <Button variant="secondary" className="mt-4 w-full" icon={Share2} onClick={() => setOpen(true)}>
        {t("loanform.share")}
      </Button>
      {sharedTo && (
        <div className="mt-3">
          <Note tone="forest" icon={Send}>
            {t("loanform.shared", { officer: officer, via: sharedTo })}
          </Note>
        </div>
      )}

      <Sheet open={open} onClose={() => setOpen(false)} title={t("loanform.shareTitle")}>
        <p className="mb-2 text-[13px] text-ink-3">{t("loanform.shareSub", { officer: officer })}</p>
        <Card className="py-1">
          <div className="divide-y divide-line">
            {SHARE_TARGETS.map((s) => (
              <ListRow
                key={s}
                icon={Send}
                title={t(`g3.share.${s}`)}
                onClick={() => {
                  tap();
                  setSharedTo(t(`g3.share.${s}`));
                  setOpen(false);
                }}
              />
            ))}
          </div>
        </Card>
        <p className="mt-3 text-center text-[11px] text-ink-3">{t("loanform.simulated")}</p>
      </Sheet>
    </>
  );
}
