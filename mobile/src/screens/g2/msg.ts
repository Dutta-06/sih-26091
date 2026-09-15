/**
 * Renders core `Msg`s with enum-like variables translated (core passes ids such as "high", "tailoring", "demand").
 * Numbers for money/count variables get Indian digit grouping. Falls back to `tm` behaviour for anything else.
 */
import { useCallback } from "react";
import { ACTIVITIES } from "../../data/activities";
import { useI18n } from "../../i18n";
import type { Msg } from "../../core/types";

const LEVEL_VARS = new Set(["saturation", "from", "to", "variation", "risk", "level"]);
const ACTIVITY_VARS = new Set(["activity", "rejected"]);
const MONEY_VARS = new Set(["capital", "need", "have", "project", "max", "surplus", "installment", "low", "high", "n", "count"]);

export function useMsg() {
  const { t, pick, tm } = useI18n();
  return useCallback(
    (m: Msg | null | undefined) => {
      if (!m) return "";
      const vars: Record<string, string | number> = {};
      for (const [k, v] of Object.entries(m.vars ?? {})) {
        if (typeof v === "string" && LEVEL_VARS.has(k)) vars[k] = t(v === "unknown" ? "g2.level.unknown" : `level.${v}`);
        else if (typeof v === "string" && ACTIVITY_VARS.has(k) && ACTIVITIES[v]) vars[k] = pick(ACTIVITIES[v].name);
        else if (typeof v === "string" && k === "topic") vars[k] = t(`evidence.topic.${v}`);
        else if (typeof v === "string" && k === "confidence") vars[k] = t(`confidence.${v}`);
        else if (typeof v === "string" && k === "id" && m.key === "c2.swot.highRisk") vars[k] = t(`c2.risk.tax.${v}`) === `c2.risk.tax.${v}` ? v : t(`c2.risk.tax.${v}`);
        else if (typeof v === "number" && MONEY_VARS.has(k) && Number.isFinite(v)) vars[k] = Math.round(v).toLocaleString("en-IN");
        else vars[k] = v;
      }
      return tm({ key: m.key, vars });
    },
    [t, pick, tm],
  );
}
