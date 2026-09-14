import { Brain, Calculator, Link2, Lock, ShieldX, Sparkles, Star } from "lucide-react";
import { useMemo, useState } from "react";
import { affordableProjectCost } from "../core/intel/catalog";
import { outcomeSeed } from "../core/pack";
import type { RankedActivity } from "../core/types";
import { useI18n } from "../i18n";
import { tap } from "../lib/haptics";
import { ratio, rupeesShort } from "../lib/format";
import { useNav } from "../nav";
import { useStore } from "../state/store";
import { Badge, Card, cx, Note, Reveal, Screen, Section } from "../ui";
import { activityLabel, placeOf } from "./g2/feasibility";
import { useMsg } from "./g2/msg";
import { ScoreBar, ScoreLegend } from "./w2/ScoreBar";
import { ShortlistSheet } from "./w2/ShortlistSheet";

export default function Shortlist() {
  const { t, pick, lang } = useI18n();
  const mt = useMsg();
  const { state, dispatch, set, view } = useStore();
  const { push } = useNav();
  const [open, setOpen] = useState<RankedActivity | null>(null);
  const f = view.feasibility;
  const ranked = f.shortlist;
  const place = placeOf(view);
  const feasible = ranked.filter((r) => r.feasible);
  const outcomes = useMemo(() => {
    const seed = outcomeSeed();
    return { synthetic: seed.filter((r) => r.is_synthetic).length, real: seed.filter((r) => !r.is_synthetic).length + state.realOutcomes.length };
  }, [state.realOutcomes.length]);
  const attemptOf = (id: string) => f.attempts.find((a) => a.activityId === id) ?? null;

  const assess = (id: string) => {
    tap();
    setOpen(null);
    dispatch({ type: "profile", patch: { activityId: id } });
    set({ chosenActivity: null });
    dispatch({ type: "event", event: { type: "analysis_run", data: { activityId: id, from: "shortlist" } } });
    push({ name: "analysis" });
  };

  return (
    <Screen title={t("shortlist.title")} subtitle={t("shortlist.subtitle", { savings: rupeesShort(state.profile.capital, lang), project: rupeesShort(affordableProjectCost(state.profile.capital), lang) })}>
      <Reveal i={0} className="mt-2">
        <Card tone="sand" className="space-y-3">
          <p className="text-[13px] leading-snug text-ink-2">{t("shortlist.how")}</p>
          <ScoreLegend />
          <p className="flex items-center gap-1.5 text-[11px] text-ink-3">
            <Calculator className="size-3" />
            {t("shortlist.rules")}
          </p>
        </Card>
      </Reveal>
      <div className="mt-3 space-y-2">
        <Note tone="marigold" icon={Brain}>
          {t("shortlist.learning", { synthetic: outcomes.synthetic, real: outcomes.real })}
        </Note>
        {f.constraints.map((c, i) => (
          <Note key={i} tone="clay">
            {mt(c)}
          </Note>
        ))}
      </div>

      <Section title={t("shortlist.count", { n: feasible.length, total: ranked.length })}>
        <div className="space-y-2.5">
          {ranked.map((r, i) => {
            const label = activityLabel(r.activityId);
            const attempt = attemptOf(r.activityId);
            const isSelected = f.selected?.activityId === r.activityId;
            const rejected = attempt && attempt.verdict !== "viable";
            return (
              <Reveal key={r.activityId} i={i + 1}>
                <Card onClick={() => setOpen(r)} className={cx(!r.feasible && "opacity-60", isSelected && "ring-2 ring-azure-600", rejected && "ring-1 ring-clay-100")}>
                  <div className="flex items-center gap-3">
                    <span className="tabular w-5 shrink-0 text-center text-sm font-bold text-ink-3">{r.feasible ? feasible.indexOf(r) + 1 : "–"}</span>
                    <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-cream text-2xl">{label.emoji}</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[15px] leading-snug font-semibold break-words">{pick(label.name)}</p>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {isSelected && (
                          <Badge tone="good" icon={Sparkles}>
                            {t("shortlist.recommended")}
                          </Badge>
                        )}
                        {r.isPreference && (
                          <Badge tone="info" icon={Star}>
                            {t("shortlist.yourIdea")}
                          </Badge>
                        )}
                        {rejected && (
                          <Badge tone={attempt.verdict === "marginal" ? "warn" : "risk"} icon={ShieldX}>
                            {t(`verdict.${attempt.verdict}`)}
                          </Badge>
                        )}
                        {r.adjacentTo && (
                          <Badge icon={Link2}>{t("g2.short.adjacentTo", { name: pick(activityLabel(r.adjacentTo).name) })}</Badge>
                        )}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className={cx("tabular text-2xl leading-none font-bold", isSelected ? "text-azure-800" : "text-ink")}>{Math.round(r.score)}</p>
                      <p className="text-[11px] text-ink-3">{t("shortlist.outOf")}</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <ScoreBar parts={r.breakdown} muted={!r.feasible} />
                  </div>
                  {r.feasible ? (
                    <p className="tabular mt-2 text-xs text-ink-3">
                      {t("shortlist.meta", { cover: r.preview.baseDscr === null ? "—" : ratio(r.preview.baseDscr), crowding: t(r.crowding === "unknown" ? "g2.level.unknown" : `level.${r.crowding}`) })}
                    </p>
                  ) : (
                    <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-clay-700">
                      <Lock className="size-3.5 shrink-0" />
                      {mt(r.infeasibleReason)}
                    </p>
                  )}
                </Card>
              </Reveal>
            );
          })}
        </div>
      </Section>
      <ShortlistSheet
        item={open}
        rank={open && open.feasible ? feasible.indexOf(open) + 1 : 0}
        total={feasible.length}
        capital={state.profile.capital}
        skills={state.profile.skills}
        place={place}
        attempt={open ? attemptOf(open.activityId) : null}
        selected={!!open && f.selected?.activityId === open.activityId}
        onClose={() => setOpen(null)}
        onAssess={() => open && assess(open.activityId)}
        onReport={() => {
          setOpen(null);
          push({ name: "report" });
        }}
        onReview={() => {
          setOpen(null);
          push({ name: "review" });
        }}
      />
    </Screen>
  );
}
