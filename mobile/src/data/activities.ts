import catalog from "../../../data/reference/business_catalog.json";
import type { ActivityEconomics } from "../engine/finance";
import type { Bi } from "../i18n";

/** Catalog entries (single source of truth shared with the Python backend) plus display names. */
export interface Activity extends ActivityEconomics {
  id: string;
  category: string;
  sector: string;
  min_project_cost: number;
  perishable: boolean;
  key_inputs: string[];
  buyers: string[];
  licences: string[];
  adjacent: string[];
  name: Bi;
  emoji: string;
}

const DISPLAY: Record<string, { name: Bi; emoji: string }> = {
  tailoring: { name: { en: "Tailoring & stitching unit", hi: "सिलाई-कढ़ाई यूनिट" }, emoji: "🧵" },
  handloom_weaving: { name: { en: "Handloom weaving", hi: "हथकरघा बुनाई" }, emoji: "🧶" },
  carpet_weaving: { name: { en: "Carpet weaving", hi: "कालीन बुनाई" }, emoji: "🪢" },
  beauty_parlour: { name: { en: "Beauty parlour", hi: "ब्यूटी पार्लर" }, emoji: "💇‍♀️" },
  food_processing_home: { name: { en: "Pickle & papad making", hi: "अचार-पापड़ निर्माण" }, emoji: "🫙" },
  dairy_farming: { name: { en: "Dairy farming", hi: "डेयरी फार्मिंग" }, emoji: "🐄" },
  goat_rearing: { name: { en: "Goat rearing", hi: "बकरी पालन" }, emoji: "🐐" },
  poultry_backyard: { name: { en: "Backyard poultry", hi: "घरेलू मुर्गी पालन" }, emoji: "🐔" },
  grocery_kirana: { name: { en: "Village kirana store", hi: "गाँव की किराना दुकान" }, emoji: "🛒" },
  mobile_repair: { name: { en: "Mobile repair shop", hi: "मोबाइल रिपेयर दुकान" }, emoji: "📱" },
  tea_snack_stall: { name: { en: "Tea & snack stall", hi: "चाय-नाश्ता स्टॉल" }, emoji: "☕" },
  flour_mill: { name: { en: "Flour mill (atta chakki)", hi: "आटा चक्की" }, emoji: "🌾" },
};

export const ACTIVITIES: Record<string, Activity> = Object.fromEntries(
  catalog.activities
    .filter((a) => DISPLAY[a.id])
    .map((a) => [a.id, { ...(a as unknown as Activity), ...DISPLAY[a.id] }]),
);

export const activity = (id: string): Activity => {
  const a = ACTIVITIES[id];
  if (!a) throw new Error(`Unknown activity ${id}`);
  return a;
};
