import { BadgeCheck, IndianRupee, Wallet } from "lucide-react";
import { motion } from "motion/react";
import { useEffect } from "react";
import { useI18n } from "../../i18n";

const COLORS = ["#F2A516", "#FFFFFF", "#BFE3CF", "#FBDC9C", "#198754", "#FDE3D3"];
/** deterministic pseudo-random in [0,1) so renders stay pure */
const rnd = (i: number, salt: number) => (((i + 1) * 9301 + salt * 49297) % 233280) / 233280;

/** Full-screen celebration: confetti for sanction, coins into a wallet for disbursal. */
export function Celebration({ kind, amount, onDone }: { kind: "sanctioned" | "disbursed"; amount: string; onDone: () => void }) {
  const { t } = useI18n();
  useEffect(() => {
    const id = setTimeout(onDone, 3200);
    return () => clearTimeout(id);
  }, [onDone]);

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} onClick={onDone} className="absolute inset-0 z-50 overflow-hidden bg-forest-900/95 text-white">
      {kind === "sanctioned"
        ? Array.from({ length: 36 }, (_, i) => (
            <motion.span
              key={i}
              className="absolute top-0 block rounded-sm"
              style={{ left: `${rnd(i, 1) * 100}%`, width: 6 + rnd(i, 2) * 6, height: 10 + rnd(i, 3) * 8, background: COLORS[i % COLORS.length] }}
              initial={{ y: -40, rotate: 0, opacity: 1 }}
              animate={{ y: 900, rotate: 360 + rnd(i, 4) * 540, x: (rnd(i, 5) - 0.5) * 120, opacity: [1, 1, 0] }}
              transition={{ duration: 2.2 + rnd(i, 6) * 1.2, delay: rnd(i, 7) * 0.5, ease: "easeIn" }}
            />
          ))
        : Array.from({ length: 10 }, (_, i) => (
            <motion.span
              key={i}
              className="absolute top-0 left-1/2 grid size-9 -ml-4.5 place-items-center rounded-full bg-marigold-500 text-forest-950 shadow"
              initial={{ y: -60, x: (rnd(i, 8) - 0.5) * 260, opacity: 0 }}
              animate={{ y: 300, x: 0, opacity: [0, 1, 1, 0], scale: [1, 1, 0.5] }}
              transition={{ duration: 1, delay: 0.2 + i * 0.14, ease: "easeIn" }}
            >
              <IndianRupee className="size-4.5" />
            </motion.span>
          ))}
      <div className="absolute inset-0 grid place-items-center px-8 text-center">
        <div>
          <motion.div initial={{ scale: 0 }} animate={{ scale: [0, 1.2, 1] }} transition={{ duration: 0.6, delay: 0.15 }} className="mx-auto grid size-24 place-items-center rounded-full bg-white/10 ring-4 ring-marigold-500">
            {kind === "sanctioned" ? <BadgeCheck className="size-12 text-marigold-500" /> : <Wallet className="size-12 text-marigold-500" />}
          </motion.div>
          <motion.p initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }} className="mt-6 text-[22px] font-bold">
            {t(`app.celebrate.${kind}`)}
          </motion.p>
          <motion.p initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.75, type: "spring" }} className="tabular mt-2 text-[44px] leading-none font-bold text-marigold-500">
            {amount}
          </motion.p>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }} className="mt-3 text-[15px] text-forest-100">
            {t(`app.celebrate.${kind}Sub`)}
          </motion.p>
          <p className="mt-10 text-xs text-forest-100/70">{t("app.celebrate.tap")}</p>
        </div>
      </div>
    </motion.div>
  );
}
