import { CheckCircle2, FlaskConical, MessageSquareHeart, Package, Quote, Star, Users, Vote } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { tap } from "../App";
import { packMeta, feedback } from "../core/pack";
import { DEFAULT_RADIUS_KM } from "../core/procurement";
import type { PackFeedback } from "../core/types";
import { useI18n } from "../i18n";
import { rupees } from "../lib/format";
import { useStore, uid, todayOf } from "../state/store";
import { Badge, Button, Card, Chip, ConfidenceBadge, cx, IconBubble, Note, Reveal, Screen, Section, toast } from "../ui";
import { activityLabel } from "./g4/model";

const TOPICS: PackFeedback["topic"][] = ["demand", "pricing", "supply", "seasonality", "competition", "other"];
const AVATAR_TONES = ["bg-forest-200 text-forest-900", "bg-marigold-200 text-forest-950", "bg-sky-100 text-sky-700", "bg-clay-100 text-clay-700"];
const MAX_AVATARS = 7;
const SURVEY_OPTIONS = 4;

export default function Community() {
  const { t, tm, pick } = useI18n();
  const { state, view, set, dispatch } = useStore();
  const [stars, setStars] = useState(0);
  const [topic, setTopic] = useState<PackFeedback["topic"] | null>(null);
  const [note, setNote] = useState("");
  const [vote, setVote] = useState<string | null>(null);
  const pool = view.pool;
  const place = view.location.chosen ?? view.location.candidates[0] ?? null;
  const placeName = place ? pick(place.village ?? place.district.name) : null;

  if (!pool || !view.activityId) {
    return (
      <Screen title={t("community.title")}>
        <Reveal>
          <div className="mt-10 grid place-items-center text-center">
            <IconBubble icon={Users} tone="sand" size="lg" />
            <p className="mt-3 text-lg font-semibold">{t("u4.community.empty.title")}</p>
            <p className="mt-1 max-w-80 text-[15px] leading-snug text-ink-3">{t("u4.community.empty.body")}</p>
          </div>
        </Reveal>
      </Screen>
    );
  }

  const act = activityLabel(view.activityId);
  const radius = view.intel?.marketReach.radiusKm ?? DEFAULT_RADIUS_KM;
  const members = pool.peers + (state.joinedPool ? 1 : 0);
  const readiness = Math.min(1, members / pool.target);
  const avatars = Array.from({ length: Math.min(pool.peers, MAX_AVATARS) }, (_, i) => i);
  const stock = view.financial?.plan.workingCapital ?? 0;
  const saving = pool.discountPct > 0 && stock > 0 ? Math.round((stock * pool.discountPct) / 100) : null;

  const joinToggle = () => {
    tap();
    const joined = !state.joinedPool;
    set({ joinedPool: joined });
    dispatch({ type: "event", event: { type: "observation", data: { kind: "pool", joined, peers: pool.peers } } });
    if (joined) toast(t(pool.ready ? "community.pool.joinedToast" : "u4.pool.joinedWaiting", { target: pool.target }));
  };

  const districtId = place?.district.id ?? null;
  const voices = districtId ? feedback(districtId, null) : [];
  const mine = state.observations.filter((o) => o.kind === "funded_entrepreneur");
  const surveyVotes = state.observations.filter((o) => o.kind === "resident_survey");
  const voted = surveyVotes.length > 0;
  const options = view.feasibility.shortlist.filter((r) => r.activityId !== view.activityId).slice(0, SURVEY_OPTIONS).map((r) => r.activityId);
  const mentions = (id: string) =>
    voices.filter((f) => f.kind === "resident_survey" && f.activityId === id).length + surveyVotes.filter((o) => o.text === id).length;

  const observe = (kind: "funded_entrepreneur" | "resident_survey", obsTopic: string, text: string, extra: Record<string, string | number> = {}) => {
    const at = todayOf(state);
    set({ observations: [...state.observations, { id: uid(), kind, topic: obsTopic, text, at }] });
    dispatch({ type: "event", event: { type: "observation", data: { kind, topic: obsTopic, ...extra } } });
  };

  return (
    <Screen
      title={t("community.title")}
      footer={
        <Button className="w-full" variant={state.joinedPool ? "secondary" : "primary"} icon={state.joinedPool ? CheckCircle2 : Users} onClick={joinToggle} disabled={!place}>
          {state.joinedPool ? t("community.pool.leave") : t("community.pool.join")}
        </Button>
      }
    >
      <Reveal>
        <Card tone="forest" className="mt-2">
          <div className="flex flex-wrap items-center gap-2">
            {pool.discountPct > 0 ? <Badge tone="warn">{t("community.pool.badge", { pct: pool.discountPct })}</Badge> : <Badge tone="neutral">{t("u4.pool.notReady", { target: pool.target })}</Badge>}
            <ConfidenceBadge value={pool.confidence} />
          </div>
          <h2 className="mt-2.5 text-xl font-bold leading-snug">
            {placeName ? t("u4.pool.title", { n: pool.peers, activity: pick(act.name), km: Math.round(radius), place: placeName }) : t("u4.pool.titleNoPlace", { activity: pick(act.name) })}
          </h2>
          <div className="mt-4 flex -space-x-2">
            <AnimatePresence initial={false}>
              {avatars.map((i) => (
                <motion.span key={i} initial={{ scale: 0, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0 }} transition={{ type: "spring", stiffness: 420, damping: 16, delay: i * 0.05 }} className={cx("grid size-10 place-items-center rounded-full text-base ring-2 ring-forest-800", AVATAR_TONES[i % AVATAR_TONES.length])}>
                  {act.emoji}
                </motion.span>
              ))}
              {pool.peers > MAX_AVATARS && (
                <span className="grid size-10 place-items-center rounded-full bg-white/20 text-xs font-bold ring-2 ring-forest-800">+{pool.peers - MAX_AVATARS}</span>
              )}
              {state.joinedPool && (
                <motion.span key="you" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} className="grid size-10 place-items-center rounded-full bg-marigold-500 text-[11px] font-bold text-forest-950 ring-2 ring-forest-800">
                  {t("u4.pool.you")}
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          <div className="mt-4 flex items-center justify-between text-[13px] text-forest-100">
            <span>{t("u4.pool.progress", { n: members, target: pool.target })}</span>
            <span className="tabular font-semibold text-white">{Math.round(readiness * 100)}%</span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-white/20">
            <motion.div animate={{ width: `${readiness * 100}%` }} transition={{ type: "spring", stiffness: 120, damping: 18 }} className="h-full rounded-full bg-marigold-500" />
          </div>
          {pool.limitations.map((l, i) => (
            <p key={i} className="mt-2 text-xs leading-snug text-forest-100">{tm(l)}</p>
          ))}
        </Card>
      </Reveal>

      <Reveal i={1}>
        <Card className="mt-3">
          <p className="text-[13px] font-semibold text-ink-3">{t("community.pool.items")}</p>
          <div className="mt-2 grid gap-2">
            {pool.items.map((it) => (
              <div key={typeof it === "string" ? it : it.en} className="flex items-center gap-3">
                <IconBubble icon={Package} tone="sand" size="sm" />
                <span className="text-[15px] [overflow-wrap:anywhere]">{pick(it)}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 rounded-xl bg-forest-50 px-3 py-2 text-[13px] leading-snug text-forest-800">
            {pool.discountPct > 0
              ? saving !== null ? t("u4.pool.saving", { pct: pool.discountPct, stock: rupees(stock), amount: rupees(saving) }) : t("community.pool.saving", { pct: pool.discountPct })
              : t("u4.pool.noSaving", { target: pool.target })}
          </p>        </Card>
      </Reveal>

      <Section title={t("community.feedback.section")}>
        <Reveal i={2}>
          <Card>
            <div className="flex items-center gap-3">
              <IconBubble icon={MessageSquareHeart} tone="marigold" size="sm" />
              <p className="text-[15px] font-semibold">{t("u4.feedback.title", { activity: pick(act.name) })}</p>
            </div>
            <div className="mt-3 flex justify-between px-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <motion.button key={n} whileTap={{ scale: 0.8 }} aria-label={t("community.feedback.stars", { n })} onClick={() => { tap(); setStars(n); }} className="grid size-11 place-items-center">
                  <motion.span animate={{ scale: n <= stars ? [1, 1.25, 1] : 1 }} transition={{ duration: 0.25 }}>
                    <Star className={cx("size-8", n <= stars ? "fill-marigold-500 text-marigold-500" : "text-ink-3/40")} />
                  </motion.span>
                </motion.button>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {TOPICS.map((c) => (
                <Chip key={c} active={topic === c} onClick={() => setTopic(topic === c ? null : c)}>
                  {t(`u4.topic.${c}`)}
                </Chip>
              ))}
            </div>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder={t("u4.feedback.placeholder")} className="mt-3 w-full resize-none rounded-xl bg-sand px-3 py-2 text-[15px] leading-snug outline-none placeholder:text-ink-3" />
            <Button
              size="md"
              variant="secondary"
              className="mt-3 w-full"
              disabled={!stars || !topic}
              onClick={() => {
                tap();
                observe("funded_entrepreneur", topic!, note.trim(), { rating: stars });
                setStars(0);
                setTopic(null);
                setNote("");
                toast(t("community.thanks"));
              }}
            >
              {t("community.feedback.send")}
            </Button>
            {mine.length > 0 && <p className="mt-2 text-xs text-ink-3">{t("u4.feedback.count", { n: mine.length })}</p>}
          </Card>
        </Reveal>
      </Section>

      {options.length > 0 && placeName && (
        <Section title={t("community.poll.section")}>
          <Reveal i={3}>
            <Card>
              <div className="flex items-center gap-3">
                <IconBubble icon={Vote} tone="sky" size="sm" />
                <p className="text-[15px] font-semibold leading-snug">{t("u4.poll.title", { place: placeName })}</p>
              </div>
              <div className="mt-3 grid gap-2">
                {options.map((id) => {
                  const active = vote === id;
                  const n = mentions(id);
                  return (
                    <button key={id} disabled={voted} onClick={() => setVote(id)} className={cx("relative min-h-12 overflow-hidden rounded-2xl px-3.5 text-left text-[15px] ring-1", active ? "ring-2 ring-forest-600" : "ring-line", !voted && "active:bg-sand")}>
                      <span className="relative flex items-center justify-between gap-2">
                        <span className={cx("min-w-0", active && "font-semibold")}>{activityLabel(id).emoji} {pick(activityLabel(id).name)}</span>
                        {voted && <span className="tabular shrink-0 text-[13px] font-semibold text-forest-800">{t("u4.poll.mentions", { n })}</span>}
                      </span>
                    </button>
                  );
                })}
              </div>
              {voted ? (
                <p className="mt-3 text-xs leading-snug text-ink-3">{t("u4.poll.result")}</p>
              ) : (
                <Button size="md" variant="secondary" className="mt-3 w-full" disabled={!vote} onClick={() => { tap(); observe("resident_survey", "demand", vote!); toast(t("community.thanks")); }}>
                  {t("community.poll.vote")}
                </Button>
              )}
            </Card>
          </Reveal>
        </Section>
      )}

      {voices.length > 0 && (
        <Section title={t("u4.voices.title")}>
          <div className="grid gap-2">
            {voices.map((f, i) => (
              <Reveal key={f.id} i={i}>
                <Card className="p-3.5">
                  <div className="flex items-start gap-2.5">
                    <Quote className="mt-0.5 size-4 shrink-0 text-ink-3" />
                    <div className="min-w-0">
                      <p className="text-[13px] leading-snug text-ink-2">{pick(f.text)}</p>
                      <p className="mt-1 text-xs text-ink-3">
                        {pick(f.who)} · {t(`u4.topic.${f.topic}`)}
                        {f.rating !== null && ` · ${"★".repeat(f.rating)}`}
                      </p>
                    </div>
                  </div>
                </Card>
              </Reveal>
            ))}
          </div>
        </Section>
      )}

      {packMeta().synthetic_sample && (
        <div className="mt-4">
          <Note tone="marigold" icon={FlaskConical}>{t("u4.samplePack")}</Note>
        </div>
      )}
    </Screen>
  );
}
