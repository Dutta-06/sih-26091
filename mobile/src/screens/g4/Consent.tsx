import { ChevronRight, EyeOff, MessageSquareText, ShieldCheck, ToggleLeft } from "lucide-react";
import { useState } from "react";
import { tap } from "../../App";
import { useI18n } from "../../i18n";
import { useNav } from "../../nav";
import { useStore } from "../../state/store";
import { Button, Card, IconBubble, ListRow, Sheet, Toggle } from "../../ui";

/** "Turn on cash-flow tracking" card with an explicit consent sheet (TDD 7.3). */
export function ConsentCard({ tabRoot }: { tabRoot?: boolean }) {
  const { t } = useI18n();
  const { state, set, dispatch } = useStore();
  const { push } = useNav();
  const [open, setOpen] = useState(false);
  const on = state.smsConsent;
  const record = (granted: boolean) => {
    set({ smsConsent: granted });
    dispatch({ type: "event", event: { type: "consent", data: { granted } } });
  };

  const allow = () => {
    tap();
    record(true);
    setOpen(false);
  };

  return (
    <>
      <Card>
        <div className="flex items-start gap-3">
          <IconBubble icon={MessageSquareText} tone="sky" />
          <div className="min-w-0 flex-1">
            <p className="text-[15px] font-semibold">{t("business.consent.title")}</p>
            <p className="mt-1 text-[13px] leading-snug text-ink-3">{t("business.consent.body")}</p>
          </div>
          <Toggle
            checked={on}
            label={t("business.consent.title")}
            onChange={(v) => {
              if (v) setOpen(true);
              else record(false);
            }}
          />
        </div>
        <button onClick={() => push({ name: "privacy" })} className="mt-2 ml-14 inline-flex min-h-9 items-center gap-0.5 text-[13px] font-semibold text-azure-700">
          {t("w4.privacy.link")}
          <ChevronRight className="size-4" />
        </button>
      </Card>
      <Sheet open={open} onClose={() => setOpen(false)} title={t("business.consent.sheetTitle")}>
        <div className="divide-y divide-line rounded-2xl bg-white px-3">
          <ListRow icon={ShieldCheck} title={t("business.consent.p1")} subtitle={t("business.consent.p1s")} />
          <ListRow icon={EyeOff} title={t("business.consent.p2")} subtitle={t("business.consent.p2s")} />
          <ListRow icon={ToggleLeft} title={t("business.consent.p3")} subtitle={t("business.consent.p3s")} />
        </div>
        <div className="mt-4 grid gap-2">
          <Button onClick={allow} icon={ShieldCheck}>
            {t("business.consent.allow")}
          </Button>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            {t("business.consent.notNow")}
          </Button>
        </div>
        {tabRoot && <div className="h-20" />}
      </Sheet>
    </>
  );
}
