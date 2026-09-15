import { ArrowRight, Calculator, CheckCircle2, FileText, ListOrdered, ShieldAlert, ShieldX, Sparkles, ThumbsUp } from "lucide-react";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { affordableProjectCost, catalogActivity } from "../core/intel/catalog";
import { SEASONAL_RISK_IDS } from "../core/review";
import type { FeasibilityAttempt, ReviewFinding } from "../core/types";
import { useI18n } from "../i18n";
import { tap } from "../lib/haptics";
import { ratio, rupees } from "../lib/format";
import { useNav } from "../nav";
import { useStore } from "../state/store";
import { CoverageGauge } from "../ui/charts";
import { Badge, Button, Card, ConfidenceBadge, cx, levelTone, Note, Reveal, Screen, Section } from "../ui";
import { activityLabel, adjacency, competitorBenchmark, firstRejected, placeOf } from "./g2/feasibility";
import { useMsg } from "./g2/msg";

const VERDICT_TONE = { viable: "good", marginal: "warn", not_recommended: "risk" } as const;

export default function Review() {
  const { t, pick } = useI18n();
  const mt = useMsg();
  const { push, goto } = useNav();
  const { state, set, dispatch, view } = useStore();
  const f = view.feasibility;
  const rejected = firstRejected(view);
  const alt = f.selected;

  if (!rejected) {
    return (
      <Screen title={t("review.title")} subtitle={t("review.subtitle")}>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-6 text-center">
          <CheckCircle2 className="mx-auto size-14 text-azure-600" />
          <h2 className="mt-3 text-xl font-bold">{t(f.attempts.length ? "g2.review.passed" : "g2.review.nothing")}</h2>
          <p className="mx-auto mt-2 max-w-80 text-[14px] leading-snug text-ink-2">
            {f.attempts.length ? t("g2.review.passedSub", { name: pick(activityLabel(f.attempts[0].activityId).name) }) : f.constraints.map(mt).join(" ") || t("g2.review.nothingSub")}
          </p>
          <div className="mt-6 flex flex-col gap-2">
            {f.attempts.length > 0 && (
              <Button icon={FileText} onClick={() => push({ name: "report" })}>
                {t("review.viewReport")}
              </Button>
            )}
            <Button variant="secondary" size="md" icon={ListOrdered} onClick={() => push({ name: "shortlist" })}>
              {t("w2.seeRanked")}
            </Button>
          </div>
        </motion.div>
      </Screen>
    );
  }

  const first = activityLabel(rejected.activityId);
  const altLabel = alt ? activityLabel(alt.activityId) : null;
  const otherRejected = f.attempts.filter((a) => a !== rejected && a.verdict !== "viable");

  const choose = () => {
    if (!alt) return;
    tap();
    set({ chosenActivity: alt.activityId });
    dispatch({ type: "event", event: { type: "activity_chosen", data: { activityId: alt.activityId, rejected: rejected.activityId } } });
    goto("plan");
  };

  return (
    <Screen
      title={t("review.title")}
      subtitle={t("review.subtitle")}
      footer={
        <div className="flex flex-col gap-1.5">
          {alt && altLabel ? (
            <Button onClick={choose} iconRight={ArrowRight} className="w-full">
              {t("review.cta", { name: pick(altLabel.name) })}
            </Button>
          ) : (
            <Button onClick={() => push({ name: "noViable" })} iconRight={ArrowRight} className="w-full">
              {t("g2.review.exhaustedCta")}
            </Button>
          )}
          <Button variant="ghost" size="md" icon={FileText} onClick={() => push({ name: "report" })} className="w-full">
            {t("review.viewReport")}
          </Button>
        </div>
      }
    >
      {/* Verdict */}
      <motion.div initial={{ opacity: 0, scale: 0.92, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ type: "spring", stiffness: 260, damping: 20 }} className="mt-2">
        <Card tone={rejected.verdict === "marginal" ? "marigold" : "clay"} className="relative overflow-hidden">
          <ShieldX className="absolute -top-3 -right-3 size-24 text-clay-100" strokeWidth={1.5} />
          <p className="relative text-xs font-medium text-clay-700">{t(rejected.activityId === state.profile.activityId ? "review.yourIdea" : "g2.review.checked")}</p>
          <div className="relative mt-2 flex items-center gap-3">
            <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-white text-3xl shadow-[var(--shadow-card)]">{first.emoji}</span>
            <div className="min-w-0">
              <h2 className="text-lg leading-tight font-bold break-words">{pick(first.name)}</h2>
              {state.profile.reason && rejected.activityId === state.profile.activityId && <p className="mt-1 line-clamp-2 text-[13px] text-ink-2 italic">“{state.profile.reason}”</p>}
            </div>
          </div>
          <div className="relative mt-3 flex flex-wrap items-center gap-2">
            <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.35, type: "spring", stiffness: 400, damping: 14 }}>
              <Badge tone={VERDICT_TONE[rejected.verdict]} icon={rejected.verdict === "marginal" ? ShieldAlert : ShieldX}>
                {t(`verdict.${rejected.verdict}`)}
              </Badge>
            </motion.span>
            <span className="tabular text-xs text-ink-2">{t("g2.review.findingCount", { n: rejected.findings.length })}</span>
          </div>
          <p className="relative mt-2 text-xs text-clay-700">{t("review.reviewedBy")}</p>
        </Card>
      </motion.div>

      {/* Why */}
      <Section title={t("review.why")}>
        <Card className="divide-y divide-line py-1">
          {rejected.findings.map((finding, i) => (
            <Reveal key={`${finding.rule}-${i}`} i={i + 3} className="flex gap-3 py-3">
              <span className={cx("tabular grid size-8 shrink-0 place-items-center rounded-full text-[11px] font-bold", finding.rule.startsWith("R") ? "bg-clay-100 text-clay-700" : "bg-marigold-100 text-marigold-600")}>{finding.rule}</span>
              <div className="min-w-0 flex-1">
                <p className="text-[15px] leading-snug">{mt(finding.msg)}</p>
                <FindingDetail finding={finding} attempt={rejected} capital={state.profile.capital} />
              </div>
            </Reveal>
          ))}
        </Card>
        {rejected.notes.length > 0 && (
          <ul className="mt-2 space-y-1 px-1">
            {rejected.notes.map((n, i) => (
              <li key={i} className="text-xs leading-snug text-ink-3">
                {mt(n)}
              </li>
            ))}
          </ul>
        )}
      </Section>

      {otherRejected.length > 0 && (
        <Section title={t("g2.review.alsoChecked")}>
          <Card className="divide-y divide-line py-1">
            {otherRejected.map((a) => (
              <div key={a.activityId} className="flex items-start gap-3 py-2.5">
                <span className="text-xl">{activityLabel(a.activityId).emoji}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold">{pick(activityLabel(a.activityId).name)}</p>
                  <p className="text-[13px] leading-snug text-ink-2">{a.findings.map((x) => mt(x.msg)).join(" ")}</p>
                </div>
                <Badge tone={VERDICT_TONE[a.verdict]}>{t(`verdict.${a.verdict}`)}</Badge>
              </div>
            ))}
          </Card>
        </Section>
      )}

      {/* Alternative */}
      {alt && altLabel ? (
        <>
          <Section title={t("review.better")}>
            <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45, type: "spring", stiffness: 200, damping: 22 }}>
              <AltCard alt={alt} rejectedId={rejected.activityId} />
            </motion.div>
          </Section>

          <Section title={t("review.compare")}>
            <Reveal i={10}>
              <CompareTable a={rejected} b={alt} />
            </Reveal>
          </Section>
        </>
      ) : (
        <div className="mt-4">
          <Note tone="clay">{t("g2.review.exhausted", { n: f.attempts.length })}</Note>
        </div>
      )}

      <div className="mt-4">
        <Note tone="azure">{t("review.honest")}</Note>
      </div>
      <Button variant="secondary" size="md" icon={ListOrdered} className="mt-3 w-full" onClick={() => push({ name: "shortlist" })}>
        {t("w2.seeRanked")}
      </Button>
    </Screen>
  );
}

