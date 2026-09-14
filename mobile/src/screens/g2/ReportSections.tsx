import { AlertTriangle, ArrowRight, Building2, Bus, Factory, GraduationCap, Landmark, Map as MapIcon, Package, ShoppingBasket, Sparkles, Store, Truck, Users, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";
import { MONTHS } from "../../core/intel/catalog";
import { packMeta } from "../../core/pack";
import type { Confidence, FeasibilityAttempt, Intel, IntelMeta, PackPoi, Swot } from "../../core/types";
import { useI18n } from "../../i18n";
import { rupees } from "../../lib/format";
import { useNav } from "../../nav";
import { BarChart } from "../../ui/charts";
import { Badge, Button, Card, ConfidenceBadge, cx, IconBubble, levelTone, Note, Progress, Reveal, Section, Stat } from "../../ui";
import { competitorBenchmark } from "./feasibility";
import { useMsg } from "./msg";

export const PLACE_ICON: Record<PackPoi["kind"], LucideIcon> = { market: Store, haat: ShoppingBasket, transport: Bus, school: GraduationCap, supplier: Truck, bank: Landmark, enterprise: Building2 };

const lvlKey = (s: string) => (s === "unknown" ? "g2.level.unknown" : `level.${s}`);
const lvlTone = (s: string) => (s === "unknown" ? "neutral" : levelTone(s as "low"));

function SectionCard({ title, meta, i, children }: { title: string; meta: IntelMeta; i: number; children: ReactNode }) {
  return (
    <Section title={title} action={<ConfidenceBadge value={meta.confidence} />}>
      <Reveal i={i}>
        <Card>
          {children}
          <MetaFooter meta={meta} />
        </Card>
      </Reveal>
    </Section>
  );
}

/** Limitations and sources of one analysis (collapsed by default). */
function MetaFooter({ meta }: { meta: IntelMeta }) {
  const { t, pick } = useI18n();
  const mt = useMsg();
  const [open, setOpen] = useState(false);
  if (!meta.limitations.length && !meta.sources.length) return null;
  return (
    <div className="mt-3 border-t border-line pt-2">
      <button onClick={() => setOpen((o) => !o)} className="flex min-h-10 w-full items-center justify-between text-left text-[13px] font-semibold text-forest-800">
        {t("g2.meta.toggle", { l: meta.limitations.length, s: meta.sources.length })}
        <ArrowRight className={cx("size-4 transition-transform", open && "rotate-90")} />
      </button>
      {open && (
        <div className="space-y-2 pb-1">
          {meta.limitations.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-ink-3">{t("g2.meta.limitations")}</p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-[13px] leading-snug text-ink-2">
                {meta.limitations.map((l, i) => (
                  <li key={i}>{mt(l)}</li>
                ))}
              </ul>
            </div>
          )}
          {meta.sources.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-ink-3">{t("g2.meta.sources")}</p>
              <ul className="mt-1 space-y-1">
                {meta.sources.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px] leading-snug text-ink-2">
                    <span className="min-w-0 flex-1 break-words">{pick(s.name)}</span>
                    <ConfidenceBadge value={s.confidence} compact />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** "+N local reports" link into the evidence screen (TDD 5.6); count = distinct pack feedback ids used by the section. */
function LocalReportsLink({ n }: { n: number }) {
  const { t } = useI18n();
  const { push } = useNav();
  if (!n) return null;
  return (
    <button onClick={() => push({ name: "evidence" })} className="mt-3 flex min-h-10 items-center gap-1 text-[13px] font-semibold text-forest-800 active:opacity-70">
      <Users className="size-4" />
      {t("w2.localReports", { n })}
      <ArrowRight className="size-4" />
    </button>
  );
}


export function MarketSection({ intel, i }: { intel: Intel; i: number }) {
  const { t, pick } = useI18n();
  const { push } = useNav();
  const m = intel.marketReach;
  return (
    <SectionCard title={t("report.market")} meta={m} i={i}>
      <div className="grid grid-cols-3 gap-3">
        <Stat label={t("report.population", { r: m.radiusKm })} value={m.population ?? "—"} />
        <Stat label={t("report.consumers")} value={m.consumerBase ?? "—"} />
        <Stat label={t("g2.market.households")} value={m.households ?? "—"} />
      </div>
      <p className="mt-4 mb-1 text-xs font-semibold text-ink-3">{t("g2.market.places", { n: m.places.length, r: m.radiusKm })}</p>
      {m.places.length === 0 ? (
        <p className="text-[13px] text-ink-3">{t("g2.market.noPlaces")}</p>
      ) : (
        <div className="divide-y divide-line">
          {m.places.slice(0, 6).map((p) => {
            const Icon = PLACE_ICON[p.poi.kind] ?? Store;
            return (
              <div key={p.poi.id} className="flex min-h-12 items-center gap-3 py-2">
                <IconBubble icon={Icon} tone={p.poi.kind === "school" ? "marigold" : "forest"} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] leading-snug">{pick(p.poi.name)}</p>
                  <p className="text-xs text-ink-3">{t(`map.type.${p.poi.kind}`)}</p>
                </div>
                <span className="tabular text-[13px] text-ink-3">{t("unit.km", { n: p.km.toFixed(1) })}</span>
                <ConfidenceBadge value="real" compact />
              </div>
            );
          })}
        </div>
      )}
      <Button variant="secondary" size="md" icon={MapIcon} className="mt-3 w-full" onClick={() => push({ name: "map" })}>
        {t("report.viewMap")}
      </Button>
    </SectionCard>
  );
}

export function OpportunitySection({ intel, i }: { intel: Intel; i: number }) {
  const { t } = useI18n();
  const o = intel.opportunity;
  const evidence = new Set(o.niches.flatMap((n) => n.evidenceIds));
  return (
    <SectionCard title={t("report.opportunity")} meta={o} i={i}>
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[13px] text-ink-3">{t("g2.opp.overall")}</span>
        <Badge tone={lvlTone(o.saturation)}>{t(lvlKey(o.saturation))}</Badge>
      </div>
      {o.niches.length === 0 ? (
        <p className="text-[13px] text-ink-3">{t("g2.opp.none")}</p>
      ) : (
        <div className="divide-y divide-line">
          {o.niches.map((n) => (
            <div key={n.name} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
              <IconBubble icon={Sparkles} tone="marigold" size="sm" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-medium break-words">{n.name}</p>
                <p className="mt-0.5 line-clamp-3 text-[13px] leading-snug text-ink-3">{n.detail}</p>
                <p className="mt-1 text-[11px] text-ink-3">
                  {t("g2.opp.source", { source: n.source.replace(/^.*[\\/]/, ""), pct: Math.round(n.relevance * 100) })}
                  {n.evidenceIds.length > 0 && ` · ${t("g2.opp.evidence", { n: n.evidenceIds.length })}`}
                </p>
              </div>
              <Badge tone={lvlTone(n.saturation)}>{t("report.saturation", { level: t(lvlKey(n.saturation)) })}</Badge>
            </div>
          ))}
        </div>
      )}
      <LocalReportsLink n={evidence.size} />
    </SectionCard>
  );
}

export function CompetitorSection({ attempt, stateName, i }: { attempt: FeasibilityAttempt; stateName: string; i: number }) {
  const { t } = useI18n();
  const c = attempt.intel.competitor;
  const bench = competitorBenchmark(attempt.intel, attempt.activityId);
  const rows = [
    { label: t(c.tier === "overpass" ? "report.yourArea" : "g2.comp.districtRegistered"), v: c.densityPer10k, tone: "forest" as const },
    ...(c.tier === "overpass" ? [{ label: t("g2.comp.districtRegistered"), v: c.districtPer10k, tone: "marigold" as const }] : []),
    { label: t("w2.bench.stateAvg", { state: stateName }), v: c.statePer10k, tone: "clay" as const },
    ...(bench.scope === "catalog" ? [{ label: t("g2.comp.benchCatalog"), v: bench.value, tone: "clay" as const }] : []),
  ];
  const scale = Math.max(0.0001, ...rows.map((r) => r.v ?? 0)) * 1.15;
  const z = c.zScore;
  const wording = z === null ? "g2.comp.noZ" : z >= 2 ? "w2.bench.wellAbove" : z >= 1 ? "g2.comp.above" : z <= -1 ? "w2.bench.wellBelow" : "w2.bench.near";
  return (
    <SectionCard title={t("report.competitors")} meta={c} i={i}>
      <div className="grid grid-cols-2 gap-3">
        <Stat label={t(c.tier === "udyam" ? "g2.comp.countDistrict" : "g2.comp.countRadius", { r: attempt.intel.marketReach.radiusKm })} value={c.count ?? "—"} tone="forest" />
        <Stat label={t("report.saturationLabel")} value={<Badge tone={lvlTone(c.saturation)}>{t(lvlKey(c.saturation))}</Badge>} />
      </div>
      <p className="mt-4 mb-1.5 text-xs font-semibold text-ink-3">{t("g2.comp.tiers")}</p>
      <div className="flex flex-wrap gap-1.5">
        {c.tiersAttempted.map((tr) => (
          <Badge key={tr.tier} tone={tr.status === "used" ? "good" : "neutral"}>
            {t(`g2.comp.tier.${tr.tier}`)} · {t(`g2.comp.status.${tr.status}`)}
          </Badge>
        ))}
      </div>
      <p className="mt-4 mb-2 text-xs font-semibold text-ink-3">{t("report.density")}</p>
      {rows.map((row) => (
        <div key={row.label} className="mb-2 flex items-center gap-3 last:mb-0">
          <span className="w-28 shrink-0 text-[13px] leading-tight text-ink-2">{row.label}</span>
          <Progress value={row.v === null ? 0 : (row.v / scale) * 100} tone={row.tone} className="h-3 flex-1" />
          <span className="tabular w-10 text-right text-sm font-semibold">{row.v === null ? "—" : row.v.toFixed(1)}</span>
        </div>
      ))}
      <div className="mt-3">
        <Note tone={z !== null && z >= 1 ? "marigold" : "forest"}>
          {t(wording)} {z !== null && <span className="tabular text-xs opacity-80">{t("g2.comp.z", { z: z.toFixed(1), scope: t(`g2.comp.scope.${bench.scope}`) })}</span>}
        </Note>
      </div>
    </SectionCard>
  );
}

export function PricingSection({ intel, i }: { intel: Intel; i: number }) {
  const { t, pick } = useI18n();
  const p = intel.pricing;
  const max = Math.max(1, ...p.points.map((x) => x.high));
  const last12 = p.history.slice(-12);
  return (
    <SectionCard title={t("report.pricing")} meta={p} i={i}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge tone={p.basis === "direct_market_data" ? "good" : p.basis === "unavailable" ? "neutral" : "warn"}>{t(`g2.price.basis.${p.basis}`)}</Badge>
        {p.purchasingPowerIndex !== null && <span className="tabular text-xs text-ink-3">{t("g2.price.index", { x: p.purchasingPowerIndex.toFixed(2) })}</span>}
      </div>
      {p.points.length === 0 ? (
        <p className="text-[13px] text-ink-3">{t("g2.price.none")}</p>
      ) : (
        p.points.map((pt) => (
          <div key={pt.label.en} className="border-t border-line py-2.5 first:border-t-0">
            <div className="flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-medium">{pick(pt.label)}</p>
                <p className="truncate text-[11px] text-ink-3">{pick(pt.unit)}</p>
              </div>
              <span className="tabular text-[14px] font-semibold">{pt.low === pt.high ? rupees(pt.low) : `${rupees(pt.low)}–${rupees(pt.high)}`}</span>
              <ConfidenceBadge value={pt.confidence} compact />
            </div>
            <div className="relative mt-2 h-1.5 rounded-full bg-ink-3/15">
              <div className="absolute inset-y-0 min-w-1.5 rounded-full bg-forest-600" style={{ left: `${(pt.low / max) * 100}%`, width: `${((pt.high - pt.low) / max) * 100}%` }} />
            </div>
          </div>
        ))
      )}
      {last12.length > 1 && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-semibold text-ink-3">{t("g2.price.history", { n: last12.length })}</p>
          <BarChart height={70} data={last12.map((h) => ({ label: MONTHS[+h.month.slice(5, 7) - 1].slice(0, 1), value: h.modal }))} formatValue={rupees} />
        </div>
      )}
    </SectionCard>
  );
}

export function RiskSection({ intel, i }: { intel: Intel; i: number }) {
  const { t, pick } = useI18n();
  const mt = useMsg();
  const r = intel.risk;
  const low = new Set(r.lowMonths);
  const feedbackFlags = r.flags.filter((f) => f.category === "local_feedback").length;
  return (
    <SectionCard title={t("report.risks")} meta={r} i={i}>
      <div className="grid grid-cols-2 gap-3">
        <Stat label={t("g2.risk.overall")} value={<Badge tone={levelTone(r.overall)}>{t(`level.${r.overall}`)}</Badge>} />
        <Stat label={t("g2.risk.hub")} value={r.hubKm === null ? "—" : t("unit.km", { n: r.hubKm })} hint={r.hubName ? pick(r.hubName) : t("g2.risk.hubUnknown")} />
      </div>
      <p className="mt-4 mb-1 text-xs font-semibold text-ink-3">{t(`g2.risk.season.${r.seasonalBasis}`)}</p>
      <BarChart height={80} data={r.seasonalIndex.map((v, m) => ({ label: MONTHS[m].slice(0, 1), value: v, tone: low.has(m) ? "clay" : "forest" }))} formatValue={(v) => `${v.toFixed(2)}×`} />
      <p className="mt-1 text-xs text-ink-3">{r.lowMonths.length ? t("g2.risk.lowMonths", { months: r.lowMonths.map((m) => MONTHS[m]).join(", ") }) : t("g2.risk.noLowMonths")}</p>
      <div className="mt-3 space-y-2.5">
        {r.flags.map((f) => (
          <div key={f.id} className="rounded-2xl bg-cream p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className={cx("mt-0.5 size-4 shrink-0", f.severity === "high" ? "text-clay-600" : f.severity === "medium" ? "text-marigold-500" : "text-forest-600")} />
              <span className="min-w-0 flex-1 text-[15px] font-semibold leading-snug">{mt(f.title)}</span>
              <Badge tone={levelTone(f.severity)}>{t("report.riskLevel", { level: t(`level.${f.severity}`) })}</Badge>
            </div>
            <p className="mt-1 text-[13px] text-ink-2">{mt(f.detail)}</p>
            <div className="mt-2 flex items-start gap-2 text-[13px]">
              {f.mitigation ? (
                <>
                  <span className="shrink-0 font-semibold text-forest-800">{t("report.mitigation")}:</span>
                  <span className="min-w-0 flex-1 text-ink-2">{f.mitigation}</span>
                </>
              ) : (
                <span className="min-w-0 flex-1 text-xs text-ink-3">{t("g2.risk.noMitigation")}</span>
              )}
              <ConfidenceBadge value={f.confidence} compact />
            </div>
          </div>
        ))}
      </div>
      <LocalReportsLink n={feedbackFlags} />
    </SectionCard>
  );
}

const ROLE_ICON = { input: Package, enterprise: Factory, logistics: Truck, buyer: Users } as const;
const ROLE_TONE = { input: "sky", enterprise: "forest", logistics: "sand", buyer: "marigold" } as const;

export function SupplySection({ intel, i }: { intel: Intel; i: number }) {
  const { t, pick } = useI18n();
  const s = intel.supplyChain;
  const spof = new Set(s.singlePointsOfFailure);
  const roles = ["input", "enterprise", "logistics", "buyer"] as const;
  const labelOf = (id: string) => {
    const n = s.nodes.find((x) => x.id === id);
    return n ? pick(n.label) : id;
  };
  return (
    <SectionCard title={t("report.supply")} meta={s} i={i}>
      {roles.map((role, ri) => {
        const nodes = s.nodes.filter((n) => n.role === role);
        if (!nodes.length) return null;
        return (
          <div key={role}>
            {ri > 0 && <div className="ml-[21px] h-4 w-0.5 bg-forest-200" />}
            <div className="flex items-start gap-3">
              <IconBubble icon={ROLE_ICON[role]} tone={ROLE_TONE[role]} />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold text-ink-3">{t(`g2.supply.role.${role}`, { n: nodes.length })}</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {nodes.map((n) => (
                    <span key={n.id} className={cx("inline-flex max-w-full items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium", spof.has(n.id) ? "bg-clay-100 text-clay-700 ring-1 ring-clay-600/30" : "bg-sand text-ink-2")}>
                      <span className="truncate">{pick(n.label)}</span>
                      {n.km !== null && <span className="tabular shrink-0 text-ink-3">· {t("unit.km", { n: n.km.toFixed(1) })}</span>}
                      <ConfidenceBadge value={n.confidence} compact />
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );
      })}
      <p className="mt-3 text-xs text-ink-3">{t("g2.supply.edges", { n: s.edges.length, suppliers: s.suppliers.length })}</p>
      <div className="mt-2">
        {spof.size ? (
          <Note tone="marigold">{t("g2.supply.spof", { nodes: [...spof].map(labelOf).join(", ") })}</Note>
        ) : (
          <Note tone="forest">{t("g2.supply.noSpof")}</Note>
        )}
      </div>
    </SectionCard>
  );
}

export function SwotSection({ swot, i }: { swot: Swot; i: number }) {
  const { t } = useI18n();
  const mt = useMsg();
  const cells = [
    { key: "strengths", cls: "bg-forest-50 ring-forest-100 text-forest-800" },
    { key: "weaknesses", cls: "bg-clay-50 ring-clay-100 text-clay-700" },
    { key: "opportunities", cls: "bg-sky-100/60 ring-sky-100 text-sky-700" },
    { key: "threats", cls: "bg-marigold-50 ring-marigold-200 text-marigold-600" },
  ] as const;
  return (
    <Section title={t("report.swot")}>
      <Reveal i={i} className="grid grid-cols-1 gap-2.5 min-[380px]:grid-cols-2">
        {cells.map((c) => (
          <div key={c.key} className={cx("rounded-2xl p-3 ring-1", c.cls)}>
            <p className="text-[13px] font-bold">{t(`report.swot.${c.key}`)}</p>
            {swot[c.key].length === 0 ? (
              <p className="mt-1.5 text-[13px] text-ink-3">{t("g2.swot.empty")}</p>
            ) : (
              <ul className="mt-1.5 space-y-1.5">
                {swot[c.key].map((s, j) => (
                  <li key={j} className="flex items-start gap-1.5 text-[13px] leading-snug text-ink-2">
                    <span className="min-w-0 flex-1 break-words">{mt(s)}</span>
                    {s.vars?.confidence && <ConfidenceBadge value={s.vars.confidence as Confidence} compact />}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </Reveal>
    </Section>
  );
}

export function ConfidenceLegend({ i }: { i: number }) {
  const { t } = useI18n();
  return (
    <Section title={t("report.legend")}>
      <Reveal i={i}>
        <Card tone="sand" className="space-y-3">
          <div className="flex items-start gap-3">
            <ConfidenceBadge value="real" />
            <p className="text-[13px] leading-snug text-ink-2">{t("report.legendReal")}</p>
          </div>
          <div className="flex items-start gap-3">
            <ConfidenceBadge value="estimated" />
            <p className="text-[13px] leading-snug text-ink-2">{t("report.legendEst")}</p>
          </div>
        </Card>
      </Reveal>
    </Section>
  );
}

/** Disclosure wherever bundled data-pack values are shown (reads `_meta.json`). */
export function PackNote() {
  const { t } = useI18n();
  const meta = packMeta() as ReturnType<typeof packMeta> & { counts?: { villages?: number; pois?: number } };
  return (
    <p className="mt-6 text-center text-[11px] leading-snug text-ink-3">
      {meta.synthetic_sample ? t("g2.pack.sample", { villages: meta.counts?.villages ?? "—", pois: meta.counts?.pois ?? "—" }) : t("g2.pack.real")}
    </p>
  );
}
