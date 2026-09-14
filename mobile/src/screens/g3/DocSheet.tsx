import { AlertTriangle, Camera, CheckCircle2, Clock, ImageUp, RotateCcw, ScanText, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { tap } from "../../App";
import { readDocument, type ScanFields, type ScanResult } from "../../core/docscan";
import { validateField } from "../../core/documents";
import type { Bi } from "../../i18n";
import { useI18n } from "../../i18n";
import { canScan, scanDocument, ScanError, type ScanFailure, type ScanSource } from "../../lib/scanner";
import type { DocStatus } from "../../state/store";
import { Badge, Button, Sheet } from "../../ui";
import { useApplicant, type Applicant } from "./applicant";

type Phase = { name: "ask" } | { name: "scanning" } | { name: "review"; result: ScanResult } | { name: "error"; reason: ScanFailure };

const FIELD_ORDER: (keyof ScanFields)[] = ["name", "dob", "gender", "aadhaarMasked", "pan", "epic", "ifsc", "accountMasked", "pincode", "udyam"];

/** Values from a scan that the application form keeps (masked where sensitive, validated first). */
function applicantPatch(f: ScanFields, keepName: boolean): Partial<Applicant> {
  const patch: Partial<Applicant> = {};
  if (f.name && keepName) patch.fullName = f.name;
  if (f.ifsc && validateField("ifsc_code", f.ifsc).ok) patch.ifsc = f.ifsc;
  if (f.accountMasked) patch.accountMasked = f.accountMasked;
  if (f.pincode && validateField("pincode", f.pincode).ok) patch.pincode = f.pincode;
  if (f.aadhaarMasked && f.aadhaarChecksumOk) patch.aadhaarLast4 = f.aadhaarMasked.slice(-4);
  if (f.udyam && validateField("udyam_registration_number", f.udyam).ok) patch.udyamNumber = f.udyam;
  return patch;
}

/** "Do you have it?" sheet: scan with the camera (on-device text recognition) or mark the document by hand. */
export function DocSheet({ doc, onClose, onSet }: { doc: { id: string; name: Bi } | null; onClose: () => void; onSet: (id: string, s: DocStatus) => void }) {
  const { t, pick } = useI18n();
  const [applicant, updateApplicant] = useApplicant();
  const [phase, setPhase] = useState<Phase>({ name: "ask" });

  function close() {
    setPhase({ name: "ask" });
    onClose();
  }

  async function scan(source: ScanSource) {
    if (!doc) return;
    tap();
    setPhase({ name: "scanning" });
    try {
      const lines = await scanDocument(source);
      setPhase({ name: "review", result: readDocument(lines, doc.id, applicant.fullName) });
      tap();
    } catch (e) {
      const reason = e instanceof ScanError ? e.reason : "failed";
      setPhase(reason === "cancelled" ? { name: "ask" } : { name: "error", reason });
    }
  }

  function accept(result: ScanResult) {
    if (!doc) return;
    const nameIssue = result.issues.some((i) => i.key === "c3.scan.issue.nameMismatch");
    updateApplicant(applicantPatch(result.fields, !applicant.fullName && !nameIssue));
    onSet(doc.id, "complete");
    tap();
    close();
  }

  if (!doc) return null;
  const scanAvailable = canScan();

  return (
    <Sheet open onClose={close} title={pick(doc.name)}>
      {phase.name === "ask" && (
        <>
          <p className="text-[15px] text-ink-2">{t("docs.sheet.ask")}</p>
          <div className="mt-4 space-y-2.5">
            {scanAvailable && (
              <div className="grid grid-cols-[1fr_auto] gap-2">
                <Button icon={Camera} onClick={() => scan("camera")}>
                  {t("docs.sheet.scan")}
                </Button>
                <Button variant="secondary" icon={ImageUp} aria-label={t("docs.scan.gallery")} onClick={() => scan("gallery")}>
                  <span className="sr-only">{t("docs.scan.gallery")}</span>
                </Button>
              </div>
            )}
            <Button variant="secondary" className="w-full" icon={CheckCircle2} onClick={() => { onSet(doc.id, "complete"); tap(); close(); }}>
              {t("docs.sheet.yes")}
            </Button>
            <Button variant="secondary" className="w-full" icon={Clock} onClick={() => { onSet(doc.id, "pending"); close(); }}>
              {t("docs.sheet.applied")}
            </Button>
          </div>
          <p className="mt-3 flex items-start justify-center gap-1.5 text-center text-xs text-ink-3">
            {scanAvailable && <ShieldCheck className="mt-px size-3.5 shrink-0" />}
            {scanAvailable ? t("docs.scan.privacy") : t("docs.sheet.hint")}
          </p>
        </>
      )}

      {phase.name === "scanning" && <ScanAnimation label={t("docs.scan.reading")} />}

      {phase.name === "review" && (
        <ReviewScan
          result={phase.result}
          onAccept={() => accept(phase.result)}
          onRetry={() => scan("camera")}
          onManual={() => { onSet(doc.id, "complete"); tap(); close(); }}
        />
      )}

      {phase.name === "error" && (
        <div className="pb-2 text-center">
          <AlertTriangle className="mx-auto mt-2 size-10 text-clay-600" />
          <p className="mt-2 text-[15px] font-semibold">{t(`docs.scan.error.${phase.reason}`)}</p>
          <div className="mt-4 grid gap-2">
            {phase.reason !== "unavailable" && (
              <Button icon={RotateCcw} onClick={() => scan("camera")}>
                {t("docs.scan.retry")}
              </Button>
            )}
            <Button variant="secondary" icon={CheckCircle2} onClick={() => { onSet(doc.id, "complete"); tap(); close(); }}>
              {t("docs.sheet.yes")}
            </Button>
          </div>
        </div>
      )}
    </Sheet>
  );
}

function ReviewScan({ result, onAccept, onRetry, onManual }: { result: ScanResult; onAccept: () => void; onRetry: () => void; onManual: () => void }) {
  const { t, tm } = useI18n();
  const fields = FIELD_ORDER.filter((k) => result.fields[k] !== undefined);
  const blocking = result.issues.some((i) => i.key === "c3.scan.issue.unreadable" || i.key === "c3.scan.issue.wrongDoc");
  const issueText = (key: string, vars?: Record<string, string | number>) => {
    if (key === "c3.scan.issue.wrongDoc") return t(key, { found: t(`docs.scan.kind.${vars?.found}`) });
    if (key === "c3.scan.issue.missing") return t(key, { fields: String(vars?.fields ?? "").split(",").map((f) => t(`docs.scan.field.${f}`)).join(", ") });
    return tm({ key, vars });
  };
  const value = (k: keyof ScanFields) => {
    const v = result.fields[k];
    if (k === "gender") return t(`docs.scan.gender.${v}`);
    if (k === "aadhaarMasked") return `${v} ${result.fields.aadhaarChecksumOk ? "✓" : ""}`.trim();
    return String(v);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div className="flex flex-wrap items-center gap-2">
        <ScanText className="size-5 text-azure-700" />
        <p className="text-[15px] font-semibold">{t("docs.scan.found")}</p>
        <Badge tone={result.kind === "other" ? "neutral" : "info"}>{t(`docs.scan.kind.${result.kind}`)}</Badge>
      </div>

      {fields.length > 0 ? (
        <dl className="mt-3 divide-y divide-line rounded-2xl bg-sand/60 px-3">
          {fields.map((k) => (
            <div key={k} className="flex items-baseline justify-between gap-3 py-2">
              <dt className="text-[13px] text-ink-3">{t(`docs.scan.field.${k}`)}</dt>
              <dd className="tabular text-right text-[15px] font-semibold break-words">{value(k)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="mt-3 text-[13px] text-ink-3">{t("docs.scan.noFields")}</p>
      )}

      {result.issues.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {result.issues.map((i, n) => (
            <li key={n} className="flex gap-2 rounded-xl bg-clay-50 px-3 py-2 text-[13px] leading-snug text-clay-700">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              {issueText(i.key, i.vars as Record<string, string | number>)}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 grid gap-2">
        {!blocking && (
          <Button icon={CheckCircle2} onClick={onAccept}>
            {t(fields.length ? "docs.scan.use" : "docs.scan.save")}
          </Button>
        )}
        <Button variant={blocking ? "primary" : "secondary"} icon={RotateCcw} onClick={onRetry}>
          {t("docs.scan.retry")}
        </Button>
        {blocking && (
          <Button variant="ghost" onClick={onManual}>
            {t("docs.sheet.yes")}
          </Button>
        )}
      </div>
      <p className="mt-2 text-center text-[11px] leading-snug text-ink-3">{t("docs.scan.kept")}</p>
    </motion.div>
  );
}

function ScanAnimation({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center pb-2">
      <div className="relative mt-2 h-56 w-44 overflow-hidden rounded-2xl bg-ink shadow-[var(--shadow-float)]">
        <div className="absolute inset-4 rounded-lg bg-white p-3">
          <div className="h-3 w-2/3 rounded bg-ink-3/30" />
          <div className="mt-3 flex gap-2">
            <div className="size-10 rounded bg-sand" />
            <div className="flex-1 space-y-1.5">
              <div className="h-2 rounded bg-ink-3/20" />
              <div className="h-2 w-4/5 rounded bg-ink-3/20" />
              <div className="h-2 w-3/5 rounded bg-ink-3/20" />
            </div>
          </div>
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="mt-2 h-2 rounded bg-ink-3/15" style={{ width: `${90 - i * 9}%` }} />
          ))}
        </div>
        {["top-2 left-2 border-t-4 border-l-4", "top-2 right-2 border-t-4 border-r-4", "bottom-2 left-2 border-b-4 border-l-4", "bottom-2 right-2 border-b-4 border-r-4"].map((c) => (
          <span key={c} className={`absolute size-6 rounded-sm border-marigold-500 ${c}`} />
        ))}
        <motion.div
          initial={{ top: "8%" }}
          animate={{ top: ["8%", "88%", "8%"] }}
          transition={{ duration: 1.6, ease: "easeInOut", repeat: Infinity }}
          className="absolute inset-x-3 h-1 rounded-full bg-azure-600 shadow-[0_0_16px_4px_rgb(14_155_179/0.6)]"
        />
      </div>
      <p className="mt-4 text-[15px] font-semibold">{label}</p>
    </div>
  );
}
