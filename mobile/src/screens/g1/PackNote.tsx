import { Database } from "lucide-react";
import { packMeta } from "../../core/pack";
import { useI18n } from "../../i18n";
import { cx } from "../../ui";

/** "Sample data pack" disclosure, shown wherever values come from the bundled pack (`packMeta().synthetic_sample`). */
export function PackNote({ light, className }: { light?: boolean; className?: string }) {
  const { t } = useI18n();
  if (!packMeta().synthetic_sample) return null;
  return (
    <p className={cx("mt-6 flex items-start justify-center gap-1.5 px-2 text-center text-[11px] leading-snug", light ? "text-forest-100/80" : "text-ink-3", className)}>
      <Database className="mt-px size-3 shrink-0" />
      {t("u1.pack.note")}
    </p>
  );
}
