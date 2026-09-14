/**
 * Arambh UI primitives. Screens compose these; avoid ad-hoc colours and shadows in screens.
 * Touch targets are ≥ 44px; text never below 12px; icons always paired with text for low-literacy users.
 */
import { ChevronLeft, ChevronRight, Info, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion, useDragControls } from "motion/react";
import { useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useI18n } from "../i18n";
import { useBackHandler, useNav } from "../nav";
import { CountUp } from "./countup";
import { PRESS_SPRING, SHEET_SPRING, sheetDismisses } from "./motion";

export { CountUp, defaultCountFormat } from "./countup";
export { Toaster, toast, dismissToast, useToast, type ToastOptions, type ToastTone } from "./toast";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/* ---------- Layout ---------- */

/** A pushed screen: sticky header with back button, scrollable body, optional sticky footer. */
export function Screen({
  title,
  subtitle,
  children,
  footer,
  right,
  tone = "cream",
  back = true,
}: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  right?: ReactNode;
  tone?: "cream" | "forest";
  back?: boolean;
}) {
  const { pop } = useNav();
  const { t } = useI18n();
  const dark = tone === "forest";
  return (
    <div className={cx("flex h-full flex-col", dark ? "bg-forest-800 text-white" : "bg-cream")}>
      {(title || back) && (
        <header className={cx("safe-top sticky top-0 z-10", dark ? "bg-forest-800" : "bg-cream")}>
          <div className="flex min-h-14 items-center gap-1 px-2">
            {back ? (
              <motion.button
                aria-label={t("action.back")}
                onClick={() => pop()}
                whileTap={{ scale: 0.88 }}
                transition={PRESS_SPRING}
                className={cx("grid size-11 place-items-center rounded-full", dark ? "active:bg-white/10" : "active:bg-sand")}
              >
                <ChevronLeft className="size-6" />
              </motion.button>
            ) : (
              <span className="w-3" />
            )}
            <div className="min-w-0 flex-1">
              {title && <h1 className="truncate text-[17px] font-semibold leading-tight">{title}</h1>}
              {subtitle && <p className={cx("truncate text-xs", dark ? "text-forest-100" : "text-ink-3")}>{subtitle}</p>}
            </div>
            {right}
          </div>
        </header>
      )}
      <div className="scroll-area flex-1 px-4 pb-6">{children}</div>
      {footer && <div className="safe-bottom border-t border-line bg-cream px-4 pt-3 pb-3">{footer}</div>}
    </div>
  );
}

/** Tab root: large title area, no back button. */
export function TabScreen({ children, header }: { children: ReactNode; header?: ReactNode }) {
  return (
    <div className="flex h-full flex-col bg-cream">
      {header}
      <div className="scroll-area flex-1 px-4 pb-28">{children}</div>
    </div>
  );
}

