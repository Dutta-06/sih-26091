import { Languages, Mic, RotateCcw, SendHorizontal, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { tap } from "../lib/haptics";
import { readWithModel, warmUpModel } from "../lib/nlp/client";
import { withOnlinePlace } from "../lib/onlinePlace";
import { useToolsUnlocked } from "../lib/tools";
import { useI18n } from "../i18n";
import { canListen, speak, voiceCapabilities } from "../lib/speech";
import { useNav, type Route } from "../nav";
import { EMPTY_PROFILE, samplePerson, uid, useStore, type ChatMessage } from "../state/store";
import { Chip, toast } from "../ui";
import { Bubble, ProfileSummaryCard, TypingDots, VerdictCard, VoiceOverlay, type VerdictTarget } from "./g1/ChatParts";
import {
  advance,
  answeredSlots,
  chatName,
  jumpMessages,
  missingSlots,
  opening,
  profileComplete,
  profileSig,
  respond,
  sampleText,
  skipName,
  verdictMessage,
  type ConvInput,
  type ConvResult,
  type JumpIntent,
  type PendingSlot,
} from "./g1/conversation";
import { ChatLangSheet, JumpCard, LocationChoices, SlotInputs, SuggestionCard, type SlotAnswer } from "./w1/ChatCards";
import { CHAT_LANG_SHORT, useChatI18n } from "./w1/chatI18n";

const TYPING_MS = 480;
const SUGGESTIONS: JumpIntent[] = ["application", "grievance", "scheme", "monitoring", "community"];
const ROUTES: Record<JumpIntent, Route> = {
  grievance: { name: "grievance" },
  application: { name: "application" },
  scheme: { name: "scheme" },
  monitoring: { name: "monitoring" },
  community: { name: "community" },
  languages: { name: "languages" },
  noViable: { name: "noViable" },
  report: { name: "report" },
  review: { name: "review" },
  plan: { name: "plan" },
};

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Apply a turn result to a local conversation copy (used by the presenter sample, which runs faster than renders). */
function applyLocal(input: ConvInput, user: ChatMessage, r: ConvResult): ConvInput {
  return { profile: { ...input.profile, ...r.profilePatch }, pendingSlot: r.pendingSlot, chat: [...input.chat, user, ...r.messages], chatLang: r.chatLang ?? input.chatLang };
}

export default function Assistant() {
  const { t } = useI18n();
  const tools = useToolsUnlocked();
  const { cl, tc, actName } = useChatI18n();
  const { state, dispatch, set, view } = useStore();
  const { push, switchTab } = useNav();
  const [typing, setTyping] = useState(false);
  const [listening, setListening] = useState(false);
  const [langSheet, setLangSheet] = useState(false);
  const [draft, setDraft] = useState("");
  const [stt, setStt] = useState(canListen());
  const [sampleRunning, setSampleRunning] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const { chat, profile, pendingSlot, analysisSeen } = state;
  const conv = (): ConvInput => ({ profile: stateRef.current.profile, pendingSlot: stateRef.current.pendingSlot, chat: stateRef.current.chat, chatLang: stateRef.current.chatLang });
  const complete = profileComplete(profile, chat);
  const sig = profileSig(profile);
  const name = chatName(chat);

  useEffect(() => {
    let alive = true;
    void voiceCapabilities().then((c) => alive && setStt(c.stt));
    return () => {
      alive = false;
    };
  }, []);

  /** Post a user message and the computed assistant reply; resolves when the reply is shown. */
  const turn = async (userText: string, r: ConvResult): Promise<ChatMessage> => {
    tap();
    const s = stateRef.current;
    const user: ChatMessage = { id: uid(), from: "user", text: userText, literal: true, ...(Object.keys(r.userVars).length ? { vars: r.userVars } : {}) };
    if (r.reset) {
      set({ chat: [user], profile: EMPTY_PROFILE, pendingSlot: null, chosenActivity: null, analysisSeen: false });
    } else {
      dispatch({ type: "chat", messages: [user] });
      if (!s.events.some((e) => e.type === "profile_started") && Object.keys(r.profilePatch).length) dispatch({ type: "event", event: { type: "profile_started" } });
      if (Object.keys(r.profilePatch).length) dispatch({ type: "profile", patch: r.profilePatch });
      if (r.changedCore && (s.analysisSeen || s.chosenActivity)) set({ analysisSeen: false, chosenActivity: null });
      r.events.forEach((event) => dispatch({ type: "event", event }));
    }
    if (r.chatLang) set({ chatLang: r.chatLang });
    setTyping(true);
    await wait(TYPING_MS);
    dispatch({ type: "chat", messages: r.messages, pendingSlot: r.pendingSlot });
    setTyping(false);
    return user;
  };

  // Load the message model in the background while the conversation opens
  useEffect(() => warmUpModel(), []);

  // Open the conversation (new chat, or a case that already has inputs).
  useEffect(() => {
    if (chat.length > 0) return;
    const o = opening(conv());
    setTyping(true);
    const timer = setTimeout(() => {
      setTyping(false);
      dispatch({ type: "chat", messages: o.messages, pendingSlot: o.pendingSlot });
    }, 350);
    return () => {
      clearTimeout(timer);
      setTyping(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.length === 0]);

  // After the analysis has been seen, post the computed verdict once per set of inputs.
  useEffect(() => {
    if (!analysisSeen || !complete || chat.length === 0 || typing) return;
    if (chat.some((m) => m.card === "verdict" && m.vars?.sig === sig)) return;
    dispatch({ type: "chat", messages: [verdictMessage(sig)] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisSeen, sig, chat.length, complete, typing]);

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [chat.length, typing, pendingSlot]);

  // Read new assistant messages aloud when the user turned that on (TDD 4.3).
  const seen = useRef(chat.length);
  useEffect(() => {
    const fresh = chat.slice(seen.current);
    seen.current = chat.length;
    if (!state.readAloud) return;
    const text = fresh
      .filter((m) => m.from === "assistant" && !m.card)
      .map((m) => tc(m.text, m.vars))
      .join(" ");
    if (text) speak(text, cl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.length]);

  const busy = typing || sampleRunning;

  const sendText = (text: string) => {
    const clean = text.trim();
    if (!clean || busy) return;
    setDraft("");
    setTyping(true);
    void readWithModel(clean)
      .then(async (reading) => ({ reading, text: await withOnlinePlace(clean, conv(), reading) }))
      .then(({ reading, text }) => {
        setTyping(false);
        return turn(clean, respond(text, conv(), text === clean ? reading : null));
      });
  };

  const answerSlot = (a: SlotAnswer) => {
    if (busy) return;
    void turn(a.text, advance(conv(), a.patch, a.answered));
  };

  const runAnalysis = () => {
    tap();
    dispatch({ type: "event", event: { type: "analysis_run", data: { sig } } });
    push({ name: "analysis" });
  };

  const openJump = (intent: JumpIntent) => {
    if (intent === "plan") switchTab("plan");
    else push(ROUTES[intent]);
  };

  /** Presenter: type the sample inputs through the same pipeline, one pending question at a time. */
  const runSample = async () => {
    if (busy) return;
    setSampleRunning(true);
    const sample = samplePerson(state);
    let local = conv();
    if (local.pendingSlot === null) local = { ...local, pendingSlot: missingSlots(local.profile, answeredSlots(local.chat))[0] ?? null };
    for (let i = 0; i < 14 && local.pendingSlot !== null; i++) {
      const slot = local.pendingSlot as PendingSlot;
      let text: string;
      let r: ConvResult;
      if (slot === "name") {
        text = sample.name;
        r = respond(text, local, await readWithModel(text));
      } else if (slot === "location_choice") {
        const code = sample.profile.locationCode;
        if (!code) break;
        text = tc("u1.loc.code", { code });
        r = advance(local, { locationCode: code }, ["location"]);
      } else {
        const typed = sampleText(sample.profile, slot);
        if (!typed) break;
        text = typed;
        r = respond(typed, local, await readWithModel(typed));
      }
      const user = await turn(text, r);
      local = applyLocal(local, user, r);
      await wait(250);
    }
    setSampleRunning(false);
  };

  const lastIndex = (card: string) => chat.map((m) => m.card).lastIndexOf(card);

  const renderCard = (m: ChatMessage, index: number) => {
    switch (m.card) {
      case "profile_summary":
        return <ProfileSummaryCard profile={profile} name={name} started={analysisSeen} onRun={runAnalysis} />;
      case "verdict":
        return <VerdictCard stale={m.vars?.sig !== sig || !analysisSeen} feasibility={view.feasibility} onOpen={(to: VerdictTarget) => push({ name: to })} onRerun={runAnalysis} />;
      case "loc_choice":
        return (
          <LocationChoices
            query={String(m.vars?.query ?? profile.locationText)}
            selected={profile.locationCode}
            active={!busy && pendingSlot === "location_choice" && index === lastIndex("loc_choice")}
            onPick={(lgd, label) => void turn(label, advance(conv(), { locationCode: lgd }, ["location"]))}
          />
        );
      case "act_suggest":
        return (
          <SuggestionCard
            ids={String(m.vars?.ids ?? "").split(",").filter(Boolean)}
            profile={profile}
            active={!busy && index === lastIndex("act_suggest")}
            onPick={(id) => void turn(actName(id), advance(conv(), { activityId: id }, []))}
          />
        );
      case "jump":
        return <JumpCard intent={m.vars?.intent as JumpIntent} onOpen={() => openJump(m.vars?.intent as JumpIntent)} />;
      default:
        return undefined;
    }
  };

  const slotChips = !busy && (pendingSlot === "skills" || pendingSlot === "premises" || pendingSlot === "category") && chat.at(-1)?.from === "assistant";

  return (
    <div className="relative flex h-full flex-col bg-cream">
      <header className="safe-top border-b border-line bg-cream/95 backdrop-blur">
        <div className="flex min-h-15 items-center gap-2 px-4 py-2">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-azure-800 text-white">
            <Sparkles className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-[17px] leading-tight font-semibold">{t("app.name")}</h1>
            <p className="flex items-center gap-1.5 truncate text-xs text-ink-3">
              <span className="size-2 shrink-0 rounded-full bg-azure-600" />
              {t("w1.assistant.status")}
            </p>
          </div>
          <button
            aria-label={t("w1.lang.chatTitle")}
            onClick={() => {
              tap();
              setLangSheet(true);
            }}
            className="flex min-h-11 items-center gap-1 rounded-full bg-white px-3 text-sm font-semibold text-azure-800 ring-1 ring-line active:bg-sand"
          >
            <Languages className="size-4" />
            {CHAT_LANG_SHORT[cl]}
          </button>
          <button
            aria-label={t("assistant.restart")}
            disabled={busy}
            onClick={() => {
              tap();
              set({ chat: [], pendingSlot: null, profile: EMPTY_PROFILE, analysisSeen: false, chosenActivity: null });
            }}
            className="grid size-11 place-items-center rounded-full text-azure-800 active:bg-sand disabled:opacity-40"
          >
            <RotateCcw className="size-4.5" />
          </button>
        </div>
      </header>

      <div ref={scroller} lang={cl} className="scroll-area flex-1 space-y-2.5 px-4 pt-4 pb-4">
        {chat.map((m, i) => (
          <Bubble key={m.id} message={m}>
            {renderCard(m, i)}
          </Bubble>
        ))}
        <AnimatePresence>{typing && <TypingDots />}</AnimatePresence>
      </div>

      <div lang={cl} className="border-t border-line bg-cream px-4 pt-2.5 pb-2.5">
        {slotChips && (
          <div className="mb-2.5">
            <SlotInputs key={pendingSlot} slot={pendingSlot as "skills" | "premises" | "category"} onSubmit={answerSlot} />
          </div>
        )}
        <div className="scroll-area -mx-4 mb-2.5 flex gap-2 overflow-x-auto px-4 empty:hidden">
          {!busy && pendingSlot === "name" && <Chip onClick={() => void turn(tc("u1.ans.skip"), skipName(conv()))}>{tc("u1.chip.skip")}</Chip>}
          {!busy && !complete && tools && (
            <Chip icon={Sparkles} onClick={() => void runSample()}>
              <span className="whitespace-nowrap">{tc("u1.chip.sample")}</span>
            </Chip>
          )}
          {!busy && complete && !analysisSeen && <Chip onClick={runAnalysis}>{tc("u1.chip.run")}</Chip>}
          {!busy &&
            complete &&
            SUGGESTIONS.map((intent) => (
              <Chip
                key={intent}
                onClick={() =>
                  void turn(tc(`u1.sugg.${intent}`), { userVars: {}, messages: jumpMessages(intent), profilePatch: {}, pendingSlot: stateRef.current.pendingSlot, events: [], changedCore: false })
                }
              >
                <span className="whitespace-nowrap">{tc(`u1.sugg.${intent}`)}</span>
              </Chip>
            ))}
        </div>
        <div className="flex items-center gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendText(draft)}
            placeholder={tc("assistant.inputPh")}
            disabled={sampleRunning}
            maxLength={300}
            className="min-h-12 min-w-0 flex-1 rounded-full bg-white px-4 text-[15px] ring-1 ring-line outline-none placeholder:text-ink-3 focus:ring-azure-600 disabled:opacity-60"
          />
          {draft.trim() ? (
            <motion.button whileTap={{ scale: 0.92 }} aria-label={tc("assistant.send")} disabled={busy} onClick={() => sendText(draft)} className="grid size-12 shrink-0 place-items-center rounded-full bg-azure-800 text-white disabled:opacity-50">
              <SendHorizontal className="size-5" />
            </motion.button>
          ) : (
            <motion.button
              whileTap={{ scale: 0.92 }}
              aria-label={tc("assistant.mic")}
              disabled={busy}
              onClick={() => {
                tap();
                if (!stt) toast(tc("u1.voice.noStt"), { tone: "info" });
                else setListening(true);
              }}
              className="grid size-12 shrink-0 place-items-center rounded-full bg-marigold-500 text-azure-950 disabled:bg-ink-3/20 disabled:text-ink-3"
            >
              <Mic className="size-5.5" />
            </motion.button>
          )}
        </div>
      </div>
      {/* room for the bottom tab bar */}
      <div className="safe-bottom shrink-0">
        <div className="h-16" />
      </div>

      <VoiceOverlay
        open={listening}
        onClose={() => setListening(false)}
        onFinal={(text) => {
          setListening(false);
          sendText(text);
        }}
      />
      <ChatLangSheet open={langSheet} onClose={() => setLangSheet(false)} />
    </div>
  );
}
