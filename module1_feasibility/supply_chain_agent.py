"""Supply Chain Agent (TDD 5.3; TECHNICAL_SETUP.md 5.8).

Models the chain as a ``networkx`` DiGraph: catalog key inputs -> (located suppliers)
-> enterprise -> logistics -> catalog buyers. When live OSM data is available and the
location is resolved below state level, real supplier/market POIs within
``SUPPLIER_RADIUS_KM`` are attached with haversine distances ("real"); otherwise
nodes are generic role names ("estimated") -- no business names are invented.

Vulnerabilities are structural: articulation points of the undirected view (other
than the enterprise itself) are single points of failure, as are a single buyer
channel or exactly one located supplier; perishable output
adds a lead-time vulnerability. Lead times are not derivable from open data here
and stay ``None``.

Reads: state.business_shortlist, state.entrepreneur_profile.location
Writes: state.supply_chain_intel
Tech: networkx graph traversal (articulation points, degree dependencies), OSM Overpass supplier POIs, haversine distance.
"""

from __future__ import annotations

from typing import Any

import networkx as nx

from common.net import DataUnavailable
from common.reference import get_activity, haversine_km
from data_connectors import overpass
from module1_feasibility.competitor_agent import usable_coordinates
from orchestrator.state import CaseState, DataSourceRef, LocationDetails, SupplyChainIntelligence, SupplyEdge, SupplyNode

SUPPLIER_TAGS: list[tuple[str, str]] = [("shop", "agrarian"), ("shop", "wholesale"), ("shop", "hardware"), ("amenity", "marketplace")]
SUPPLIER_RADIUS_KM = 25.0
LOCAL_KM = 10.0
MAX_SUPPLIERS = 5
ENTERPRISE = "Enterprise"
LOGISTICS = "Road transport to buyers"


def locate_suppliers(loc: LocationDetails) -> tuple[list[dict], str]:
    """Nearest named supplier/market POIs as ``{name, distance_km, tag}``; raises ``DataUnavailable``."""
    coords = usable_coordinates(loc)
    if coords is None:
        raise DataUnavailable("location not resolved below state level; supplier search skipped")
    pois = overpass.query_pois(coords[0], coords[1], int(SUPPLIER_RADIUS_KM * 1000), SUPPLIER_TAGS)
    found = []
    for p in pois:
        if not p.get("name") or p.get("lat") is None or p.get("lon") is None:
            continue
        tags = p.get("tags") or {}
        kind = next((f"{k}={v}" for k, v in SUPPLIER_TAGS if tags.get(k) == v), "supplier")
        found.append({"name": p["name"], "distance_km": round(haversine_km(coords[0], coords[1], p["lat"], p["lon"]), 2), "tag": kind})
    found.sort(key=lambda s: s["distance_km"])
    return found[:MAX_SUPPLIERS], f"{len(pois)} OSM features within {SUPPLIER_RADIUS_KM:g} km, {len(found)} named"


