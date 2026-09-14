import { BarChart3, CheckCircle2, ClipboardList, Mic, Send, Square, Star } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { tap } from "../lib/haptics";
import { canListen, listen, type ListenError } from "../lib/speech";
import { useNav } from "../nav";
import { todayOf, uid, useStore, type Observation } from "../state/store";
import { Button, Card, Chip, cx, Note, Progress, Reveal, Screen, Section, Segmented } from "../ui";
import { activityLabel, placeOf } from "./g2/feasibility";
import { PackNote } from "./g2/ReportSections";
import { FEEDBACK_PRESETS, FEEDBACK_TOPICS, SURVEY_QUESTIONS, tallies, type EvidenceTopic } from "./w2/evidence";

type Mode = "resident" | "funded";

export default function Survey() {
  const { t, pick, lang } = useI18n();
  const { state, set, dispatch, view } = useStore();
  const { push } = useNav();
  const [mode, setMode] = useState<Mode>("resident");
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [topic, setTopic] = useState<EvidenceTopic | null>(null);
  const [rating, setRating] = useState(0);
  const [preset, setPreset] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [voice, setVoice] = useState<"none" | "recording" | "saved">("none");
  const [voiceError, setVoiceError] = useState<ListenError | null>(null);
  const [done, setDone] = useState<Mode | null>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const place = placeOf(view);
  const district = place?.district.id ?? null;
  const activityId = view.activityId ?? state.profile.activityId;
  const tally = tallies(district, state.observations);

  useEffect(() => () => stopRef.current?.(), []);

  const toggle = (q: string, o: string, multi: boolean) => {
    tap();
    setAnswers((a) => {
      const cur = a[q] ?? [];
      const next = multi ? (cur.includes(o) ? cur.filter((x) => x !== o) : [...cur, o]) : cur[0] === o ? [] : [o];
      return { ...a, [q]: next };
    });
  };

  const toggleVoice = async () => {
    tap();
    if (voice === "recording") {
      stopRef.current?.();
      stopRef.current = null;
      setVoice(note.trim() ? "saved" : "none");
      return;
    }
    setVoiceError(null);
    setVoice("recording");
    const before = note;
    stopRef.current = await listen({
      lang,
      onPartial: (text) => setNote([before, text].filter(Boolean).join(" ")),
      onFinal: (text) => {
        setNote([before, text].filter(Boolean).join(" "));
        setVoice("saved");
        stopRef.current = null;
      },
      onError: (e) => {
        setVoiceError(e);
        setVoice("none");
        stopRef.current = null;
      },
    });
  };

  const reset = () => {
    setAnswers({});
    setTopic(null);
    setRating(0);
    setPreset(null);
    setNote("");
    setVoice("none");
    setDone(null);
  };

  const canSubmit = mode === "resident" ? Object.values(answers).some((v) => v.length) || !!note.trim() : !!topic && rating > 0;

  const submit = () => {
    tap();
    const at = todayOf(state);
    const obs: Observation =
      mode === "resident"
        ? { id: uid(), kind: "resident_survey", topic: "demand", text: JSON.stringify({ answers, note: note.trim(), voice: voice === "saved", district, activityId }), at }
        : { id: uid(), kind: "funded_entrepreneur", topic: topic!, text: JSON.stringify({ rating, preset, note: note.trim(), voice: voice === "saved", district, activityId }), at };
    set({ observations: [...state.observations, obs] });
    dispatch({ type: "event", event: { type: "observation", data: { id: obs.id, kind: obs.kind, topic: obs.topic, district, activityId } } });
    setDone(mode);
  };

  if (done) {
    return (
      <Screen title={t("survey.title")}>
        <motion.div initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 22 }} className="mt-10 text-center">
          <CheckCircle2 className="mx-auto size-16 text-azure-600" />
          <h2 className="mt-4 text-xl font-bold">{t("survey.thanks")}</h2>
          <p className="mx-auto mt-2 max-w-72 text-[15px] leading-snug text-ink-2">{t("survey.thanksSub", { n: tally.mineCount, place: place ? pick(place.district.name) : "—" })}</p>
          <div className="mt-6 flex flex-col gap-2">
            <Button icon={ClipboardList} onClick={() => push({ name: "evidence" })}>
              {t("survey.seeEvidence")}
            </Button>
            <Button variant="ghost" size="md" onClick={reset}>
              {t("survey.another")}
            </Button>
          </div>
        </motion.div>
      </Screen>
    );
  }

  return (
    <Screen
      title={t("survey.title")}
      subtitle={place ? t("survey.subtitle", { place: pick(place.district.name), activity: activityId ? pick(activityLabel(activityId).name) : t("g2.evidence.allWork") }) : undefined}
      footer={
        <Button className="w-full" icon={Send} disabled={!canSubmit} onClick={submit}>
          {t("survey.submit")}
        </Button>
      }
    >
      {!place && (
        <div className="mt-2">
          <Note tone="marigold">{t("g2.survey.noPlace")}</Note>
        </div>
      )}

      {/* grouped totals for this district */}
      <Section title={t("g2.survey.tallies")} action={<BarChart3 className="size-4 text-ink-3" />}>
        <Card>
          <div className="grid grid-cols-3 gap-2 text-center">
            {[
              [tally.packCount, "g2.survey.packCount"],
              [tally.funded, "g2.survey.funded"],
              [tally.residents, "g2.survey.residents"],
            ].map(([n, key]) => (
              <div key={key}>
                <p className="tabular text-xl font-bold text-azure-800">{n}</p>
                <p className="text-[11px] leading-tight text-ink-3">{t(key as string)}</p>
              </div>
            ))}
          </div>
          {tally.topics.length > 0 ? (
            <div className="mt-3 space-y-2">
              {tally.topics.map((tp) => (
                <div key={tp.topic} className="flex items-center gap-2">
                  <span className="w-20 shrink-0 text-[13px] text-ink-2">{t(`evidence.topic.${tp.topic}`)}</span>
                  <Progress value={(tp.n / Math.max(1, tally.topics[0].n)) * 100} className="h-2.5 flex-1" />
                  <span className="tabular w-6 text-right text-[13px] font-semibold">{tp.n}</span>
                  <span className="tabular w-10 text-right text-xs text-ink-3">{tp.avg === null ? "—" : `${tp.avg.toFixed(1)}★`}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-[13px] text-ink-3">{t("g2.survey.noTallies")}</p>
          )}
        </Card>
      </Section>

      <div className="mt-5 flex justify-center">
        <Segmented<Mode>
          value={mode}
          onChange={(m) => {
            tap();
            setMode(m);
          }}
          options={[
            { value: "resident", label: t("survey.tab.resident") },
            { value: "funded", label: t("survey.tab.funded") },
          ]}
        />
      </div>

      {mode === "resident" ? (
        SURVEY_QUESTIONS.map((q, i) => {
          const counts = tally.options.find((o) => o.id === q.id);
          return (
            <Section key={q.id} title={`${i + 1}. ${t(`survey.q.${q.id}`)}`}>
              <Reveal i={i}>
                {q.multi && <p className="-mt-1 mb-2 px-1 text-xs text-ink-3">{t("survey.pickMany")}</p>}
                <div className="flex flex-wrap gap-2">
                  {q.options.map((o) => {
                    const n = counts?.counts.find((c) => c.opt === o)?.n ?? 0;
                    return (
                      <Chip key={o} active={(answers[q.id] ?? []).includes(o)} onClick={() => toggle(q.id, o, q.multi)}>
                        {t(`survey.o.${q.id}.${o}`)}
                        {n > 0 && <span className="tabular ml-1 text-xs opacity-70">{n}</span>}
                      </Chip>
                    );
                  })}
                </div>
              </Reveal>
            </Section>
          );
        })
      ) : (
        <>
          <Section title={t("survey.f.topic")}>
            <div className="flex flex-wrap gap-2">
              {FEEDBACK_TOPICS.map((tp) => (
                <Chip
                  key={tp}
                  active={topic === tp}
                  onClick={() => {
                    tap();
                    setTopic(tp);
                    setPreset(null);
                  }}
                >
                  {t(`evidence.topic.${tp}`)}
                </Chip>
              ))}
            </div>
          </Section>
          {topic && (
            <Section title={t("survey.f.say")}>
              <div className="flex flex-wrap gap-2">
                {FEEDBACK_PRESETS[topic].map((p) => (
                  <Chip key={p} active={preset === p} onClick={() => setPreset(preset === p ? null : p)}>
                    {t(`survey.preset.${p}`)}
                  </Chip>
                ))}
              </div>
            </Section>
          )}
          <Section title={t("survey.f.rating")}>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} aria-label={`${n}`} onClick={() => setRating(n)} className="grid size-12 place-items-center rounded-full active:bg-sand">
                  <Star className={cx("size-8", n <= rating ? "fill-marigold-500 text-marigold-500" : "text-ink-3/40")} />
                </button>
              ))}
            </div>
          </Section>
        </>
      )}

      <Section title={t("survey.voice")}>
        <Card>
          <div className="flex items-center gap-3">
            <motion.button
              whileTap={{ scale: 0.92 }}
              onClick={toggleVoice}
              disabled={!canListen()}
              className={cx("grid size-13 shrink-0 place-items-center rounded-full text-white disabled:bg-ink-3/40", voice === "recording" ? "bg-clay-600" : "bg-azure-800")}
              aria-label={t("survey.voice")}
            >
              {voice === "recording" ? <Square className="size-5" /> : <Mic className="size-6" />}
            </motion.button>
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-medium">{t(canListen() ? `survey.voice.${voice}` : "g2.survey.voiceUnavailable")}</p>
              <p className="text-xs text-ink-3">{voiceError ? t(`g2.survey.voiceError.${voiceError}`) : t("survey.voiceHint")}</p>
            </div>
            {voice === "recording" && <motion.span animate={{ opacity: [1, 0.2, 1] }} transition={{ repeat: Infinity, duration: 1 }} className="size-3 rounded-full bg-clay-600" />}
          </div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            placeholder={t("survey.f.notePh")}
            className="mt-3 w-full rounded-2xl bg-cream p-3 text-[15px] ring-1 ring-line outline-none focus:ring-azure-600"
          />
        </Card>
      </Section>

      <div className="mt-4">
        <Note>{t("survey.privacy")}</Note>
      </div>
      <PackNote />
    </Screen>
  );
}
