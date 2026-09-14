/**
 * Voice I/O on the device's own OS services (TDD 4.3) — our code makes no network/API calls.
 *  - Text-to-speech: Android TextToSpeech engine via @capacitor-community/text-to-speech on native,
 *    `window.speechSynthesis` in the browser.
 *  - Speech-to-text: Android SpeechRecognizer via @capacitor-community/speech-recognition on native
 *    (no popup, partial results), `SpeechRecognition`/`webkitSpeechRecognition` in the browser (on-device when offered).
 * Everything degrades gracefully: callers get `false` / an `onError` code and can show a preview instead.
 */
import { Capacitor, type PluginListenerHandle } from "@capacitor/core";
import { SpeechRecognition } from "@capacitor-community/speech-recognition";
import { TextToSpeech } from "@capacitor-community/text-to-speech";
import { pickLanguageTag } from "./speechLang";

export type SpeechLang = "en" | "hi" | "bn" | "mr" | "ta";
export { pickLanguageTag };

export const SPEECH_TAGS: Record<SpeechLang, string> = { en: "en-IN", hi: "hi-IN", bn: "bn-IN", mr: "mr-IN", ta: "ta-IN" };
const ALL_LANGS = Object.keys(SPEECH_TAGS) as SpeechLang[];

const native = () => Capacitor.isNativePlatform();
const webSynth = () => typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";

/* ---------------- capabilities ---------------- */

export interface VoiceCapabilities {
  tts: boolean;
  stt: boolean;
  /** app languages the TTS engine can speak */
  languages: SpeechLang[];
}

/** Language tags reported by the native TTS engine (null until probed). */
let nativeTtsTags: string[] | null = null;
let capsPromise: Promise<VoiceCapabilities> | null = null;

async function webVoices(): Promise<SpeechSynthesisVoice[]> {
  if (!webSynth()) return [];
  const now = window.speechSynthesis.getVoices();
  if (now.length) return now;
  return new Promise((resolve) => {
    const done = () => resolve(window.speechSynthesis.getVoices());
    window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    setTimeout(done, 1200);
  });
}

type WebRecognitionCtor = new () => WebRecognition;
interface WebRecognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  processLocally?: boolean;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
const webRecognitionCtor = (): (WebRecognitionCtor & { available?: (o: { langs: string[]; processLocally: boolean }) => Promise<string> }) | null => {
  if (typeof window === "undefined") return null;
  const w = window as unknown as Record<string, unknown>;
  return ((w.SpeechRecognition ?? w.webkitSpeechRecognition) as never) ?? null;
};

/** Probe what this device can do (cached). Safe to call early to warm up language data. */
export function voiceCapabilities(): Promise<VoiceCapabilities> {
  capsPromise ??= (async (): Promise<VoiceCapabilities> => {
    if (native()) {
      let tts = false;
      try {
        const { languages } = await TextToSpeech.getSupportedLanguages();
        nativeTtsTags = languages ?? [];
        tts = true;
      } catch {
        nativeTtsTags = [];
      }
      let stt = false;
      try {
        stt = (await SpeechRecognition.available()).available;
      } catch {
        stt = false;
      }
      const languages = ALL_LANGS.filter((l) => pickLanguageTag(l, nativeTtsTags ?? []) !== null);
      return { tts: tts && languages.length > 0, stt, languages };
    }
    const voices = await webVoices();
    const tags = voices.map((v) => v.lang);
    const languages = ALL_LANGS.filter((l) => pickLanguageTag(l, tags) !== null);
    return { tts: webSynth() && voices.length > 0, stt: webRecognitionCtor() !== null, languages };
  })();
  return capsPromise;
}

/** Synchronous best guess used by screens to label the voice button. */
export const canSpeak = (): boolean => (native() ? nativeTtsTags === null || nativeTtsTags.length > 0 : webSynth());

/* ---------------- text-to-speech ---------------- */

let speakToken = 0;

