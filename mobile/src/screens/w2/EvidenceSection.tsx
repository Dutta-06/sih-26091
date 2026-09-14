import { ArrowRight, Quote } from "lucide-react";
import type { Intel } from "../../core/types";
import { useI18n } from "../../i18n";
import { useNav } from "../../nav";
import { useStore } from "../../state/store";
import { Button, Card, ConfidenceBadge, Reveal, Section } from "../../ui";
import { evidenceFor } from "./evidence";

/** Report section: a preview of evidence from people nearby (TDD 5.6), read from the pack and this phone. */
export function EvidenceSection({ intel, district, activityId, i }: { intel: Intel; district: string | null; activityId: string | null; i: number }) {
  const { t, pick } = useI18n();
  const { push } = useNav();
  const { state } = useStore();
  const ev = evidenceFor(district, activityId, intel, state.observations);
  const quote = ev.pack.find((e) => e.uses.length) ?? ev.pack[0];
  const total = ev.pack.length + ev.mine.length;
  return (
    <Section title={t("w2.evidenceSection")} action={<ConfidenceBadge value="real" />}>
      <Reveal i={i}>
        <Card>
          {quote ? (
            <div className="flex gap-2.5">
              <Quote className="mt-0.5 size-4 shrink-0 text-azure-600" />
              <div className="min-w-0">
                <p className="text-[14px] leading-snug text-ink-2">“{pick(quote.record.text)}”</p>
                <p className="mt-1 text-xs text-ink-3">{pick(quote.record.who)}</p>
              </div>
            </div>
          ) : (
            <p className="text-[13px] text-ink-3">{t("g2.evidence.none")}</p>
          )}
          <div className="mt-3 grid grid-cols-2 gap-2 rounded-2xl bg-cream p-3 text-center">
            <div>
              <p className="tabular text-xl font-bold text-azure-800">{ev.usedCount}</p>
              <p className="text-[11px] leading-tight text-ink-3">{t("g2.evidence.used")}</p>
            </div>
            <div>
              <p className="tabular text-xl font-bold text-marigold-600">{ev.mine.length}</p>
              <p className="text-[11px] leading-tight text-ink-3">{t("evidence.mine")}</p>
            </div>
          </div>
          <Button variant="secondary" size="md" iconRight={ArrowRight} className="mt-3 w-full" onClick={() => push({ name: "evidence" })}>
            {t("w2.evidenceAll", { n: total })}
          </Button>
        </Card>
      </Reveal>
    </Section>
  );
}
