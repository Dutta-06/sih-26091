import { Building2, Home, MapPinOff, MessageCircle, Store, Truck, GraduationCap, WifiOff } from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useRef, useState } from "react";
import type { Confidence, PackPoi } from "../core/types";
import { useI18n, type Bi } from "../i18n";
import { tap } from "../lib/haptics";
import { useNav } from "../nav";
import { useStore } from "../state/store";
import { Badge, Button, Chip, ConfidenceBadge, cx, Note, Screen, Sheet } from "../ui";
import { activityLabel, caseIntel, placeOf } from "./g2/feasibility";
import { PackNote, PLACE_ICON } from "./g2/ReportSections";

type Layer = "markets" | "competitors" | "suppliers" | "schools";
const LAYERS: { id: Layer; icon: typeof Store }[] = [
  { id: "markets", icon: Store },
  { id: "competitors", icon: Building2 },
  { id: "suppliers", icon: Truck },
  { id: "schools", icon: GraduationCap },
];

interface Pin {
  key: string;
  name: Bi;
  kind: PackPoi["kind"] | "competitor";
  layer: Layer;
  km: number;
  x: number; // km east of home
  y: number; // km north of home
  confidence: Confidence;
}

/** Map size in SVG units (1 unit = VIEW / (2 × extent) km). */
const VIEW = 100;
/** The draggable drawing layer is 130% of the viewport. */
const LAYER = 1.3;
const KM_PER_DEG_LAT = 110.574;
const KM_PER_DEG_LON_EQ = 111.32;

/** Equirectangular projection around the home point: offsets in km (x east, y north). */
function project(lat0: number, lon0: number, lat: number, lon: number) {
  return { x: (lon - lon0) * KM_PER_DEG_LON_EQ * Math.cos((lat0 * Math.PI) / 180), y: (lat - lat0) * KM_PER_DEG_LAT };
}

/** A 1-2-5 step close to a quarter of the visible width, for the scale bar. */
function niceScale(extentKm: number) {
  const target = (extentKm * 2) / 4;
  const pow = 10 ** Math.floor(Math.log10(target));
  return [1, 2, 5, 10].map((m) => m * pow).reduce((best, v) => (Math.abs(v - target) < Math.abs(best - target) ? v : best));
}

const PIN_STYLE: Record<Pin["kind"], { bg: string; size: number }> = {
  market: { bg: "#0A8AA0", size: 7 },
  haat: { bg: "#0A8AA0", size: 7 },
  transport: { bg: "#0A8AA0", size: 6 },
  school: { bg: "#D48806", size: 5.5 },
  supplier: { bg: "#0369A1", size: 6.5 },
  bank: { bg: "#0A8AA0", size: 5.5 },
  enterprise: { bg: "#C2410C", size: 4.5 },
  competitor: { bg: "#C2410C", size: 4.5 },
};

