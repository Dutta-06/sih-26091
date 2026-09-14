import { ArrowRight, Hammer, IndianRupee, Landmark, Lightbulb, MapPin, MessageSquareQuote, Mic, Play, RotateCcw, ShieldAlert, ShieldCheck, Sparkles, Sprout, UserRound, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ACTIVITIES } from "../../data/activities";
import { buildPlan } from "../../engine/finance";
import type { FeasibilityOutcome } from "../../core/feasibility";
import type { ProfileInput } from "../../core/types";
import { rupees } from "../../lib/format";
import { listen, type ListenError } from "../../lib/speech";
import type { ChatMessage } from "../../state/store";
import { Badge, Button, ConfidenceBadge, cx } from "../../ui";
import { CHAT_LANG_LABEL, useChatI18n } from "../w1/chatI18n";
import { SpeakButton } from "../w1/SpeakButton";
import { placeOf } from "./conversation";

export function Bubble({ message, children }: { message: ChatMessage; children?: ReactNode }) {
  const { tc } = useChatI18n();
  const mine = message.from === "user";
  const text = message.literal ? message.text : tc(message.text, message.vars);
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={cx("flex items-end gap-1", mine ? "justify-end" : "justify-start")}
    >
      {children ?? (
        <>
          <div
            className={cx(
              "max-w-[78%] rounded-3xl px-4 py-2.5 text-[15px] leading-snug break-words whitespace-pre-line",
              mine ? "rounded-br-lg bg-forest-800 text-white" : "rounded-bl-lg bg-white text-ink shadow-[var(--shadow-card)]",
            )}
          >
            {text}
          </div>
          {!mine && <SpeakButton text={text} />}
        </>
      )}
    </motion.div>
  );
}

export function TypingDots() {
  const { tc } = useChatI18n();
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex justify-start" aria-label={tc("assistant.typing")}>
      <div className="flex items-center gap-1.5 rounded-3xl rounded-bl-lg bg-white px-4 py-3.5 shadow-[var(--shadow-card)]">
        {[0, 1, 2].map((i) => (
          <motion.span key={i} className="size-2 rounded-full bg-forest-600" animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }} transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }} />
        ))}
      </div>
    </motion.div>
  );
}

