import { ArrowRight, Check, Combine, LoaderCircle, MessageCircle, Repeat2, ShieldAlert, ShieldCheck, Sprout } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ACTIVITIES } from "../data/activities";
import { MAX_ATTEMPTS } from "../core/intel/catalog";
import type { FeasibilityAttempt, Verdict } from "../core/types";
import { useI18n } from "../i18n";
import { tap } from "../lib/haptics";
import { useNav, type Route } from "../nav";
import { useStore } from "../state/store";
import { Badge, Button, ConfidenceBadge, cx, Screen } from "../ui";
import { placeOf } from "./g1/conversation";
import { AGENT_ORDER, confidenceOf, findingLine, type AgentId } from "./g1/findings";
import { AGENT_ICONS, OrchestratorDiagram } from "./g1/OrchestratorDiagram";
import { PackNote } from "./g1/PackNote";
import { useFmt } from "./w1/chatI18n";

/* Animation timeline per attempt (ms). Only the pacing is fixed; every line shown is computed. */
const AGENT_AT = (i: number) => 350 + i * 300;
const SWOT_AT = 2300;
const REDTEAM_AT = 3000;
const VERDICT_AT = 3800;
const ATTEMPT_MS = 4600;
const SKIPPED = 1e9;

const verdictTone = (v: Verdict) => (v === "viable" ? "good" : v === "marginal" ? "warn" : "risk");

