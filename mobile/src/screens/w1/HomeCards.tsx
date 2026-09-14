import { ArrowRight, CalendarCheck, History, X } from "lucide-react";
import { motion } from "motion/react";
import type { CaseView } from "../../core/session";
import { useI18n } from "../../i18n";
import type { JourneyState } from "../../state/store";
import { Button, Card, IconBubble } from "../../ui";
import { useFmt } from "./chatI18n";
import { timelineItems } from "./timeline";

const DAY = 86_400_000;

/** Days since the previous visit, or null when it was recent (TDD 4.1 resume after a gap). */
export function daysAway(s: JourneyState): number | null {
  if (!s.previousVisitAt) return null;
  const days = Math.floor((Date.now() - new Date(s.previousVisitAt).getTime()) / DAY);
  return days >= 2 ? days : null;
}

type Line = { key: string; vars?: Record<string, string | number> };

/** What changed since the previous visit (recorded events), else where the case stands now (computed). */
function bullets(s: JourneyState, view: CaseView): { since: boolean; lines: Line[] } {
  const prev = s.previousVisitAt ?? "";
  const since = timelineItems(s)
    .filter((e) => e.at > prev)
    .slice(-3)
    .map((e) => ({ key: e.title, vars: e.vars }));
  if (since.length) return { since: true, lines: since };
  const lines: Line[] = [];
  if (s.appStage !== "not_started") lines.push({ key: "u1.wb.stage", vars: { stage: `@u1.stage.${s.appStage}` } });
  if (view.documents && s.appStage !== "not_started" && s.appStage !== "disbursed") {
    const total = view.documents.items.length;
    const n = view.documents.outstanding.length;
    lines.push(n ? { key: "u1.wb.docs", vars: { n, total } } : { key: "u1.wb.docsDone", vars: { total } });
  }
  if (view.latestHealth?.score != null) lines.push({ key: "u1.wb.health", vars: { score: Math.round(view.latestHealth.score) } });
  return { since: false, lines };
}

export function WelcomeBackCard({ state, view, days, onContinue, onHistory, onDismiss }: { state: JourneyState; view: CaseView; days: number; onContinue: () => void; onHistory: () => void; onDismiss: () => void }) {
  const { t } = useI18n();
  const fmt = useFmt();
  const { since, lines } = bullets(state, view);
  return (
    <motion.div initial={{ opacity: 0, y: -8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: "spring", damping: 24, stiffness: 260 }} className="mt-3">
      <Card tone="marigold" className="relative">
        <button aria-label={t("action.close")} onClick={onDismiss} className="absolute top-2 right-2 grid size-10 place-items-center rounded-full text-ink-3 active:bg-white/60">
          <X className="size-4.5" />
        </button>
        <div className="flex items-start gap-3 pr-8">
          <IconBubble icon={CalendarCheck} tone="marigold" size="sm" />
          <div className="min-w-0">
            <p className="text-[17px] leading-tight font-bold text-ink">{t("u1.wb.title")}</p>
            <p className="mt-1 text-[14px] leading-snug text-ink-2">
              {t("u1.wb.days", { n: days })} {t(since ? "u1.wb.since" : "u1.wb.nothing")}
            </p>
          </div>
        </div>
        {lines.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {lines.map((b, i) => (
              <li key={`${b.key}-${i}`} className="flex gap-2 text-[14px] leading-snug text-ink-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-marigold-500" />
                {fmt(b)}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
          <Button size="md" iconRight={ArrowRight} onClick={onContinue}>
            {t("u1.wb.continue")}
          </Button>
          <Button size="md" variant="secondary" icon={History} onClick={onHistory}>
            {t("u1.wb.history")}
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}
