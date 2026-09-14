import { ArrowRight, Calculator, CheckCircle2, ClipboardList, ListOrdered, Map as MapIcon, MessageCircle, ShieldAlert, ShieldX } from "lucide-react";
import { motion } from "motion/react";
import { useI18n } from "../i18n";
import { tap } from "../lib/haptics";
import { ratio } from "../lib/format";
import { useNav } from "../nav";
import { useStore } from "../state/store";
import { Badge, Button, Card, ConfidenceBadge, Note, Ring, Screen } from "../ui";
import { activityLabel, confidenceCounts, firstRejected, placeOf, reportAttempt } from "./g2/feasibility";
import { useMsg } from "./g2/msg";
import { CompetitorSection, ConfidenceLegend, MarketSection, OpportunitySection, PricingSection, RiskSection, SupplySection, SwotSection } from "./g2/ReportSections";
import { EvidenceSection } from "./w2/EvidenceSection";

const VERDICT = { viable: { tone: "good", icon: CheckCircle2 }, marginal: { tone: "warn", icon: ShieldAlert }, not_recommended: { tone: "risk", icon: ShieldX } } as const;

export default function Report() {
  const { t, pick } = useI18n();
  const mt = useMsg();
  const { push, goto } = useNav();
  const { state, view } = useStore();
  const attempt = reportAttempt(view, state.profile);
  const place = placeOf(view);
  const rejected = firstRejected(view);

  if (!attempt) {
    return (
      <Screen title={t("report.title")}>
        <Card tone="sand" className="mt-4">
          <p className="text-[15px] font-semibold">{t("g2.report.empty")}</p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-[13px] leading-snug text-ink-2">
            {(view.feasibility.constraints.length ? view.feasibility.constraints.map(mt) : [t(view.feasibility.exhausted ? "g2.report.emptyExhausted" : "g2.report.emptySub")]).map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </Card>
        <div className="mt-4 flex flex-col gap-2">
          {view.feasibility.exhausted && (
            <Button iconRight={ArrowRight} onClick={() => push({ name: "noViable" })}>
              {t("g2.review.exhaustedCta")}
            </Button>
          )}
          <Button variant={view.feasibility.exhausted ? "secondary" : "primary"} icon={MessageCircle} onClick={() => goto("assistant")}>
            {t("g2.report.tellUs")}
          </Button>
          <Button variant="secondary" size="md" icon={ListOrdered} onClick={() => push({ name: "shortlist" })}>
            {t("w2.seeRanked")}
          </Button>
        </div>
      </Screen>
    );
  }

  const label = activityLabel(attempt.activityId);
  const counts = confidenceCounts(attempt.intel);
  const verdict = VERDICT[attempt.verdict];
  const isRejectedOne = rejected?.activityId === attempt.activityId;
  const placeName = place ? [place.village ? pick(place.village) : null, pick(place.district.name)].filter(Boolean).join(", ") : state.profile.locationText || t("g2.place.unknown");
  const chosen = state.chosenActivity === attempt.activityId;

  return (
    <Screen
      title={t("report.title")}
      subtitle={t("report.subtitle", { village: placeName, n: counts.total })}
      right={
        <button aria-label={t("w2.seeRanked")} onClick={() => push({ name: "shortlist" })} className="flex min-h-11 items-center gap-1.5 rounded-full px-3 text-[13px] font-semibold text-azure-800 active:bg-sand">
          <ListOrdered className="size-5" />
          {t("w2.options")}
        </button>
      }
      footer={
        <div className="flex flex-col gap-1.5">
          {attempt.verdict === "viable" || chosen ? (
            <Button
              className="w-full"
              iconRight={ArrowRight}
              onClick={() => {
                tap();
                goto("plan");
              }}
            >
              {t("report.ctaPlan")}
            </Button>
          ) : view.feasibility.exhausted ? (
            <Button className="w-full" iconRight={ArrowRight} onClick={() => push({ name: "noViable" })}>
              {t("g2.review.exhaustedCta")}
            </Button>
          ) : (
            <Button className="w-full" iconRight={ArrowRight} onClick={() => push({ name: "review" })}>
              {t("report.ctaReview", { name: pick(label.name) })}
            </Button>
          )}
          <div className="grid grid-cols-2 gap-1.5">
            <Button variant="ghost" size="md" icon={MapIcon} onClick={() => push({ name: "map" })}>
              {t("g2.report.map")}
            </Button>
            <Button variant="ghost" size="md" icon={ClipboardList} onClick={() => push({ name: "evidence" })}>
              {t("g2.report.evidence")}
            </Button>
          </div>
        </div>
      }
    >
      {rejected && !isRejectedOne && (
        <motion.button
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => push({ name: "review" })}
          className="mt-2 flex w-full items-center gap-3 rounded-2xl bg-clay-50 p-3 text-left ring-1 ring-clay-100"
        >
          <ShieldX className="size-5 shrink-0 text-clay-600" />
          <span className="min-w-0 flex-1 text-[13px] leading-snug text-clay-700">{t("report.rejectedBanner", { name: pick(activityLabel(rejected.activityId).name) })}</span>
          <span className="flex shrink-0 items-center gap-1 text-[13px] font-semibold text-clay-700">
            {t("report.seeWhy")}
            <ArrowRight className="size-4" />
          </span>
        </motion.button>
      )}

      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: "spring", stiffness: 240, damping: 22 }} className="mt-3">
        <Card tone="azure">
          <div className="flex items-center gap-3">
            <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-white/10 text-2xl">{label.emoji}</span>
            <div className="min-w-0">
              <h2 className="text-lg leading-tight font-bold break-words">{pick(label.name)}</h2>
              <p className="truncate text-[13px] text-azure-100">{placeName}</p>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-4">
            <Ring value={attempt.score} tone="light" size={92} sub={t("report.score")} />
            <div className="min-w-0 flex-1 space-y-2">
              <div>
                <p className="text-xs text-azure-100">{t("report.verdict")}</p>
                <Badge tone={verdict.tone} icon={verdict.icon}>
                  {t(`verdict.${attempt.verdict}`)}
                </Badge>
              </div>
              <div>
                <p className="text-xs text-azure-100">{t("report.coverage")}</p>
                <p className="tabular text-xl font-bold">{attempt.preview.baseDscr === null ? "—" : ratio(attempt.preview.baseDscr)}</p>
                <p className="flex items-center gap-1 text-[11px] text-azure-100">
                  <Calculator className="size-3" />
                  {t("review.rules")}
                </p>
              </div>
            </div>
          </div>
          <div className="mt-4 rounded-2xl bg-white/10 p-3">
            <p className="text-[13px] font-semibold">{t("report.analyses", { done: counts.total, total: counts.total })}</p>
            <div className="mt-2 flex h-2 overflow-hidden rounded-full">
              <motion.div initial={{ width: 0 }} animate={{ width: `${(counts.real / counts.total) * 100}%` }} transition={{ duration: 0.8, delay: 0.2 }} className="bg-azure-200" />
              <motion.div initial={{ width: 0 }} animate={{ width: `${(counts.estimated / counts.total) * 100}%` }} transition={{ duration: 0.8, delay: 0.5 }} className="bg-marigold-500" />
            </div>
            <div className="mt-2 flex gap-4 text-xs text-azure-50">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-azure-200" />
                {t("report.realCount", { n: counts.real })}
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-marigold-500" />
                {t("report.estCount", { n: counts.estimated })}
              </span>
            </div>
          </div>
        </Card>
      </motion.div>

      {attempt.findings.length > 0 && (
        <div className="mt-3">
          <Note tone={attempt.verdict === "marginal" ? "marigold" : "clay"} icon={ShieldAlert}>
            <ul className="space-y-1">
              {attempt.findings.map((f, i) => (
                <li key={i}>
                  <span className="font-semibold">{f.rule}</span> · {mt(f.msg)}
                </li>
              ))}
            </ul>
          </Note>
        </div>
      )}
      {attempt.notes.length > 0 && (
        <ul className="mt-2 space-y-1 px-1">
          {attempt.notes.map((n, i) => (
            <li key={i} className="text-xs leading-snug text-ink-3">
              {mt(n)}
            </li>
          ))}
        </ul>
      )}
      {view.location.limitations.length > 0 && (
        <div className="mt-2 flex items-start gap-2 px-1">
          <ConfidenceBadge value={view.location.confidence} compact />
          <p className="text-xs leading-snug text-ink-3">{view.location.limitations.map(mt).join(" ")}</p>
        </div>
      )}

      <MarketSection intel={attempt.intel} i={1} />
      <OpportunitySection intel={attempt.intel} i={2} />
      <CompetitorSection attempt={attempt} stateName={place?.district.state ?? "—"} i={3} />
      <PricingSection intel={attempt.intel} i={4} />
      <RiskSection intel={attempt.intel} i={5} />
      <SupplySection intel={attempt.intel} i={6} />
      <EvidenceSection intel={attempt.intel} district={place?.district.id ?? null} activityId={attempt.activityId} i={7} />
      <SwotSection swot={attempt.swot} i={8} />
      <ConfidenceLegend i={9} />
    </Screen>
  );
}