/** Profile summary built from the inputs, with engine figures for the savings (rules, not AI). */
export function ProfileSummaryCard({ profile, name, started, onRun }: { profile: ProfileInput; name: string | null; started: boolean; onRun: () => void }) {
  const { tc, actName, pickc } = useChatI18n();
  const place = placeOf(profile);
  const plan = buildPlan(profile.capital);
  const none = tc("u1.sum.none");
  const list = (keys: string[]) => keys.map((k) => tc(k)).join(", ");
  const act = profile.activityId ? ACTIVITIES[profile.activityId] : null;
  const placeText = place ? [place.village, place.block, place.district.name].flatMap((b) => (b ? [pickc(b)] : [])).join(" · ") : profile.locationText || none;
  const rows: { icon: typeof MapPin; label: string; value: string; sub?: ReactNode }[] = [
    ...(name ? [{ icon: UserRound, label: tc("u1.sum.name"), value: name }] : []),
    {
      icon: IndianRupee,
      label: tc("u1.sum.capital"),
      value: profile.capital > 0 ? rupees(profile.capital) : none,
      sub: profile.capital > 0 ? <span className="text-[12px] text-ink-3">{plan.eligible ? tc("u1.sum.capitalSub", { project: rupees(plan.projectCost), loan: rupees(plan.loan) }) : tc("u1.sum.outside")}</span> : undefined,
    },
    {
      icon: MapPin,
      label: tc("u1.sum.location"),
      value: placeText,
      sub: place ? (
        <span className="flex flex-wrap items-center gap-1.5">
          {place.lgd && <span className="tabular rounded-full bg-forest-50 px-2 py-0.5 text-[11px] font-semibold text-forest-800">{tc("u1.loc.code", { code: place.lgd })}</span>}
          <ConfidenceBadge value={place.method === "village_table" ? "real" : "estimated"} compact />
        </span>
      ) : undefined,
    },
    { icon: Sparkles, label: tc("u1.sum.skills"), value: list(profile.skills.map((s) => `w1.skill.${s}`)) || none },
    { icon: Hammer, label: tc("u1.sum.premises"), value: [profile.premises ? tc(`w1.premises.${profile.premises}`) : none, ...profile.assets.map((x) => tc(`u1.asset.${x}`))].join(", ") },
    { icon: Landmark, label: tc("u1.sum.category"), value: `${profile.category ? tc(`w1.cat.${profile.category}`) : tc("u1.cat.none")}, ${tc(profile.shgMember ? "w1.shg.yes" : "w1.shg.no")}` },
    { icon: Lightbulb, label: tc("u1.sum.idea"), value: act ? `${act.emoji} ${actName(act.id)}` : none },
    { icon: MessageSquareQuote, label: tc("u1.sum.reason"), value: profile.reason ?? none },
  ];
  return (
    <div className="w-[90%] rounded-[var(--radius-card)] bg-white p-4 shadow-[var(--shadow-card)]">
      <p className="text-xs font-semibold tracking-wide text-ink-3 uppercase">{tc("u1.sum.title")}</p>
      <div className="mt-2 divide-y divide-line">
        {rows.map((r) => (
          <div key={r.label} className="flex items-start gap-3 py-2">
            <r.icon className="mt-0.5 size-4.5 shrink-0 text-forest-700" />
            <div className="min-w-0 flex-1">
              <p className="text-xs text-ink-3">{r.label}</p>
              <p className="text-[15px] leading-snug font-medium break-words">{r.value}</p>
              {r.sub && <div className="mt-0.5">{r.sub}</div>}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-1 text-[11px] font-medium text-ink-3">{tc("g1.rulesNotAi")}</p>
      <Button className="mt-3 w-full" icon={Play} onClick={onRun} variant={started ? "secondary" : "primary"}>
        {tc(started ? "u1.sum.rerun" : "u1.sum.run")}
      </Button>
    </div>
  );
}

export type VerdictTarget = "report" | "review" | "noViable";

/** The computed verdict: first attempt, then the selected alternative or an exhausted search (or profiling constraints). */
export function VerdictCard({ stale, feasibility, onOpen, onRerun }: { stale: boolean; feasibility: FeasibilityOutcome; onOpen: (to: VerdictTarget) => void; onRerun: () => void }) {
  const { tc, tmc, actName } = useChatI18n();
  if (stale) {
    return (
      <div className="w-[88%] rounded-[var(--radius-card)] bg-sand p-4">
        <p className="text-[14px] leading-snug text-ink-2">{tc("u1.v.stale")}</p>
        <Button className="mt-3 w-full" size="md" variant="secondary" icon={RotateCcw} onClick={onRerun}>
          {tc("u1.v.rerun")}
        </Button>
      </div>
    );
  }
  const { attempts, selected, exhausted, constraints } = feasibility;
  if (!attempts.length && !exhausted) {
    return (
      <div className="w-[88%] rounded-[var(--radius-card)] bg-marigold-50 p-4 ring-1 ring-marigold-200">
        <p className="text-[15px] font-semibold">{tc("u1.v.constraint")}</p>
        <ul className="mt-2 space-y-1.5">
          {constraints.map((c) => (
            <li key={c.key} className="flex gap-2 text-[14px] leading-snug text-ink-2">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-marigold-500" />
              {tmc(c)}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  const first = attempts[0] ?? null;
  const firstAct = first ? ACTIVITIES[first.activityId] : null;
  const tone = first?.verdict === "viable" ? "good" : first?.verdict === "marginal" ? "warn" : "risk";
  const alt = first && selected && selected.activityId !== first.activityId ? selected : null;
  return (
    <div className="w-[90%] space-y-2">
      {first && (<div className={cx("rounded-[var(--radius-card)] p-4", first.verdict === "viable" ? "bg-forest-50 ring-1 ring-forest-100" : "bg-clay-50 ring-1 ring-clay-100")}>
        <div className="flex items-center gap-2">
          {first.verdict === "viable" ? <ShieldCheck className="size-5 text-forest-700" /> : <ShieldAlert className="size-5 text-clay-700" />}
          <Badge tone={tone}>{tc(`verdict.${first.verdict}`)}</Badge>
        </div>
        <p className="mt-2 text-[17px] leading-snug font-semibold">
          {firstAct?.emoji} {tc("u1.v.first", { idea: actName(first.activityId) })}
        </p>
        <ul className="mt-1.5 space-y-1">
          {(first.findings.length ? first.findings.slice(0, 3).map((f) => tmc(f.msg)) : [tc("u1.v.noRule")]).map((line, i) => (
            <li key={i} className="text-[14px] leading-snug text-ink-2">
              {line}
            </li>
          ))}
        </ul>
        <p className="mt-1.5 text-[11px] font-medium text-ink-3">{tc("g1.rulesNotAi")}</p>
      </div>)}
      {alt && (
        <div className="rounded-[var(--radius-card)] bg-forest-800 p-4 text-white shadow-[var(--shadow-float)]">
          <p className="flex items-center gap-2 text-[16px] leading-snug font-semibold">
            <Sparkles className="size-5 shrink-0 text-marigold-200" />
            {tc("u1.v.alt", { idea: `${ACTIVITIES[alt.activityId]?.emoji ?? ""} ${actName(alt.activityId)}` })}
          </p>
          <p className="mt-1 text-[13px] text-forest-100">{tc("u1.v.altSub", { n: attempts.indexOf(alt) + 1, score: Math.round(alt.score) })}</p>
          <Button className="mt-3 w-full" variant="accent" iconRight={ArrowRight} onClick={() => onOpen("review")}>
            {tc("u1.jump.review")}
          </Button>
        </div>
      )}
      {!alt && selected && (
        <Button className="w-full" iconRight={ArrowRight} onClick={() => onOpen("report")}>
          {tc("u1.jump.report")}
        </Button>
      )}
      {exhausted && (
        <div className="rounded-[var(--radius-card)] bg-white p-4 shadow-[var(--shadow-card)]">
          <p className="flex items-center gap-2 text-[15px] leading-snug font-semibold">
            <Sprout className="size-5 shrink-0 text-marigold-600" />
            {tc("u1.v.exhausted")}
          </p>
          <p className="mt-1 text-[13px] text-ink-3">{tc("u1.v.exhaustedSub", { n: attempts.length })}</p>
          {constraints.map((c) => (
            <p key={c.key} className="mt-1 text-[13px] leading-snug text-ink-2">
              {tmc(c)}
            </p>
          ))}
          <Button className="mt-3 w-full" iconRight={ArrowRight} onClick={() => onOpen("noViable")}>
            {tc("u1.jump.noViable")}
          </Button>
        </div>
      )}
    </div>
  );
}

const ERR_KEY: Record<ListenError, string> = {
  permission: "u1.voice.err.permission",
  unavailable: "u1.voice.err.unavailable",
  "no-speech": "u1.voice.err.no-speech",
  network: "u1.voice.err.other",
  busy: "u1.voice.err.other",
  aborted: "u1.voice.err.other",
  unknown: "u1.voice.err.other",
};

/** Real speech input on the device (lib/speech `listen`): live partial transcript, final text goes through the chat pipeline. */
export function VoiceOverlay({ open, onFinal, onClose }: { open: boolean; onFinal: (text: string) => void; onClose: () => void }) {
  const { tc, cl } = useChatI18n();
  const [partial, setPartial] = useState("");
  const [error, setError] = useState<ListenError | null>(null);
  const [session, setSession] = useState(0);
  const stop = useRef<(() => void) | null>(null);
  const cb = useRef({ onFinal, onClose });
  cb.current = { onFinal, onClose };

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setPartial("");
    setError(null);
    void listen({
      lang: cl,
      onPartial: (text) => alive && setPartial(text),
      onFinal: (text) => {
        if (!alive) return;
        cb.current.onFinal(text);
      },
      onError: (e) => alive && setError(e),
    }).then((s) => {
      if (alive) stop.current = s;
      else s();
    });
    return () => {
      alive = false;
      stop.current?.();
      stop.current = null;
    };
  }, [open, cl, session]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="safe-top safe-bottom absolute inset-0 z-50 flex flex-col bg-forest-900/97 text-white">
          <div className="flex justify-end p-3">
            <button aria-label={tc("action.close")} onClick={onClose} className="grid size-11 place-items-center rounded-full active:bg-white/10">
              <X className="size-6" />
            </button>
          </div>
          <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
            <p className="text-sm font-medium text-forest-100">{error ? tc(ERR_KEY[error]) : tc("u1.voice.listening")}</p>
            <div className="mt-8 flex h-24 items-center gap-1.5">
              {Array.from({ length: 18 }, (_, i) => (
                <motion.span
                  key={i}
                  className="w-1.5 rounded-full bg-marigold-500"
                  animate={error ? { height: 6 } : { height: [10, 20 + ((i * 37) % 60), 10] }}
                  transition={error ? { duration: 0.3 } : { duration: 0.6 + ((i * 13) % 5) / 10, repeat: Infinity, ease: "easeInOut", delay: i * 0.04 }}
                />
              ))}
            </div>
            <div className="mt-8 min-h-16">
              {partial ? (
                <motion.p initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="text-xl leading-snug font-semibold break-words">
                  “{partial}”
                </motion.p>
              ) : (
                <p className="text-[14px] text-forest-100">{tc("u1.voice.hint", { lang: CHAT_LANG_LABEL[cl] })}</p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 px-6 pb-24">
            {error ? (
              <Button variant="accent" icon={Mic} onClick={() => setSession((n) => n + 1)}>
                {tc("action.retry")}
              </Button>
            ) : (
              <Button variant="accent" onClick={() => stop.current?.()}>
                {tc("u1.voice.stop")}
              </Button>
            )}
            <Button variant="secondary" onClick={onClose}>
              {tc("u1.voice.type")}
            </Button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