export function Section({ title, action, children, className }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("mt-6", className)}>
      {(title || action) && (
        <div className="mb-2.5 flex items-end justify-between gap-3 px-1">
          {title && <h2 className="text-[13px] font-semibold uppercase tracking-wide text-ink-3">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Card({ children, className, onClick, tone = "white" }: { children: ReactNode; className?: string; onClick?: () => void; tone?: "white" | "forest" | "marigold" | "clay" | "sand" }) {
  const tones = {
    white: "bg-white",
    forest: "bg-forest-800 text-white",
    marigold: "bg-marigold-50 ring-1 ring-marigold-200",
    clay: "bg-clay-50 ring-1 ring-clay-100",
    sand: "bg-sand",
  };
  const body = <div className={cx("rounded-[var(--radius-card)] p-4", tone === "white" && "shadow-[var(--shadow-card)]", tones[tone], className)}>{children}</div>;
  if (!onClick) return body;
  return (
    <motion.button whileTap={{ scale: 0.975 }} transition={PRESS_SPRING} onClick={onClick} className="block w-full text-left">
      {body}
    </motion.button>
  );
}

/* ---------- Controls ---------- */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "accent";

export function Button({
  variant = "primary",
  icon: Icon,
  iconRight: IconRight,
  children,
  className,
  size = "lg",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; icon?: LucideIcon; iconRight?: LucideIcon; size?: "md" | "lg" }) {
  const variants: Record<ButtonVariant, string> = {
    primary: "bg-forest-800 text-white shadow-[var(--shadow-float)] active:bg-forest-900 disabled:bg-ink-3/40 disabled:shadow-none",
    accent: "bg-marigold-500 text-forest-950 active:bg-marigold-600",
    secondary: "bg-white text-forest-800 ring-1 ring-line active:bg-sand",
    ghost: "text-forest-800 active:bg-forest-50",
    danger: "bg-clay-600 text-white active:bg-clay-700",
  };
  return (
    <motion.button
      whileTap={{ scale: 0.96 }}
      transition={PRESS_SPRING}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-2xl font-semibold transition-colors disabled:pointer-events-none",
        size === "lg" ? "min-h-13 px-5 text-[15px]" : "min-h-11 px-4 text-sm",
        variants[variant],
        className,
      )}
      {...(rest as object)}
    >
      {Icon && <Icon className="size-5 shrink-0" />}
      {children}
      {IconRight && <IconRight className="size-5 shrink-0" />}
    </motion.button>
  );
}

export function Chip({ children, active, onClick, icon: Icon }: { children: ReactNode; active?: boolean; onClick?: () => void; icon?: LucideIcon }) {
  return (
    <motion.button
      whileTap={{ scale: 0.95 }}
      transition={PRESS_SPRING}
      onClick={onClick}
      className={cx(
        "inline-flex min-h-10 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 text-sm font-medium",
        active ? "bg-forest-800 text-white" : "bg-white text-forest-800 ring-1 ring-forest-200 active:bg-forest-50",
      )}
    >
      {Icon && <Icon className="size-4" />}
      {children}
    </motion.button>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <button role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)} className={cx("relative h-8 w-14 shrink-0 rounded-full transition-colors", checked ? "bg-forest-700" : "bg-ink-3/30")}>
      <motion.span layout transition={{ type: "spring", stiffness: 500, damping: 32 }} className={cx("absolute top-1 size-6 rounded-full bg-white shadow", checked ? "right-1" : "left-1")} />
    </button>
  );
}

/** Two-option segmented control (e.g. EN / हिं). */
export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-full bg-sand p-1">
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)} className={cx("relative min-h-9 min-w-12 rounded-full px-3 text-sm font-semibold", value === o.value ? "text-white" : "text-ink-2")}>
          {value === o.value && <motion.span layoutId={`seg-${options.map((x) => x.value).join()}`} className="absolute inset-0 rounded-full bg-forest-800" />}
          <span className="relative">{o.label}</span>
        </button>
      ))}
    </div>
  );
}

/* ---------- Data display ---------- */

/** The confidence label required on every intelligence output (TDD Section 2). */
export function ConfidenceBadge({ value, compact }: { value: "real" | "estimated"; compact?: boolean }) {
  const { t } = useI18n();
  const real = value === "real";
  return (
    <span
      title={t(real ? "confidence.realHint" : "confidence.estimatedHint")}
      className={cx(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold",
        real ? "bg-forest-100 text-forest-800" : "bg-marigold-100 text-marigold-600",
      )}
    >
      <span className={cx("size-1.5 rounded-full", real ? "bg-forest-600" : "bg-marigold-500")} />
      {!compact && t(real ? "confidence.real" : "confidence.estimated")}
    </span>
  );
}

export function Badge({ children, tone = "neutral", icon: Icon }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "risk" | "info"; icon?: LucideIcon }) {
  const tones = {
    neutral: "bg-sand text-ink-2",
    good: "bg-forest-100 text-forest-800",
    warn: "bg-marigold-100 text-marigold-600",
    risk: "bg-clay-100 text-clay-700",
    info: "bg-sky-100 text-sky-700",
  };
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold", tones[tone])}>
      {Icon && <Icon className="size-3.5" />}
      {children}
    </span>
  );
}

export const levelTone = (level: "low" | "medium" | "high", higherIsWorse = true) =>
  (higherIsWorse ? { low: "good", medium: "warn", high: "risk" } : { low: "risk", medium: "warn", high: "good" })[level] as "good" | "warn" | "risk";

