/**
 * Document scanning: the phone camera (or gallery) takes the photo, the native DocumentText plugin reads it with
 * on-device ML Kit text recognition, and core/docscan interprets the lines. Nothing leaves the phone.
 * In the browser (development) a test hook `window.__scanLines` stands in for the camera and recogniser.
 */
import { Camera, MediaTypeSelection } from "@capacitor/camera";
import { Capacitor, registerPlugin } from "@capacitor/core";

interface DocumentTextPlugin {
  recognize(options: { path: string }): Promise<{ lines: string[]; width: number; height: number }>;
}

const DocumentText = registerPlugin<DocumentTextPlugin>("DocumentText");

declare global {
  interface Window {
    __scanLines?: string[];
  }
}

export type ScanSource = "camera" | "gallery";
export type ScanFailure = "cancelled" | "permission" | "unavailable" | "failed";

export class ScanError extends Error {
  constructor(readonly reason: ScanFailure) {
    super(reason);
  }
}

export const canScan = () => Capacitor.isNativePlatform() || (import.meta.env.DEV && Array.isArray(window.__scanLines));

function failure(e: unknown): ScanError {
  const msg = String((e as { message?: string })?.message ?? e).toLowerCase();
  if (/cancel|dismiss|no image|user/.test(msg)) return new ScanError("cancelled");
  if (/permission|denied/.test(msg)) return new ScanError("permission");
  return new ScanError("failed");
}

/** Take or pick a photo and return the recognised lines in reading order. */
export async function scanDocument(source: ScanSource): Promise<string[]> {
  if (!Capacitor.isNativePlatform()) {
    if (import.meta.env.DEV && Array.isArray(window.__scanLines)) {
      await new Promise((r) => setTimeout(r, 900));
      return window.__scanLines;
    }
    throw new ScanError("unavailable");
  }
  let uri: string | undefined;
  try {
    if (source === "camera") {
      uri = (await Camera.takePhoto({ quality: 90, targetWidth: 2200, targetHeight: 2200, correctOrientation: true })).uri;
    } else {
      uri = (await Camera.chooseFromGallery({ mediaType: MediaTypeSelection.Photo, limit: 1 })).results[0]?.uri;
    }
  } catch (e) {
    throw failure(e);
  }
  if (!uri) throw new ScanError("cancelled");
  try {
    return (await DocumentText.recognize({ path: uri })).lines;
  } catch {
    throw new ScanError("failed");
  }
}