export default function Analysis() {
  const { t, pick } = useI18n();
  const fmt = useFmt();
  const { state, set, view } = useStore();
  const { pop, push } = useNav();
  const [elapsed, setElapsed] = useState(0);
  const resultRef = useRef<HTMLDivElement>(null);

  const f = view.feasibility;
  const attempts = f.attempts;
  const resultAt = attempts.length ? (attempts.length - 1) * ATTEMPT_MS + VERDICT_AT + 500 : 900;
  const done = elapsed >= resultAt;
  const current = Math.min(Math.max(attempts.length - 1, 0), Math.floor(Math.min(elapsed, resultAt) / ATTEMPT_MS));
  const local = elapsed - current * ATTEMPT_MS;

  useEffect(() => {
    const start = performance.now();
    const id = setInterval(() => setElapsed((e) => (e >= SKIPPED ? e : performance.now() - start)), 100);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!done) return;
    if (!state.analysisSeen) set({ analysisSeen: true });
    resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done]);

  const place = placeOf(state.profile);
  const placeName = place ? [place.village, place.district.name].flatMap((b) => (b ? [pick(b)] : [])).join(", ") : undefined;
  const attempt = attempts[current] ?? null;
  const name = (id: string) => `${ACTIVITIES[id]?.emoji ?? ""} ${ACTIVITIES[id] ? pick(ACTIVITIES[id].name) : id}`.trim();

  const go = (route: Route | null) => {
    tap();
    if (!state.analysisSeen) set({ analysisSeen: true });
    pop();
    if (route) push(route);
  };

  const doneFlags = Object.fromEntries(AGENT_ORDER.map((id, i) => [id, !!attempt && local >= AGENT_AT(i)])) as Record<AgentId, boolean>;

  return (
    <Screen
      tone="forest"
      title={attempt ? t("u1.an.title", { idea: pick(ACTIVITIES[attempt.activityId]?.name ?? { en: attempt.activityId, hi: attempt.activityId }) }) : t("u1.an.titleIdle")}
      subtitle={placeName}
      right={
        !done && (
          <button onClick={() => setElapsed(SKIPPED)} className="min-h-11 rounded-full px-3 text-sm font-medium text-marigold-200 active:bg-white/10">
            {t("u1.an.skip")}
          </button>
        )
      }
    >
      <p className="mt-1 text-center text-[13px] text-forest-100">{t(done ? "u1.an.done" : "u1.an.running")}</p>

      {attempt && (
        <div className="mt-3">
          <OrchestratorDiagram done={doneFlags} />
        </div>
      )}

      {/* earlier attempts, collapsed to their computed verdict */}
      <div className="mt-3 space-y-2">
        {attempts.slice(0, current).map((a, k) => (
          <motion.div key={a.activityId} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex min-h-13 items-center gap-3 rounded-2xl bg-white/5 px-3 py-2 ring-1 ring-white/10">
            <span className="tabular grid size-7 shrink-0 place-items-center rounded-full bg-white/10 text-xs font-bold">{k + 1}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[14px] font-semibold">{name(a.activityId)}</p>
              <p className="text-[12px] leading-snug text-forest-100">{a.findings[0] ? fmt(a.findings[0].msg) : t("u1.an.redteamNone")}</p>
            </div>
            <Badge tone={verdictTone(a.verdict)}>{t(`verdict.${a.verdict}`)}</Badge>
          </motion.div>
        ))}
      </div>

      {attempt && (
        <AttemptView key={attempt.activityId} attempt={attempt} index={current} local={elapsed >= SKIPPED ? SKIPPED : local} finished={done} name={name} />
      )}

      <div ref={resultRef} className="scroll-mt-16">
        {done && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 22 }}
            className="mt-5 rounded-[var(--radius-card)] bg-cream p-4 text-ink shadow-[var(--shadow-float)]"
          >
            {f.selected ? (
              <>
                <Badge tone="good" icon={ShieldCheck}>
                  {t("verdict.viable")}
                </Badge>
                <h2 className="mt-2 text-xl leading-snug font-bold">{t("u1.an.selected", { idea: name(f.selected.activityId) })}</h2>
                <p className="mt-1.5 text-[14px] leading-snug text-ink-2">{t("u1.an.selectedSub", { n: attempts.indexOf(f.selected) + 1, score: Math.round(f.selected.score) })}</p>
                <p className="mt-1 text-[11px] font-medium text-ink-3">{t("g1.rulesNotAi")}</p>
                <Button className="mt-4 w-full" iconRight={ArrowRight} onClick={() => go({ name: attempts[0] === f.selected ? "report" : "review" })}>
                  {t(attempts[0] === f.selected ? "u1.an.cta.report" : "u1.an.cta.review")}
                </Button>
              </>
            ) : f.exhausted ? (
              <>
                <Badge tone="warn" icon={Sprout}>
                  {t("verdict.not_recommended")}
                </Badge>
                <h2 className="mt-2 text-xl leading-snug font-bold">{t("u1.an.exhausted")}</h2>
                <p className="mt-1.5 text-[14px] leading-snug text-ink-2">{t("u1.an.exhaustedSub", { n: attempts.length })}</p>
                {f.constraints.map((c) => (
                  <p key={c.key} className="mt-1.5 text-[13px] leading-snug text-ink-2">
                    {fmt(c)}
                  </p>
                ))}
                <Button className="mt-4 w-full" iconRight={ArrowRight} onClick={() => go({ name: "noViable" })}>
                  {t("u1.an.cta.noViable")}
                </Button>
              </>
            ) : (
              <>
                <Badge tone="warn" icon={ShieldAlert}>
                  {t("u1.an.constraint")}
                </Badge>
                {f.constraints.length ? (
                  <ul className="mt-2 space-y-1.5">
                    {f.constraints.map((c) => (
                      <li key={c.key} className="text-[14px] leading-snug text-ink-2">
                        {fmt(c)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-[14px] leading-snug text-ink-2">{t("u1.an.noProfile")}</p>
                )}
              </>
            )}
            <Button variant="ghost" size="md" icon={MessageCircle} className="mt-1 w-full" onClick={() => go(null)}>
              {t("u1.an.cta.chat")}
            </Button>
          </motion.div>
        )}
      </div>
      <PackNote light />
    </Screen>
  );
}