/**
 * Speak `text` in the given language. Returns true if speech was started (or is being started on native);
 * `onEnd` fires once when it finishes, is stopped, or fails. Returns false when this language cannot be spoken.
 */
export function speak(text: string, langCode: SpeechLang, onEnd?: () => void): boolean {
  if (!text.trim()) return false;
  const my = ++speakToken;
  let ended = false;
  const end = () => {
    if (ended) return;
    ended = true;
    onEnd?.();
  };

  if (native()) {
    if (nativeTtsTags === null) void voiceCapabilities(); // warm the language list for next time
    if (nativeTtsTags !== null && pickLanguageTag(langCode, nativeTtsTags) === null) return false;
    const tag = nativeTtsTags ? (pickLanguageTag(langCode, nativeTtsTags) ?? SPEECH_TAGS[langCode]) : SPEECH_TAGS[langCode];
    (async () => {
      try {
        if (nativeTtsTags === null) {
          const { supported } = await TextToSpeech.isLanguageSupported({ lang: tag }).catch(() => ({ supported: true }));
          if (!supported) throw new Error("unsupported");
        }
        if (my !== speakToken) return end();
        await TextToSpeech.speak({ text, lang: tag, rate: 0.95, pitch: 1, volume: 1, category: "playback", queueStrategy: 0 });
      } catch {
        /* engine missing, language data not installed, or interrupted */
      }
      end();
    })();
    return true;
  }

  if (!webSynth()) return false;
  try {
    const synth = window.speechSynthesis;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const voices = synth.getVoices();
    const tag = pickLanguageTag(langCode, voices.map((v) => v.lang)) ?? SPEECH_TAGS[langCode];
    u.lang = tag;
    const voice = voices.find((v) => v.lang === tag && v.localService) ?? voices.find((v) => v.lang === tag);
    if (voice) u.voice = voice;
    u.rate = 0.95;
    u.onend = end;
    u.onerror = end;
    synth.speak(u);
    return true;
  } catch {
    return false;
  }
}

/** Promise form of `speak`: resolves true when speech finished normally-ish, false if it could not start. */
export function speakAsync(text: string, langCode: SpeechLang): Promise<boolean> {
  return new Promise((resolve) => {
    const started = speak(text, langCode, () => resolve(true));
    if (!started) resolve(false);
  });
}

export function stopSpeaking() {
  speakToken++;
  if (native()) {
    TextToSpeech.stop().catch(() => undefined);
    return;
  }
  if (webSynth()) window.speechSynthesis.cancel();
}

/* ---------------- speech-to-text ---------------- */

export type ListenError = "unavailable" | "permission" | "no-speech" | "network" | "busy" | "aborted" | "unknown";

export interface ListenOptions {
  lang: SpeechLang;
  /** live transcript while the user is speaking */
  onPartial?: (text: string) => void;
  /** final transcript (called at most once; not called when nothing was heard) */
  onFinal?: (text: string) => void;
  onError?: (error: ListenError) => void;
  /** give up when nothing is heard for this long (ms, default 8000) */
  silenceMs?: number;
}

export const canListen = (): boolean => native() || webRecognitionCtor() !== null;

/** Start listening. Resolves to a `stop()` function that ends listening and delivers the final transcript. */
export async function listen(opts: ListenOptions): Promise<() => void> {
  return native() ? listenNative(opts) : listenWeb(opts);
}