/** Supporting numbers for one finding, read from the attempt's preview and intel. */
function FindingDetail({ finding, attempt, capital }: { finding: ReviewFinding; attempt: FeasibilityAttempt; capital: number }) {
  const { t } = useI18n();
  const { view } = useStore();
  const stateName = placeOf(view)?.district.state ?? "—";
  const { preview, intel } = attempt;
  const box = (children: ReactNode) => <div className="mt-3 rounded-2xl bg-cream p-3">{children}</div>;
  switch (finding.rule) {
    case "R1": {
      const need = catalogActivity(attempt.activityId)?.min_project_cost ?? 0;
      const have = affordableProjectCost(capital);
      return box(
        <>
          <TwoStats a={[t("g2.review.projectNeed"), rupees(need)]} b={[t("g2.review.projectHave"), rupees(have)]} bad="b" />
          <Bar value={need ? have / need : 0} />
        </>,
      );
    }
    case "R2":
    case "M1": {
      const d = preview.baseDscr ?? 0;
      return box(
        <>
          <TwoStats a={[t("review.surplus"), rupees(preview.quarterlySurplus)]} b={[t("review.installment"), rupees(preview.plan.regularInstallment)]} bad="b" />
          <div className="mx-auto mt-2 w-36">
            <CoverageGauge value={d} size={144} />
          </div>
          <p className={cx("text-center text-[13px] font-semibold", d < 1 ? "text-clay-700" : "text-marigold-600")}>{t(d < 1 ? "review.coverShort" : "g2.review.coverThin", { ratio: ratio(d), pct: Math.round(d * 100) })}</p>
          <RulesCue />
        </>,
      );
    }
    case "M4": {
      const d = preview.minSeasonalDscr ?? 0;
      return box(
        <>
          <div className="mx-auto w-36">
            <CoverageGauge value={d} size={144} />
          </div>
          <p className="text-center text-[13px] font-semibold text-marigold-600">{t("g2.review.seasonalCover", { ratio: ratio(d), base: ratio(preview.baseDscr ?? 0) })}</p>
          <RulesCue />
        </>,
      );
    }
    case "R3":
    case "M2": {
      if (finding.msg.key === "c2.review.M2niches") {
        return box(
          <div className="flex flex-wrap gap-1.5">
            {intel.opportunity.niches.map((n) => (
              <Badge key={n.name} tone={n.saturation === "unknown" ? "neutral" : levelTone(n.saturation)}>
                {n.name}
              </Badge>
            ))}
          </div>,
        );
      }
      const c = intel.competitor;
      const bench = competitorBenchmark(intel, attempt.activityId);
      return box(
        <>
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-ink-3">{t(c.tier === "udyam" ? "g2.comp.countDistrict" : "g2.comp.countRadius", { r: intel.marketReach.radiusKm })}</span>
            <ConfidenceBadge value={c.confidence} compact />
          </div>
          <p className="tabular text-lg font-bold text-clay-700">{c.count ?? "—"}</p>
          <DensityRow label={t("report.yourArea")} value={c.densityPer10k} max={Math.max(c.densityPer10k ?? 0, bench.value ?? 0)} tone="clay" />
          <DensityRow label={t(bench.scope === "state" ? "g2.comp.benchState" : "g2.comp.benchCatalog", { state: stateName })} value={bench.value} max={Math.max(c.densityPer10k ?? 0, bench.value ?? 0)} tone="azure" />
          {c.zScore !== null && <p className="tabular mt-1 text-xs text-ink-3">{t("w2.bench.z", { z: c.zScore.toFixed(1) })}</p>}
        </>,
      );
    }
    case "M3": {
      const highs = intel.risk.flags.filter((x) => x.severity === "high" && x.category !== "seasonal" && !SEASONAL_RISK_IDS.has(x.id));
      return box(
        <ul className="space-y-1">
          {highs.map((x) => (
            <li key={x.id} className="flex items-center gap-2 text-[13px]">
              <Badge tone="risk">{t("level.high")}</Badge>
              <FlagTitle titleKey={x.title} />
            </li>
          ))}
        </ul>,
      );
    }
  }
  return null;
}

