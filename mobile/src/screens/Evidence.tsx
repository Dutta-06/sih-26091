import { LANG_INFO } from "../i18n";
import { ClipboardList, Mic, Plus, Quote, Star, Users } from "lucide-react";
import type { PackFeedback } from "../core/types";
import { useI18n } from "../i18n";
import { useNav } from "../nav";
import { useStore, type Observation } from "../state/store";
import { Badge, Button, Card, ConfidenceBadge, cx, IconBubble, levelTone, Note, Reveal, Screen, Section } from "../ui";
import { activityLabel, caseIntel, placeOf } from "./g2/feasibility";
import { PackNote } from "./g2/ReportSections";
import { evidenceFor, observationUse, parseFeedback, parseSurvey, type PackEvidence } from "./w2/evidence";

function Stars({ n }: { n: number }) {
  return (
    <span className="flex" aria-label={`${n}/5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} className={cx("size-3.5", i <= n ? "fill-marigold-500 text-marigold-500" : "text-ink-3/30")} />
      ))}
    </span>
  );
}

export default function Evidence() {
  const { t, pick } = useI18n();
  const { state, view } = useStore();
  const { push } = useNav();
  const place = placeOf(view);
  const intel = caseIntel(view, state.profile);
  const activityId = view.activityId ?? view.feasibility.attempts.at(-1)?.activityId ?? state.profile.activityId;
  const ev = evidenceFor(place?.district.id ?? null, activityId, intel, state.observations);
  const groups: { kind: PackFeedback["kind"]; items: PackEvidence[] }[] = [
    { kind: "funded_entrepreneur", items: ev.pack.filter((e) => e.record.kind === "funded_entrepreneur") },
    { kind: "resident_survey", items: ev.pack.filter((e) => e.record.kind === "resident_survey") },
  ];

  return (
    <Screen
      title={t("evidence.title")}
      subtitle={place ? t("evidence.subtitle", { place: pick(place.district.name), activity: activityId ? pick(activityLabel(activityId).name) : t("g2.evidence.allWork") }) : undefined}
      footer={
        <Button className="w-full" icon={Plus} onClick={() => push({ name: "survey" })}>
          {t("evidence.cta")}
        </Button>
      }
    >
      <div className="mt-2">
        <Note tone="azure">{t("evidence.intro", { n: ev.pack.length, used: ev.usedCount })}</Note>
      </div>
      {!place && (
        <div className="mt-2">
          <Note tone="marigold">{t("g2.evidence.noPlace")}</Note>
        </div>
      )}

      {place && ev.pack.length === 0 && (
        <Card tone="sand" className="mt-4">
          <p className="text-[13px] leading-snug text-ink-2">{t("g2.evidence.nonePack", { place: pick(place.district.name) })}</p>
        </Card>
      )}

      {groups.map(
        (g) =>
          g.items.length > 0 && (
            <Section key={g.kind} title={t(g.kind === "funded_entrepreneur" ? "evidence.funded" : "evidence.survey")} action={<ConfidenceBadge value="real" />}>
              <div className="space-y-2.5">
                {g.items.map((e, i) => (
                  <Reveal key={e.record.id} i={i}>
                    <PackCard e={e} />
                  </Reveal>
                ))}
              </div>
            </Section>
          ),
      )}

      <Section title={t("evidence.mine")}>
        {ev.mine.length === 0 ? (
          <Card tone="sand">
            <div className="flex items-center gap-3">
              <IconBubble icon={ClipboardList} tone="sand" size="sm" />
              <p className="text-[13px] leading-snug text-ink-2">{t("evidence.mineEmpty")}</p>
            </div>
          </Card>
        ) : (
          <div className="space-y-2.5">
            {ev.mine.map((o, i) => (
              <Reveal key={o.id} i={i}>
                <MyObservation o={o} />
              </Reveal>
            ))}
          </div>
        )}
      </Section>
      <PackNote />
    </Screen>
  );
}

function PackCard({ e }: { e: PackEvidence }) {
  const { t, pick } = useI18n();
  const r = e.record;
  return (
    <Card>
      <div className="flex items-center gap-3">
        <IconBubble icon={r.kind === "funded_entrepreneur" ? Quote : Users} tone="azure" size="sm" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-semibold">{pick(r.who)}</p>
          <p className="text-xs text-ink-3">
            {t(`evidence.topic.${r.topic}`)}
            {r.monthsInBusiness !== undefined && ` · ${t("unit.months", { n: r.monthsInBusiness })}`}
            {r.activityId && ` · ${pick(activityLabel(r.activityId).name)}`}
          </p>
        </div>
        {r.rating !== null && <Stars n={r.rating} />}
      </div>
      <p className="mt-2.5 text-[14px] leading-snug text-ink-2">“{pick(r.text)}”</p>
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-line pt-2.5">
        <span className="text-xs text-ink-3">{t("evidence.usedAs")}</span>
        {e.uses.length === 0 && <span className="text-xs text-ink-3">{t("g2.evidence.notUsed")}</span>}
        {e.uses.map((u, i) =>
          u.kind === "niche" ? (
            <Badge key={i} tone="good">
              {t("g2.evidence.use.niche", { label: u.label })}
            </Badge>
          ) : u.kind === "risk" ? (
            <Badge key={i} tone={levelTone(u.severity)}>
              {t("g2.evidence.use.risk", { level: t(`level.${u.severity}`) })}
            </Badge>
          ) : (
            <Badge key={i} tone={u.saturation === "high" ? "warn" : "info"}>
              {t(`g2.evidence.use.signal.${u.saturation}`)}
            </Badge>
          ),
        )}
      </div>
    </Card>
  );
}

function MyObservation({ o }: { o: Observation }) {
  const { t, lang } = useI18n();
  const use = observationUse(o);
  const date = new Date(o.at).toLocaleDateString(LANG_INFO[lang].dateLocale, { day: "numeric", month: "short" });
  let body: string = o.text;
  let voice = false;
  let rating = 0;
  if (o.kind === "resident_survey") {
    const s = parseSurvey(o);
    if (s) {
      voice = s.voice;
      body = Object.entries(s.answers)
        .filter(([, v]) => v.length)
        .map(([q, v]) => `${t(`survey.q.${q}.short`)}: ${v.map((x) => t(`survey.o.${q}.${x}`)).join(", ")}`)
        .concat(s.note ? [s.note] : [])
        .join(" · ");
    }
  } else {
    const f = parseFeedback(o);
    if (f) {
      voice = f.voice;
      rating = f.rating;
      body = [f.preset ? t(`survey.preset.${f.preset}`) : "", f.note].filter(Boolean).join(" — ");
    }
  }
  return (
    <Card>
      <div className="flex items-center gap-2">
        <IconBubble icon={o.kind === "resident_survey" ? Users : Quote} tone="marigold" size="sm" />
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-semibold">{t(`evidence.kind.${o.kind}`)}</p>
          <p className="text-xs text-ink-3">
            {date}
            {o.kind === "funded_entrepreneur" && ` · ${t(`evidence.topic.${o.topic}`)}`}
          </p>
        </div>
        {rating > 0 && <Stars n={rating} />}
      </div>
      <p className="mt-2 text-[13px] leading-snug break-words text-ink-2">{body}</p>
      {voice && (
        <p className="mt-1.5 flex items-center gap-1 text-xs text-ink-3">
          <Mic className="size-3.5" />
          {t("survey.voiceSaved")}
        </p>
      )}
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-line pt-2.5">
        <Badge tone="warn">{t("evidence.surveyLabel")}</Badge>
        <span className="text-xs text-ink-3">{t(`evidence.pendingUse.${use}`)}</span>
      </div>
    </Card>
  );
}
