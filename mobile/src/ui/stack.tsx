/**
 * Native-feeling navigation stack: every page in the stack stays mounted (state and scroll preserved),
 * pages beneath the top are parked with <Activity mode="hidden"> (effects paused, no layout/paint) and only
 * revealed while a transition or swipe-back needs them. Only transform/opacity animate.
 */
import { animate, AnimatePresence, motion, useMotionValue, usePresence, useReducedMotion, useTransform, type MotionValue } from "motion/react";
import { Activity, createContext, memo, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ComponentType, type PointerEvent as ReactPointerEvent } from "react";
import { ScreenCtx, TABS, useNav, type NavAction, type Route, type Tab } from "../nav";
import { clamp, EDGE_PX, layerDim, layerShadow, layerX, NAV_SPRING, releaseVelocity, swipeCompletes, TAB_FADE } from "./motion";

type Role = "top" | "under" | "off";

interface StackCtxValue {
  register: (index: number, pos: MotionValue<number>) => () => void;
  /** set by the swipe gesture: velocity (page widths/s) to hand to the next spring */
  handoff: { current: number };
  action: { current: NavAction };
  dragging: boolean;
  reduced: boolean;
}
const StackCtx = createContext<StackCtxValue | null>(null);

const ScreenHost = memo(function ScreenHost({ Comp }: { Comp: ComponentType }) {
  return <Comp />;
});

function useSpringTo(pos: MotionValue<number>, reduced: boolean) {
  const controls = useRef<ReturnType<typeof animate> | null>(null);
  const token = useRef(0);
  const [animating, setAnimating] = useState(false);
  const run = useCallback(
    (target: number, velocity = 0, done?: () => void) => {
      controls.current?.stop();
      const my = ++token.current;
      if (reduced || pos.get() === target) {
        pos.set(target);
        setAnimating(false);
        done?.();
        return;
      }
      setAnimating(true);
      controls.current = animate(pos, target, { ...NAV_SPRING, velocity });
      controls.current.then(() => {
        if (my !== token.current) return;
        setAnimating(false);
        done?.();
      });
    },
    [pos, reduced],
  );
  return { run, animating };
}

