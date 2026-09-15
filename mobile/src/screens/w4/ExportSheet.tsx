import { Copy, FileJson } from "lucide-react";
import { useMemo } from "react";
import { useI18n } from "../../i18n";
import { useStore, todayOf } from "../../state/store";
import { Button, Note, Sheet, toast } from "../../ui";
import { consentLog } from "../g4/model";

const PREVIEW_CHARS = 1800;

/** "Download my data": builds the JSON of what is actually stored on this phone (inputs, events, parsed transactions). */
export function ExportSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const { state, view } = useStore();

  const { json, bytes, txCount, consentCount } = useMemo(() => {
    if (!open) return { json: "", bytes: 0, txCount: 0, consentCount: 0 };
    const txns = view.transactions;
    const sum = (dir: "credit" | "debit") => Math.round(txns.filter((x) => x.direction === dir).reduce((s, x) => s + x.amount, 0));
    const byChannel: Record<string, number> = {};
    for (const x of txns) byChannel[x.channel] = (byChannel[x.channel] ?? 0) + 1;
    const consent = consentLog(state);
    const data = {
      exportedAt: todayOf(state),
      inputs: { profile: state.profile, chosenActivity: state.chosenActivity },
      application: { stage: state.appStage, disbursedOn: state.disbursedOn, documents: state.documents },
      monitoring: {
        consent: state.smsConsent,
        consentLog: consent,
        dataDeletedOn: state.dataDeletedOn,
        transactions: {
          count: txns.length,
          from: txns.length ? txns.reduce((m, x) => (x.at < m ? x.at : m), txns[0].at).slice(0, 10) : null,
          to: txns.length ? txns.reduce((m, x) => (x.at > m ? x.at : m), txns[0].at).slice(0, 10) : null,
          creditTotal: sum("credit"),
          debitTotal: sum("debit"),
          byChannel,
          records: txns,
        },
      },
      milestonesDone: state.milestonesDone,
      interventionChosen: state.interventionChosen,
      followUp: state.followUp,
      realOutcomes: state.realOutcomes,
      grievances: state.grievances.map((g) => ({ id: g.id, issue: g.issue, text: g.text, at: g.at, routedTo: g.routedTo.key })),
      observations: state.observations,
      joinedPool: state.joinedPool,
    };
    const s = JSON.stringify(data, null, 1);
    return { json: s, bytes: new Blob([s]).size, txCount: txns.length, consentCount: consent.length };
  }, [open, state, view.transactions]);

  const size = bytes >= 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes} B`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      toast(t("u4.export.copied"));
    } catch {
      toast(t("u4.export.copyFailed"), { tone: "warn" });
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title={t("w4.export.title")}>
      <p className="text-[13px] text-ink-3">{t("w4.export.count", { n: txCount, c: consentCount })}</p>
      <div className="mt-3 overflow-x-auto rounded-2xl bg-white p-3">
        <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-ink-3">
          <FileJson className="size-4" />
          {t("u4.export.size", { size })}
        </p>
        <pre className="tabular max-h-72 overflow-y-auto text-[11px] leading-snug whitespace-pre-wrap text-ink-2 [overflow-wrap:anywhere]">
          {json.length > PREVIEW_CHARS ? `${json.slice(0, PREVIEW_CHARS)}\n…` : json}
        </pre>
      </div>
      <div className="mt-3">
        <Note>{t("u4.export.note")}</Note>
      </div>
      <div className="mt-4 grid gap-2">
        <Button icon={Copy} onClick={copy}>
          {t("u4.export.copy")}
        </Button>
        <Button variant="ghost" onClick={onClose}>
          {t("action.done")}
        </Button>
      </div>
    </Sheet>
  );
}