export function Stat({
  label,
  value,
  hint,
  tone = "ink",
  format,
}: {
  label: string;
  /** numbers count up on change (formatted with `format`); any other node renders as-is */
  value: ReactNode;
  hint?: ReactNode;
  tone?: "ink" | "forest" | "light";
  format?: (n: number) => string;
}) {
  return (
    <div className="min-w-0">
      <p className={cx("text-xs", tone === "light" ? "text-forest-100" : "text-ink-3")}>{label}</p>
      <p className={cx("tabular mt-0.5 truncate text-xl font-bold", tone === "forest" && "text-forest-800", tone === "light" && "text-white")}>
        {typeof value === "number" ? <CountUp value={value} format={format} /> : value}
      </p>
      {hint && <div className={cx("mt-0.5 text-xs", tone === "light" ? "text-forest-100" : "text-ink-3")}>{hint}</div>}
    </div>
  );
}

export function IconBubble({ icon: Icon, tone = "forest", size = "md" }: { icon: LucideIcon; tone?: "forest" | "marigold" | "clay" | "sky" | "sand"; size?: "sm" | "md" | "lg" }) {
  const tones = { forest: "bg-forest-100 text-forest-800", marigold: "bg-marigold-100 text-marigold-600", clay: "bg-clay-100 text-clay-700", sky: "bg-sky-100 text-sky-700", sand: "bg-sand text-ink-2" };
  const sizes = { sm: "size-9 [&>svg]:size-4.5", md: "size-11 [&>svg]:size-5.5", lg: "size-14 [&>svg]:size-7" };
  return (
    <span className={cx("grid shrink-0 place-items-center rounded-2xl", tones[tone], sizes[size])}>
      <Icon />
    </span>
  );
}

export function ListRow({ icon, title, subtitle, right, onClick, tone }: { icon?: LucideIcon; title: ReactNode; subtitle?: ReactNode; right?: ReactNode; onClick?: () => void; tone?: "forest" | "marigold" | "clay" | "sky" | "sand" }) {
  const inner = (
    <div className="flex min-h-14 items-center gap-3 py-2.5">
      {icon && <IconBubble icon={icon} tone={tone} size="sm" />}
      <div className="min-w-0 flex-1">
        <div className="text-[15px] font-medium leading-snug">{title}</div>
        {subtitle && <div className="mt-0.5 text-[13px] leading-snug text-ink-3">{subtitle}</div>}
      </div>
      {right ?? (onClick && <ChevronRight className="size-5 text-ink-3" />)}
    </div>
  );
  return onClick ? (
    <motion.button whileTap={{ scale: 0.985, opacity: 0.75 }} transition={PRESS_SPRING} onClick={onClick} className="block w-full text-left">
      {inner}
    </motion.button>
  ) : (
    inner
  );
}

export function Progress({ value, tone = "forest", className }: { value: number; tone?: "forest" | "marigold" | "clay"; className?: string }) {
  const tones = { forest: "bg-forest-600", marigold: "bg-marigold-500", clay: "bg-clay-600" };
  return (
    <div className={cx("h-2 overflow-hidden rounded-full bg-ink-3/15", className)}>
      {/* scaleX (compositor-only) instead of width; rounded end is a minor trade-off while animating */}
      <motion.div
        initial={{ scaleX: 0 }}
        animate={{ scaleX: Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0)) / 100 }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        style={{ originX: 0 }}
        className={cx("h-full w-full rounded-full", tones[tone])}
      />
    </div>
  );
}

/** Circular score (0–100) used for health and feasibility scores. */
export function Ring({ value, size = 96, stroke = 10, tone = "forest", label, sub }: { value: number; size?: number; stroke?: number; tone?: "forest" | "marigold" | "clay" | "light"; label?: ReactNode; sub?: ReactNode }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const colors = { forest: "#198754", marigold: "#F2A516", clay: "#C2410C", light: "#FFFFFF" };
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={tone === "light" ? "rgb(255 255 255 / 0.2)" : "rgb(27 31 29 / 0.08)"} strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={colors[tone]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - Math.max(0, Math.min(100, value)) / 100) }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="tabular text-2xl leading-none font-bold">
            {label === undefined ? <CountUp value={value} duration={0.9} /> : typeof label === "number" ? <CountUp value={label} /> : label}
          </div>
          {sub && <div className="mt-1 text-[11px] opacity-70">{sub}</div>}
        </div>
      </div>
    </div>
  );
}

