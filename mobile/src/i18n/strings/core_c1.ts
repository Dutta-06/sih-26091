import type { Strings } from "../index";

/** C1: on-device location resolution messages (limitations returned by core/geo.ts). */
const core_c1: Strings = {
  en: {
    "core.c1.geo.ambiguous": "{count} places match “{name}”. Please choose yours so the advice is about the right area.",
    "core.c1.geo.choice_invalid": "The chosen location code {lgd} is not one of the matching places.",
    "core.c1.geo.village_not_in_district": "“{name}” was not found in the district you named, so the district headquarters is used instead.",
    "core.c1.geo.district_hq": "Village not found; using the {district} district headquarters as an approximate location.",
    "core.c1.geo.state_centroid": "Only the state was recognised; using the {state} capital as a rough location. Local population and market figures are not available.",
    "core.c1.geo.unresolved": "We could not find “{query}” in the location table. Please give your village and district.",
  },
  hi: {
    "core.c1.geo.ambiguous": "“{name}” नाम की {count} जगहें हैं। अपनी जगह चुनें, ताकि सलाह सही इलाके की हो।",
    "core.c1.geo.choice_invalid": "चुना गया स्थान कोड {lgd} मिलती-जुलती जगहों में नहीं है।",
    "core.c1.geo.village_not_in_district": "“{name}” आपके बताए ज़िले में नहीं मिला, इसलिए ज़िला मुख्यालय का स्थान लिया गया है।",
    "core.c1.geo.district_hq": "गाँव नहीं मिला; अंदाज़े के लिए {district} ज़िला मुख्यालय का स्थान लिया गया है।",
    "core.c1.geo.state_centroid": "सिर्फ़ राज्य पहचाना गया; मोटे अंदाज़े के लिए {state} की राजधानी ली गई है। स्थानीय आबादी और बाज़ार के आँकड़े उपलब्ध नहीं हैं।",
    "core.c1.geo.unresolved": "“{query}” स्थान तालिका में नहीं मिला। कृपया अपना गाँव और ज़िला बताएँ।",
  },
};

export default core_c1;
