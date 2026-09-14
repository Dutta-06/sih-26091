/**
 * When a place in the message is not in the bundled tables, look it up online (Photon / Nominatim, no key) and put the
 * nearest Census village and district in its place, so the offline pipeline can take over. Offline: text unchanged.
 */
import { resolveLocation } from "../core/geo";
import { extract } from "../core/nlu";
import { mergeExtraction, type ModelReading } from "../core/nluModel";
import type { Slot } from "../core/types";
import type { ConvInput } from "../screens/g1/conversation";
import { geocode, placeTextFor } from "./online";

export async function withOnlinePlace(text: string, input: ConvInput, reading: ModelReading | null): Promise<string> {
  const pending = input.pendingSlot === "location_choice" ? "location" : (input.pendingSlot as Slot | null);
  const { ext } = mergeExtraction(extract(text, pending), reading, pending);
  const phrase = ext.locationText ?? (pending === "location" ? text.trim() : null);
  if (!phrase || phrase.length < 3 || resolveLocation(phrase, null).candidates.length > 0) return text;
  const hit = await geocode(phrase);
  const replacement = hit ? placeTextFor(hit, phrase) : null;
  if (!replacement) return text;
  return text.includes(phrase) ? text.replace(phrase, replacement) : replacement;
}
