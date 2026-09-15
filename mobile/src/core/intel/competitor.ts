/**
 * Competitor mapping (port of module1_feasibility/competitor_agent.py over the data pack).
 *
 * Tiers, in the backend order:
 *  1. udyam     — pack Udyam extract: registrations for the catalog NIC class in the district (district scope; the
 *                 extract has no coordinates). Normalised by district population → district per-10k average, and the
 *                 state total over pack districts → state per-10k average ("real" table values).
 *  2. overpass  — pack POI table: enterprises within RADIUS_KM whose OSM tags match catalog `osm_tags`.
 *  3. web_search — never available on device; recorded, never fabricated.
 *
 * The pack Udyam extract is district-wide (it cannot be normalised by the radius population, as the backend notes) and
 * covers registered enterprises only, so its per-10k averages are not in the same unit as a count of all mapped
 * enterprises. Comparisons therefore stay within one measure:
 *  - radius count available (POI tier): density within the radius vs the catalog `typical_density_per_10k`
 *    benchmark — exactly the backend rule (benchmark = catalog planning density);
 *  - otherwise Udyam district density vs Udyam state average (both registered-only); catalog benchmark if no state row.
 * The Udyam district and state averages are always reported (`districtPer10k`, `statePer10k`).
 *
 * z (Poisson): expected = benchmark × population / 10k; z = (count − expected) / √expected.
 * Saturation: density / benchmark ≤ 0.75 low, ≤ 1.25 medium, else high; unknown when either is missing.
 */
import { openPlacesLoaded, openPlacesNear } from "../openData";
import { district as packDistrict, isDetailed, mappedCounts, MIN_STATE_MAPPED, poisNear, stateMapped, udyam, udyamState } from "../pack";
import type { CompetitorIntel, LocationCandidate, Saturation } from "../types";
import { type CatalogActivity, msg, RADIUS_KM, round, src, usableCoords } from "./catalog";
import { populationWithinRadius } from "./marketReach";

export function poissonZ(count: number | null, population: number | null, benchmark: number | null): number | null {
  if (count === null || !population || !benchmark) return null;
  const expected = (benchmark * population) / 10_000;
  return expected > 0 ? round((count - expected) / Math.sqrt(expected), 2) : null;
}

/** competitor_agent.saturation_from_ratio / opportunity_agent.classify_saturation level. */
export function classifySaturation(density: number | null, benchmark: number | null): Saturation {
  if (density === null || benchmark === null || benchmark <= 0 || density < 0) return "unknown";
  const ratio = density / benchmark;
  return ratio <= 0.75 ? "low" : ratio <= 1.25 ? "medium" : "high";
}

const per10k = (count: number, population: number) => round((count / population) * 10_000, 3);

