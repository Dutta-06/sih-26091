import { Calculator, FileText, RefreshCw, ShieldX } from "lucide-react";
import { cachedCompetitor, categoryPriorMultiplier } from "../../core/discovery";
import { affordableProjectCost, catalogActivity } from "../../core/intel/catalog";
import type { FeasibilityAttempt, LocationCandidate, RankedActivity } from "../../core/types";
import { coverageBand } from "../../engine/finance";
import { useI18n } from "../../i18n";
import { ratio, rupeesShort } from "../../lib/format";
import { Badge, Button, Card, ConfidenceBadge, cx, levelTone, Note, Ring, Sheet } from "../../ui";
import { activityLabel } from "../g2/feasibility";
import { useMsg } from "../g2/msg";
import { COMPONENT_COLOR, COMPONENT_MAX, COMPONENTS } from "./ScoreBar";

export function ShortlistSheet({
  item,
  rank,
  total,
  capital,
  skills,
  place,
  attempt,
  selected,
  onClose,
  onAssess,
  onReport,
  onReview,
}: {
  item: RankedActivity | null;
  rank: number;
  total: number;
  capital: number;
  skills: string[];
  place: LocationCandidate | null;
  attempt: FeasibilityAttempt | null;
  selected: boolean;
  onClose: () => void;
  onAssess: () => void;
  onReport: () => void;
  onReview: () => void;
}) {
  const { t, pick, lang } = useI18n();
  const mt = useMsg();
  if (!item) return null;
  const a = catalogActivity(item.activityId);
  const label = activityLabel(item.activityId);
  const b = item.breakdown;
  const share = (c: keyof typeof b) => b[c] / COMPONENT_MAX[c];
  const strongest = [...COMPONENTS].sort((x, y) => share(y) - share(x))[0];
  const weakest = [...COMPONENTS].sort((x, y) => share(x) - share(y))[0];
  const comp = a ? cachedCompetitor(a, place) : null;
  const prior = categoryPriorMultiplier(item.activityId, place?.district.id ?? null);
  const d = item.preview.baseDscr;
  const have = affordableProjectCost(capital);
  const need = a?.min_project_cost ?? 0;
  const skillKey = !skills.length ? "none" : b.skills >= COMPONENT_MAX.skills ? "yes" : b.skills > 4 ? "sector" : "no";
  const detail: Record<keyof typeof b, string> = {
    capitalFit: item.feasible ? t("shortlist.d.capitalOk", { need: rupeesShort(need, lang), have: rupeesShort(have, lang) }) : mt(item.infeasibleReason),
    repayment: d === null ? t("g2.short.noCover") : t(`shortlist.d.band.${coverageBand(d)}`, { cover: ratio(d) }),
    skills: t(`shortlist.d.skills.${skillKey}`),
    localDemand: comp && comp.count !== null ? t("shortlist.d.demand", { nearby: comp.count, level: t(item.crowding === "unknown" ? "g2.level.unknown" : `level.${item.crowding}`) }) : t("g2.short.demandUnknown"),
    outcomes: t("shortlist.d.prior", { x: prior.toFixed(2) }),
  };

  return (
    <Sheet open onClose={onClose} title={`${label.emoji} ${pick(label.name)}`}>
      <div className="flex items-center gap-4">
        <Ring value={item.score} size={84} tone={item.feasible ? "forest" : "clay"} sub={t("shortlist.outOf")} />
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-[13px] text-ink-3">{item.feasible ? t("shortlist.rankOf", { rank, total }) : t("shortlist.notRanked")}</p>
          <p className="tabular text-lg font-bold">{t("shortlist.coverLabel", { cover: d === null ? "—" : ratio(d) })}</p>
          <p className="flex items-center gap-1 text-[11px] text-ink-3">
            <Calculator className="size-3" />
            {t("shortlist.rules")}
          </p>
        </div>
      </div>

      <Card className="mt-4 divide-y divide-line py-1">
        {COMPONENTS.map((c) => (
          <div key={c} className="py-2.5">
            <div className="flex items-center gap-2">
              <span className={cx("size-2.5 shrink-0 rounded-full", COMPONENT_COLOR[c])} />
              <span className="min-w-0 flex-1 text-[14px] font-medium">{t(`shortlist.c.${c}`)}</span>
              {c === "localDemand" && comp && <ConfidenceBadge value={comp.confidence} />}
              <span className="tabular text-[14px] font-semibold">
                {b[c]}
                <span className="text-ink-3">/{COMPONENT_MAX[c]}</span>
              </span>
            </div>
            <p className="mt-1 pl-4.5 text-[13px] leading-snug text-ink-2">{detail[c]}</p>
          </div>
        ))}
      </Card>

      <div className="mt-3 flex flex-wrap items-center gap-2 px-1">
        <span className="text-[13px] text-ink-3">{t("shortlist.crowding")}</span>
        <Badge tone={item.crowding === "unknown" ? "neutral" : levelTone(item.crowding)}>{t(item.crowding === "unknown" ? "g2.level.unknown" : `level.${item.crowding}`)}</Badge>
        {item.adjacentTo && <Badge tone="info">{t("g2.short.adjacentTo", { name: pick(activityLabel(item.adjacentTo).name) })}</Badge>}
      </div>

      <h4 className="mt-4 mb-2 px-1 text-[13px] font-semibold tracking-wide text-ink-3 uppercase">{t("shortlist.why")}</h4>
      <Note tone={attempt && attempt.verdict !== "viable" ? "clay" : !item.feasible ? "clay" : selected ? "forest" : "sand"} icon={attempt && attempt.verdict !== "viable" ? ShieldX : undefined}>
        {item.feasible ? t("shortlist.whyRanked", { strong: t(`shortlist.c.${strongest}`), weak: t(`shortlist.c.${weakest}`) }) : mt(item.infeasibleReason)}
        {attempt && attempt.verdict !== "viable" && (
          <span className="mt-1 block">
            {t("g2.short.reviewSaid", { verdict: t(`verdict.${attempt.verdict}`) })} {attempt.findings.map((f) => mt(f.msg)).join(" ")}
          </span>
        )}
        {selected && <span className="mt-1 block">{t("g2.short.selected")}</span>}
      </Note>

      {attempt ? (
        <Button variant="secondary" size="md" icon={attempt.verdict === "viable" ? FileText : ShieldX} className="mt-3 w-full" onClick={attempt.verdict === "viable" ? onReport : onReview}>
          {t(attempt.verdict === "viable" ? "review.viewReport" : "shortlist.openReview")}
        </Button>
      ) : (
        <Button size="md" icon={RefreshCw} className="mt-3 w-full" onClick={onAssess}>
          {t("g2.short.assess")}
        </Button>
      )}
      <Button variant="ghost" size="md" className="mt-1 w-full" onClick={onClose}>
        {t("shortlist.close")}
      </Button>
    </Sheet>
  );
}
