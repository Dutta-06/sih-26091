/** Simple shape illustrations for onboarding slides (inline SVG, no images). */
import { motion } from "motion/react";

export function SunriseArt() {
  return (
    <svg viewBox="0 0 240 150" className="h-36 w-auto" aria-hidden>
      <motion.circle cx="120" cy="96" r="42" fill="#F2A516" initial={{ cy: 130, opacity: 0 }} animate={{ cy: 96, opacity: 1 }} transition={{ duration: 1.1, ease: "easeOut" }} />
      {[0, 1, 2, 3, 4, 5, 6].map((i) => {
        const a = Math.PI * (0.1 + (0.8 * i) / 6);
        return (
          <motion.line
            key={i}
            x1={120 - Math.cos(a) * 54}
            y1={96 - Math.sin(a) * 54}
            x2={120 - Math.cos(a) * 68}
            y2={96 - Math.sin(a) * 68}
            stroke="#FBDC9C"
            strokeWidth="4"
            strokeLinecap="round"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.7 + i * 0.06 }}
          />
        );
      })}
      <path d="M0 110 Q60 86 120 104 T240 98 V150 H0Z" fill="#146C43" />
      <path d="M0 126 Q70 108 140 122 T240 118 V150 H0Z" fill="#0A3A24" />
      <path d="M30 150 L100 118 M70 150 L120 120 M120 150 L140 122 M175 150 L160 121 M220 150 L182 120" stroke="#198754" strokeWidth="2" opacity="0.7" />
    </svg>
  );
}

export function VoiceArt() {
  return (
    <svg viewBox="0 0 240 150" className="h-36 w-auto" aria-hidden>
      <rect x="22" y="20" width="120" height="46" rx="18" fill="#FFFFFF" opacity="0.95" />
      <path d="M40 66 L36 80 L56 66Z" fill="#FFFFFF" opacity="0.95" />
      <rect x="38" y="36" width="70" height="6" rx="3" fill="#BFE3CF" />
      <rect x="38" y="48" width="46" height="6" rx="3" fill="#BFE3CF" />
      <rect x="96" y="80" width="122" height="46" rx="18" fill="#F2A516" />
      <path d="M200 126 L206 140 L184 126Z" fill="#F2A516" />
      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
        <motion.rect
          key={i}
          x={116 + i * 11}
          width="5"
          rx="2.5"
          fill="#06291A"
          animate={{ height: [8, 22, 8], y: [99, 92, 99] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.1, ease: "easeInOut" }}
        />
      ))}
    </svg>
  );
}

export function HonestArt() {
  return (
    <svg viewBox="0 0 240 150" className="h-36 w-auto" aria-hidden>
      <path d="M78 14 L130 30 V70 C130 104 106 126 78 136 C50 126 26 104 26 70 V30Z" fill="#FFFFFF" opacity="0.95" />
      <motion.path d="M56 74 L72 90 L102 58" fill="none" stroke="#198754" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.8, delay: 0.3 }} />
      <rect x="150" y="40" width="72" height="22" rx="11" fill="#D8EFE3" />
      <circle cx="164" cy="51" r="4" fill="#198754" />
      <rect x="174" y="48" width="38" height="6" rx="3" fill="#198754" opacity="0.6" />
      <rect x="150" y="72" width="72" height="22" rx="11" fill="#FDEFD0" />
      <circle cx="164" cy="83" r="4" fill="#F2A516" />
      <rect x="174" y="80" width="38" height="6" rx="3" fill="#C77C02" opacity="0.6" />
      <rect x="150" y="104" width="72" height="22" rx="11" fill="#FDE3D3" />
      <path d="M160 111 L168 119 M168 111 L160 119" stroke="#C2410C" strokeWidth="3" strokeLinecap="round" />
      <rect x="174" y="112" width="38" height="6" rx="3" fill="#C2410C" opacity="0.6" />
    </svg>
  );
}
