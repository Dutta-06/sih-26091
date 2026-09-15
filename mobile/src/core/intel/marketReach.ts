/**
 * Market reach (port of module1_feasibility/market_reach_agent.py over the data pack).
 *
 * Population within RADIUS_KM: sum of pack village populations within the radius ("real": the village table stands
 * in for Census 2011 village points), else π r² × state density from the state reference ("estimated"), else null.
 *
 * Documented planning assumptions (always "estimated"):
 *  - CATCHMENT_SHARE: share of residents within the radius a single village micro-enterprise can reach. The backend
 *    uses one share (0.30) for every sector; the table lets a deployer calibrate per sector and currently keeps 0.30
 *    everywhere, because no sourced per-sector figure exists in the repo.
 *  - HOUSEHOLD_SIZE 4.8 (≈ Census 2011 all-India average).
 */
import { poisNear, settlementsNear, stateRef } from "../pack";
import type { LocationCandidate, MarketReachIntel, PackPoi } from "../types";
import { msg, RADIUS_KM, src, usableCoords } from "./catalog";

export const DEFAULT_CATCHMENT_SHARE = 0.3;
export const CATCHMENT_SHARE: Record<string, number> = {
  textiles_apparel: 0.3,
  services: 0.3,
  retail_trade: 0.3,
  food_processing: 0.3,
  animal_husbandry: 0.3,
  agri_allied: 0.3,
  fisheries: 0.3,
};
export const HOUSEHOLD_SIZE = 4.8;
export const MAX_POINTS = 25;
const PLACE_KINDS: PackPoi["kind"][] = ["market", "haat", "transport", "school"];

export interface PopulationEstimate {
  population: number | null;
  confidence: "real" | "estimated";
  villages: number;
}

/** census.population_within_radius → state_density_estimate fallback. */
export function populationWithinRadius(lat: number, lon: number, radiusKm: number, state: string | null): PopulationEstimate {
  const hits = settlementsNear(lat, lon, radiusKm);
  if (hits.length) return { population: hits.reduce((s, v) => s + v.population, 0), confidence: "real", villages: hits.length };
  const ref = state ? stateRef(state) : null;
  if (!ref) return { population: null, confidence: "estimated", villages: 0 };
  return { population: Math.round(Math.PI * radiusKm ** 2 * ref.density), confidence: "estimated", villages: 0 };
}

export function marketReach(location: LocationCandidate | null, sector: string | null): MarketReachIntel {
  const intel: MarketReachIntel = {
    confidence: "estimated", sources: [], limitations: [], radiusKm: RADIUS_KM,
    population: null, consumerBase: null, households: null, places: [],
  };
  if (!location) {
    intel.limitations.push(msg("c2.reach.noLocation"));
    return intel;
  }
  const coarse = location.method === "state_centroid";
  const state = location.district.state;
  let pop: PopulationEstimate;
  if (coarse) {
    const ref = stateRef(state);
    pop = { population: ref ? Math.round(Math.PI * RADIUS_KM ** 2 * ref.density) : null, confidence: "estimated", villages: 0 };
    intel.limitations.push(msg("c2.reach.coarseLocation"));
  } else {
    pop = populationWithinRadius(location.lat, location.lon, RADIUS_KM, state);
  }
  if (pop.population === null) {
    intel.limitations.push(msg("c2.reach.noPopulation", { state }));
  } else if (pop.confidence === "real") {
    intel.sources.push(src(`Village population table: ${pop.villages} villages within ${RADIUS_KM} km`, `गाँव जनसंख्या तालिका: ${RADIUS_KM} किमी में ${pop.villages} गाँव`, "real"));
    intel.limitations.push(msg("c2.reach.censusDated"));
  } else {
    intel.sources.push(src(`State density × area (${state})`, `राज्य जनघनत्व × क्षेत्रफल (${state})`, "estimated"));
    intel.limitations.push(msg("c2.reach.stateDensity"));
  }
  if (pop.population !== null) {
    const share = (sector && CATCHMENT_SHARE[sector]) || DEFAULT_CATCHMENT_SHARE;
    intel.population = pop.population;
    intel.consumerBase = Math.round(pop.population * share);
    intel.households = Math.round(pop.population / HOUSEHOLD_SIZE);
    intel.sources.push(src(`Catchment share ${share * 100}% and household size ${HOUSEHOLD_SIZE} (planning assumptions)`, `पहुँच हिस्सा ${share * 100}% और परिवार आकार ${HOUSEHOLD_SIZE} (योजना अनुमान)`, "estimated"));
  }

  const coords = usableCoords(location);
  if (!coords) {
    intel.limitations.push(msg("c2.reach.placesSkipped"));
  } else {
    intel.places = poisNear(coords.lat, coords.lon, RADIUS_KM, (p) => PLACE_KINDS.includes(p.kind)).slice(0, MAX_POINTS);
    intel.sources.push(src(`Mapped places table: ${intel.places.length} within ${RADIUS_KM} km`, `स्थान तालिका: ${RADIUS_KM} किमी में ${intel.places.length}`, "real"));
    if (!intel.places.length) intel.limitations.push(msg("c2.reach.noPlaces", { km: RADIUS_KM }));
  }
  intel.confidence = pop.population !== null && pop.confidence === "real" && location.method === "village_table" ? "real" : "estimated";
  return intel;
}
