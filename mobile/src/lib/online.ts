/**
 * Optional online sources that need no key. Every call is best-effort: offline, slow or failing requests return null
 * and the app carries on with the bundled data.
 *  - Open-Meteo historical weather (ERA5): ten years of daily rain at a point → core/climate.ts summary.
 *  - Photon (komoot, OpenStreetMap) place search, then Nominatim (OpenStreetMap) — used only when a typed place is not
 *    in the bundled village / district / PIN tables. Results are snapped to the nearest Census village so the rest of
 *    the analysis works from the bundled tables. Both services ask for light use: one request per unresolved place.
 */
import { summariseDaily, type ClimateSummary } from "../core/climate";
import { openVillagesNear } from "../core/openData";
import { district as packDistrict, districts, distanceKm } from "../core/pack";

const online = () => typeof navigator === "undefined" || navigator.onLine !== false;

async function getJson(url: string, timeoutMs: number): Promise<unknown | null> {
  if (!online()) return null;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: ctrl.signal, headers: { Accept: "application/json" } });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchClimate(lat: number, lon: number, today = new Date()): Promise<ClimateSummary | null> {
  const end = today.getUTCFullYear() - 1;
  const url = `https://archive-api.open-meteo.com/v1/archive?latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}&start_date=${end - 9}-01-01&end_date=${end}-12-31&daily=precipitation_sum&timezone=Asia%2FKolkata`;
  const data = (await getJson(url, 15_000)) as { daily?: { time: string[]; precipitation_sum: (number | null)[] } } | null;
  if (!data?.daily?.time?.length) return null;
  return summariseDaily(lat, lon, data.daily.time, data.daily.precipitation_sum, today.toISOString().slice(0, 10));
}

export interface GeocodeHit {
  lat: number;
  lon: number;
  label: string;
  source: "photon" | "nominatim";
}

const IN_BBOX = { minLon: 68, minLat: 6, maxLon: 98, maxLat: 37.5 };
const inIndia = (lat: number, lon: number) => lat >= IN_BBOX.minLat && lat <= IN_BBOX.maxLat && lon >= IN_BBOX.minLon && lon <= IN_BBOX.maxLon;

export async function geocode(query: string): Promise<GeocodeHit | null> {
  const q = encodeURIComponent(query.trim().slice(0, 120));
  if (!q) return null;
  const photon = (await getJson(`https://photon.komoot.io/api/?q=${q}&limit=5&bbox=${IN_BBOX.minLon},${IN_BBOX.minLat},${IN_BBOX.maxLon},${IN_BBOX.maxLat}`, 8_000)) as
    | { features?: { geometry: { coordinates: [number, number] }; properties: { name?: string; countrycode?: string; state?: string } }[] }
    | null;
  const f = photon?.features?.find((x) => (x.properties.countrycode ?? "IN").toUpperCase() === "IN" && inIndia(x.geometry.coordinates[1], x.geometry.coordinates[0]));
  if (f) return { lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0], label: [f.properties.name, f.properties.state].filter(Boolean).join(", "), source: "photon" };
  const nom = (await getJson(`https://nominatim.openstreetmap.org/search?format=jsonv2&countrycodes=in&limit=1&q=${q}`, 8_000)) as { lat: string; lon: string; display_name: string }[] | null;
  const n = nom?.[0];
  return n ? { lat: +n.lat, lon: +n.lon, label: n.display_name, source: "nominatim" } : null;
}

/**
 * Text the offline resolver understands for a geocoded point: the nearest Census village within 6 km with its district
 * ("Kandi, Murshidabad"), else the nearest district.
 */
export function placeTextFor(hit: GeocodeHit, query = ""): string | null {
  const simple = (s: string) => s.toLowerCase().replace(/[^a-z]/g, "");
  const wanted = simple(query.split(",")[0] ?? "");
  // A town (not in the village table) keeps its district rather than a nearby village the user did not name
  const byDistance = openVillagesNear(hit.lat, hit.lon, 6).sort((a, b) => distanceKm(hit.lat, hit.lon, a.lat, a.lon) - distanceKm(hit.lat, hit.lon, b.lat, b.lon));
  const near = byDistance.find((v) => !wanted || simple(v.name.en).startsWith(wanted.slice(0, 5)) || wanted.startsWith(simple(v.name.en).slice(0, 5)));
  // A town's district is the one most of the closest villages belong to (the nearest headquarters can be across a border)
  const votes = new Map<string, number>();
  for (const v of byDistance.slice(0, 7)) votes.set(v.district, (votes.get(v.district) ?? 0) + 1);
  const voted = [...votes.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  const d = near ? packDistrict(near.district)
    : voted ? packDistrict(voted)
    : districts().slice().sort((a, b) => distanceKm(hit.lat, hit.lon, a.lat, a.lon) - distanceKm(hit.lat, hit.lon, b.lat, b.lon))[0];
  if (!d || distanceKm(hit.lat, hit.lon, d.lat, d.lon) > 150) return null;
  return near ? `${near.name.en}, ${d.name.en}` : d.name.en;
}