function FlagTitle({ titleKey }: { titleKey: { key: string; vars?: Record<string, string | number> } }) {
  const mt = useMsg();
  return <span className="min-w-0 flex-1">{mt(titleKey)}</span>;
}

function TwoStats({ a, b, bad }: { a: [string, string]; b: [string, string]; bad?: "a" | "b" }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {[a, b].map(([label, value], i) => (
        <div key={label}>
          <p className="text-xs text-ink-3">{label}</p>
          <p className={cx("tabular mt-0.5 text-lg font-bold", bad === (i ? "b" : "a") && "text-clay-700")}>{value}</p>
        </div>
      ))}
    </div>
  );
}

function Bar({ value }: { value: number }) {
  return (
    <div className="mt-2 h-2 overflow-hidden rounded-full bg-ink-3/15">
      <motion.div initial={{ scaleX: 0 }} animate={{ scaleX: Math.max(0, Math.min(1, value)) }} style={{ originX: 0 }} transition={{ duration: 0.7 }} className="h-full w-full rounded-full bg-clay-600" />
    </div>
  );
}

function DensityRow({ label, value, max, tone }: { label: string; value: number | null; max: number; tone: "clay" | "azure" }) {
  const scale = max * 1.15 || 1;
  return (
    <div className="mt-2 flex items-center gap-2">
      <span className="w-28 shrink-0 truncate text-[12px] text-ink-2">{label}</span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-ink-3/15">
        <motion.div initial={{ scaleX: 0 }} animate={{ scaleX: value === null ? 0 : value / scale }} style={{ originX: 0 }} transition={{ duration: 0.7 }} className={cx("h-full w-full rounded-full", tone === "clay" ? "bg-clay-600" : "bg-azure-600")} />
      </div>
      <span className="tabular w-10 text-right text-[13px] font-semibold">{value === null ? "—" : value.toFixed(1)}</span>
    </div>
  );
}

