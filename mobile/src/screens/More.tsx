import { LANG_INFO } from "../i18n";
import { Building2, CalendarClock, ChevronRight, ClipboardList, Flag, History, Inbox, Languages, ListChecks, MonitorPlay, RotateCcw, Rocket, ShieldCheck, Users, Volume2, Workflow } from "lucide-react";
import { useState } from "react";
import { tap } from "../lib/haptics";
import { setToolsUnlocked, useToolsUnlocked } from "../lib/tools";
import { ACTIVITIES } from "../data/activities";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useNav, type Route, type Tab } from "../nav";
import { todayOf, useStore, type DemoCheckpoint, type JourneyState } from "../state/store";
import { Button, Card, ListRow, Reveal, Section, Segmented, Sheet, TabScreen, toast } from "../ui";
import { chatName, placeOf, profileStarted } from "./g1/conversation";
import { CHAT_LANG_LABEL } from "./w1/chatI18n";
import { LanguageSwitch } from "./w1/LanguageSwitch";

const JUMPS: { to: DemoCheckpoint; tab: Tab; route?: Route }[] = [
  { to: "start", tab: "assistant" },
  { to: "sample_profile", tab: "assistant" },
  { to: "report", tab: "home", route: { name: "report" } },
  { to: "plan", tab: "plan" },
  { to: "application", tab: "home", route: { name: "application" } },
  { to: "launched", tab: "business" },
  { to: "monitoring", tab: "business", route: { name: "monitoring" } },
  { to: "followup", tab: "business", route: { name: "outcome" } },
  { to: "returning", tab: "home" },
  { to: "no_viable", tab: "home", route: { name: "noViable" } },
];

