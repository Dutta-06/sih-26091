import { Check, Languages as LanguagesIcon } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { LANG_INFO, LANGS, useI18n, type Lang } from "../../i18n";
import { tap } from "../../lib/haptics";
import { cx, Sheet } from "../../ui";
import { useSetAppLang } from "./chatI18n";

/** Grid of the app's languages, each in its own script. */
export function LanguageGrid({ value, onChange, tone = "light", compact = false }: { value: Lang; onChange: (l: Lang) => void; tone?: "light" | "dark"; compact?: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-2.5">
      {LANGS.map((l) => {
        const active = value === l;
        return (
          <motion.button
            key={l}
            whileTap={{ scale: 0.96 }}
            onClick={() => {
              tap();
              onChange(l);
            }}
            className={cx(
              "relative flex flex-col items-start justify-center rounded-2xl px-3.5 text-left transition-colors",
              compact ? "min-h-14" : "min-h-16",
              tone === "dark"
                ? active ? "bg-white text-azure-900" : "bg-white/10 text-white ring-1 ring-white/20"
                : active ? "bg-azure-800 text-white shadow-[var(--shadow-float)]" : "bg-white text-ink shadow-[var(--shadow-card)]",
            )}
          >
            {active && (
              <span className={cx("absolute top-2 right-2 grid size-5 place-items-center rounded-full", tone === "dark" ? "bg-azure-700 text-white" : "bg-white/25")}>
                <Check className="size-3.5" />
              </span>
            )}
            <span lang={l} className={cx("font-bold", compact ? "text-[17px]" : "text-lg")}>{LANG_INFO[l].native}</span>
            <span className={cx("text-[11px]", active ? (tone === "dark" ? "text-ink-3" : "text-azure-100") : tone === "dark" ? "text-azure-100" : "text-ink-3")}>{LANG_INFO[l].english}</span>
          </motion.button>
        );
      })}
    </div>
  );
}

/** Compact current-language button that opens the language sheet (Home and More headers). */
export function LanguageSwitch() {
  const { t, lang } = useI18n();
  const setLang = useSetAppLang();
  const [open, setOpen] = useState(false);
  return (
    <>
      <motion.button
        whileTap={{ scale: 0.95 }}
        onClick={() => {
          tap();
          setOpen(true);
        }}
        aria-label={t("w1.lang.title")}
        className="inline-flex min-h-10 items-center gap-1.5 rounded-full bg-sand px-3.5 text-sm font-semibold text-azure-900 active:bg-line"
      >
        <LanguagesIcon className="size-4" />
        <span lang={lang}>{LANG_INFO[lang].short}</span>
      </motion.button>
      <Sheet open={open} onClose={() => setOpen(false)} title={t("w1.lang.app")}>
        <LanguageGrid
          value={lang}
          compact
          onChange={(l) => {
            setLang(l);
            setOpen(false);
          }}
        />
      </Sheet>
    </>
  );
}
