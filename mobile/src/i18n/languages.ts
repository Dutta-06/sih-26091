/** Languages the app supports: full UI, conversation, message understanding and voice. */
export const LANGS = ["en", "hi", "bn", "ta", "te", "pa", "kn", "mr"] as const;
export type Lang = (typeof LANGS)[number];

export interface LangInfo {
  code: Lang;
  /** Name in its own script. */
  native: string;
  /** Name in English. */
  english: string;
  /** Short label for compact switches. */
  short: string;
  /** BCP-47 tag for speech recognition and text-to-speech. */
  speech: string;
  /** Locale used for dates (digits stay Latin across the app). */
  dateLocale: string;
}

export const LANG_INFO: Record<Lang, LangInfo> = {
  en: { code: "en", native: "English", english: "English", short: "EN", speech: "en-IN", dateLocale: "en-IN" },
  hi: { code: "hi", native: "हिंदी", english: "Hindi", short: "हिं", speech: "hi-IN", dateLocale: "hi-IN-u-nu-latn" },
  bn: { code: "bn", native: "বাংলা", english: "Bangla", short: "বাং", speech: "bn-IN", dateLocale: "bn-IN-u-nu-latn" },
  ta: { code: "ta", native: "தமிழ்", english: "Tamil", short: "தமி", speech: "ta-IN", dateLocale: "ta-IN-u-nu-latn" },
  te: { code: "te", native: "తెలుగు", english: "Telugu", short: "తెలు", speech: "te-IN", dateLocale: "te-IN-u-nu-latn" },
  pa: { code: "pa", native: "ਪੰਜਾਬੀ", english: "Punjabi", short: "ਪੰਜਾ", speech: "pa-IN", dateLocale: "pa-IN-u-nu-latn" },
  kn: { code: "kn", native: "ಕನ್ನಡ", english: "Kannada", short: "ಕನ್ನ", speech: "kn-IN", dateLocale: "kn-IN-u-nu-latn" },
  mr: { code: "mr", native: "मराठी", english: "Marathi", short: "मरा", speech: "mr-IN", dateLocale: "mr-IN-u-nu-latn" },
};

export const isLang = (v: unknown): v is Lang => typeof v === "string" && (LANGS as readonly string[]).includes(v);
