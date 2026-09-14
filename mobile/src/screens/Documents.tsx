import { CheckCircle2, CircleAlert, Clock, MessageCircle, Send } from "lucide-react";
import { useState } from "react";
import { tap } from "../App";
import { useI18n } from "../i18n";
import { useNav } from "../nav";
import { useStore } from "../state/store";
import { Badge, Button, Card, ListRow, Note, Ring, Section, Screen } from "../ui";
import { AutoFill } from "./g3/AutoFill";
import { DocSheet } from "./g3/DocSheet";

const STATUS = {
  complete: { icon: CheckCircle2, tone: "forest", badge: "good" },
  pending: { icon: Clock, tone: "marigold", badge: "warn" },
  missing: { icon: CircleAlert, tone: "clay", badge: "risk" },
} as const;

/** Checklist computed by the core (base documents + scheme documents for the tier and profile). */
export default function Documents() {
  const { t, pick } = useI18n();
  const { state, dispatch, view } = useStore();
  const { push, switchTab } = useNav();
  const [openId, setOpenId] = useState<string | null>(null);
  const checklist = view.documents;

  if (!checklist || checklist.items.length === 0) {
    return (
      <Screen title={t("docs.title")} subtitle={t("docs.subtitle")}>
        <Card tone="marigold" className="mt-2">
          <p className="text-[17px] font-semibold">{t("g3.docs.empty.title")}</p>
          <p className="mt-1 text-[15px] leading-snug text-ink-2">{t("g3.docs.empty.body")}</p>
          <Button size="md" icon={MessageCircle} className="mt-3" onClick={() => switchTab(view.activityId ? "plan" : "assistant")}>
            {t(view.activityId ? "g3.docs.empty.toPlan" : "plan.empty.cta")}
          </Button>
        </Card>
      </Screen>
    );
  }

  const total = checklist.items.length;
  const done = total - checklist.outstanding.length;
  const left = checklist.outstanding.length;
  const openDoc = checklist.items.find((d) => d.id === openId) ?? null;
  const eligible = !!view.financial?.plan.eligible;
  const alreadySubmitted = !["not_started", "documents_pending"].includes(state.appStage);

  const submit = () => {
    tap();
    dispatch({ type: "application", event: "submit", allDocsComplete: checklist.complete });
    push({ name: "application" });
  };

  return (
    <Screen
      title={t("docs.title")}
      subtitle={t("docs.subtitle")}
      footer={
        alreadySubmitted ? (
          <Button variant="secondary" className="w-full" onClick={() => push({ name: "application" })}>
            {t("g3.docs.viewStatus")}
          </Button>
        ) : checklist.complete && eligible ? (
          <Button className="w-full" icon={Send} onClick={submit}>
            {t("docs.submit")}
          </Button>
        ) : (
          <Button className="w-full" disabled>
            {!eligible ? t("g3.docs.notEligible") : t(left === 1 ? "docs.leftOne" : "docs.left", { n: left })}
          </Button>
        )
      }
    >
      <Card className="mt-2 flex items-center gap-4">
        <Ring value={(done / total) * 100} tone={left === 0 ? "forest" : "marigold"} label={`${done}/${total}`} sub={t("docs.ringSub")} />
        <div className="min-w-0">
          <p className="text-[17px] leading-snug font-semibold">{left === 0 ? t("docs.allDone") : t("docs.progress", { n: left })}</p>
          <p className="mt-1 text-[13px] leading-snug text-ink-3">{t("docs.progressSub")}</p>
        </div>
      </Card>

      {state.appStage === "documents_pending" && state.events.some((e) => e.type === "application" && e.data?.event === "return_documents") && (
        <div className="mt-3">
          <Note tone="marigold">{t("g3.docs.returned")}</Note>
        </div>
      )}

      <Section title={t("docs.checklist")}>
        <Card className="py-1">
          <div className="divide-y divide-line">
            {checklist.items.map((d) => {
              const s = d.status;
              const cfg = STATUS[s];
              if (d.id === "udyam_certificate" && s !== "complete") {
                return (
                  <ListRow
                    key={d.id}
                    icon={cfg.icon}
                    tone={cfg.tone}
                    title={pick(d.name)}
                    subtitle={<span className="font-semibold text-forest-700">{t("docs.udyam.help")}</span>}
                    right={<Badge tone={cfg.badge}>{t(`status.${s}`)}</Badge>}
                    onClick={() => push({ name: "udyam" })}
                  />
                );
              }
              return (
                <ListRow
                  key={d.id}
                  icon={cfg.icon}
                  tone={cfg.tone}
                  title={<span className="break-words">{pick(d.name)}</span>}
                  subtitle={s === "complete" ? t("docs.row.complete") : s === "pending" ? t("docs.row.pending") : t("docs.row.missing")}
                  right={<Badge tone={cfg.badge}>{t(`status.${s}`)}</Badge>}
                  onClick={s === "complete" || alreadySubmitted ? undefined : () => setOpenId(d.id)}
                />
              );
            })}
          </div>
        </Card>
      </Section>

      <Section title={t("docs.formSection")}>
        <AutoFill />
      </Section>

      <div className="mt-4">
        <Note tone="forest">{t("docs.privacy")}</Note>
      </div>

      <DocSheet doc={openDoc} onClose={() => setOpenId(null)} onSet={(id, status) => dispatch({ type: "doc", id, status })} />
    </Screen>
  );
}
