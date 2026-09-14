import type { GrievanceTicket } from "../../core/types";
import { useI18n } from "../../i18n";
import { Badge, Card, cx } from "../../ui";
import { dateLabel } from "../g4/model";

const STEPS = ["logged", "mentor_assigned", "in_progress", "resolved"] as const;

/** Earlier ticket with its routing and the status derived from elapsed time on the demo clock. */
export function PastTicket({ ticket: g, status }: { ticket: GrievanceTicket; status: GrievanceTicket["status"] }) {
  const { t, tm, lang } = useI18n();
  const at = Math.max(0, (STEPS as readonly string[]).indexOf(status));
  const resolved = status === "resolved";
  return (
    <Card className="p-3.5">
      <div className="flex items-center justify-between gap-2">
        <span className="tabular truncate text-xs font-bold text-ink-3">{g.id} · {dateLabel(g.at, lang)}</span>
        <Badge tone={resolved ? "good" : "warn"}>{t(`grievance.step.${STEPS[at]}`)}</Badge>
      </div>
      <p className="mt-1 text-[15px] font-semibold">{t(`grievance.issue.${g.issue}`)}</p>
      <p className="truncate text-[13px] text-ink-3">{g.text}</p>
      <p className="mt-0.5 truncate text-xs text-ink-3">{t("grievance.routedTo")}: {tm(g.routedTo)}</p>

      <div className="mt-3 flex items-center" aria-label={t(`grievance.step.${STEPS[at]}`)}>
        {STEPS.map((s, i) => (
          <div key={s} className={cx("flex items-center", i < STEPS.length - 1 && "flex-1")}>
            <span className={cx("size-2.5 shrink-0 rounded-full", i <= at ? "bg-forest-600" : "bg-line")} />
            {i < STEPS.length - 1 && <span className={cx("mx-1 h-0.5 flex-1 rounded-full", i < at ? "bg-forest-600" : "bg-line")} />}
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between gap-1 text-[11px] text-ink-3">
        {STEPS.map((s, i) => (
          <span key={s} className={cx(i === at && "font-semibold text-ink-2")}>{t(`grievance.step.${s}`)}</span>
        ))}
      </div>
    </Card>
  );
}
