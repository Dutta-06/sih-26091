import { ArrowRight, BookOpen, Check, CircleCheck, FileText, Frown, Languages, MapPin, Activity as Pulse, ScrollText, ShieldAlert, Users, Wallet, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { ACTIVITIES } from "../../data/activities";
import { CATEGORIES, PREMISES, SKILLS } from "../../data/w1";
import { resolveLocation } from "../../core/geo";
import { affordableProjectCost } from "../../core/intel/catalog";
import type { ProfileInput } from "../../core/types";
import { useI18n } from "../../i18n";
import { tap } from "../../lib/haptics";
import { rupees } from "../../lib/format";
import { useStore, type ChatLang } from "../../state/store";
import { Button, Chip, ConfidenceBadge, cx, IconBubble, Sheet } from "../../ui";
import { ASSET_OPTIONS, type JumpIntent } from "../g1/conversation";
import { CHAT_LANG_LABEL, CHAT_LANGS, useChatI18n } from "./chatI18n";

/** Location disambiguation (TDD 5.3): every matching village from the pack table, with block, district and LGD code. */
export function LocationChoices({ query, selected, active, onPick }: { query: string; selected: string | null; active: boolean; onPick: (lgd: string, label: string) => void }) {
  const { tc, pickc } = useChatI18n();
  const candidates = resolveLocation(query, null).candidates;
  return (
    <div className="w-[90%] space-y-2">
      {candidates.map((c, i) => {
        const chosen = !!c.lgd && selected === c.lgd;
        const label = [c.village, c.block, c.district.name].flatMap((b) => (b ? [pickc(b)] : [])).join(" · ");
        return (
          <motion.button
            key={`${c.lgd ?? c.district.id}-${i}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.06 * i }}
            whileTap={active ? { scale: 0.98 } : undefined}
            disabled={!active || !c.lgd}
            onClick={() => c.lgd && onPick(c.lgd, label)}
            className={cx(
              "flex min-h-14 w-full items-center gap-3 rounded-2xl p-3 text-left transition-colors",
              chosen ? "bg-azure-800 text-white" : "bg-white shadow-[var(--shadow-card)]",
              !active && !chosen && "opacity-50",
            )}
          >
            <MapPin className={cx("size-5 shrink-0", chosen ? "text-marigold-200" : "text-azure-700")} />
            <span className="min-w-0 flex-1">
              <span className="block text-[15px] leading-snug font-semibold break-words">{c.village ? pickc(c.village) : pickc(c.district.name)}</span>
              <span className={cx("block text-[12px] leading-snug", chosen ? "text-azure-100" : "text-ink-3")}>
                {[c.block ? tc("u1.loc.block", { block: pickc(c.block) }) : null, pickc(c.district.name), c.district.state].filter(Boolean).join(" · ")}
              </span>
            </span>
            {c.lgd && (
              <span className={cx("tabular shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold", chosen ? "bg-white/15" : "bg-azure-50 text-azure-800")}>
                {tc("u1.loc.code", { code: c.lgd })}
              </span>
            )}
            {chosen && <CircleCheck className="size-5 shrink-0" />}
          </motion.button>
        );
      })}
      <div className="flex items-center gap-2 px-1">
        <ConfidenceBadge value="real" compact />
      </div>
    </div>
  );
}

/** Activity suggestions from the discovery ranking; each shows the catalog minimum against what the savings support. */
export function SuggestionCard({ ids, profile, active, onPick }: { ids: string[]; profile: ProfileInput; active: boolean; onPick: (id: string) => void }) {
  const { actName } = useChatI18n();
  const affordable = affordableProjectCost(profile.capital);
  return (
    <div className="w-[90%] space-y-2">
      {ids.map((id, i) => {
        const a = ACTIVITIES[id];
        if (!a) return null;
        const chosen = profile.activityId === id;
        return (
          <motion.button
            key={id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.06 * i }}
            disabled={!active}
            onClick={() => onPick(id)}
            className={cx("flex min-h-13 w-full items-center gap-3 rounded-2xl p-3 text-left", chosen ? "bg-azure-800 text-white" : "bg-white shadow-[var(--shadow-card)]", !active && !chosen && "opacity-60")}
          >
            <span className="text-2xl" aria-hidden>
              {a.emoji}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[15px] leading-snug font-semibold">{actName(id)}</span>
              {profile.capital > 0 && (
                <span className={cx("tabular block text-[12px]", chosen ? "text-azure-100" : "text-ink-3")}>
                  {rupees(a.min_project_cost)} / {rupees(affordable)}
                </span>
              )}
            </span>
            <ArrowRight className="size-4.5 shrink-0 opacity-60" />
          </motion.button>
        );
      })}
    </div>
  );
}

const INTENT_ICONS: Record<JumpIntent, LucideIcon> = {
  grievance: Frown,
  application: FileText,
  scheme: BookOpen,
  monitoring: Pulse,
  community: Users,
  languages: Languages,
  noViable: Frown,
  report: ScrollText,
  review: ShieldAlert,
  plan: Wallet,
};

/** Jump card: the assistant routes an intent to the right screen (TDD 4.1). */
export function JumpCard({ intent, onOpen }: { intent: JumpIntent; onOpen: () => void }) {
  const { tc } = useChatI18n();
  return (
    <motion.button
      whileTap={{ scale: 0.98 }}
      onClick={() => {
        tap();
        onOpen();
      }}
      className="flex w-[80%] items-center gap-3 rounded-[var(--radius-card)] bg-white p-3 text-left shadow-[var(--shadow-card)]"
    >
      <IconBubble icon={INTENT_ICONS[intent] ?? FileText} tone={intent === "grievance" || intent === "noViable" ? "clay" : "azure"} size="sm" />
      <span className="min-w-0 flex-1 text-[15px] font-semibold text-azure-800">{tc(`u1.jump.${intent}`)}</span>
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-azure-800 text-white">
        <ArrowRight className="size-4" />
      </span>
    </motion.button>
  );
}

/** Quick conversation-language switcher from the assistant header. */
export function ChatLangSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const { state, set } = useStore();
  return (
    <Sheet open={open} onClose={onClose} title={t("w1.lang.chatTitle")}>
      <div className="grid gap-2">
        {CHAT_LANGS.map((l) => (
          <button
            key={l}
            onClick={() => {
              tap();
              set({ chatLang: l as ChatLang });
              onClose();
            }}
            className={cx("flex min-h-13 items-center justify-between rounded-2xl px-4 text-left text-[16px] font-semibold", state.chatLang === l ? "bg-azure-800 text-white" : "bg-white ring-1 ring-line")}
          >
            {CHAT_LANG_LABEL[l]}
            {state.chatLang === l && <Check className="size-5" />}
          </button>
        ))}
      </div>
      <p className="mt-3 text-[13px] leading-snug text-ink-3">{t("w1.lang.note")}</p>
      <div className="h-16" />
    </Sheet>
  );
}

export type SlotAnswer = { text: string; patch: Partial<ProfileInput>; answered: string[] };

/** Chip inputs for the multi-choice slots (skills; work place + assets; category + SHG). Typing works too. */
export function SlotInputs({ slot, onSubmit }: { slot: "skills" | "premises" | "category"; onSubmit: (a: SlotAnswer) => void }) {
  const { tc } = useChatI18n();
  const [skills, setSkills] = useState<string[]>([]);
  const [assets, setAssets] = useState<string[]>([]);
  const [first, setFirst] = useState<string | null>(null);

  if (slot === "skills") {
    return (
      <div className="flex flex-wrap gap-2">
        {SKILLS.map((s) => (
          <Chip key={s} active={skills.includes(s)} onClick={() => setSkills((xs) => (xs.includes(s) ? xs.filter((x) => x !== s) : [...xs, s]))}>
            {tc(`w1.skill.${s}`)}
          </Chip>
        ))}
        <Chip onClick={() => onSubmit({ text: tc("u1.ans.none"), patch: { skills: [] }, answered: ["skills"] })}>{tc("u1.chip.none")}</Chip>
        <Button size="md" icon={Check} disabled={!skills.length} onClick={() => onSubmit({ text: tc("u1.ans.skills", { list: skills.map((k) => `@w1.skill.${k}`).join("|") }), patch: { skills }, answered: ["skills"] })}>
          {tc("u1.chip.done")}
        </Button>
      </div>
    );
  }

  if (slot === "premises") {
    const submit = (premises: string) => {
      const owned = assets.filter((x) => x !== "none");
      onSubmit({
        text: tc("u1.ans.premises", { premises: `@w1.premises.${premises}`, assets: owned.length ? owned.map((x) => `@u1.asset.${x}`).join("|") : "@u1.asset.none" }),
        patch: { premises: premises as ProfileInput["premises"], assets: owned },
        answered: ["premises"],
      });
    };
    return (
      <div className="space-y-2">
        <Row label={tc("u1.asset.label")}>
          {ASSET_OPTIONS.map((k) => (
            <Chip key={k} active={assets.includes(k)} onClick={() => setAssets((xs) => (k === "none" ? ["none"] : xs.includes(k) ? xs.filter((x) => x !== k) : [...xs.filter((x) => x !== "none"), k]))}>
              <span className="whitespace-nowrap">{tc(`u1.asset.${k}`)}</span>
            </Chip>
          ))}
        </Row>
        <Row label={tc("u1.premises.label")}>
          {PREMISES.map((k) => (
            <Chip key={k} onClick={() => submit(k)}>
              <span className="whitespace-nowrap">{tc(`w1.premises.${k}`)}</span>
            </Chip>
          ))}
        </Row>
        <p className="px-1 text-[11px] text-ink-3">{tc("u1.chip.pickHint")}</p>
      </div>
    );
  }

  const pickShg = (shg: boolean) => {
    const category = first && first !== "none" ? (first as ProfileInput["category"]) : null;
    onSubmit({
      text: tc("u1.ans.category", { cat: category ? `@w1.cat.${category}` : "@u1.cat.none", shg: shg ? "@w1.shg.yes" : "@w1.shg.no" }),
      patch: { category, shgMember: shg },
      answered: ["category"],
    });
  };
  return (
    <div className="space-y-2">
      <Row label={tc("u1.cat.label")}>
        {[...CATEGORIES, "none"].map((k) => (
          <Chip key={k} active={first === k} onClick={() => setFirst(k)}>
            <span className="whitespace-nowrap">{tc(k === "none" ? "u1.cat.none" : `w1.cat.${k}`)}</span>
          </Chip>
        ))}
      </Row>
      <div className={cx("transition-opacity", !first && "pointer-events-none opacity-45")}>
        <Row label={tc("u1.shg.label")}>
          <Chip onClick={() => pickShg(true)}>{tc("w1.shg.yes")}</Chip>
          <Chip onClick={() => pickShg(false)}>{tc("w1.shg.no")}</Chip>
        </Row>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1 px-1 text-xs font-medium text-ink-3">{label}</p>
      <div className="scroll-area -mx-4 flex gap-2 overflow-x-auto px-4">{children}</div>
    </div>
  );
}
