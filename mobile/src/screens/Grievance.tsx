import { Clock, Mic, Send, Sparkles, UserRound } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { tap } from "../App";
import { catalogEntry } from "../core/financial";
import { classifyIssue, createTicket, routeTicket } from "../core/grievance";
import type { GrievanceTicket } from "../core/types";
import { useI18n } from "../i18n";
import { canListen, listen, type ListenError } from "../lib/speech";
import { Badge, Button, Card, Chip, cx, IconBubble, Reveal, Screen, Section, toast } from "../ui";
import { dateLabel, ticketStatus, useLifecycle } from "./g4/model";
import { PastTicket } from "./w4/PastTicket";

type Issue = GrievanceTicket["issue"];
const ISSUES: Issue[] = ["machinery_breakdown", "supply_delay", "loan_repayment_stress", "pricing_collapse", "other"];
const STEPS = ["logged", "mentor_assigned", "in_progress", "resolved"] as const;

function Timeline({ status, ticket }: { status: GrievanceTicket["status"]; ticket: GrievanceTicket }) {
  const { t, lang } = useI18n();
  const at = Math.max(0, (STEPS as readonly string[]).indexOf(status));
  const hint = (s: (typeof STEPS)[number]) => {
    if (s === "logged") return dateLabel(ticket.at, lang, true);
    if (s === "in_progress") return t("u4.griev.by", { date: dateLabel(new Date(Date.parse(ticket.at) + ticket.responseHours * 3_600_000).toISOString(), lang, true) });
    if (s === "resolved") return t("u4.griev.expected", { date: dateLabel(new Date(Date.parse(ticket.at) + 3 * ticket.responseHours * 3_600_000).toISOString(), lang, true) });
    return null;
  };
  return (
    <div className="mt-3">
      {STEPS.map((s, i) => {
        const done = i <= at;
        const current = i === at + 1;
        const h = hint(s);
        return (
          <div key={s} className="flex gap-3">
            <div className="flex flex-col items-center">
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.15 * i, type: "spring", stiffness: 400, damping: 18 }}
                className={cx("mt-0.5 size-4 shrink-0 rounded-full ring-2", done ? "bg-azure-600 ring-azure-600" : current ? "bg-white ring-marigold-500" : "bg-white ring-line")}
              />
              {i < STEPS.length - 1 && <span className={cx("my-0.5 w-0.5 flex-1", i < at ? "bg-azure-600" : "bg-line")} />}
            </div>
            <div className="pb-3">
              <p className={cx("text-[13px] leading-snug", done ? "font-semibold text-ink" : current ? "font-medium text-marigold-600" : "text-ink-3")}>{t(`grievance.step.${s}`)}</p>
              {h && <p className="text-[11px] text-ink-3">{h}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Grievance() {
  const { t, tm } = useI18n();
  const { state, view, lc, set, dispatch } = useLifecycle();
  const [text, setText] = useState("");
  const [manual, setManual] = useState<Issue | null>(null);
  const [listening, setListening] = useState(false);
  const [submittedId, setSubmittedId] = useState<string | null>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sector = view.activityId ? catalogEntry(view.activityId).sector : null;

  useEffect(() => () => stopRef.current?.(), []);

  const detected = classifyIssue(text);
  const issue = manual ?? detected;
  const submitted = state.grievances.find((g) => g.id === submittedId) ?? null;
  const past = [...state.grievances].filter((g) => g.id !== submittedId).reverse();

  const onVoiceError = (err: ListenError) => {
    setListening(false);
    stopRef.current = null;
    if (err !== "aborted") toast(t(`u4.voice.${err === "no-speech" || err === "permission" || err === "unavailable" ? err : "failed"}`), { tone: "warn" });
    inputRef.current?.focus();
  };

  const toggleVoice = async () => {
    tap();
    if (listening) {
      stopRef.current?.();
      return;
    }
    if (!canListen()) {
      onVoiceError("unavailable");
      return;
    }
    const before = text.trim();
    setListening(true);
    stopRef.current = await listen({
      lang: state.chatLang,
      onPartial: (s) => setText(before ? `${before} ${s}` : s),
      onFinal: (s) => {
        setText(before ? `${before} ${s}` : s);
        setListening(false);
        stopRef.current = null;
      },
      onError: onVoiceError,
    });
  };

  const submit = () => {
    const body = text.trim();
    if (!body) return;
    tap();
    const at = lc.now;
    let ticket = createTicket(body, at, sector);
    if (manual && manual !== ticket.issue) {
      const r = routeTicket(manual, sector);
      ticket = { ...ticket, issue: manual, routedTo: r.routedTo, responseHours: r.responseHours };
    }
    set({ grievances: [...state.grievances, ticket] });
    dispatch({ type: "event", event: { type: "grievance", data: { id: ticket.id, issue: ticket.issue, hours: ticket.responseHours } } });
    setSubmittedId(ticket.id);
  };

  const footer = submitted ? (
    <Button className="w-full" variant="secondary" onClick={() => { setSubmittedId(null); setManual(null); setText(""); }}>
      {t("grievance.another")}
    </Button>
  ) : (
    <Button className="w-full" icon={Send} disabled={!text.trim() || listening} onClick={submit}>
      {t("grievance.submit")}
    </Button>
  );

  return (
    <Screen title={t("grievance.title")} subtitle={t("grievance.subtitle")} footer={footer}>
      <AnimatePresence mode="wait" initial={false}>
        {submitted ? (
          <motion.div key="done" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <Card tone="azure" className="mt-2">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[13px] text-azure-100">{t("grievance.ticket")}</p>
                <span className="tabular rounded-full bg-white/15 px-2.5 py-1 text-xs font-bold">{submitted.id}</span>
              </div>
              <p className="mt-2 text-lg font-bold leading-snug">{t("grievance.logged")}</p>
              <p className="mt-1 text-[13px] leading-snug text-azure-100 [overflow-wrap:anywhere]">“{submitted.text}”</p>
            </Card>
            <Card className="mt-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="info" icon={Sparkles}>{t(manual ? "u4.griev.chosen" : "grievance.classified")}</Badge>
                <span className="text-[15px] font-semibold">{t(`grievance.issue.${submitted.issue}`)}</span>
              </div>
              <div className="mt-3 flex items-start gap-3">
                <IconBubble icon={UserRound} size="sm" />
                <div className="min-w-0">
                  <p className="text-xs text-ink-3">{t("grievance.routedTo")}</p>
                  <p className="text-[15px] font-semibold leading-snug">{tm(submitted.routedTo)}</p>
                  <p className="mt-1 text-[13px] leading-snug text-ink-2">{tm(routeTicket(submitted.issue, sector).action)}</p>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2 rounded-xl bg-marigold-50 px-3 py-2 text-[13px] text-marigold-600">
                <Clock className="size-4 shrink-0" />
                {t("grievance.response", { h: submitted.responseHours })}
              </div>
              <Timeline status={ticketStatus(submitted, lc.now)} ticket={submitted} />
            </Card>
          </motion.div>
        ) : (
          <motion.div key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <Section title={t("grievance.describe")} className="mt-3">
              <Card className="p-3">
                <textarea
                  ref={inputRef}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={4}
                  placeholder={t("grievance.placeholder")}
                  className="w-full resize-none bg-transparent text-[15px] leading-snug outline-none placeholder:text-ink-3"
                />
                <div className="flex items-center justify-between gap-3 border-t border-line pt-3">
                  <AnimatePresence mode="wait">
                    {listening ? (
                      <motion.div key="l" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-2 text-[13px] font-medium text-clay-700">
                        <span className="flex h-5 items-end gap-0.5">
                          {[0, 1, 2, 3, 4].map((b) => (
                            <motion.span key={b} className="w-1 rounded-full bg-clay-600" animate={{ height: [4, 18, 6, 14, 4] }} transition={{ duration: 0.9, repeat: Infinity, delay: b * 0.1 }} />
                          ))}
                        </span>
                        {t("grievance.listening")}
                      </motion.div>
                    ) : (
                      <motion.p key="h" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-[13px] text-ink-3">
                        {t("grievance.voiceHint")}
                      </motion.p>
                    )}
                  </AnimatePresence>
                  <motion.button
                    whileTap={{ scale: 0.9 }}
                    aria-label={t("grievance.speak")}
                    aria-pressed={listening}
                    onClick={toggleVoice}
                    className={cx("relative grid size-13 shrink-0 place-items-center rounded-full text-white", listening ? "bg-clay-600" : "bg-azure-800")}
                  >
                    {listening && <motion.span className="absolute inset-0 rounded-full bg-clay-600" animate={{ scale: [1, 1.6], opacity: [0.5, 0] }} transition={{ duration: 1.1, repeat: Infinity }} />}
                    <Mic className="relative size-6" />
                  </motion.button>
                </div>
              </Card>
            </Section>

            <Section title={t("grievance.category")}>
              <div className="flex flex-wrap gap-2">
                {ISSUES.map((i) => (
                  <Chip key={i} active={issue === i} onClick={() => setManual(manual === i ? null : i)}>
                    {t(`grievance.issue.${i}`)}
                  </Chip>
                ))}
              </div>
              {text.trim() && (
                <p className="mt-2 flex items-start gap-1.5 px-1 text-xs leading-snug text-sky-700">
                  <Sparkles className="mt-px size-3.5 shrink-0" />
                  {manual ? t("u4.griev.manual") : t("u4.griev.detected", { issue: t(`grievance.issue.${detected}`), role: tm(routeTicket(detected, sector).routedTo), h: routeTicket(detected, sector).responseHours })}
                </p>
              )}
            </Section>
          </motion.div>
        )}
      </AnimatePresence>

      {past.length > 0 && (
        <Section title={t("grievance.past")}>
          <div className="grid gap-2">
            {past.map((g, i) => (
              <Reveal key={g.id} i={i}>
                <PastTicket ticket={g} status={ticketStatus(g, lc.now)} />
              </Reveal>
            ))}
          </div>
        </Section>
      )}
    </Screen>
  );
}
