/**
 * On-device core contract. The app computes its advice locally from bundled data files, mirroring the
 * Python backend (orchestrator + module1/2/3). No network calls and no external APIs.
 *
 * Text shown to users is never produced here as prose: results carry i18n keys + vars (`Msg`) or bilingual
 * data (`Bi`) so the UI renders them in the chosen language.
 */
import type { DebtServicePreview, Plan, Scenario } from "../engine/finance";
import type { Bi } from "../i18n";

export type Confidence = "real" | "estimated";
export type Level = "low" | "medium" | "high";
export type Saturation = Level | "unknown";
export type Verdict = "viable" | "marginal" | "not_recommended";

/** A translatable message: i18n key + variables (numbers are formatted by the UI). */
export interface Msg {
  key: string;
  vars?: Record<string, string | number>;
}

export interface SourceRef {
  name: Bi;
  confidence: Confidence;
}

export interface IntelMeta {
  confidence: Confidence;
  sources: SourceRef[];
  limitations: Msg[];
}

/* ------------------------------------------------------------------ Data pack (src/core/data/*.json) */

export interface PackVillage {
  lgd: string; // Local Government Directory code
  name: Bi;
  block: Bi;
  district: string; // district id
  lat: number;
  lon: number;
  population: number; // Census-style village population
}

export interface PackDistrict {
  id: string;
  name: Bi;
  aliases: string[]; // all scripts, lower-case matching
  state: string; // state name (English, key of state reference)
  lat: number;
  lon: number;
  population: number;
  areaSqKm: number;
}

export interface PackPoi {
  id: string;
  name: Bi;
  kind: "market" | "haat" | "transport" | "school" | "supplier" | "bank" | "enterprise";
  tags: [string, string][]; // OSM-style key/value tags, e.g. ["shop","tailor"]
  lat: number;
  lon: number;
}

export interface PackUdyam {
  district: string;
  nic: string; // 4-digit NIC class
  count: number; // registered enterprises in district for the class
}

export interface PackPriceSeries {
  commodity: string;
  state: string;
  months: { month: string; modal: number }[]; // "YYYY-MM", ≥ 24 months when present
}

export interface PackFeedback {
  id: string;
  kind: "funded_entrepreneur" | "resident_survey";
  district: string;
  activityId: string | null;
  topic: "demand" | "pricing" | "supply" | "seasonality" | "competition" | "other";
  rating: number | null;
  text: Bi;
  who: Bi;
  monthsInBusiness?: number;
}

export interface PackDoc {
  collection: "sector_reports" | "risk_taxonomy" | "scheme_guidelines";
  source: string; // file name in the repo data/ folder
  heading: string;
  text: string; // English source text (documents are English in the repo)
}

export interface OutcomeRecord {
  catalog_id: string;
  district: string | null;
  intervention_type: "pricing_adjustment" | "supply_chain_change" | "mentor_outreach" | "repayment_counselling";
  health_before: number;
  health_after: number;
  is_synthetic: boolean;
}

/* ------------------------------------------------------------------ Inputs */

export interface ProfileInput {
  capital: number;
  locationText: string;
  locationCode: string | null; // chosen LGD code after disambiguation
  activityId: string | null;
  reason: string | null;
  skills: string[]; // skill ids: stitching, embroidery, weaving, cooking, livestock, retail, repair, beauty
  assets: string[];
  premises: "home" | "rented_shop" | "own_land" | null;
  category: "sc" | "st" | "obc" | "general" | null;
  womanOwned: boolean;
  shgMember: boolean;
}

/* ------------------------------------------------------------------ NLU (src/core/nlu.ts) */

export type Slot = "location" | "capital" | "activity" | "reason" | "skills" | "premises" | "category";
export type Intent =
  | "provide_info"
  | "new_case"
  | "raise_grievance"
  | "application_status"
  | "scheme_inquiry"
  | "monitoring"
  | "community"
  | "change_language"
  | "greeting"
  | "unknown";

export interface Extraction {
  capital?: number;
  locationText?: string;
  activityId?: string;
  reason?: string;
  skills?: string[];
  premises?: ProfileInput["premises"];
  category?: ProfileInput["category"];
  shgMember?: boolean;
  language?: "en" | "hi" | "bn" | "mr" | "ta";
}

/* ------------------------------------------------------------------ Location (src/core/geo.ts) */

export interface LocationCandidate {
  lgd: string | null;
  village: Bi | null;
  block: Bi | null;
  district: PackDistrict;
  lat: number;
  lon: number;
  method: "village_table" | "district_table" | "state_centroid";
}

export interface ResolvedLocation {
  query: string;
  candidates: LocationCandidate[]; // >1 means the user must choose (TDD 5.3 disambiguation)
  chosen: LocationCandidate | null;
  confidence: Confidence; // real only for a village-table match
  limitations: Msg[];
}

/* ------------------------------------------------------------------ Module 1 */

export interface ScoreBreakdown {
  capitalFit: number; // /20
  repayment: number; // /30
  skills: number; // /20
  localDemand: number; // /20
  outcomes: number; // /10
}

export interface RankedActivity {
  activityId: string;
  score: number; // 0-100
  breakdown: ScoreBreakdown;
  feasible: boolean;
  infeasibleReason: Msg | null;
  isPreference: boolean;
  adjacentTo: string | null;
  preview: DebtServicePreview;
  crowding: Saturation;
}

export interface MarketReachIntel extends IntelMeta {
  radiusKm: number;
  population: number | null;
  consumerBase: number | null;
  households: number | null;
  places: { poi: PackPoi; km: number }[];
}

