import { ArrowLeftRight, Ban, Building2, CalendarDays, CheckCircle2, Download, Gauge, IndianRupee, KeyRound, Landmark, MessageSquareText, Radio, ShieldCheck, ShieldOff, Store, Trash2, XCircle, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { tap } from "../App";
import type { Transaction } from "../core/types";
import { useI18n } from "../i18n";
import { Badge, Button, Card, IconBubble, ListRow, Note, Reveal, Screen, Section, Sheet, Toggle } from "../ui";
import { consentLog, dateLabel, useLifecycle } from "./g4/model";
import { ExportSheet } from "./w4/ExportSheet";

/** Every field a parsed transaction keeps; `satisfies` makes this list fail to compile if the Transaction type changes. */
const STORED_FIELDS = {
  at: CalendarDays,
  amount: IndianRupee,
  direction: ArrowLeftRight,
  channel: Radio,
  isLoanRepayment: Landmark,
} satisfies Record<keyof Transaction, LucideIcon>;

/** Consent & privacy centre (TDD 7.3, 10): grant/withdraw, what is stored, history, export and deletion. */
export default function Privacy() {
  const { t, lang } = useI18n();
  const { state, view, lc, set, dispatch } = useLifecycle();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const on = state.smsConsent;
  const log = consentLog(state);
  const txCount = view.transactions.length;
  const monthsCount = view.health.length;

  const toggle = (v: boolean) => {
    tap();
    set({ smsConsent: v });
    dispatch({ type: "event", event: { type: "consent", data: { granted: v } } });
  };

  const erase = () => {
    tap();
    set({ dataDeletedOn: lc.today, smsConsent: false });
    if (on) dispatch({ type: "event", event: { type: "consent", data: { granted: false } } });
    dispatch({ type: "event", event: { type: "data_deleted", data: { transactions: txCount, months: monthsCount } } });
    setConfirmDelete(false);
  };

  const never: { icon: LucideIcon; key: string }[] = [
    { icon: KeyRound, key: "logins" },
    { icon: Building2, key: "bureau" },
    { icon: Store, key: "selling" },
    { icon: MessageSquareText, key: "text" },
  ];
  const deletedEvent = [...state.events].reverse().find((e) => e.type === "data_deleted");

  return (
    <Screen title={t("w4.privacy.title")} subtitle={t("w4.privacy.subtitle")}>
      <Reveal>
        <Card className="mt-2">
          <div className="flex items-start gap-3">
            <IconBubble icon={on ? ShieldCheck : ShieldOff} tone={on ? "azure" : "sand"} />
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-semibold">{t("w4.privacy.sms")}</p>
              <div className="mt-1">
                <Badge tone={on ? "good" : "neutral"}>{t(on ? "w4.privacy.on" : "w4.privacy.off")}</Badge>
              </div>
            </div>
            <Toggle checked={on} onChange={toggle} label={t("w4.privacy.sms")} />
          </div>
          <p className="mt-3 text-[13px] leading-snug text-ink-2">{t(on ? "w4.privacy.onBody" : "w4.privacy.offBody")}</p>
          {on && <p className="mt-2 text-[13px] leading-snug text-ink-3">{t("u4.privacy.nowStored", { n: txCount, months: monthsCount })}</p>}
          <div className="mt-3">
            <Note tone="marigold">{t("w4.privacy.coverage")}</Note>
          </div>
        </Card>
      </Reveal>

      <Section title={t("w4.privacy.stored")}>
        <Reveal i={1}>
          <Card className="divide-y divide-line py-1">
            {(Object.entries(STORED_FIELDS) as [keyof Transaction, LucideIcon][]).map(([field, icon]) => (
              <ListRow key={field} icon={icon} tone="azure" title={t(`u4.field.${field}`)} subtitle={t(`u4.field.${field}.sub`)} right={<code className="text-[11px] text-ink-3">{field}</code>} />
            ))}
          </Card>
          <p className="mt-2 px-1 text-[13px] leading-snug text-ink-3">{t("u4.privacy.storedNote", { n: Object.keys(STORED_FIELDS).length })}</p>
        </Reveal>
      </Section>

      <Section title={t("w4.privacy.never")}>
        <Reveal i={2}>
          <Card tone="clay" className="grid gap-2.5">
            {never.map((n) => (
              <div key={n.key} className="flex items-center gap-2.5 text-[15px] font-medium text-clay-700">
                <Ban className="size-4.5 shrink-0" />
                <n.icon className="size-4.5 shrink-0 opacity-70" />
                <span className="leading-snug">{t(`w4.privacy.never.${n.key}`)}</span>
              </div>
            ))}
          </Card>
        </Reveal>
      </Section>

      <Section title={t("monitoring.credit")}>
        <Reveal i={3}>
          <Card>
            <div className="flex items-start gap-3">
              <IconBubble icon={Gauge} tone="sky" size="sm" />
              <div className="min-w-0">
                <p className="text-xs font-semibold text-marigold-600">{t("monitoring.credit.label")}</p>
                <p className="mt-1 text-[13px] leading-snug text-ink-2">{t("w4.privacy.credit")}</p>
              </div>
            </div>
          </Card>
        </Reveal>
      </Section>

      <Section title={t("w4.privacy.history")}>
        <Card className="divide-y divide-line py-1">
          {log.length === 0 ? (
            <p className="py-3 text-[13px] text-ink-3">{t("w4.privacy.history.empty")}</p>
          ) : (
            [...log].reverse().map((c, i) => (
              <ListRow
                key={`${c.at}-${i}`}
                icon={c.granted ? CheckCircle2 : XCircle}
                tone={c.granted ? "azure" : "clay"}
                title={t(c.granted ? "w4.privacy.history.granted" : "w4.privacy.history.withdrawn")}
                subtitle={dateLabel(c.at, lang, true)}
              />
            ))
          )}
        </Card>
      </Section>

      <Section title={t("w4.privacy.yourData")}>
        <div className="grid gap-2">
          <Button variant="secondary" icon={Download} onClick={() => setExportOpen(true)}>
            {t("w4.privacy.download")}
          </Button>
          <Button variant="secondary" icon={Trash2} className="text-clay-700" disabled={!txCount && !on} onClick={() => setConfirmDelete(true)}>
            {t("w4.privacy.delete")}
          </Button>
        </div>
        {state.dataDeletedOn && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="mt-3">
              <p className="text-[15px] font-semibold">{t("u4.privacy.deletedOn", { date: dateLabel(state.dataDeletedOn, lang) })}</p>
              <div className="mt-2 grid gap-2 text-[13px]">
                <p className="flex items-center gap-2 text-clay-700">
                  <XCircle className="size-4 shrink-0" />
                  <span className="line-through decoration-clay-600/60">{t("u4.privacy.deleted.health", { n: Number(deletedEvent?.data?.months ?? 0) })}</span>
                  <Badge tone="risk">{t("w4.privacy.deleted.removed")}</Badge>
                </p>
                <p className="flex items-center gap-2 text-clay-700">
                  <XCircle className="size-4 shrink-0" />
                  <span className="line-through decoration-clay-600/60">{t("u4.privacy.deleted.tx", { n: Number(deletedEvent?.data?.transactions ?? 0) })}</span>
                  <Badge tone="risk">{t("w4.privacy.deleted.removed")}</Badge>
                </p>
                <p className="flex items-center gap-2 text-azure-800">
                  <CheckCircle2 className="size-4 shrink-0" />
                  <span>{t("w4.privacy.deleted.loan")}</span>
                  <Badge tone="good">{t("w4.privacy.deleted.kept")}</Badge>
                </p>
              </div>
              <p className="mt-2 text-xs leading-snug text-ink-3">{t(on ? "u4.privacy.deleted.resumed" : "w4.privacy.deleted.why")}</p>
            </Card>
          </motion.div>
        )}
      </Section>

      <Sheet open={confirmDelete} onClose={() => setConfirmDelete(false)} title={t("w4.privacy.confirm.title")}>
        <p className="text-[15px] leading-snug text-ink-2">{t("u4.privacy.confirm.body", { n: txCount, months: monthsCount })}</p>
        <div className="mt-3">
          <Note tone="azure">{t("w4.privacy.confirm.loan")}</Note>
        </div>
        <div className="mt-4 grid gap-2">
          <Button variant="danger" icon={Trash2} onClick={erase}>
            {t("w4.privacy.confirm.yes")}
          </Button>
          <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
            {t("w4.privacy.confirm.no")}
          </Button>
        </div>
      </Sheet>
      <ExportSheet open={exportOpen} onClose={() => setExportOpen(false)} />
    </Screen>
  );
}