/** One page of the stack. */
function Layer({ index, role, enter, Comp, tabRoot }: { index: number; role: Role; enter: boolean; Comp: ComponentType; tabRoot?: boolean }) {
  const ctx = useContext(StackCtx)!;
  const [isPresent, safeToRemove] = usePresence();
  const pos = useMotionValue(enter && !tabRoot ? 1 : role === "under" ? -1 : 0);
  const fade = useMotionValue(1);
  const tabShift = useMotionValue(0);
  const x = useTransform(pos, layerX);
  const dim = useTransform(pos, layerDim);
  const shadow = useTransform(pos, layerShadow);
  const { run, animating } = useSpringTo(pos, ctx.reduced);
  const [lingering, setLingering] = useState(false); // outgoing tab root kept visible under the incoming fade
  const [parked, setParked] = useState(role === "under"); // underneath and settled → safe to hide
  const [roleSeen, setRoleSeen] = useState(role);
  if (roleSeen !== role) {
    // adjust visibility flags in the same render as the role change so nothing blinks for a frame
    setRoleSeen(role);
    setParked(roleSeen === "off" && role === "under");
    if (tabRoot && roleSeen === "top" && role === "off" && !ctx.reduced) setLingering(true);
  }
  const prevRole = useRef<Role | null>(null);
  const scrolls = useRef(new Map<Element, number>());

  // Register the position so the swipe gesture can drive it.
  const { register } = ctx;
  useEffect(() => {
    if (role === "off" || !isPresent) return;
    return register(index, pos);
  }, [register, index, pos, role, isPresent]);

  // Animate to the resting place for the current role.
  useLayoutEffect(() => {
    const was = prevRole.current;
    prevRole.current = role;
    if (!isPresent || was === role) return;
    const v = ctx.handoff.current;
    if (role === "top") {
      if (tabRoot && (was === "off" || (was === null && enter)) && ctx.action.current === "tab" && !ctx.reduced) {
        // tab change: cross-fade in over the outgoing root with a small slide (no remount)
        pos.set(0);
        fade.set(0);
        tabShift.set(12);
        animate(fade, 1, TAB_FADE);
        animate(tabShift, 0, TAB_FADE);
        return;
      }
      if (was === null && !enter) return;
      run(0, v);
    } else if (role === "under") {
      if (was === "off" || was === null) pos.set(-1);
      else run(-1, v, () => setParked(true));
    } else {
      pos.set(0);
      if (was === "top" && tabRoot && !ctx.reduced) {
        const t = setTimeout(() => setLingering(false), 230);
        return () => {
          clearTimeout(t);
          setLingering(false);
        };
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, isPresent]);

  // Exit: slide off to the right on pop, park underneath on replace, fade on tab change.
  useEffect(() => {
    if (isPresent) return;
    const kind = ctx.action.current;
    const v = ctx.handoff.current;
    if (ctx.reduced) {
      safeToRemove();
      return;
    }
    if (kind === "tab") {
      const c = animate(fade, 0, { duration: 0.14 });
      c.then(safeToRemove);
      return () => c.stop();
    }
    run(kind === "pop" ? 1 : -1, v, safeToRemove);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPresent]);

  const visible = role === "top" || lingering || !isPresent || (role === "under" && (!parked || ctx.dragging));
  const busy = animating || !isPresent || lingering || (ctx.dragging && role !== "off");

  // Hidden subtrees are display:none, which drops scroll offsets — remember and restore them.
  useLayoutEffect(() => {
    if (!visible) return;
    scrolls.current.forEach((top, el) => {
      if (el.isConnected) el.scrollTop = top;
    });
  }, [visible]);

  const exitingZ = !isPresent ? (ctx.action.current === "pop" ? 5 : -5) : 0;
  const z = tabRoot ? (role === "top" ? 2 : 1) : index * 10 + exitingZ;

  return (
    <motion.div
      aria-hidden={role !== "top" || !isPresent}
      className="absolute inset-0"
      onScrollCapture={(e) => {
        const el = e.target as Element;
        if (el && "scrollTop" in el) scrolls.current.set(el, (el as HTMLElement).scrollTop);
      }}
      style={{
        x,
        opacity: fade,
        zIndex: z,
        visibility: visible ? "visible" : "hidden",
        pointerEvents: role === "top" && isPresent ? "auto" : "none",
        willChange: busy ? "transform" : "auto",
      }}
    >
      {index > 0 && (
        <motion.div aria-hidden className="pointer-events-none absolute inset-y-0 right-full w-4 bg-gradient-to-l from-black/10 to-transparent" style={{ opacity: shadow }} />
      )}
      <motion.div className="screen-layer absolute inset-0 bg-cream" style={tabRoot ? { x: tabShift } : undefined}>
        <Activity mode={visible ? "visible" : "hidden"}>
          <ScreenCtx.Provider value={{ index, isTop: role === "top" && isPresent }}>
            <ScreenHost Comp={Comp} />
          </ScreenCtx.Provider>
        </Activity>
      </motion.div>
      <motion.div aria-hidden className="pointer-events-none absolute inset-0 bg-black" style={{ opacity: dim }} />
    </motion.div>
  );
}

/** Router: tab roots (kept alive once visited) + pushed pages, the swipe-back edge and hardware back. */
export function StackRouter({ screens }: { screens: Record<Route["name"], ComponentType> }) {
  const nav = useNav();
  const { stack, tab, action, pop } = nav;
  const reduced = !!useReducedMotion();
  const positions = useRef(new Map<number, MotionValue<number>>());
  const handoff = useRef(0);
  const actionRef = useRef<NavAction>(action);
  actionRef.current = action;
  const mounted = useRef(false);
  const [visited, setVisited] = useState<Tab[]>([tab]);
  const [dragging, setDragging] = useState(false);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    mounted.current = true;
  }, []);
  useEffect(() => {
    setVisited((v) => (v.includes(tab) ? v : [...v, tab]));
    handoff.current = 0;
  }, [tab, stack]);

  const register = useCallback((index: number, pos: MotionValue<number>) => {
    positions.current.set(index, pos);
    return () => {
      if (positions.current.get(index) === pos) positions.current.delete(index);
    };
  }, []);

  /* ---- edge swipe-back ---- */
  const gesture = useRef<{ id: number; x0: number; y0: number; active: boolean; samples: { x: number; t: number }[]; width: number } | null>(null);
  const depth = stack.length;

  const onDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (depth < 2) return;
    gesture.current = { id: e.pointerId, x0: e.clientX, y0: e.clientY, active: false, samples: [{ x: e.clientX, t: e.timeStamp }], width: container.current?.clientWidth ?? window.innerWidth };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const g = gesture.current;
    if (!g || g.id !== e.pointerId) return;
    const dx = e.clientX - g.x0;
    const dy = e.clientY - g.y0;
    if (!g.active) {
      if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) {
        gesture.current = null;
        return;
      }
      if (dx < 6) return;
      g.active = true;
      setDragging(true);
    }
    g.samples.push({ x: e.clientX, t: e.timeStamp });
    if (g.samples.length > 8) g.samples.shift();
    const p = clamp(dx / g.width, 0, 1);
    positions.current.get(depth - 1)?.set(p);
    positions.current.get(depth - 2)?.set(p - 1);
  };
  const onUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    const g = gesture.current;
    gesture.current = null;
    if (!g || g.id !== e.pointerId || !g.active) return;
    const dx = e.clientX - g.x0;
    const vx = e.type === "pointercancel" ? 0 : releaseVelocity(g.samples);
    const top = positions.current.get(depth - 1);
    const under = positions.current.get(depth - 2);
    handoff.current = vx / g.width;
    if (swipeCompletes(dx, vx, g.width) && pop()) {
      // the layers pick up from their current positions with the release velocity
      setTimeout(() => setDragging(false), 360);
      return;
    }
    const opts = reduced ? { duration: 0 } : { ...NAV_SPRING, velocity: handoff.current };
    if (top) animate(top, 0, opts);
    const c = under ? animate(under, -1, opts) : null;
    handoff.current = 0;
    if (c) c.then(() => setDragging(false));
    else setDragging(false);
  };

  const enter = mounted.current && (action === "push" || action === "goto");
  return (
    <StackCtx.Provider value={{ register, handoff, action: actionRef, dragging, reduced }}>
      <div ref={container} className="absolute inset-0 overflow-hidden">
        {TABS.filter((t) => visited.includes(t) || t === tab).map((t) => (
          <Layer key={`tab:${t}`} tabRoot index={0} role={t !== tab ? "off" : depth > 1 ? "under" : "top"} enter={mounted.current && action === "tab"} Comp={screens[t]} />
        ))}
        <div className="pointer-events-none absolute inset-0" style={{ zIndex: 10 }}>
          <AnimatePresence initial={false}>
            {stack.slice(1).map((r, i) => (
              <Layer key={`${i + 1}:${r.name}`} index={i + 1} role={i + 1 === depth - 1 ? "top" : "under"} enter={enter && i + 1 === depth - 1} Comp={screens[r.name]} />
            ))}
          </AnimatePresence>
        </div>
        {depth > 1 && (
          <div
            aria-hidden
            className="absolute inset-y-0 left-0"
            style={{ width: EDGE_PX, zIndex: 1000, touchAction: "none" }}
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
          />
        )}
      </div>
    </StackCtx.Provider>
  );
}
