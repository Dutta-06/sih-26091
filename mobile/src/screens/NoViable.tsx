import { Calculator, CheckCircle2, HandHeart, ListOrdered, MessageCircle, PhoneCall, PiggyBank, Sprout, Users, XCircle, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { affordableProjectCost } from "../core/intel/catalog";
import { useI18n } from "../i18n";
import { tap } from "../lib/haptics";
import { ratio, rupees } from "../lib/format";
import { useNav } from "../nav";
import { useStore } from "../state/store";
import { Badge, Button, Card, IconBubble, Note, Reveal, Screen, Section, Sheet } from "../ui";
import { activityLabel, cheapestViable, placeOf } from "./g2/feasibility";
import { useMsg } from "./g2/msg";

export default function NoViable() {
  const { t, pick } = useI18n();
  const mt = useMsg();
  const { state, view } = useStore();
  const { push, goto } = useNav();
  const [sheet, setSheet] = useState(false);
  const [requested, setRequested] = useState(false);
  const f = view.feasibility;
  const place = placeOf(view);
  const capital = state.profile.capital;
  const project = affordableProjectCost(capital);
  const profileKey = JSON.stringify([state.profile, place?.lgd, place?.district.id]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const target = useMemo(() => cheapestViable(state.profile, place), [profileKey]);
  const hasSelection = !!f.selected;
  const untried = f.shortlist.filter((r) => r.feasible && !f.attempts.some((a) => a.activityId === r.activityId));

  // SHG path: members pooling the same savings as this entrepreneur to reach the target capital (ceil(target / own)).
  const members = target && capital > 0 ? Math.ceil(target.capital / capital) : null;

  const paths: { icon: LucideIcon; tone: "azure" | "marigold" | "sky" | "sand"; title: string; sub: string; onClick?: () => void }[] = [];
  if (target) {
    const label = activityLabel(target.activityId);
    paths.push({
      icon: PiggyBank,
      tone: "azure",
      title: t("noViable.path.save", { more: rupees(target.more), name: pick(label.name), capital: rupees(target.capital) }),
      sub: t(target.confirmed ? "noViable.path.saveSub" : "g2.noViable.saveUnconfirmed", { project: rupees(target.project), cover: target.dscr === null ? "—" : ratio(target.dscr) }),
    });
  }
  paths.push({
    icon: Users,
    tone: "sky",
    title: t(state.profile.shgMember ? "g2.noViable.shgMember" : "noViable.path.shg"),
    sub: members && members > 1 ? t("g2.noViable.shgMembers", { n: members, each: rupees(capital), total: rupees(target!.capital) }) : t("noViable.path.shgSub"),
  });
  if (untried.length && f.exhausted && f.attempts.length > 0) {
    const next = untried[0];
    paths.push({
      icon: ListOrdered,
      tone: "marigold",
      title: t("noViable.path.smaller", { name: pick(activityLabel(next.activityId).name), n: untried.length }),
      sub: t("noViable.path.smallerSub", { score: Math.round(next.score) }),
      onClick: () => push({ name: "shortlist" }),
    });
  }
  paths.push({ icon: PhoneCall, tone: "sand", title: t("noViable.path.counsellor"), sub: t("noViable.path.counsellorSub"), onClick: () => setSheet(true) });

  return (
    <Screen
      title={t("noViable.title")}
      footer={
        <div className="flex flex-col gap-1.5">
          <Button className="w-full" icon={PhoneCall} onClick={() => setSheet(true)}>
            {t("noViable.path.counsellor")}
          </Button>
          <Button variant="ghost" size="md" icon={ListOrdered} className="w-full" onClick={() => push({ name: "shortlist" })}>
            {t("w2.seeRanked")}
          </Button>
        </div>
      }
    >
      {hasSelection && (
        <div className="mt-2">
          <Note tone="azure" icon={CheckCircle2}>
            {t("g2.noViable.hasSelection", { name: pick(activityLabel(f.selected!.activityId).name) })}{" "}
            <button className="font-semibold underline" onClick={() => push({ name: "report" })}>
              {t("review.viewReport")}
            </button>
          </Note>
        </div>
      )}

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: "spring", stiffness: 220, damping: 24 }} className="mt-2">
        <Card className="bg-azure-50 shadow-none ring-1 ring-azure-100">
          <Sprout className="size-9 text-azure-600" />
          <h2 className="mt-2 text-xl leading-snug font-bold text-azure-900">{t(f.attempts.length ? "noViable.headline" : f.exhausted ? "g2.noViable.headlineNoneFit" : "g2.noViable.headlineNoAttempt")}</h2>
          <p className="mt-1.5 text-[14px] leading-snug text-ink-2">
            {capital <= 0 ? t("g2.noViable.leadNoCapital") : t(f.attempts.length ? "noViable.lead" : "g2.noViable.leadNoneFit", { savings: rupees(capital), project: rupees(project), n: f.attempts.length })}
          </p>
        </Card>
      </motion.div>

      {f.constraints.length > 0 && (
        <Section title={t("g2.noViable.constraints")}>
          <div className="space-y-2">
            {f.constraints.map((c, i) => (
              <Note key={i} tone="clay">
                {mt(c)}
              </Note>
            ))}
          </div>
          {capital <= 0 && (
            <Button variant="secondary" size="md" icon={MessageCircle} className="mt-2 w-full" onClick={() => goto("assistant")}>
              {t("g2.report.tellUs")}
            </Button>
          )}
        </Section>
      )}

      {f.attempts.length > 0 && (
        <Section title={t("noViable.tried")}>
          <Card className="divide-y divide-line py-1">
            {f.attempts.map((a, i) => {
              const label = activityLabel(a.activityId);
              return (
                <Reveal key={a.activityId} i={i + 1} className="flex items-start gap-3 py-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-cream text-xl">{label.emoji}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[15px] font-semibold break-words">
                      {pick(label.name)} {a.activityId === state.profile.activityId && <span className="text-xs font-medium text-ink-3">· {t("shortlist.yourIdea")}</span>}
                    </p>
                    <Badge tone={a.verdict === "viable" ? "good" : a.verdict === "marginal" ? "warn" : "risk"}>{t(`verdict.${a.verdict}`)}</Badge>
                    <ul className="mt-1 space-y-1">
                      {a.findings.map((fd, j) => (
                        <li key={j} className="flex items-start gap-1.5 text-[13px] leading-snug text-ink-2">
                          <XCircle className="mt-0.5 size-3.5 shrink-0 text-clay-600" />
                          {mt(fd.msg)}
                        </li>
                      ))}
                    </ul>
                  </div>
                </Reveal>
              );
            })}
          </Card>
          <p className="mt-2 flex items-center justify-center gap-1 text-[11px] text-ink-3">
            <Calculator className="size-3" />
            {t("shortlist.rules")}
          </p>
        </Section>
      )}

      <Section title={t("noViable.paths")}>
        <div className="space-y-2.5">
          {!target && <Note tone="sand">{t("g2.noViable.noTarget")}</Note>}
          {paths.map((p, i) => (
            <Reveal key={p.title} i={i + 4}>
              <Card onClick={p.onClick}>
                <div className="flex items-start gap-3">
                  <IconBubble icon={p.icon} tone={p.tone} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[15px] leading-snug font-semibold">{p.title}</p>
                    <p className="mt-0.5 text-[13px] leading-snug text-ink-3">{p.sub}</p>
                  </div>
                </div>
              </Card>
            </Reveal>
          ))}
        </div>
        <p className="mt-2 px-1 text-[11px] leading-snug text-ink-3">{t("g2.noViable.method")}</p>
      </Section>

      <div className="mt-4">
        <Note tone="azure" icon={HandHeart}>
          {t("noViable.honest")}
        </Note>
      </div>

      <Sheet open={sheet} onClose={() => setSheet(false)} title={t("noViable.sheet.title")}>
        {requested ? <Note tone="azure">{t("noViable.sheet.done")}</Note> : <p className="text-[15px] leading-snug text-ink-2">{t("noViable.sheet.body", { district: place ? pick(place.district.name) : "—" })}</p>}
        <Button
          className="mt-4 w-full"
          icon={requested ? undefined : PhoneCall}
          variant={requested ? "secondary" : "primary"}
          onClick={() => {
            tap();
            if (requested) setSheet(false);
            else setRequested(true);
          }}
        >
          {t(requested ? "shortlist.close" : "noViable.sheet.cta")}
        </Button>
      </Sheet>
    </Screen>
  );
}
