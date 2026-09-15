import { describe, expect, it } from "vitest";
import { LEXICONS } from "./lexicon";
import { DICTIONARIES } from "../i18n";
import { LANGS } from "../i18n/languages";
import { classifyIntent, detectScript, extract } from "./nlu";

/** Typical first messages in each lexicon language: activity, capital and language must be understood. */
const MESSAGES: { lang: string; text: string; activityId: string; capital: number }[] = [
  { lang: "bn", text: "আমি সেলাইয়ের কাজ শুরু করতে চাই, আমার কাছে ২ লাখ টাকা আছে", activityId: "tailoring", capital: 200000 },
  { lang: "bn", text: "গরু কিনে দুধের ব্যবসা করব, পঞ্চাশ হাজার টাকা", activityId: "dairy_farming", capital: 50000 },
  { lang: "ta", text: "நான் தையல் கடை தொடங்க விரும்புகிறேன், 2 லட்சம் ரூபாய் இருக்கிறது", activityId: "tailoring", capital: 200000 },
  { lang: "ta", text: "ஆடு வளர்ப்பு செய்ய ஐம்பது ஆயிரம் ரூபாய்", activityId: "goat_rearing", capital: 50000 },
  { lang: "pa", text: "ਮੈਂ ਸਿਲਾਈ ਦਾ ਕੰਮ ਸ਼ੁਰੂ ਕਰਨਾ ਚਾਹੁੰਦੀ ਹਾਂ, ਮੇਰੇ ਕੋਲ 2 ਲੱਖ ਰੁਪਏ ਹਨ", activityId: "tailoring", capital: 200000 },
  { lang: "pa", text: "ਮੱਝਾਂ ਰੱਖ ਕੇ ਦੁੱਧ ਵੇਚਣਾ ਹੈ, ਪੰਜਾਹ ਹਜ਼ਾਰ", activityId: "dairy_farming", capital: 50000 },
  { lang: "mr", text: "मला शिवणकाम सुरू करायचे आहे, माझ्याकडे 2 लाख रुपये आहेत", activityId: "tailoring", capital: 200000 },
  { lang: "mr", text: "शेळीपालन करायचे आहे, पन्नास हजार रुपये", activityId: "goat_rearing", capital: 50000 },
  { lang: "te", text: "నేను టైలరింగ్ పని మొదలు పెట్టాలి, నా దగ్గర 2 లక్షల రూపాయలు ఉన్నాయి", activityId: "tailoring", capital: 200000 },
  { lang: "te", text: "మేకల పెంపకం చేయాలి, యాభై వేల రూపాయలు", activityId: "goat_rearing", capital: 50000 },
  { lang: "kn", text: "ನಾನು ಟೈಲರಿಂಗ್ ಕೆಲಸ ಶುರು ಮಾಡಬೇಕು, ನನ್ನ ಬಳಿ 2 ಲಕ್ಷ ರೂಪಾಯಿ ಇದೆ", activityId: "tailoring", capital: 200000 },
  { lang: "kn", text: "ಮೇಕೆ ಸಾಕಣೆ ಮಾಡಬೇಕು, ಐವತ್ತು ಸಾವಿರ ರೂಪಾಯಿ", activityId: "goat_rearing", capital: 50000 },
];

describe("lexicon-language understanding", () => {
  for (const m of MESSAGES.filter((x) => LEXICONS[x.lang as keyof typeof LEXICONS])) {
    it(`${m.lang}: ${m.text}`, () => {
      const e = extract(m.text, null);
      expect(e.activityId).toBe(m.activityId);
      expect(e.capital).toBe(m.capital);
      expect(detectScript(m.text)).toBe(m.lang);
      expect(classifyIntent(m.text)).not.toBe("raise_grievance");
    });
  }
});

describe("every app language is complete", () => {
  it("each dictionary has every English key and can name every language", () => {
    const keys = Object.keys(DICTIONARIES.en);
    for (const l of LANGS) {
      expect(keys.filter((k) => !DICTIONARIES[l]?.[k]), l).toEqual([]);
      for (const other of LANGS) expect(DICTIONARIES[l][`u1.langName.${other}`], `${l} u1.langName.${other}`).toBeTruthy();
    }
  });
});