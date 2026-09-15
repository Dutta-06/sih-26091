import { Volume2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { tap } from "../../lib/haptics";
import { speak, stopSpeaking } from "../../lib/speech";
import { cx } from "../../ui";
import { useChatI18n } from "./chatI18n";

/** Small speaker on assistant bubbles: reads the message aloud, or shows a short voice preview when speech is unavailable. */
export function SpeakButton({ text }: { text: string }) {
  const { cl, tc } = useChatI18n();
  const [mode, setMode] = useState<"idle" | "speaking" | "preview">("idle");
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  const onClick = () => {
    tap();
    clearTimeout(timer.current);
    if (mode === "speaking") {
      stopSpeaking();
      setMode("idle");
      return;
    }
    const started = speak(text, cl, () => setMode("idle"));
    setMode(started ? "speaking" : "preview");
    // Safety net: some engines never fire onend; previews last a moment.
    timer.current = setTimeout(() => setMode("idle"), started ? Math.min(30_000, 1500 + text.length * 70) : 2200);
  };

  const active = mode !== "idle";
  return (
    <div className="relative mb-0.5 shrink-0">
      <motion.button
        whileTap={{ scale: 0.9 }}
        aria-label={tc("w1.speak")}
        onClick={onClick}
        className={cx("grid size-9 place-items-center rounded-full transition-colors", active ? "bg-azure-100 text-azure-800" : "text-ink-3 active:bg-sand")}
      >
        {active ? (
          <span className="flex h-4 items-center gap-0.5">
            {[0, 1, 2, 3].map((i) => (
              <motion.span key={i} className="w-0.5 rounded-full bg-azure-700" animate={{ height: [4, 14, 4] }} transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.12 }} />
            ))}
          </span>
        ) : (
          <Volume2 className="size-4.5" />
        )}
      </motion.button>
      <AnimatePresence>
        {mode === "preview" && (
          <motion.span
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="absolute right-0 bottom-full mb-1 rounded-full bg-azure-800 px-2.5 py-1 text-[11px] font-medium whitespace-nowrap text-white"
          >
            {tc("w1.voicePreview")}
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  );
}