export interface SubNicheIntel {
  name: string; // heading text from the retrieved sector document
  detail: string;
  source: string;
  relevance: number;
  saturation: Saturation;
  evidenceIds: string[]; // PackFeedback ids that support/contradict it
}

export interface OpportunityIntel extends IntelMeta {
  niches: SubNicheIntel[];
  saturation: Saturation;
}

export interface CompetitorIntel extends IntelMeta {
  tier: "udyam" | "overpass" | "none";
  tiersAttempted: { tier: "udyam" | "overpass" | "web_search"; status: "used" | "no_data" | "unavailable" }[];
  count: number | null; // within radius (POI tier) or district (Udyam tier)
  nearby: { poi: PackPoi; km: number }[];
  densityPer10k: number | null;
  districtPer10k: number | null;
  statePer10k: number | null;
  zScore: number | null;
  saturation: Saturation;
}

export interface PricePointIntel {
  label: Bi;
  low: number;
  high: number;
  unit: Bi | string;
  confidence: Confidence;
}

export interface PricingIntel extends IntelMeta {
  basis: "direct_market_data" | "purchasing_power_proxy" | "unavailable";
  points: PricePointIntel[];
  targetPrice: number | null;
  purchasingPowerIndex: number | null;
  history: { month: string; modal: number }[];
}

export interface RiskFlagIntel {
  id: string; // taxonomy id or "route_distance" / "seasonal_demand_variation" / "local_feedback"
  category: "route" | "seasonal" | "structural" | "local_feedback";
  severity: Level;
  title: Msg;
  detail: Msg;
  mitigation: string | null; // from the taxonomy document (English) or null
  confidence: Confidence;
}

export interface RiskIntel extends IntelMeta {
  overall: Level;
  hubKm: number | null;
  hubName: Bi | null;
  routeMethod: "haversine_estimate" | "unavailable";
  seasonalIndex: number[]; // 12 values, mean 1
  seasonalBasis: "price_history" | "catalog_profile";
  lowMonths: number[]; // 0-11
  flags: RiskFlagIntel[];
}

export interface SupplyChainIntel extends IntelMeta {
  nodes: { id: string; label: Bi | string; role: "input" | "enterprise" | "logistics" | "buyer"; km: number | null; confidence: Confidence }[];
  edges: { from: string; to: string }[];
  singlePointsOfFailure: string[]; // node ids
  suppliers: { poi: PackPoi; km: number }[];
}

export interface Intel {
  marketReach: MarketReachIntel;
  opportunity: OpportunityIntel;
  competitor: CompetitorIntel;
  pricing: PricingIntel;
  risk: RiskIntel;
  supplyChain: SupplyChainIntel;
}

export interface Swot {
  strengths: Msg[];
  weaknesses: Msg[];
  opportunities: Msg[];
  threats: Msg[];
}

export interface ReviewFinding {
  rule: "R1" | "R2" | "R3" | "M1" | "M2" | "M3" | "M4";
  msg: Msg;
}

export interface FeasibilityAttempt {
  activityId: string;
  intel: Intel;
  swot: Swot;
  verdict: Verdict;
  findings: ReviewFinding[];
  notes: Msg[];
  preview: DebtServicePreview;
  score: number; // feasibility score 0-100 for display
}

export interface FeasibilityResult {
  attempts: FeasibilityAttempt[]; // in order; last is the selected or final one
  selected: FeasibilityAttempt | null; // first viable attempt
  exhausted: boolean;
  shortlist: RankedActivity[];
}

/* ------------------------------------------------------------------ Module 2 */

export interface EarningsStep {
  id: "project" | "base" | "pricing" | "reach" | "surplus" | "coverage" | "seasons";
  value: number;
  factor?: number;
  applied: boolean;
  confidence: Confidence;
}

export interface FinancialResult {
  plan: Plan;
  preview: DebtServicePreview;
  scenarios: { id: "low_season" | "price_drop" | "input_cost"; result: Scenario }[];
  earnings: EarningsStep[];
  budget: { item: Bi | string; amount: number }[]; // project cost split over catalog key inputs + working capital
  policy: { tier: string | null; rules: PackDoc[]; documents: string[]; steps: string[] };
}

export type DocStatus = "complete" | "pending" | "missing";
export type AppStage = "not_started" | "documents_pending" | "submitted" | "under_verification" | "sanctioned" | "disbursed" | "rejected";

/* ------------------------------------------------------------------ Module 3 */

export interface Transaction {
  at: string; // ISO date
  direction: "credit" | "debit";
  amount: number;
  channel: "upi" | "neft_imps" | "cash_deposit" | "card" | "atm" | "other";
  isLoanRepayment: boolean;
}

export interface HealthSnapshot {
  month: string; // YYYY-MM
  revenue: number;
  expenses: number;
  planned: number;
  surplus: number;
  score: number;
  band: "healthy" | "watch" | "at_risk";
  components: { revenueVsPlan: number; coverage: number; repayment: number };
  earlyWarning: boolean;
  intervention: OutcomeRecord["intervention_type"] | null;
  creditIndex: number | null;
}

export interface InterventionOption {
  type: OutcomeRecord["intervention_type"];
  successRate: number;
  real: number;
  synthetic: number;
  improved: number;
  total: number;
}

export interface GrievanceTicket {
  id: string;
  issue: "supply_delay" | "pricing_collapse" | "machinery_breakdown" | "loan_repayment_stress" | "other";
  text: string;
  routedTo: Msg; // mentor role
  responseHours: number;
  status: "open" | "mentor_assigned" | "in_progress" | "resolved";
  at: string;
}
