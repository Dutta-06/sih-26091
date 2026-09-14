import type { Strings } from "../index";

/** Places, PIN codes and mapped businesses from the bundled open data (core/openData.ts). */
const opendata: Strings = {
  "en": {
    "u1.loc.villageCensus": "Found it: {village}, {block}, {district} district (Census 2011 village). Local checks will use this village.",
    "u1.loc.pincode": "Found the {office} post office area in {district} district. Local checks will use the centre of this PIN area.",
    "core.c1.geo.pincode": "Located by PIN code {pin} (centre of the {office} post office area), not an exact village.",
    "c2.comp.mappedRelative": "Counted from businesses mapped online and compared with the state average; small informal units are often missing.",
    "g3.form.ifscUnknown": "No bank branch has this IFSC code. Check it on your passbook or cheque.",
    "g3.form.pinOther": "This PIN code is in {district} district, not in {case}.",
    "c2.risk.rain.title": "Depends on rainfall",
    "c2.risk.rain.detail": "Here {share}% of the year's rain ({annual} mm) falls in June–September, {dry} months are nearly dry, and yearly rain varies by about {cv}%. Fodder, water and buyers' income follow the rain.",
    "arch.src.overture": "Overture Maps",
    "arch.src.indiapost": "India Post PIN",
    "arch.src.ifsc": "Razorpay IFSC",
    "arch.src.openmeteo": "Open-Meteo"
  },
  "hi": {
    "u1.loc.villageCensus": "मिल गया: {village}, {block}, {district} ज़िला (जनगणना 2011 का गाँव)। स्थानीय जाँच इसी गाँव से होगी।",
    "u1.loc.pincode": "{district} ज़िले में {office} डाकघर का इलाका मिला। स्थानीय जाँच इस पिन इलाके के बीच के स्थान से होगी।",
    "core.c1.geo.pincode": "पिन कोड {pin} से स्थान लिया ({office} डाकघर इलाके का बीच), सटीक गाँव नहीं।",
    "c2.comp.mappedRelative": "ऑनलाइन नक्शे पर दर्ज कामों से गिना और राज्य के औसत से मिलाया; छोटे अनौपचारिक काम अक्सर छूट जाते हैं।",
    "g3.form.ifscUnknown": "इस IFSC कोड की कोई बैंक शाखा नहीं है। पासबुक या चेक पर देखकर जाँचें।",
    "g3.form.pinOther": "यह पिन कोड {district} ज़िले का है, {case} का नहीं।",
    "c2.risk.rain.title": "बारिश पर निर्भर",
    "c2.risk.rain.detail": "यहाँ साल की {share}% बारिश ({annual} मिमी) जून–सितंबर में होती है, {dry} महीने लगभग सूखे रहते हैं और हर साल बारिश लगभग {cv}% ऊपर-नीचे होती है। चारा, पानी और ग्राहकों की कमाई बारिश पर चलती है।",
    "arch.src.overture": "ओवरचर मैप्स",
    "arch.src.indiapost": "इंडिया पोस्ट पिन",
    "arch.src.ifsc": "रेज़रपे IFSC",
    "arch.src.openmeteo": "ओपन-मीटियो"
  }
};

export default opendata;
