/**
 * Hidden presentation tools (stage jumps, date controls, message pattern, example profile). Unlocked on this
 * device by tapping the version line in More seven times; remembered in local storage, separate from the case.
 */
import { useSyncExternalStore } from "react";

const KEY = "aashaudyami.tools";
const listeners = new Set<() => void>();

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

let unlocked = read();

export function setToolsUnlocked(value: boolean) {
  unlocked = value;
  try {
    if (value) localStorage.setItem(KEY, "1");
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: keep for this session */
  }
  listeners.forEach((l) => l());
}

export function useToolsUnlocked(): boolean {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => unlocked,
    () => false,
  );
}
