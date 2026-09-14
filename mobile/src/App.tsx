import { App as CapApp } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";
import { SplashScreen } from "@capacitor/splash-screen";
import { StatusBar, Style } from "@capacitor/status-bar";
import { BriefcaseBusiness, Home as HomeIcon, IndianRupee, LayoutGrid, MessageCircle } from "lucide-react";
import { motion, MotionConfig } from "motion/react";
import { useEffect, useRef, type ComponentType } from "react";
import { I18nProvider, useI18n } from "./i18n";
import { NavProvider, TABS, useNav, type Tab } from "./nav";
import { SCREENS } from "./screens";
import Onboarding from "./screens/Onboarding";
import { tap } from "./lib/haptics";
import { StoreProvider, useStore } from "./state/store";
import { cx, Toaster } from "./ui";
import { NAV_SPRING } from "./ui/motion";
import { StackRouter } from "./ui/stack";

const TAB_ICONS: Record<Tab, ComponentType<{ className?: string }>> = {
  home: HomeIcon,
  assistant: MessageCircle,
  plan: IndianRupee,
  business: BriefcaseBusiness,
  more: LayoutGrid,
};

export { tap } from "./lib/haptics";

function TabBar() {
  const { tab, switchTab, stack } = useNav();
  const { t } = useI18n();
  const hidden = stack.length > 1; // pushed screens are full-screen; the bar slides away beneath them
  return (
    <motion.nav
      initial={false}
      animate={{ y: hidden ? "105%" : "0%" }}
      transition={NAV_SPRING}
      aria-hidden={hidden}
      style={{ pointerEvents: hidden ? "none" : "auto", zIndex: 5 }}
      className="safe-bottom absolute inset-x-0 bottom-0 border-t border-line bg-white"
    >
      <div className="flex">
        {TABS.map((name) => {
          const Icon = TAB_ICONS[name];
          const active = tab === name;
          return (
            <motion.button
              key={name}
              whileTap={{ scale: 0.92 }}
              onClick={() => {
                tap();
                if (!active) switchTab(name);
              }}
              className="relative flex min-h-16 flex-1 flex-col items-center justify-center gap-1"
            >
              {active && <motion.span layoutId="tab-pill" transition={{ type: "spring", stiffness: 500, damping: 38 }} className="absolute top-2 h-8 w-14 rounded-full bg-forest-100" />}
              <Icon className={cx("relative size-5.5 transition-colors", active ? "text-forest-800" : "text-ink-3")} />
              <span className={cx("relative text-[11px] font-medium transition-colors", active ? "text-forest-800" : "text-ink-3")}>{t(`nav.${name}`)}</span>
            </motion.button>
          );
        })}
      </div>
    </motion.nav>
  );
}

function Router() {
  const { back } = useNav();
  const backRef = useRef(back);
  backRef.current = back;

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    const sub = CapApp.addListener("backButton", () => {
      if (!backRef.current()) CapApp.minimizeApp();
    });
    return () => {
      sub.then((s) => s.remove());
    };
  }, []);

  return (
    <div className="relative h-full overflow-hidden">
      <StackRouter screens={SCREENS} />
      <TabBar />
    </div>
  );
}

function Shell() {
  const { state, set } = useStore();
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    StatusBar.setStyle({ style: Style.Light }).catch(() => undefined);
    StatusBar.setBackgroundColor({ color: "#FBF7EF" }).catch(() => undefined);
    SplashScreen.hide().catch(() => undefined);
  }, []);
  return (
    <I18nProvider lang={state.lang} setLang={(lang) => set({ lang })}>
      <NavProvider>
        {state.onboarded ? <Router /> : <Onboarding />}
        <Toaster />
      </NavProvider>
    </I18nProvider>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <StoreProvider>
        <Shell />
      </StoreProvider>
    </MotionConfig>
  );
}
