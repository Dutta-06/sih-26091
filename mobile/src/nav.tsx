import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

/** Screens reachable in the app. Tabs are roots; everything else is pushed on top of the current tab. */
export type Tab = "home" | "assistant" | "plan" | "business" | "more";

export type Route =
  | { name: Tab }
  | { name: "analysis" }
  | { name: "report" }
  | { name: "review" }
  | { name: "map" }
  | { name: "scheme" }
  | { name: "documents" }
  | { name: "application" }
  | { name: "roadmap" }
  | { name: "monitoring" }
  | { name: "warning" }
  | { name: "grievance" }
  | { name: "community" }
  | { name: "agency" }
  | { name: "architecture" }
  | { name: "shortlist" }
  | { name: "noViable" }
  | { name: "survey" }
  | { name: "evidence" }
  | { name: "earnings" }
  | { name: "udyam" }
  | { name: "outcome" }
  | { name: "privacy" }
  | { name: "timeline" }
  | { name: "languages" };

export const TABS: Tab[] = ["home", "assistant", "plan", "business", "more"];

/** What caused the last stack change; the router picks the matching transition. */
export type NavAction = "push" | "pop" | "tab" | "goto";

interface Nav {
  tab: Tab;
  stack: Route[];
  current: Route;
  /** direction of the last transition, for animation */
  direction: 1 | -1;
  /** the kind of the last transition (push/pop slide, tab cross-fade, goto replace) */
  action: NavAction;
  /** index of the previous tab when the last action was a tab change (for the slide direction) */
  prevTab: Tab;
  push: (r: Route) => void;
  pop: () => boolean;
  switchTab: (t: Tab) => void;
  /** Go to a tab root and immediately push a route on it. */
  goto: (t: Tab, r?: Route) => void;
  /**
   * Register a handler for the Android back button / swipe-back that runs before popping (e.g. an open sheet).
   * Return true from the handler when it consumed the back press. Returns an unregister function.
   */
  addBackHandler: (h: () => boolean) => () => void;
  /** Runs registered back handlers (newest first), then pops. Returns false when nothing could go back. */
  back: () => boolean;
}

const Ctx = createContext<Nav | null>(null);

/** Dev-only deep link for screenshots: #tab or #tab/route (ignored in production builds). */
function initialStack(): Route[] {
  if (!import.meta.env.DEV) return [{ name: "home" }];
  const [tab, route] = location.hash.replace(/^#/, "").split("?")[0].split("/");
  if (!tab || !(TABS as string[]).includes(tab)) return [{ name: "home" }];
  return route ? [{ name: tab as Tab }, { name: route } as Route] : [{ name: tab as Tab }];
}

export function NavProvider({ children }: { children: ReactNode }) {
  const [nav, setNav] = useState(() => {
    const stack = initialStack();
    return { stack, tab: stack[0].name as Tab, prevTab: stack[0].name as Tab, direction: 1 as 1 | -1, action: "push" as NavAction };
  });
  const handlers = useRef<(() => boolean)[]>([]);
  const depth = useRef(nav.stack.length);
  depth.current = nav.stack.length;

  const push = useCallback((r: Route) => {
    setNav((n) => ({ ...n, direction: 1, action: "push", stack: [...n.stack, r] }));
  }, []);
  const pop = useCallback(() => {
    if (depth.current <= 1) return false;
    depth.current -= 1; // guard against double pops within one frame
    setNav((n) => (n.stack.length <= 1 ? n : { ...n, direction: -1, action: "pop", stack: n.stack.slice(0, -1) }));
    return true;
  }, []);
  const switchTab = useCallback((t: Tab) => {
    setNav((n) => ({ ...n, direction: 1, action: "tab", prevTab: n.tab, tab: t, stack: [{ name: t }] }));
  }, []);
  const goto = useCallback((t: Tab, r?: Route) => {
    setNav((n) => ({ ...n, direction: 1, action: r ? "goto" : "tab", prevTab: n.tab, tab: t, stack: r ? [{ name: t }, r] : [{ name: t }] }));
  }, []);
  const addBackHandler = useCallback((h: () => boolean) => {
    handlers.current.push(h);
    return () => {
      handlers.current = handlers.current.filter((x) => x !== h);
    };
  }, []);
  const back = useCallback(() => {
    for (let i = handlers.current.length - 1; i >= 0; i--) if (handlers.current[i]()) return true;
    return pop();
  }, [pop]);

  const value = useMemo<Nav>(
    () => ({ ...nav, current: nav.stack[nav.stack.length - 1], push, pop, switchTab, goto, addBackHandler, back }),
    [nav, push, pop, switchTab, goto, addBackHandler, back],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useNav(): Nav {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useNav outside NavProvider");
  return ctx;
}

/** Intercept back (hardware button) while `active` — e.g. close a sheet instead of leaving the screen. */
export function useBackHandler(active: boolean, handler: () => void) {
  const ctx = useContext(Ctx);
  const ref = useRef(handler);
  ref.current = handler;
  const add = ctx?.addBackHandler;
  useEffect(() => {
    if (!active || !add) return;
    return add(() => {
      ref.current();
      return true;
    });
  }, [active, add]);
}

/** Per-layer info so a screen can tell whether it is the visible top page (e.g. to pause side effects). */
export const ScreenCtx = createContext<{ index: number; isTop: boolean }>({ index: 0, isTop: true });
export const useScreen = () => useContext(ScreenCtx);