def build_graph(activity: dict[str, Any], suppliers: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_node(ENTERPRISE, role="enterprise", confidence="estimated", distance_km=None)
    for item in activity.get("key_inputs") or []:
        g.add_node(item, role="input_supplier", confidence="estimated", distance_km=None)
        g.add_edge(item, ENTERPRISE, transport_mode="road")
    for s in suppliers:  # located suppliers feed the enterprise directly (inputs they carry are not known)
        g.add_node(s["name"], role="input_supplier", confidence="real", distance_km=s["distance_km"])
        g.add_edge(s["name"], ENTERPRISE, transport_mode="road")
    g.add_node(LOGISTICS, role="logistics", confidence="estimated", distance_km=None)
    g.add_edge(ENTERPRISE, LOGISTICS, transport_mode="road")
    for buyer in activity.get("buyers") or []:
        g.add_node(buyer, role="buyer", confidence="estimated", distance_km=None)
        g.add_edge(LOGISTICS, buyer, transport_mode="road")
    return g


def single_points_of_failure(g: nx.DiGraph) -> list[str]:
    """Cut vertices (excluding the enterprise) plus degree-1 dependencies."""
    spof = [n for n in nx.articulation_points(g.to_undirected()) if n != ENTERPRISE]
    buyers = [n for n, d in g.nodes(data=True) if d["role"] == "buyer"]
    if len(buyers) == 1:
        spof.append(buyers[0])
    real_suppliers = [n for n, d in g.nodes(data=True) if d["role"] == "input_supplier" and d["confidence"] == "real"]
    if len(real_suppliers) == 1:
        spof.append(real_suppliers[0])
    return sorted(set(spof))


def run(state: CaseState) -> dict[str, Any]:
    candidate = state.selected_candidate()
    activity = get_activity(candidate.catalog_id) if candidate and candidate.catalog_id else None
    profile = state.entrepreneur_profile
    loc = profile.location if profile else LocationDetails()
    if activity is None:
        return {"supply_chain_intel": SupplyChainIntelligence(
            data_source_detail="No catalog activity selected.",
            limitations=["No catalog activity selected; supply chain not assessed."])}

    limitations: list[str] = []
    sources = [DataSourceRef(name="Business catalog inputs and buyers", source_confidence="estimated",
                             detail="generic chain roles (planning assumption)")]
    suppliers: list[dict] = []
    availability = "unknown"
    osm_ok = False
    try:
        suppliers, detail = locate_suppliers(loc)
        osm_ok = True
        sources.append(DataSourceRef(name="OpenStreetMap Overpass (suppliers/markets)", source_confidence="real", detail=detail))
        if suppliers:
            availability = "locally_available" if suppliers[0]["distance_km"] <= LOCAL_KM else "regionally_available"
        else:
            limitations.append(f"No named supplier or market found in OSM within {SUPPLIER_RADIUS_KM:g} km; this may "
                               "reflect sparse OSM coverage, so input availability is unknown.")
    except DataUnavailable as exc:
        limitations.append(f"Supplier lookup unavailable ({exc}); chain uses generic roles and no named suppliers.")
    except Exception as exc:  # unexpected connector failure: degrade
        limitations.append(f"Supplier lookup failed ({exc.__class__.__name__}); chain uses generic roles.")

    g = build_graph(activity, suppliers)
    spof = single_points_of_failure(g)
    vulnerabilities = [f"Single point of failure: '{n}' ({g.nodes[n]['role']})" for n in spof]
    if activity.get("perishable"):
        vulnerabilities.append("Perishable output: any transport delay or cold-chain gap directly causes spoilage losses.")
    if osm_ok and not suppliers:
        vulnerabilities.append("No located input supplier nearby; supply sourcing must be verified on the ground.")
    limitations.append("Lead times are not derivable from open data here; lead_time_days left unknown.")

    alternates = [f"{s['name']} ({s['tag']}, {s['distance_km']} km)" for s in suppliers[1:]]
    intel = SupplyChainIntelligence(
        raw_material_availability=availability,
        nodes=[SupplyNode(name=n, role=d["role"], distance_km=d["distance_km"], source_confidence=d["confidence"])
               for n, d in g.nodes(data=True)],
        edges=[SupplyEdge(source=u, target=v, transport_mode=d.get("transport_mode", "")) for u, v, d in g.edges(data=True)],
        major_suppliers=[s["name"] for s in suppliers],
        transport_modes=["road"],
        lead_time_days=None,
        single_points_of_failure=spof,
        critical_vulnerabilities=vulnerabilities,
        alternate_sources=alternates,
        source_confidence="estimated",  # the chain itself is modelled; located suppliers are labeled per node
        data_source_detail=(f"{len(suppliers)} located suppliers attached to a modelled chain" if suppliers
                            else "Modelled chain from catalog inputs and buyers (generic roles)"),
        sources=sources,
        limitations=limitations,
    )
    return {"supply_chain_intel": intel}