export default function MapScreen() {
  const { t, pick } = useI18n();
  const { goto } = useNav();
  const { state, view } = useStore();
  const [layers, setLayers] = useState<Record<Layer, boolean>>({ markets: true, competitors: true, suppliers: true, schools: true });
  const [selected, setSelected] = useState<Pin | null>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const place = placeOf(view);
  const intel = caseIntel(view, state.profile);
  const activityId = view.activityId ?? view.feasibility.attempts.at(-1)?.activityId ?? null;

  const geo = useMemo(() => {
    if (!place || !intel) return null;
    const pins: Pin[] = [];
    const add = (poi: PackPoi, km: number, layer: Layer, kind: Pin["kind"]) => {
      const p = project(place.lat, place.lon, poi.lat, poi.lon);
      pins.push({ key: `${layer}:${poi.id}`, name: poi.name, kind, layer, km, x: p.x, y: p.y, confidence: "real" });
    };
    for (const p of intel.marketReach.places) add(p.poi, p.km, p.poi.kind === "school" ? "schools" : "markets", p.poi.kind);
    for (const p of intel.competitor.nearby) add(p.poi, p.km, "competitors", "competitor");
    for (const p of intel.supplyChain.suppliers) if (!pins.some((x) => x.key === `markets:${p.poi.id}`)) add(p.poi, p.km, "suppliers", "supplier");
    const radius = intel.marketReach.radiusKm;
    // visible half-width fits the reach circle and every pin; the draggable layer is LAYER × the viewport
    const visibleKm = Math.max(radius, ...pins.map((p) => Math.max(Math.abs(p.x), Math.abs(p.y)))) * 1.08;
    return { pins, radius, extent: visibleKm * LAYER, scaleKm: niceScale(visibleKm) };
  }, [place, intel]);

  if (!place || !intel || !geo || place.method === "state_centroid") {
    const ambiguous = view.location.candidates.length > 1 && !view.location.chosen;
    return (
      <Screen title={t("map.title")}>
        <div className="mt-8 text-center">
          <MapPinOff className="mx-auto size-14 text-ink-3" />
          <h2 className="mt-3 text-lg font-bold">{t(ambiguous ? "g2.map.ambiguous" : state.profile.locationText ? "g2.map.coarse" : "g2.map.noPlace")}</h2>
          <p className="mx-auto mt-2 max-w-80 text-[14px] leading-snug text-ink-2">
            {t(ambiguous ? "g2.map.ambiguousSub" : "g2.map.emptySub", { n: view.location.candidates.length, text: state.profile.locationText })}
          </p>
          <Button className="mt-5" icon={MessageCircle} onClick={() => goto("assistant")}>
            {t("g2.report.tellUs")}
          </Button>
        </div>
      </Screen>
    );
  }

  const { pins, radius, extent, scaleKm } = geo;
  const u = VIEW / (2 * extent); // svg units per km
  const sx = (km: number) => VIEW / 2 + km * u;
  const sy = (km: number) => VIEW / 2 - km * u;
  const visible = pins.filter((p) => layers[p.layer]);
  const count = (l: Layer) => pins.filter((p) => p.layer === l).length;
  const homeName = place.village ? pick(place.village) : pick(place.district.name);

  const open = (p: Pin) => {
    if (dragging.current) return;
    tap();
    setSelected(p);
  };
  const pinLabel = (p: Pin) => pick(p.name) || t("map.type.competitor");

  return (
    <Screen title={t("map.title")} subtitle={t("map.subtitle", { r: radius, village: homeName })}>
      <div className="-mx-1 mt-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none]">
        {LAYERS.map((l) => (
          <Chip key={l.id} icon={l.icon} active={layers[l.id]} onClick={() => setLayers((s) => ({ ...s, [l.id]: !s[l.id] }))}>
            {t(`map.layer.${l.id}`)} · {count(l.id)}
          </Chip>
        ))}
      </div>

      <div ref={viewport} className="relative mt-3 aspect-square w-full touch-none overflow-hidden rounded-[var(--radius-card)] bg-[#e3eff0] shadow-[var(--shadow-card)]">
        <motion.div
          drag
          dragConstraints={viewport}
          dragElastic={0.08}
          dragMomentum={false}
          onDragStart={() => (dragging.current = true)}
          onDragEnd={() => setTimeout(() => (dragging.current = false), 60)}
          className="absolute cursor-grab active:cursor-grabbing"
          style={{ width: "130%", height: "130%", left: "-15%", top: "-15%" }}
        >
          <svg viewBox={`0 0 ${VIEW} ${VIEW}`} className="absolute inset-0 size-full">
            {/* 1-scale-unit grid */}
            {Array.from({ length: Math.floor(extent / scaleKm) * 2 + 1 }, (_, i) => (i - Math.floor(extent / scaleKm)) * scaleKm).map((k) => (
              <g key={k} stroke="#ffffff" strokeOpacity={0.6} strokeWidth={0.25}>
                <line x1={sx(k)} x2={sx(k)} y1={0} y2={VIEW} />
                <line y1={sy(k)} y2={sy(k)} x1={0} x2={VIEW} />
              </g>
            ))}
            <circle cx={50} cy={50} r={radius * u} fill="#0e9bb3" fillOpacity="0.07" stroke="#0e9bb3" strokeOpacity="0.55" strokeWidth="0.4" strokeDasharray="1.6 1.2" />
            <motion.circle cx={50} cy={50} r={3} fill="#0e9bb3" initial={{ scale: 0.4, opacity: 0.45 }} animate={{ scale: 2.2, opacity: 0 }} transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }} style={{ transformBox: "fill-box", originX: 0.5, originY: 0.5 }} />
            {visible.map((p, i) => {
              const st = PIN_STYLE[p.kind];
              const r = (st.size / 2) * (selected?.key === p.key ? 1.3 : 1);
              return (
                <motion.g
                  key={p.key}
                  role="button"
                  aria-label={pinLabel(p)}
                  initial={{ opacity: 0, scale: 0 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: Math.min(0.5, 0.1 + i * 0.02), type: "spring", stiffness: 380, damping: 18 }}
                  style={{ transformBox: "fill-box", originX: 0.5, originY: 0.5, cursor: "pointer" }}
                  onClick={() => open(p)}
                >
                  <circle cx={sx(p.x)} cy={sy(p.y)} r={Math.max(r, 3)} fill="transparent" />
                  <circle cx={sx(p.x)} cy={sy(p.y)} r={r} fill={st.bg} stroke="#fff" strokeWidth={0.6} />
                  {p.kind !== "competitor" && p.kind !== "enterprise" && <circle cx={sx(p.x)} cy={sy(p.y)} r={r * 0.35} fill="#fff" />}
                </motion.g>
              );
            })}
            <circle cx={50} cy={50} r={3.2} fill="#00596A" stroke="#fff" strokeWidth={0.8} />
          </svg>
          <span className="pointer-events-none absolute grid size-5 -translate-x-1/2 -translate-y-1/2 place-items-center text-white" style={{ left: "50%", top: "50%" }}>
            <Home className="size-3" />
          </span>
        </motion.div>

        <span className="pointer-events-none absolute top-2.5 left-2.5 inline-flex items-center gap-1 rounded-full bg-white/90 px-2 py-1 text-[11px] font-medium text-ink-2">
          <WifiOff className="size-3" />
          {t("map.offline")}
        </span>
        {/* scale bar: the drawing layer is LAYER × the viewport, so a map-unit fraction f spans f × LAYER of it */}
        <div className="pointer-events-none absolute top-2.5 right-2.5 flex flex-col items-end rounded-lg bg-white/90 px-2 py-1 text-[11px] text-ink-2">
          <span className="tabular">{t("unit.km", { n: scaleKm })}</span>
        </div>
        <div className="pointer-events-none absolute top-9 right-2.5 h-1.5 border-x-2 border-b-2 border-ink-2" style={{ width: `${((scaleKm * u) / VIEW) * LAYER * 100}%` }} />
        <span className="pointer-events-none absolute bottom-2.5 left-2.5 rounded-full bg-ink/70 px-2.5 py-1 text-[11px] whitespace-nowrap text-white">{t("map.hint")}</span>
      </div>

      <div className="mt-3 flex items-center gap-3 rounded-2xl bg-azure-50 p-3 ring-1 ring-azure-100">
        <Building2 className="size-5 shrink-0 text-azure-800" />
        <p className="min-w-0 flex-1 text-[14px] font-semibold text-azure-800">
          {intel.competitor.nearby.length
            ? t("map.summary", { n: intel.competitor.nearby.length, r: radius, name: activityId ? pick(activityLabel(activityId).name) : "", density: t(intel.competitor.saturation === "unknown" ? "g2.level.unknown" : `level.${intel.competitor.saturation}`) })
            : t("g2.map.noCompetitors", { r: radius })}
        </p>
        <ConfidenceBadge value={intel.competitor.confidence} compact />
      </div>
      {place.method !== "village_table" && (
        <div className="mt-2">
          <Note tone="marigold">{t("g2.map.districtCentre", { district: pick(place.district.name) })}</Note>
        </div>
      )}

      <div className="mt-3 rounded-[var(--radius-card)] bg-white p-4 shadow-[var(--shadow-card)]">
        <p className="mb-2 text-[13px] font-semibold tracking-wide text-ink-3 uppercase">{t("map.legend")}</p>
        <div className="grid grid-cols-2 gap-x-3 gap-y-2.5 text-[13px] text-ink-2">
          <LegendItem color="#00596A" label={t("map.home", { name: homeName })} />
          <LegendItem color="transparent" dashed label={t("map.reach", { r: radius })} />
          <LegendItem color={PIN_STYLE.market.bg} label={t("map.layer.markets")} />
          <LegendItem color={PIN_STYLE.competitor.bg} label={t("map.layer.competitors")} />
          <LegendItem color={PIN_STYLE.supplier.bg} label={t("map.layer.suppliers")} />
          <LegendItem color={PIN_STYLE.school.bg} label={t("map.layer.schools")} />
        </div>
        <p className="mt-3 text-[11px] leading-snug text-ink-3">{t("g2.map.projection", { km: scaleKm })}</p>
      </div>

      <PackNote />

      <Sheet open={!!selected} onClose={() => setSelected(null)}>
        {selected && (
          <div>
            <div className="flex items-start gap-3">
              <span className="grid size-12 shrink-0 place-items-center rounded-2xl text-white" style={{ background: PIN_STYLE[selected.kind].bg }}>
                {(() => {
                  const Icon = selected.kind === "competitor" ? Building2 : PLACE_ICON[selected.kind];
                  return <Icon className="size-6" />;
                })()}
              </span>
              <div className="min-w-0 flex-1">
                <h3 className="text-lg leading-tight font-semibold break-words">{pinLabel(selected)}</h3>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <Badge tone={selected.kind === "competitor" ? "risk" : "neutral"}>{t(`map.type.${selected.kind}`)}</Badge>
                  <ConfidenceBadge value={selected.confidence} />
                </div>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between rounded-2xl bg-white p-3 shadow-[var(--shadow-card)]">
              <span className="tabular text-[15px] font-semibold">{t("map.distance", { km: selected.km.toFixed(1) })}</span>
              <Badge tone={selected.km <= radius ? "good" : "warn"}>{t(selected.km <= radius ? "map.inside" : "map.outside")}</Badge>
            </div>
            <p className="mt-2 px-1 text-xs text-ink-3">{t("g2.map.straightLine")}</p>
            <Button variant="secondary" className="mt-4 w-full" onClick={() => setSelected(null)}>
              {t("action.close")}
            </Button>
          </div>
        )}
      </Sheet>
    </Screen>
  );
}

function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <span className={cx("size-3 shrink-0 rounded-full", dashed && "border-2 border-dashed border-azure-600 bg-azure-100")} style={dashed ? undefined : { background: color }} />
      <span className="truncate">{label}</span>
    </span>
  );
}
