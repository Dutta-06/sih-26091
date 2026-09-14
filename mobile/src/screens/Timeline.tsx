import {
  Banknote,
  BellRing,
  ChevronRight,
  Eye,
  FileText,
  Flag,
  HandHelping,
  Headset,
  History,
  MapPin,
  MessageCircle,
  Search,
  ShieldCheck,
  Sparkles,
  Stamp,
  Trash2,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { tap } from "../lib/haptics";
import { useI18n } from "../i18n";
import { useNav } from "../nav";
import { todayOf, useStore } from "../state/store";
import { cx, Note, Reveal, Screen } from "../ui";
import { useFmt } from "./w1/chatI18n";
import { timelineItems, type TimelineItem, type TimelineKind } from "./w1/timeline";

const ICONS: Partial<Record<TimelineKind, LucideIcon>> = {
  chat: MessageCircle,
  profile_started: UserRound,
  location_confirmed: MapPin,
  analysis_run: Search,
  activity_chosen: Sparkles,
  documents_updated: FileText,
  application: Stamp,
  consent: ShieldCheck,
  data_deleted: Trash2,
  milestone: Flag,
  intervention: HandHelping,
  follow_up: Banknote,
  grievance: BellRing,
  observation: Eye,
  counsellor_request: Headset,
};

const DOT = { forest: "bg-forest-100 text-forest-800", marigold: "bg-marigold-100 text-marigold-600", clay: "bg-clay-100 text-clay-700", sky: "bg-sky-100 text-sky-700" };

/** Case history: every recorded event with its real (demo-clock) timestamp; each links to its screen. */
export default function Timeline() {
  const { t, lang } = useI18n();
  const fmt = useFmt();
  const { state } = useStore();
  const { push, goto, switchTab } = useNav();
  const items = timelineItems(state);
  const locale = lang === "hi" ? "hi-IN" : "en-IN";
  const month = (iso: string) => new Date(iso).toLocaleDateString(locale, { month: "long", year: "numeric", numberingSystem: "latn" });
  const day = (iso: string) => new Date(iso).toLocaleString(locale, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", numberingSystem: "latn" });

  const open = (e: TimelineItem) => {
    tap();
    const { tab, route } = e.target;
    if (!route) switchTab(tab);
    else if (tab === "home") push(route);
    else goto(tab, route);
  };

  return (
    <Screen title={t("w1.tl.title")} subtitle={t("w1.tl.subtitle", { n: items.length })}>
      <div className="mt-2">
        <Note icon={History} tone="forest">
          {t("w1.tl.saved")}
        </Note>
      </div>

      {items.length === 0 ? (
        <p className="mt-10 text-center text-[15px] text-ink-3">{t("w1.tl.empty")}</p>
      ) : (
        <ol className="relative mt-5">
          <span aria-hidden className="absolute top-2 bottom-2 left-[19px] w-0.5 rounded-full bg-line" />
          {items.map((e, i) => {
            const Icon = ICONS[e.kind] ?? History;
            const newMonth = i === 0 || month(items[i - 1].at) !== month(e.at);
            return (
              <li key={e.id}>
                {newMonth && (
                  <Reveal i={Math.min(i, 8)}>
                    <p className="relative mt-3 mb-2 ml-12 text-[13px] font-semibold tracking-wide text-ink-3 uppercase first:mt-0">{month(e.at)}</p>
                  </Reveal>
                )}
                <Reveal i={Math.min(i, 8)}>
                  <button onClick={() => open(e)} className="relative flex w-full items-start gap-3 py-1.5 text-left active:opacity-70">
                    <span className={cx("relative z-[1] grid size-10 shrink-0 place-items-center rounded-full ring-4 ring-cream", DOT[e.tone])}>
                      <Icon className="size-4.5" />
                    </span>
                    <span className="flex min-w-0 flex-1 items-center gap-2 rounded-2xl bg-white p-3 shadow-[var(--shadow-card)]">
                      <span className="min-w-0 flex-1">
                        <span className="tabular block text-[11px] font-medium text-ink-3">{day(e.at)}</span>
                        <span className="block text-[15px] leading-snug font-semibold break-words">{fmt({ key: e.title, vars: e.vars })}</span>
                        {e.body && <span className="mt-0.5 block text-[13px] leading-snug text-ink-2">{fmt({ key: e.body, vars: e.vars })}</span>}
                      </span>
                      <ChevronRight className="size-4.5 shrink-0 text-ink-3" />
                    </span>
                  </button>
                </Reveal>
              </li>
            );
          })}
          <li className="relative flex items-center gap-3 pt-3">
            <span className="relative z-[1] grid size-10 shrink-0 place-items-center rounded-full bg-forest-800 text-white ring-4 ring-cream">
              <span className="size-2.5 animate-pulse rounded-full bg-marigold-500" />
            </span>
            <span className="text-[14px] font-semibold text-forest-800">
              {t("w1.tl.now")} · <span className="tabular">{new Date(todayOf(state)).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric", numberingSystem: "latn" })}</span>
            </span>
          </li>
        </ol>
      )}
    </Screen>
  );
}
