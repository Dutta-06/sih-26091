import { ArrowRight, Check } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { tap } from "../App";
import { useI18n, type Lang } from "../i18n";
import { useStore } from "../state/store";
import { cx } from "../ui";
import { HonestArt, SunriseArt, VoiceArt } from "./g1/OnboardingArt";

const SLIDES = 3;

export default function Onboarding() {
  const { t, lang } = useI18n();
  const { set } = useStore();
  const [index, setIndex] = useState(0);
  const [dir, setDir] = useState(1);

  const go = (next: number) => {
    if (next < 0 || next >= SLIDES) return;
    tap();
    setDir(next > index ? 1 : -1);
    setIndex(next);
  };
  const finish = () => {
    tap();
    set({ onboarded: true });
  };
  const chooseLang = (l: Lang) => {
    tap();
    set({ lang: l, chatLang: l });
  };

  return (
    <div className="safe-top safe-bottom relative flex h-full flex-col overflow-hidden bg-forest-800 text-white">
      <div aria-hidden className="pointer-events-none absolute -top-24 -right-24 size-72 rounded-full bg-forest-700/60" />
      <div aria-hidden className="pointer-events-none absolute -bottom-32 -left-20 size-80 rounded-full bg-forest-900/50" />

      <div className="relative flex min-h-14 items-center justify-end px-3">
        {index < SLIDES - 1 && (
          <button onClick={finish} className="min-h-11 rounded-full px-4 text-sm font-medium text-forest-100 active:bg-white/10">
            {t("onb.skip")}
          </button>
        )}
      </div>

      <div className="relative flex-1 overflow-hidden">
        <AnimatePresence initial={false} custom={dir} mode="popLayout">
          <motion.div
            key={index}
            custom={dir}
            initial={{ x: dir > 0 ? "100%" : "-100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: dir > 0 ? "-100%" : "100%", opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 30 }}
            drag="x"
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.25}
            onDragEnd={(_, info) => {
              if (info.offset.x < -60) go(index + 1);
              else if (info.offset.x > 60) go(index - 1);
            }}
            className="absolute inset-0 flex flex-col px-6"
          >
            {index === 0 && (
              <>
                <div className="flex flex-1 flex-col items-center justify-center text-center">
                  <SunriseArt />
                  <h1 className="mt-5 text-5xl leading-tight font-bold">{t("onb.brandHi")}</h1>
                  <p className="mt-1 text-lg font-semibold tracking-[0.2em] text-marigold-200 uppercase">{t("onb.brandEn")}</p>
                  <p className="mt-3 max-w-72 text-[15px] text-forest-100">{t("app.tagline")}</p>
                </div>
                <p className="mb-3 text-center text-sm text-forest-100">{t("onb.chooseLang")}</p>
                <div className="grid grid-cols-2 gap-3 pb-4">
                  {(["en", "hi"] as const).map((l) => (
                    <motion.button
                      key={l}
                      whileTap={{ scale: 0.96 }}
                      onClick={() => chooseLang(l)}
                      className={cx(
                        "relative flex min-h-24 flex-col items-start justify-end rounded-[var(--radius-card)] p-4 text-left transition-colors",
                        lang === l ? "bg-white text-forest-900" : "bg-white/10 text-white ring-1 ring-white/20",
                      )}
                    >
                      {lang === l && (
                        <span className="absolute top-3 right-3 grid size-6 place-items-center rounded-full bg-forest-700 text-white">
                          <Check className="size-4" />
                        </span>
                      )}
                      <span className="text-2xl font-bold">{t(`g1.lang.${l}`)}</span>
                      <span className={cx("text-xs", lang === l ? "text-ink-3" : "text-forest-100")}>{t(`g1.lang.${l}Sub`)}</span>
                    </motion.button>
                  ))}
                </div>
              </>
            )}
            {index === 1 && <Slide art={<VoiceArt />} title={t("onb.s2.title")} body={t("onb.s2.body")} />}
            {index === 2 && <Slide art={<HonestArt />} title={t("onb.s3.title")} body={t("onb.s3.body")} />}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="relative px-6 pt-2 pb-5">
        <div className="mb-4 flex justify-center gap-2">
          {Array.from({ length: SLIDES }, (_, i) => (
            <button key={i} aria-label={t("onb.slide", { n: i + 1 })} onClick={() => go(i)} className="grid h-6 place-items-center">
              <motion.span animate={{ width: i === index ? 24 : 8 }} className={cx("block h-2 rounded-full", i === index ? "bg-marigold-500" : "bg-white/30")} />
            </button>
          ))}
        </div>
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() => (index === SLIDES - 1 ? finish() : go(index + 1))}
          className="flex min-h-14 w-full items-center justify-center gap-2 rounded-2xl bg-marigold-500 text-base font-semibold text-forest-950 active:bg-marigold-600"
        >
          {index === SLIDES - 1 ? t("onb.begin") : t("action.next")}
          <ArrowRight className="size-5" />
        </motion.button>
      </div>
    </div>
  );
}

function Slide({ art, title, body }: { art: ReactNode; title: string; body: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center">
      {art}
      <h2 className="mt-8 max-w-80 text-[26px] leading-snug font-bold">{title}</h2>
      <p className="mt-3 max-w-80 text-[15px] leading-relaxed text-forest-100">{body}</p>
    </div>
  );
}
