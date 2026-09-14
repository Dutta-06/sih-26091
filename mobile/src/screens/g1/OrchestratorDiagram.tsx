import { Check, IndianRupee, Lightbulb, MapPin, Network, ShieldAlert, Store, Truck, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useI18n } from "../../i18n";
import { cx } from "../../ui";
import { AGENT_ORDER, type AgentId } from "./findings";

export const AGENT_ICONS: Record<AgentId, LucideIcon> = { marketReach: MapPin, opportunity: Lightbulb, competitor: Store, pricing: IndianRupee, risk: ShieldAlert, supplyChain: Truck };

const R = 38; // node ring radius in % of the box

/** Central orchestrator with the six analyses fanning out; each lights up when its computed finding is in. */
export function OrchestratorDiagram({ done }: { done: Record<AgentId, boolean> }) {
  const { t } = useI18n();
  const nodes = AGENT_ORDER.map((id, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / AGENT_ORDER.length;
    return { id, x: 50 + Math.cos(angle) * R, y: 50 + Math.sin(angle) * R, done: done[id] };
  });
  const allDone = nodes.every((n) => n.done);
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[280px]">
      <svg viewBox="0 0 100 100" className="absolute inset-0 size-full" aria-hidden>
        {nodes.map((n, i) => (
          <g key={n.id}>
            <motion.line
              x1="50"
              y1="50"
              x2={n.x}
              y2={n.y}
              stroke={n.done ? "#F2A516" : "rgb(255 255 255 / 0.25)"}
              strokeWidth="0.7"
              strokeDasharray={n.done ? "0" : "1.5 1.5"}
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.5, delay: 0.1 + i * 0.07 }}
            />
            {!n.done && (
              <motion.circle
                r="1.1"
                fill="#FBDC9C"
                initial={{ cx: 50, cy: 50, opacity: 0 }}
                animate={{ cx: [50, n.x], cy: [50, n.y], opacity: [0, 1, 0] }}
                transition={{ duration: 0.9, repeat: Infinity, delay: 0.5 + i * 0.12, ease: "easeInOut" }}
              />
            )}
          </g>
        ))}
      </svg>

      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <motion.span aria-hidden className="absolute inset-0 rounded-full bg-marigold-500" animate={allDone ? { scale: 1, opacity: 0 } : { scale: [1, 1.6], opacity: [0.4, 0] }} transition={{ duration: 1.4, repeat: allDone ? 0 : Infinity }} />
        <span className={cx("relative grid size-18 place-items-center rounded-full shadow-[var(--shadow-float)] transition-colors", allDone ? "bg-marigold-500 text-azure-950" : "bg-white text-azure-800")}>
          <Network className="size-8" />
        </span>
      </div>

      {nodes.map((n) => {
        const Icon = AGENT_ICONS[n.id];
        return (
          <div key={n.id} className="absolute flex w-20 -translate-x-1/2 -translate-y-1/2 flex-col items-center" style={{ left: `${n.x}%`, top: `${n.y}%` }}>
            <motion.span
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: n.done ? [1.18, 1] : 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 400, damping: 18 }}
              className={cx("relative grid size-12 place-items-center rounded-full ring-2 transition-colors", n.done ? "bg-azure-600 text-white ring-marigold-500" : "bg-azure-900 text-azure-100 ring-white/20")}
            >
              <Icon className="size-5" />
              {n.done && (
                <span className="absolute -right-1 -bottom-1 grid size-5 place-items-center rounded-full bg-marigold-500 text-azure-950">
                  <Check className="size-3.5" strokeWidth={3} />
                </span>
              )}
            </motion.span>
            <span className="mt-1 text-center text-[11px] leading-tight font-medium text-azure-100">{t(`u1.agent.${n.id}`)}</span>
          </div>
        );
      })}
    </div>
  );
}
