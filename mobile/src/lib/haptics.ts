import { Capacitor } from "@capacitor/core";
import { Haptics, ImpactStyle } from "@capacitor/haptics";

/** Light haptic tick on native builds; no-op in the browser. */
export const tap = () => {
  if (Capacitor.isNativePlatform()) Haptics.impact({ style: ImpactStyle.Light }).catch(() => undefined);
};
