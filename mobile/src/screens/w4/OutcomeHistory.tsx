import { LifeBuoy, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { useI18n } from "../../i18n";
import { Badge, Card, cx, IconBubble } from "../../ui";
import { monthLabel, ticketResolvedAt, ticketStatus, useLifecycle } from "../g4/model";

interface HistoryItem {
  id: string;
  kind: "intervention" | "grievance";
  title: string;
  month: string | null;
  before: number | null;
  after: number | null;
}

/** Recorded follow-ups (real outcome records on this device) and resolved grievances with the health change around them. */
export function OutcomeHistory() {
  const { t, lang } = useI18n();
  const { state, view, lc } = useLifecycle();
  const followUps = state.events.filter((e) => e.type === "follow_up");

  const items: HistoryItem[] = state.realOutcomes.map((r, i) => ({
    id: `o${i}`,
    kind: "intervention",
    title: t(`u4.intervention.${r.intervention_type}`),
    month: typeof followUps[i]?.data?.month === "string" ? (followUps[i].data!.month as string) : null,
    before: Math.round(r.health_before),
    after: Math.round(r.health_after),
  }));

  for (const g of state.grievances) {
    if (ticketStatus(g, lc.now) !== "resolved") continue;
    const openedMonth = g.at.slice(0, 7);
    const resolvedMonth = ticketResolvedAt(g).slice(0, 7);
    const before = view.health.find((h) => h.month === openedMonth)?.score ?? null;
    const after = lc.done.find((h) => h.month > resolvedMonth && h.score !== null)?.score ?? null;
    items.push({ id: g.id, kind: "grievance", title: t(`grievance.issue.${g.issue}`), month: resolvedMonth, before: before === null ? null : Math.round(before), after: after === null ? null : Math.round(after) });
  }

  if (!items.length) {
    return (
      <Card>
        <p className="text-[13px] leading-snug text-ink-3">{t("u4.history.empty")}</p>
      </Card>
    );
  }

  return (
    <Card className="divide-y divide-line py-1">
      {items.reverse().map((h) => {
        const measured = h.before !== null && h.after !== null;
        const up = measured && h.after! > h.before!;
        return (
          <div key={h.id} className="flex min-h-16 items-center gap-3 py-2.5">
            <IconBubble icon={h.kind === "grievance" ? LifeBuoy : Sparkles} tone={h.kind === "grievance" ? "clay" : "marigold"} size="sm" />
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-medium leading-snug">{h.title}</p>
              <p className="text-[13px] text-ink-3">
                {t(h.kind === "grievance" ? "w4.history.grievance" : "w4.history.intervention")}
                {h.month ? ` · ${monthLabel(h.month, lang)}` : ""}
              </p>
            </div>
            <div className="text-right">
              {measured ? (
                <>
                  <p className={cx("tabular flex items-center justify-end gap-1 text-[15px] font-semibold", up ? "text-forest-700" : "text-clay-700")}>
                    {up ? <TrendingUp className="size-4" /> : <TrendingDown className="size-4" />}
                    {h.before} → {h.after}
                  </p>
                  <Badge tone={up ? "good" : "risk"}>{t(up ? "w4.history.improved" : "w4.history.notImproved")}</Badge>
                </>
              ) : (
                <Badge tone="neutral">{t("u4.history.notMeasured")}</Badge>
              )}
            </div>
          </div>
        );
      })}
    </Card>
  );
}