function AltCard({ alt, rejectedId }: { alt: FeasibilityAttempt; rejectedId: string }) {
  const { t, pick } = useI18n();
  const label = activityLabel(alt.activityId);
  const adj = adjacency(rejectedId, alt.activityId);
  const d = alt.preview.baseDscr ?? 0;
  const c = alt.intel.competitor;
  return (
    <Card tone="azure" className="relative overflow-hidden">
      <Sparkles className="absolute top-3 right-3 size-5 text-marigold-500" />
      <div className="flex items-center gap-3">
        <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-white/10 text-3xl">{label.emoji}</span>
        <div className="min-w-0">
          <h2 className="text-lg leading-tight font-bold break-words">{pick(label.name)}</h2>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            <Badge tone="good" icon={ThumbsUp}>
              {t(`verdict.${alt.verdict}`)}
            </Badge>
            {adj !== "none" && <span className="inline-flex items-center rounded-full bg-marigold-500 px-2.5 py-1 text-xs font-semibold text-azure-950">{t(`g2.review.adj.${adj}`)}</span>}
          </div>
        </div>
      </div>
      <p className="mt-3 text-[14px] leading-snug text-azure-50">
        {t(`g2.review.adjWhy.${adj}`, { from: pick(activityLabel(rejectedId).name), to: pick(label.name) })}
      </p>
      <div className="mt-3 flex items-center gap-3 rounded-2xl bg-white p-3 text-ink">
        <div className="w-28 shrink-0">
          <CoverageGauge value={d} size={112} />
        </div>
        <div className="min-w-0 space-y-1">
          <p className="text-[13px] font-semibold text-azure-800">{t(d >= 1.25 ? "review.coverGood" : "g2.review.coverThin", { ratio: ratio(d), pct: Math.round(d * 100) })}</p>
          <p className="tabular text-xs text-ink-3">
            {rupees(alt.preview.quarterlySurplus)} / {rupees(alt.preview.plan.regularInstallment)}
          </p>
          <p className="flex flex-wrap items-center gap-1.5 text-xs text-ink-2">
            {t("review.row.saturation")}: <Badge tone={c.saturation === "unknown" ? "neutral" : levelTone(c.saturation)}>{t(c.saturation === "unknown" ? "g2.level.unknown" : `level.${c.saturation}`)}</Badge>
            <ConfidenceBadge value={c.confidence} compact />
          </p>
          <RulesCue />
        </div>
      </div>
    </Card>
  );
}