export default function More() {
  const { t, pick, lang } = useI18n();
  const { state, dispatch, set } = useStore();
  const { push, goto } = useNav();
  const [confirmReset, setConfirmReset] = useState(false);
  const tools = useToolsUnlocked();
  const [versionTaps, setVersionTaps] = useState(0);
  const tapVersion = () => {
    const n = versionTaps + 1;
    setVersionTaps(n >= 7 ? 0 : n);
    if (n >= 7) {
      tap();
      setToolsUnlocked(!tools);
      toast(t(tools ? "more.tools.off" : "more.tools.on"));
    }
  };

  const profile = state.profile;
  const name = chatName(state.chat);
  const place = placeOf(profile);
  const started = profileStarted(profile);
  const initials = (name ?? "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => [...w][0]).join("").toUpperCase();
  const locale = LANG_INFO[lang].dateLocale;
  const demoDate = new Date(todayOf(state)).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric", numberingSystem: "latn" });

  const jump = (j: (typeof JUMPS)[number]) => {
    tap();
    dispatch({ type: "jump", to: j.to });
    goto(j.tab, j.route);
  };

  return (
    <TabScreen
      header={
        <header className="safe-top bg-cream px-4">
          <h1 className="pt-4 pb-1 text-[26px] font-bold">{t("nav.more")}</h1>
        </header>
      }
    >
      <Reveal i={0}>
        <Card className="mt-3 flex items-center gap-4" onClick={() => goto("assistant")}>
          <span className="grid size-16 shrink-0 place-items-center rounded-full bg-azure-800 text-xl font-bold text-white">
            {initials || (profile.activityId ? ACTIVITIES[profile.activityId]?.emoji : "") || "?"}
          </span>
          <div className="min-w-0">
            <p className="truncate text-lg leading-tight font-semibold">{name ?? t(started ? "u1.more.anon" : "u1.more.noProfile")}</p>
            {started ? (
              <>
                <p className="text-[13px] break-words text-ink-3">
                  {[place ? [place.village, place.district.name].flatMap((x) => (x ? [pick(x)] : [])).join(", ") : profile.locationText || null, profile.capital > 0 ? rupees(profile.capital) : null]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {profile.activityId && ACTIVITIES[profile.activityId] && (
                    <span className="rounded-full bg-marigold-50 px-2.5 py-0.5 text-xs font-medium text-marigold-600">
                      {ACTIVITIES[profile.activityId].emoji} {pick(ACTIVITIES[profile.activityId].name)}
                    </span>
                  )}
                  {profile.skills.map((k) => (
                    <span key={k} className="rounded-full bg-azure-50 px-2.5 py-0.5 text-xs font-medium text-azure-800">
                      {t(`w1.skill.${k}`)}
                    </span>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-[13px] text-ink-3">{t("u1.more.noProfileSub")}</p>
            )}
          </div>
        </Card>
      </Reveal>

      <Section title={t("more.settings")}>
        <Card className="divide-y divide-line py-1">
          <ListRow
            icon={Languages}
            title={t("more.language")}
            subtitle={t("more.languageSub")}
            right={<LanguageSwitch />}
          />
          <ListRow
            icon={Volume2}
            tone="sky"
            title={t("w1.more.languages")}
            subtitle={t("w1.more.languagesSub", { lang: CHAT_LANG_LABEL[state.chatLang] })}
            onClick={() => push({ name: "languages" })}
          />
          <ListRow icon={ShieldCheck} title={t("w1.more.privacy")} subtitle={t("w1.more.privacySub")} onClick={() => push({ name: "privacy" })} />
        </Card>
      </Section>

      <Section title={t("w1.more.myCase")}>
        <Card className="divide-y divide-line py-1">
          <ListRow icon={History} tone="marigold" title={t("w1.more.timeline")} subtitle={t("w1.more.timelineSub")} onClick={() => push({ name: "timeline" })} />
          <ListRow icon={ListChecks} title={t("w1.more.shortlist")} subtitle={t("w1.more.shortlistSub")} onClick={() => push({ name: "shortlist" })} />
          <ListRow icon={ClipboardList} tone="sky" title={t("w1.more.survey")} subtitle={t("w1.more.surveySub")} onClick={() => push({ name: "survey" })} />
        </Card>
      </Section>

      <Section title={t("more.explore")}>
        <Card className="divide-y divide-line py-1">
          <ListRow icon={Workflow} title={t("more.how")} subtitle={t("more.howSub")} onClick={() => push({ name: "architecture" })} />
          <ListRow icon={Building2} tone="sky" title={t("more.agency")} subtitle={t("more.agencySub")} onClick={() => push({ name: "agency" })} />
          <ListRow icon={Users} tone="marigold" title={t("more.community")} subtitle={t("more.communitySub")} onClick={() => push({ name: "community" })} />
        </Card>
      </Section>

      {tools && (
      <Section title={t("more.presenter")}>
        <Card tone="sand">
          <div className="flex items-start gap-3">
            <MonitorPlay className="mt-0.5 size-5 shrink-0 text-azure-800" />
            <p className="text-[13px] leading-snug text-ink-2">{t("more.presenterSub")}</p>
          </div>
          <p className="mt-3 text-[12px] font-semibold text-ink-3">{t("u1.more.checkpoints")}</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {JUMPS.map((j, i) => (
              <button
                key={j.to}
                onClick={() => jump(j)}
                className="flex min-h-12 items-center gap-2 rounded-2xl bg-white px-3 text-left text-[14px] font-medium text-azure-800 ring-1 ring-line active:bg-azure-50"
              >
                <span className="tabular grid size-6 shrink-0 place-items-center rounded-full bg-azure-100 text-xs font-bold">{i + 1}</span>
                <span className="min-w-0 flex-1 leading-tight">{t(`more.jump.${j.to}`)}</span>
                <ChevronRight className="size-4 shrink-0 text-ink-3" />
              </button>
            ))}
          </div>
          <ClockControls state={state} demoDate={demoDate} onAdvance={(days) => dispatch({ type: "advanceClock", days })} />
          <div className="mt-3 rounded-2xl bg-white p-3 ring-1 ring-line">
            <div className="flex items-start gap-2.5">
              <Inbox className="mt-0.5 size-4.5 shrink-0 text-azure-800" />
              <div className="min-w-0">
                <p className="text-[14px] font-semibold">{t("u1.more.inbox")}</p>
                <p className="text-[12px] leading-snug text-ink-3">{t("u1.more.inboxSub")}</p>
              </div>
            </div>
            <div className="mt-2">
              <Segmented<JourneyState["inbox"]>
                value={state.inbox}
                onChange={(v) => set({ inbox: v })}
                options={[
                  { value: "typical", label: t("u1.more.inbox.typical") },
                  { value: "monsoon_disruption", label: t("u1.more.inbox.monsoon_disruption") },
                ]}
              />
            </div>
          </div>
          <Button variant="secondary" size="md" icon={RotateCcw} className="mt-3 w-full text-clay-700" onClick={() => setConfirmReset(true)}>
            {t("more.reset")}
          </Button>
        </Card>
      </Section>
      )}

      {!tools && (
        <Button variant="secondary" size="md" icon={RotateCcw} className="mt-6 w-full text-clay-700" onClick={() => setConfirmReset(true)}>
          {t("more.reset")}
        </Button>
      )}

      <div className="mt-8 flex flex-col items-center gap-1 text-center text-xs text-ink-3">
        <button type="button" onClick={tapVersion} className="flex min-h-8 items-center gap-1.5 px-2">
          <Rocket className="size-3.5" />
          {t("more.version", { v: "1.0" })}
        </button>
        <span className="flex items-center gap-1.5">
          <Flag className="size-3.5" />
          {t("more.footer")}
        </span>
      </div>

      <Sheet open={confirmReset} onClose={() => setConfirmReset(false)} title={t("more.resetTitle")}>
        <p className="text-[15px] leading-snug text-ink-2">{t("more.resetBody")}</p>
        <div className="mt-5 grid gap-2">
          <Button
            variant="danger"
            icon={RotateCcw}
            onClick={() => {
              tap();
              setConfirmReset(false);
              dispatch({ type: "reset" });
              goto("home");
            }}
          >
            {t("more.resetConfirm")}
          </Button>
          <Button variant="ghost" onClick={() => setConfirmReset(false)}>
            {t("more.cancel")}
          </Button>
        </div>
        {/* keeps the actions clear of the tab bar, which sits above the sheet */}
        <div className="h-16" />
      </Sheet>
    </TabScreen>
  );
}

/** Presenter clock: let months of business pass so monitoring reads more of the sample inbox. */
function ClockControls({ state, demoDate, onAdvance }: { state: JourneyState; demoDate: string; onAdvance: (days: number) => void }) {
  const { t } = useI18n();
  return (
    <div className="mt-3 rounded-2xl bg-white p-3 ring-1 ring-line">
      <div className="flex items-start gap-2.5">
        <CalendarClock className="mt-0.5 size-4.5 shrink-0 text-azure-800" />
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-semibold">
            {t("u1.more.clock")}: <span className="tabular">{demoDate}</span>
          </p>
          <p className="text-[12px] text-ink-3">{state.clockOffsetDays ? t("u1.more.clockSub", { n: state.clockOffsetDays }) : t("u1.more.clockReal")}</p>
        </div>
      </div>
      <p className="mt-2 text-[12px] font-medium text-ink-3">{t("u1.more.months")}</p>
      <div className="mt-1.5 grid grid-cols-3 gap-2">
        {[30, 90].map((d) => (
          <Button
            key={d}
            size="md"
            variant="secondary"
            onClick={() => {
              tap();
              onAdvance(d);
            }}
          >
            {t(d === 30 ? "u1.more.plus30" : "u1.more.plus90")}
          </Button>
        ))}
        <Button
          size="md"
          variant="ghost"
          disabled={!state.clockOffsetDays}
          onClick={() => {
            tap();
            onAdvance(-state.clockOffsetDays);
          }}
        >
          {t("u1.more.resetClock")}
        </Button>
      </div>
    </div>
  );
}