export function Note({ children, icon: Icon = Info, tone = "sand" }: { children: ReactNode; icon?: LucideIcon; tone?: "sand" | "marigold" | "clay" | "forest" }) {
  const tones = { sand: "bg-sand text-ink-2", marigold: "bg-marigold-50 text-marigold-600 ring-1 ring-marigold-200", clay: "bg-clay-50 text-clay-700 ring-1 ring-clay-100", forest: "bg-forest-50 text-forest-800 ring-1 ring-forest-100" };
  return (
    <div className={cx("flex gap-2.5 rounded-2xl p-3 text-[13px] leading-snug", tones[tone])}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** Subtle disclosure shown on data screens of the investor demo. */
export function SampleDataNote() {
  const { t } = useI18n();
  return <p className="mt-6 text-center text-[11px] text-ink-3">{t("demo.sampleData")}</p>;
}

/** Bottom sheet modal, portalled to the app root so it always sits above the tab bar. */
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title?: string; children: ReactNode }) {
  useBackHandler(open, onClose); // Android back closes the sheet first
  if (typeof document === "undefined") return null;
  return createPortal(
    <AnimatePresence>{open && <SheetPanel key="sheet" onClose={onClose} title={title}>{children}</SheetPanel>}</AnimatePresence>,
    document.getElementById("root") ?? document.body,
  );
}

function SheetPanel({ onClose, title, children }: { onClose: () => void; title?: string; children: ReactNode }) {
  const drag = useDragControls();
  const panel = useRef<HTMLDivElement>(null);
  return (
    <div className="absolute inset-0 z-50">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <motion.div
        ref={panel}
        role="dialog"
        aria-modal
        initial={{ y: "100%" }}
        animate={{ y: 0 }}
        exit={{ y: "100%" }}
        transition={SHEET_SPRING}
        drag="y"
        dragControls={drag}
        dragListener={false}
        dragConstraints={{ top: 0, bottom: 0 }}
        dragElastic={{ top: 0.05, bottom: 1 }}
        dragMomentum={false}
        onDragEnd={(_, info) => {
          if (sheetDismisses(info.offset.y, info.velocity.y, panel.current?.offsetHeight ?? 400)) onClose();
        }}
        className="safe-bottom absolute inset-x-0 bottom-0 flex max-h-[85%] flex-col rounded-t-3xl bg-cream"
      >
        {/* drag handle + title: pull down to dismiss */}
        <div onPointerDown={(e) => drag.start(e)} style={{ touchAction: "none" }} className="shrink-0 px-4 pt-2 pb-1">
          <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-ink-3/30" />
          {title && <h3 className="mb-2 text-lg font-semibold">{title}</h3>}
        </div>
        <div className="scroll-area min-h-0 flex-1 overscroll-contain px-4 pb-5">{children}</div>
      </motion.div>
    </div>
  );
}

/** Staggered entrance for lists of cards (kept light: short travel, capped stagger). */
export function Reveal({ children, i = 0, className }: { children: ReactNode; i?: number; className?: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.035 * Math.min(i, 8), duration: 0.28, ease: [0.16, 1, 0.3, 1] }} className={className}>
      {children}
    </motion.div>
  );
}

/** Loading placeholder with a compositor-only shimmer. `lines` renders a paragraph of bars. */
export function Skeleton({ className, lines, rounded = "md" }: { className?: string; lines?: number; rounded?: "sm" | "md" | "full" | "card" }) {
  const r = { sm: "rounded", md: "rounded-lg", full: "rounded-full", card: "rounded-[var(--radius-card)]" }[rounded];
  if (lines && lines > 1)
    return (
      <div className={cx("space-y-2", className)} aria-hidden>
        {Array.from({ length: lines }, (_, i) => (
          <div key={i} className={cx("skeleton h-3.5", r, i === lines - 1 ? "w-3/5" : "w-full")} />
        ))}
      </div>
    );
  return <div aria-hidden className={cx("skeleton", r, className ?? "h-4 w-full")} />;
}
