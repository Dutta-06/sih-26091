import { Check, Info, Mic, MicOff, Volume2, VolumeX } from "lucide-react";
import { useEffect, useState } from "react";
import { tap } from "../lib/haptics";
import { useI18n, type Lang } from "../i18n";
import { speak, voiceCapabilities, type VoiceCapabilities } from "../lib/speech";
import { useStore, type ChatLang } from "../state/store";
import { Button, Card, cx, ListRow, Note, Reveal, Section, Screen, Toggle } from "../ui";
import { CHAT_LANG_LABEL, CHAT_LANGS, translateChat, useSetAppLang } from "./w1/chatI18n";

/** Languages & voice (TDD 4.3): app language, conversation language and read-aloud. */
export default function Languages() {
  const { t, lang } = useI18n();
  const { state, set } = useStore();
  const setAppLang = useSetAppLang();
  const [preview, setPreview] = useState(false);
  const [caps, setCaps] = useState<VoiceCapabilities | null>(null);

  // What this phone's own speech services can do (probed once, cached by lib/speech)
  useEffect(() => {
    let alive = true;
    void voiceCapabilities().then((c) => alive && setCaps(c));
    return () => {
      alive = false;
    };
  }, []);

  const testVoice = () => {
    tap();
    const started = speak(translateChat(state.chatLang, lang, "u1.greet"), state.chatLang);
    if (!started) {
      setPreview(true);
      setTimeout(() => setPreview(false), 2200);
    }
  };

  return (
    <Screen title={t("w1.lang.title")} subtitle={t("w1.lang.subtitle")}>
      <Section title={t("w1.lang.app")}>
        <Reveal i={0}>
          <div className="grid grid-cols-2 gap-3">
            {(["en", "hi"] as Lang[]).map((l) => (
              <button
                key={l}
                onClick={() => {
                  tap();
                  setAppLang(l);
                }}
                className={cx(
                  "relative flex min-h-20 flex-col items-start justify-end rounded-[var(--radius-card)] p-4 text-left",
                  lang === l ? "bg-forest-800 text-white shadow-[var(--shadow-float)]" : "bg-white shadow-[var(--shadow-card)]",
                )}
              >
                {lang === l && <Check className="absolute top-3 right-3 size-5" />}
                <span className="text-xl font-bold">{CHAT_LANG_LABEL[l]}</span>
                <span className={cx("text-xs", lang === l ? "text-forest-100" : "text-ink-3")}>{t("w1.lang.fullUi")}</span>
              </button>
            ))}
          </div>
        </Reveal>
      </Section>

      <Section title={t("w1.lang.chat")}>
        <Reveal i={1}>
          <Card className="divide-y divide-line py-1">
            {CHAT_LANGS.map((l) => (
              <ListRow
                key={l}
                title={<span lang={l} className="text-[16px] font-semibold">{CHAT_LANG_LABEL[l]}</span>}
                subtitle={
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <span>{t(l === "en" || l === "hi" ? "w1.lang.coverFull" : "w1.lang.coverChat")}</span>
                    {caps === null ? (
                      <span className="text-ink-3">{t("u1.lang.checking")}</span>
                    ) : caps.languages.includes(l) ? (
                      <span className="inline-flex items-center gap-1 font-medium text-forest-700">
                        <Volume2 className="size-3.5" />
                        {t("u1.lang.speaks")}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 font-medium text-clay-700">
                        <VolumeX className="size-3.5" />
                        {t("u1.lang.noVoice")}
                      </span>
                    )}
                  </span>
                }
                onClick={() => {
                  tap();
                  set({ chatLang: l as ChatLang });
                }}
                right={
                  <span className={cx("grid size-7 place-items-center rounded-full", state.chatLang === l ? "bg-forest-800 text-white" : "ring-2 ring-line")}>
                    {state.chatLang === l && <Check className="size-4" />}
                  </span>
                }
              />
            ))}
          </Card>
        </Reveal>
        <div className="mt-3">
          <Note icon={Info}>{t("w1.lang.note")}</Note>
        </div>
      </Section>

      <Section title={t("w1.lang.voice")}>
        <Reveal i={2}>
          <Card>
            <ListRow
              icon={Volume2}
              title={t("w1.lang.readAloud")}
              subtitle={t("w1.lang.readAloudSub")}
              right={<Toggle checked={state.readAloud} label={t("w1.lang.readAloud")} onChange={(v) => set({ readAloud: v })} />}
            />
            <Button variant="secondary" size="md" icon={Volume2} className="mt-2 w-full" onClick={testVoice}>
              {preview ? t("w1.lang.previewing") : t("w1.lang.test", { lang: CHAT_LANG_LABEL[state.chatLang] })}
            </Button>
            {caps && !caps.tts && <p className="mt-2 text-center text-[12px] text-clay-700">{t("u1.lang.ttsNone")}</p>}
            <div className="mt-2 border-t border-line pt-1">
              <ListRow
                icon={caps?.stt === false ? MicOff : Mic}
                tone={caps?.stt === false ? "clay" : "forest"}
                title={t("u1.lang.listen")}
                subtitle={caps === null ? t("u1.lang.checking") : t(caps.stt ? "u1.lang.listenYes" : "u1.lang.listenNo")}
              />
            </div>
            <p className="mt-1 text-center text-[11px] text-ink-3">{t("u1.lang.onDevice")}</p>
          </Card>
        </Reveal>
      </Section>
    </Screen>
  );
}
