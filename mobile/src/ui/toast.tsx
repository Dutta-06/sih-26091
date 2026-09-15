/** Lightweight confirmation toasts: `toast("Saved")` from anywhere, or `useToast()` in components; `<Toaster/>` is mounted once in App. */
import { AlertTriangle, CheckCircle2, Info, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useSyncExternalStore } from "react";

export type ToastTone = "success" | "info" | "warn";
export interface ToastOptions {
  tone?: ToastTone;
  icon?: LucideIcon;
  /** ms before auto-dismiss (default 2600) */
  duration?: number;
}
interface ToastItem extends Required<Pick<ToastOptions, "tone" | "duration">> {
  id: number;
  message: string;
  icon?: LucideIcon;
}

let items: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function dismissToast(id: number) {
  items = items.filter((t) => t.id !== id);
  emit();
}

/** Show a toast; returns its id. Only the latest 3 are kept on screen. */
export function toast(message: string, opts: ToastOptions = {}): number {
  const item: ToastItem = { id: nextId++, message, tone: opts.tone ?? "success", duration: opts.duration ?? 2600, icon: opts.icon };
  items = [...items.slice(-2), item];
  emit();
  if (typeof window !== "undefined") window.setTimeout(() => dismissToast(item.id), item.duration);
  return item.id;
}

export function useToast() {
  return { toast, dismiss: dismissToast };
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

const TONE: Record<ToastTone, { cls: string; icon: LucideIcon }> = {
  success: { cls: "bg-azure-800 text-white", icon: CheckCircle2 },
  info: { cls: "bg-ink text-white", icon: Info },
  warn: { cls: "bg-marigold-500 text-azure-950", icon: AlertTriangle },
};

export function Toaster() {
  const list = useSyncExternalStore(subscribe, () => items, () => items);
  return (
    <div aria-live="polite" className="safe-top pointer-events-none absolute inset-x-0 top-0 z-[60] flex flex-col items-center gap-2 px-4 pt-3">
      <AnimatePresence initial={false}>
        {list.map((t) => {
          const Icon = t.icon ?? TONE[t.tone].icon;
          return (
            <motion.button
              key={t.id}
              layout="position"
              initial={{ opacity: 0, y: -16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.96, transition: { duration: 0.16 } }}
              transition={{ type: "spring", stiffness: 520, damping: 36 }}
              onClick={() => dismissToast(t.id)}
              className={`pointer-events-auto flex max-w-full items-center gap-2 rounded-full py-2.5 pr-4 pl-3 text-sm font-medium shadow-[var(--shadow-float)] ${TONE[t.tone].cls}`}
            >
              <Icon className="size-4.5 shrink-0" />
              <span className="min-w-0 truncate">{t.message}</span>
            </motion.button>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
