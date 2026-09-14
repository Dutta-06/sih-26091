import { Activity, ArrowRight, BookOpen, BriefcaseBusiness, Calculator, Check, ClipboardCheck, FileText, Mic } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { tap } from "../lib/haptics";
import { useI18n, type Lang } from "../i18n";
import { rupees } from "../lib/format";
import { useNav, type Route, type Tab } from "../nav";
import { useStore } from "../state/store";
import { Badge, Card, cx, IconBubble, Reveal, Ring, Section, Segmented, TabScreen } from "../ui";
import { chatName, placeOf } from "./g1/conversation";
import { currentStep, STAGES } from "./g1/journey";
import { useSetAppLang } from "./w1/chatI18n";
import { daysAway, WelcomeBackCard } from "./w1/HomeCards";

export default function Home() {
  const { t, pick, lang } = useI18n();
  const { state, view } = useStore();
  const { push, goto, switchTab } = useNav();
  const setLang = useSetAppLang();
  const step = currentStep(state, view);
  const [welcomeDismissed, setWelcomeDismissed] = useState(false);
  const away = welcomeDismissed ? null : daysAway(state);
  const followUpDue = !!state.interventionChosen && !state.followUp && step.cta !== "followup";
  const health = view.latestHealth;

  const open = (tab: Tab, route?: Route) => {
    tap();
    if (tab === "home" && route) push(route);
    else if (route) goto(tab, route);
    else switchTab(tab);
  };

  const hour = new Date().getHours();
  const greeting = t(hour < 12 ? "home.morning" : hour < 17 ? "home.afternoon" : "home.evening");
  const name = chatName(state.chat);
  const place = placeOf(state.profile);
  const placeLine = place ? [place.village, place.district.name].flatMap((b) => (b ? [pick(b)] : [])).join(", ") : null;
  const monthLabel = (ym: string) => new Date(`${ym}-01T00:00:00Z`).toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { month: "long", year: "numeric", numberingSystem: "latn" });

  const tiles = [
    { icon: Calculator, key: "calculator", tone: "forest" as const, go: () => open("plan") },
    { icon: BookOpen, key: "scheme", tone: "sky" as const, go: () => open("home", { name: "scheme" }) },
    { icon: FileText, key: "documents", tone: "marigold" as const, go: () => open("home", { name: "documents" }) },
    { icon: BriefcaseBusiness, key: "business", tone: "forest" as const, go: () => open("business") },
  ];

  return (
    <TabScreen
      header={
        <header className="safe-top bg-cream px-4">
          <div className="flex min-h-16 items-center justify-between gap-3 pt-2">
            <div className="min-w-0">
              <p className="text-[13px] text-ink-3">{greeting}</p>
              <h1 className="truncate text-[22px] leading-tight font-bold">{name ? t("home.hello", { name }) : t("u1.home.hello")}</h1>
              {placeLine && <p className="truncate text-[13px] text-ink-3">{placeLine}</p>}
            </div>
            <Segmented<Lang> value={lang} onChange={setLang} options={[{ value: "en", label: "EN" }, { value: "hi", label: "हिं" }]} />
          </div>
        </header>
      }
    >
      {away !== null && (
        <WelcomeBackCard
          state={state}
          view={view}
          days={away}
          onDismiss={() => setWelcomeDismissed(true)}
          onHistory={() => open("home", { name: "timeline" })}
          onContinue={() => {
            setWelcomeDismissed(true);
            open(step.target.tab, step.target.route);
          }}
        />
      )}

      <Reveal i={0}>
        <div className="relative mt-3 overflow-hidden rounded-[var(--radius-card)] bg-forest-800 p-4 text-white shadow-[var(--shadow-float)]">
          <div aria-hidden className="absolute -top-16 -right-12 size-44 rounded-full bg-forest-700/60" />
          <div className="relative">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold tracking-wide text-forest-100 uppercase">{t("home.journey")}</p>
              <span className="tabular text-xs text-forest-100">{t("home.stepOf", { n: step.index + 1, total: STAGES.length })}</span>
            </div>
            <h2 className="mt-1 text-xl font-bold">{t(`home.stage.${step.stage}`)}</h2>
            <p className="mt-1 text-[13px] leading-snug text-forest-100">{t(`home.stageHint.${step.cta}`)}</p>

            <div className="mt-4 flex items-center">
              {STAGES.map((s, i) => (
                <div key={s} className={cx("flex items-center", i < STAGES.length - 1 && "flex-1")}>
                  <motion.span
                    initial={false}
                    animate={{ scale: i === step.index ? 1.15 : 1 }}
                    className={cx(
                      "grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-bold",
                      i < step.index ? "bg-marigold-500 text-forest-950" : i === step.index ? "bg-white text-forest-800 ring-4 ring-white/25" : "bg-white/15 text-forest-100",
                    )}
                  >
                    {i < step.index ? <Check className="size-3.5" /> : i + 1}
                  </motion.span>
                  {i < STAGES.length - 1 && <span className={cx("mx-1 h-0.5 flex-1 rounded-full", i < step.index ? "bg-marigold-500" : "bg-white/15")} />}
                </div>
              ))}
            </div>
            <div className="mt-1.5 flex justify-between text-[10px] text-forest-100">
              <span>{t("home.stage.profile")}</span>
              <span>{t("home.stage.monitoring")}</span>
            </div>

            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={() => open(step.target.tab, step.target.route)}
              className={cx(
                "mt-4 flex min-h-13 w-full items-center justify-center gap-2 rounded-2xl px-4 text-[15px] font-semibold",
                step.tone === "clay" ? "bg-clay-600 text-white active:bg-clay-700" : "bg-marigold-500 text-forest-950 active:bg-marigold-600",
              )}
            >
              {t(`home.cta.${step.cta}`)}
              <ArrowRight className="size-5" />
            </motion.button>
          </div>
        </div>
      </Reveal>

      <Reveal i={1}>
        <Card className="mt-4 flex items-center gap-4" onClick={() => open("assistant")}>
          <span className="relative grid size-14 shrink-0 place-items-center rounded-full bg-forest-700 text-white">
            <motion.span aria-hidden className="absolute inset-0 rounded-full bg-forest-600" animate={{ scale: [1, 1.35], opacity: [0.5, 0] }} transition={{ duration: 1.6, repeat: Infinity }} />
            <Mic className="relative size-6" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[16px] font-semibold">{t("home.talk")}</p>
            <p className="mt-0.5 text-[13px] leading-snug text-ink-3">{t("home.talkSub")}</p>
          </div>
          <ArrowRight className="size-5 text-ink-3" />
        </Card>
      </Reveal>

      {followUpDue && (
        <Reveal i={2}>
          <Card tone="marigold" className="mt-4 flex items-center gap-3" onClick={() => open("home", { name: "outcome" })}>
            <IconBubble icon={ClipboardCheck} tone="marigold" />
            <div className="min-w-0 flex-1">
              <p className="text-[16px] leading-tight font-semibold">{t("w1.home.followup")}</p>
              <p className="mt-0.5 text-[13px] leading-snug text-ink-2">{t("w1.home.followupSub")}</p>
            </div>
            <ArrowRight className="size-5 text-marigold-600" />
          </Card>
        </Reveal>
      )}

      {health && (
        <Reveal i={2}>
          <Section title={t("home.health")}>
            <Card className="flex items-center gap-4" onClick={() => open("home", { name: health.earlyWarning ? "warning" : "monitoring" })}>
              <Ring
                value={health.score ?? 0}
                label={health.score != null ? Math.round(health.score) : "—"}
                size={72}
                stroke={8}
                tone={health.band === "healthy" ? "forest" : health.band === "at_risk" ? "clay" : "marigold"}
              />
              <div className="min-w-0 flex-1">
                {health.band ? (
                  <Badge tone={health.band === "healthy" ? "good" : health.band === "at_risk" ? "risk" : "warn"} icon={Activity}>
                    {t(`u1.band.${health.band}`)}
                  </Badge>
                ) : (
                  <p className="text-[13px] text-ink-3">{t("u1.home.noScore")}</p>
                )}
                <p className="mt-1.5 text-[14px] leading-snug text-ink-2">
                  {t("u1.home.healthSub", { month: monthLabel(health.month), revenue: rupees(health.revenue), planned: rupees(health.planned) })}
                </p>
              </div>
            </Card>
          </Section>
        </Reveal>
      )}

      <Section title={t("home.quick")}>
        <div className="grid grid-cols-2 gap-3">
          {tiles.map((tile, i) => (
            <Reveal key={tile.key} i={3 + i}>
              <Card onClick={tile.go} className="flex min-h-28 flex-col justify-between">
                <IconBubble icon={tile.icon} tone={tile.tone} size="sm" />
                <div className="mt-3">
                  <p className="text-[15px] leading-tight font-semibold">{t(`home.tile.${tile.key}`)}</p>
                  <p className="mt-0.5 text-xs text-ink-3">{t(`home.tile.${tile.key}Sub`)}</p>
                </div>
              </Card>
            </Reveal>
          ))}
        </div>
      </Section>
    </TabScreen>
  );
}
