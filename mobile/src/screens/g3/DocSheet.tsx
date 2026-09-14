import { Camera, CheckCircle2, Clock } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { tap } from "../../App";
import type { Bi } from "../../i18n";
import { useI18n } from "../../i18n";
import type { DocStatus } from "../../state/store";
import { Button, Sheet } from "../../ui";

/** "Do you have it?" sheet with a simulated camera scan. */
export function DocSheet({ doc, onClose, onSet }: { doc: { id: string; name: Bi } | null; onClose: () => void; onSet: (id: string, s: DocStatus) => void }) {
  const { t, pick } = useI18n();
  const [phase, setPhase] = useState<"ask" | "scanning" | "done">("ask");

  useEffect(() => {
    if (phase === "scanning") {
      const a = setTimeout(() => {
        if (doc) onSet(doc.id, "complete");
        tap();
        setPhase("done");
      }, 1800);
      return () => clearTimeout(a);
    }
    if (phase === "done") {
      const b = setTimeout(close, 900);
      return () => clearTimeout(b);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  function close() {
    setPhase("ask");
    onClose();
  }

  if (!doc) return null;
  return (
    <Sheet open onClose={close} title={pick(doc.name)}>
      {phase === "ask" ? (
        <>
          <p className="text-[15px] text-ink-2">{t("docs.sheet.ask")}</p>
          <div className="mt-4 space-y-2.5">
            <Button className="w-full" icon={Camera} onClick={() => setPhase("scanning")}>
              {t("docs.sheet.scan")}
            </Button>
            <Button variant="secondary" className="w-full" icon={CheckCircle2} onClick={() => { onSet(doc.id, "complete"); tap(); close(); }}>
              {t("docs.sheet.yes")}
            </Button>
            <Button variant="secondary" className="w-full" icon={Clock} onClick={() => { onSet(doc.id, "pending"); close(); }}>
              {t("docs.sheet.applied")}
            </Button>
          </div>
          <p className="mt-3 text-center text-xs text-ink-3">{t("docs.sheet.hint")}</p>
        </>
      ) : (
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
            {phase === "scanning" ? (
              <motion.div
                initial={{ top: "8%" }}
                animate={{ top: ["8%", "88%", "8%"] }}
                transition={{ duration: 1.6, ease: "easeInOut" }}
                className="absolute inset-x-3 h-1 rounded-full bg-azure-600 shadow-[0_0_16px_4px_rgb(25_135_84/0.6)]"
              />
            ) : (
              <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 400, damping: 18 }} className="absolute inset-0 grid place-items-center bg-azure-800/70">
                <CheckCircle2 className="size-16 text-white" />
              </motion.div>
            )}
          </div>
          <p className="mt-4 text-[15px] font-semibold">{phase === "scanning" ? t("docs.sheet.scanning") : t("docs.sheet.scanned")}</p>
        </div>
      )}
    </Sheet>
  );
}