function CompareTable({ a, b }: { a: FeasibilityAttempt; b: FeasibilityAttempt }) {
  const { t } = useI18n();
  const lvl = (s: string) => t(s === "unknown" ? "g2.level.unknown" : `level.${s}`);
  const tier = (x: FeasibilityAttempt) => t(x.preview.plan.tier ? `review.tier.${x.preview.plan.tier.name}` : "review.tier.none");
  const num = (v: number | null, f: (n: number) => string) => (v === null ? "—" : f(v));
  const rows: { label: string; first: string; alt: string; firstWorse: boolean }[] = [
    { label: t("report.score"), first: String(Math.round(a.score)), alt: String(Math.round(b.score)), firstWorse: a.score < b.score },
    { label: t("review.row.coverage"), first: num(a.preview.baseDscr, ratio), alt: num(b.preview.baseDscr, ratio), firstWorse: (a.preview.baseDscr ?? 0) < (b.preview.baseDscr ?? 0) },
    { label: t("g2.review.row.seasonal"), first: num(a.preview.minSeasonalDscr, ratio), alt: num(b.preview.minSeasonalDscr, ratio), firstWorse: (a.preview.minSeasonalDscr ?? 0) < (b.preview.minSeasonalDscr ?? 0) },
    { label: t("review.row.competitors"), first: num(a.intel.competitor.count, String), alt: num(b.intel.competitor.count, String), firstWorse: (a.intel.competitor.zScore ?? 0) > (b.intel.competitor.zScore ?? 0) },
    { label: t("review.row.saturation"), first: lvl(a.intel.competitor.saturation), alt: lvl(b.intel.competitor.saturation), firstWorse: rank(a.intel.competitor.saturation) > rank(b.intel.competitor.saturation) },
    { label: t("g2.review.row.risk"), first: lvl(a.intel.risk.overall), alt: lvl(b.intel.risk.overall), firstWorse: rank(a.intel.risk.overall) > rank(b.intel.risk.overall) },
    { label: t("review.row.tier"), first: tier(a), alt: tier(b), firstWorse: false },
  ];
  return (
    <Card className="overflow-hidden p-0">
      <div className="grid grid-cols-[1.3fr_1fr_1fr] bg-sand text-xs font-semibold text-ink-2">
        <span className="px-3 py-2.5" />
        <span className="truncate px-2 py-2.5 text-clay-700">
          {activityLabel(a.activityId).emoji} {t(`verdict.${a.verdict}`)}
        </span>
        <span className="truncate px-2 py-2.5 text-azure-800">
          {activityLabel(b.activityId).emoji} {t(`verdict.${b.verdict}`)}
        </span>
      </div>
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[1.3fr_1fr_1fr] items-center border-t border-line text-[14px]">
          <span className="min-w-0 px-3 py-3 text-[13px] text-ink-2">{r.label}</span>
          <span className={cx("tabular min-w-0 px-2 py-3 font-semibold", r.firstWorse ? "text-clay-700" : "text-ink")}>{r.first}</span>
          <span className="tabular min-w-0 bg-azure-50 px-2 py-3 font-semibold text-azure-800">{r.alt}</span>
        </div>
      ))}
    </Card>
  );
}

const rank = (s: string) => ({ low: 0, medium: 1, high: 2 })[s as "low"] ?? -1;

function RulesCue() {
  const { t } = useI18n();
  return (
    <p className="mt-1.5 flex items-center justify-center gap-1 text-[11px] text-ink-3">
      <Calculator className="size-3" />
      {t("review.rules")}
    </p>
  );
}
