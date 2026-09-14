import type { ComponentType } from "react";
import type { Route } from "../nav";
import Home from "./Home";
import Assistant from "./Assistant";
import Plan from "./Plan";
import Business from "./Business";
import More from "./More";
import Analysis from "./Analysis";
import Report from "./Report";
import Review from "./Review";
import MapScreen from "./MapScreen";
import Scheme from "./Scheme";
import Documents from "./Documents";
import Application from "./Application";
import Roadmap from "./Roadmap";
import Monitoring from "./Monitoring";
import Warning from "./Warning";
import Grievance from "./Grievance";
import Community from "./Community";
import Agency from "./Agency";
import Architecture from "./Architecture";
import Shortlist from "./Shortlist";
import Outcome from "./Outcome";
import Privacy from "./Privacy";
import Timeline from "./Timeline";
import Udyam from "./Udyam";
import Earnings from "./Earnings";
import Languages from "./Languages";
import Survey from "./Survey";
import Evidence from "./Evidence";
import NoViable from "./NoViable";

/** Route name → screen component. */
export const SCREENS: Record<Route["name"], ComponentType> = {
  home: Home,
  assistant: Assistant,
  plan: Plan,
  business: Business,
  more: More,
  analysis: Analysis,
  report: Report,
  review: Review,
  map: MapScreen,
  scheme: Scheme,
  documents: Documents,
  application: Application,
  roadmap: Roadmap,
  monitoring: Monitoring,
  warning: Warning,
  grievance: Grievance,
  community: Community,
  agency: Agency,
  architecture: Architecture,
  shortlist: Shortlist,
  outcome: Outcome,
  privacy: Privacy,
  timeline: Timeline,
  udyam: Udyam,
  earnings: Earnings,
  languages: Languages,
  survey: Survey,
  evidence: Evidence,
  noViable: NoViable,
};
