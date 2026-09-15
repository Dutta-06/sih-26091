import { Landmark, Phone, Tag, Truck, type LucideIcon } from "lucide-react";
import type { InterventionType } from "./model";

export const INTERVENTION_LOOK: Record<InterventionType, { icon: LucideIcon; tone: "marigold" | "sky" | "azure" | "clay" }> = {
  pricing_adjustment: { icon: Tag, tone: "marigold" },
  supply_chain_change: { icon: Truck, tone: "sky" },
  mentor_outreach: { icon: Phone, tone: "azure" },
  repayment_counselling: { icon: Landmark, tone: "clay" },
};