function AttemptView({ attempt, index, local, finished, name }: { attempt: FeasibilityAttempt; index: number; local: number; finished: boolean; name: (id: string) => string }) {
  const { t } = useI18n();
  const fmt = useFmt();
  const at = (ms: number) => local >= ms;
  const swot = attempt.swot;
  return (
    <div className="mt-3">
      {index > 0 && (
        <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="mb-2 flex items-center gap-2 rounded-2xl bg-marigold-500/15 px-3 py-2.5 text-[14px] font-semibold text-marigold-200 ring-1 ring-marigold-500/40">
          <Repeat2 className="size-4.5 shrink-0" />
          {t("u1.an.trying", { idea: name(attempt.activityId) })}
        </motion.div>
      )}
      <p className="mb-2 px-1 text-[11px] font-semibold tracking-wide text-forest-100 uppercase">{t("u1.an.attempt", { n: index + 1, max: MAX_ATTEMPTS })}</p>
      <div className="space-y-2">
        {AGENT_ORDER.map((id, i) => {
          const ok = at(AGENT_AT(i));
          const Icon = AGENT_ICONS[id];
          return (
            <div key={id} className={cx("flex min-h-14 items-center gap-3 rounded-2xl px-3 py-2.5 transition-colors", ok ? "bg-white/10" : "bg-white/5")}>
              <span className="grid size-8 shrink-0 place-items-center text-forest-100">
                <Icon className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-semibold">{t(`u1.agent.${id}`)}</p>
                <AnimatePresence mode="wait">
                  {ok ? (
                    <motion.p key="f" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="text-[13px] leading-snug break-words text-forest-100">
                      {fmt(findingLine(attempt.intel, id))}
                    </motion.p>
                  ) : (
                    <motion.p key="w" exit={{ opacity: 0 }} className="text-[13px] text-forest-100/60">
                      {t("u1.an.reading")}
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
              {ok ? (
                <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }}>
                  <ConfidenceBadge value={confidenceOf(attempt.intel, id)} />
                </motion.span>
              ) : (
                <LoaderCircle className="size-5 animate-spin text-marigold-200" />
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-3 space-y-2">
        <Phase show={at(SWOT_AT)} busy={!at(REDTEAM_AT)} icon={<Combine className="size-5" />} title={t("u1.an.swot")}>
          <p>{t("u1.an.swotSub", { s: swot.strengths.length, w: swot.weaknesses.length, o: swot.opportunities.length, t: swot.threats.length })}</p>
          {at(REDTEAM_AT) && (swot.strengths[0] || swot.threats[0]) && (
            <p className="mt-0.5 text-forest-100/80">{[swot.strengths[0], swot.threats[0]].filter(Boolean).map((m) => fmt(m)).join(" · ")}</p>
          )}
        </Phase>
        <Phase show={at(REDTEAM_AT)} busy={!at(VERDICT_AT)} clay icon={<ShieldAlert className="size-5" />} title={t("u1.an.redteam")}>
          {!at(VERDICT_AT) ? (
            <p>{t("u1.an.redteamBusy")}</p>
          ) : attempt.findings.length ? (
            <ul className="space-y-1">
              {attempt.findings.map((fd, k) => (
                <li key={`${fd.rule}-${k}`} className="flex gap-1.5">
                  <span className="tabular shrink-0 rounded bg-white/15 px-1 text-[10px] leading-4 font-bold">{fd.rule}</span>
                  <span>{fmt(fd.msg)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>{t("u1.an.redteamNone")}</p>
          )}
        </Phase>
        {(at(VERDICT_AT) || finished) && (
          <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="flex items-center gap-2 px-1 pt-1">
            <Badge tone={verdictTone(attempt.verdict)}>{t(`verdict.${attempt.verdict}`)}</Badge>
            <span className="min-w-0 truncate text-[14px] font-semibold">{t("u1.an.verdict", { idea: name(attempt.activityId), verdict: t(`verdict.${attempt.verdict}`) })}</span>
          </motion.div>
        )}
      </div>
    </div>
  );
}

function Phase({ show, busy, icon, title, children, clay }: { show: boolean; busy: boolean; icon: ReactNode; title: string; children: ReactNode; clay?: boolean }) {
  if (!show) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cx("flex min-h-14 items-start gap-3 rounded-2xl px-3 py-2.5", clay ? "bg-clay-600/25 ring-1 ring-clay-600/60" : "bg-white/10")}
    >
      <span className={cx("mt-0.5 grid size-8 shrink-0 place-items-center rounded-full", clay ? "bg-clay-600 text-white" : "bg-marigold-500 text-forest-950")}>{icon}</span>
      <div className="min-w-0 flex-1 text-[13px] leading-snug text-forest-100">
        <p className="text-[14px] font-semibold text-white">{title}</p>
        {children}
      </div>
      {busy ? <LoaderCircle className="mt-1 size-5 animate-spin text-marigold-200" /> : <Check className="mt-1 size-5 text-marigold-500" />}
    </motion.div>
  );
}