export function competitorIntel(activity: CatalogActivity, location: LocationCandidate | null): CompetitorIntel {
  const intel: CompetitorIntel = {
    confidence: "estimated", sources: [], limitations: [], tier: "none", tiersAttempted: [], count: null, nearby: [],
    densityPer10k: null, districtPer10k: null, statePer10k: null, zScore: null, saturation: "unknown",
  };
  if (!location) {
    intel.tiersAttempted = [{ tier: "udyam", status: "no_data" }, { tier: "overpass", status: "no_data" }, { tier: "web_search", status: "unavailable" }];
    intel.limitations.push(msg("c2.comp.noLocation"), msg("c2.comp.unknown"));
    return intel;
  }
  const d = location.district;
  const districtRow = packDistrict(d.id);

  // Mapped places (Overture Maps): where the state has enough of them for this activity, the district's density is
  // compared with the state's in the same source, which cancels how unevenly businesses are mapped.
  const state = districtRow ? stateMapped(districtRow.state) : null;
  const stateCount = state?.activities[activity.id] ?? 0;
  if (districtRow && state && openPlacesLoaded() && !isDetailed(districtRow.id) && stateCount >= MIN_STATE_MAPPED && state.population > 0) {
    const districtCount = mappedCounts(districtRow.id).activities[activity.id] ?? 0;
    const coords = usableCoords(location);
    const ids = new Set(openPlacesNear(location.lat, location.lon, RADIUS_KM).filter((p) => p.activities.includes(activity.id)).map((p) => p.poi.id));
    intel.nearby = coords ? poisNear(coords.lat, coords.lon, RADIUS_KM, (p) => ids.has(p.id)) : [];
    intel.tier = "overpass";
    intel.tiersAttempted = [{ tier: "udyam", status: "no_data" }, { tier: "overpass", status: "used" }, { tier: "web_search", status: "unavailable" }];
    intel.count = districtCount;
    intel.districtPer10k = per10k(districtCount, districtRow.population);
    intel.statePer10k = per10k(stateCount, state.population);
    intel.densityPer10k = intel.districtPer10k;
    intel.zScore = poissonZ(districtCount, districtRow.population, intel.statePer10k);
    intel.saturation = classifySaturation(intel.districtPer10k, intel.statePer10k);
    intel.confidence = "real";
    intel.sources.push(src(
      `Overture Maps places: ${districtCount} mapped in the district, ${stateCount} in ${districtRow.state}; ${intel.nearby.length} within ${RADIUS_KM} km`,
      `ओवरचर मैप्स स्थान: ज़िले में ${districtCount}, ${districtRow.state} में ${stateCount}; ${RADIUS_KM} किमी में ${intel.nearby.length}`,
      "real",
    ));
    intel.limitations.push(msg("c2.comp.mappedRelative"));
    return intel;
  }

  // Tier 1: Udyam (district scope)
  const districtCount = districtRow ? udyam(districtRow.id, activity.nic_class) : null;
  const stateRow = udyamState(d.state, activity.nic_class);
  const udyamUsed = !!districtCount && districtRow !== null;
  intel.tiersAttempted.push({ tier: "udyam", status: udyamUsed ? "used" : "no_data" });
  if (udyamUsed) {
    intel.districtPer10k = per10k(districtCount!, districtRow!.population);
    intel.sources.push(src(`Udyam registrations, NIC ${activity.nic_class}: ${districtCount} in district`, `उद्यम पंजीकरण, NIC ${activity.nic_class}: ज़िले में ${districtCount}`, "real"));
    intel.limitations.push(msg("c2.comp.udyamRegisteredOnly"));
  } else {
    intel.limitations.push(msg("c2.comp.udyamNoData", { nic: activity.nic_class }));
  }
  if (stateRow && stateRow.count > 0 && stateRow.population > 0) intel.statePer10k = per10k(stateRow.count, stateRow.population);

  // Tier 2: POI table within radius
  const coords = usableCoords(location);
  const tags = activity.osm_tags ?? [];
  let radiusPop: number | null = null;
  let radiusPopReal = false;
  if (coords && tags.length) {
    intel.nearby = poisNear(coords.lat, coords.lon, RADIUS_KM, (p) => p.tags.some(([k, v]) => tags.some(([tk, tv]) => tk === k && tv === v)));
    intel.tiersAttempted.push({ tier: "overpass", status: intel.nearby.length ? "used" : "no_data" });
    if (!intel.nearby.length) intel.limitations.push(msg("c2.comp.poiNoData", { km: RADIUS_KM }));
    else intel.limitations.push(msg("c2.comp.poiUndercount"));
  } else {
    intel.tiersAttempted.push({ tier: "overpass", status: "no_data" });
    intel.limitations.push(msg(coords ? "c2.comp.noTags" : "c2.comp.coarse"));
  }
  intel.tiersAttempted.push({ tier: "web_search", status: "unavailable" });

  const catalogBench = activity.typical_density_per_10k ?? null;
  let benchmark: number | null = null;
  let benchReal = false;
  let population: number | null = null;
  if (intel.nearby.length && coords) {
    const pop = populationWithinRadius(coords.lat, coords.lon, RADIUS_KM, d.state);
    radiusPop = pop.population;
    radiusPopReal = pop.confidence === "real";
    intel.tier = "overpass";
    intel.count = intel.nearby.length;
    population = radiusPop;
    benchmark = catalogBench;
    intel.sources.push(src(`Mapped enterprises within ${RADIUS_KM} km: ${intel.count}`, `${RADIUS_KM} किमी में दर्ज उद्यम: ${intel.count}`, "real"));
  } else if (udyamUsed) {
    intel.tier = "udyam";
    intel.count = districtCount;
    population = districtRow!.population;
    radiusPopReal = true;
    benchmark = intel.statePer10k ?? catalogBench;
    benchReal = intel.statePer10k !== null;
    intel.limitations.push(msg("c2.comp.districtScope"));
  } else {
    intel.limitations.push(msg("c2.comp.unknown"));
  }
  if (intel.count !== null && population) intel.densityPer10k = per10k(intel.count, population);
  else if (intel.count !== null) intel.limitations.push(msg("c2.comp.noPopulation"));
  if (intel.count !== null && !benchReal && catalogBench) {
    intel.sources.push(src(`Catalog typical density ${catalogBench}/10k (planning assumption)`, `कैटलॉग सामान्य घनत्व ${catalogBench}/10 हज़ार (योजना अनुमान)`, "estimated"));
    intel.limitations.push(msg("c2.comp.catalogBenchmark"));
  }
  intel.zScore = poissonZ(intel.count, population, benchmark);
  intel.saturation = classifySaturation(intel.densityPer10k, benchmark);
  // competitor_agent: real when the count and the population it is normalised by come from real tables.
  intel.confidence = intel.densityPer10k !== null && radiusPopReal ? "real" : "estimated";
  return intel;
}