async function listenNative({ lang, onPartial, onFinal, onError, silenceMs = 8000 }: ListenOptions): Promise<() => void> {
  const noop = () => undefined;
  try {
    if (!(await SpeechRecognition.available()).available) {
      onError?.("unavailable");
      return noop;
    }
    let perm = (await SpeechRecognition.checkPermissions()).speechRecognition;
    if (perm !== "granted") perm = (await SpeechRecognition.requestPermissions()).speechRecognition;
    if (perm !== "granted") {
      onError?.("permission");
      return noop;
    }
  } catch {
    onError?.("unavailable");
    return noop;
  }

  let last = "";
  let finished = false;
  let finalizeTimer: ReturnType<typeof setTimeout> | undefined;
  const handles: PluginListenerHandle[] = [];
  const cleanup = () => {
    clearTimeout(finalizeTimer);
    clearTimeout(silenceTimer);
    handles.forEach((h) => h.remove().catch(() => undefined));
  };
  const finish = (err?: ListenError) => {
    if (finished) return;
    finished = true;
    cleanup();
    SpeechRecognition.stop().catch(() => undefined);
    if (last.trim()) onFinal?.(last.trim());
    else onError?.(err ?? "no-speech");
  };
  // Results arrive shortly after the "stopped" event (end of speech), so finalize after a short grace period.
  const finalizeSoon = (ms: number) => {
    clearTimeout(finalizeTimer);
    finalizeTimer = setTimeout(() => finish(), ms);
  };
  let stopped = false;
  let silenceTimer = setTimeout(() => finish("no-speech"), silenceMs);

  handles.push(
    await SpeechRecognition.addListener("partialResults", (data) => {
      const text = data.matches?.[0] ?? "";
      if (!text || finished) return;
      last = text;
      onPartial?.(text);
      clearTimeout(silenceTimer);
      silenceTimer = setTimeout(() => finish(), silenceMs);
      if (stopped) finalizeSoon(250);
    }),
    await SpeechRecognition.addListener("listeningState", (data) => {
      if (data.status === "stopped") {
        stopped = true;
        finalizeSoon(900);
      }
    }),
  );

  try {
    await SpeechRecognition.start({ language: SPEECH_TAGS[lang], maxResults: 3, partialResults: true, popup: false });
  } catch (e) {
    const msg = String((e as Error)?.message ?? e).toLowerCase();
    finished = true;
    cleanup();
    onError?.(msg.includes("permission") ? "permission" : msg.includes("busy") ? "busy" : msg.includes("network") ? "network" : "unknown");
    return noop;
  }

  return () => {
    if (finished) return;
    stopped = true;
    SpeechRecognition.stop().catch(() => undefined);
    finalizeSoon(700);
  };
}

async function listenWeb({ lang, onPartial, onFinal, onError, silenceMs = 8000 }: ListenOptions): Promise<() => void> {
  const Ctor = webRecognitionCtor();
  if (!Ctor) {
    onError?.("unavailable");
    return () => undefined;
  }
  const tag = SPEECH_TAGS[lang];
  const rec = new Ctor();
  rec.lang = tag;
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  // Prefer on-device recognition where the browser offers it (Chrome's processLocally).
  try {
    if (typeof Ctor.available === "function" && "processLocally" in rec) {
      const status = await Ctor.available({ langs: [tag], processLocally: true });
      if (status === "available") rec.processLocally = true;
    }
  } catch {
    /* not supported: browser default */
  }

  let finalText = "";
  let interim = "";
  let done = false;
  let silence = setTimeout(() => rec.stop(), silenceMs);
  rec.onresult = (e) => {
    interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    onPartial?.((finalText + interim).trim());
    clearTimeout(silence);
    silence = setTimeout(() => rec.stop(), silenceMs);
  };
  let error: ListenError | null = null;
  rec.onerror = (e) => {
    const map: Record<string, ListenError> = { "not-allowed": "permission", "service-not-allowed": "permission", "no-speech": "no-speech", network: "network", aborted: "aborted", "audio-capture": "unavailable", "language-not-supported": "unavailable" };
    error = map[e.error] ?? "unknown";
  };
  rec.onend = () => {
    if (done) return;
    done = true;
    clearTimeout(silence);
    const text = (finalText || interim).trim();
    if (text) onFinal?.(text);
    else onError?.(error ?? "no-speech");
  };
  try {
    rec.start();
  } catch {
    clearTimeout(silence);
    onError?.("busy");
    return () => undefined;
  }
  return () => {
    if (!done) rec.stop();
  };
}
