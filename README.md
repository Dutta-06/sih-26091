# rural-advisory-agents — Market Reach Agent + Opportunity Agent

A two-agent build extracted from the full *Hyper-Local Business Advisory and
Financial Structuring Platform* design. This repository implements **only**
the **Market Reach Agent** and **Opportunity Agent** (design doc Section
5.3), wired as LangGraph nodes so they drop into the full system's
orchestrator later without a rewrite.

Read these two documents first — together they define what's actually
built here and why:

- **`IMPLEMENTATION_PLAN.md`** — scope, feasibility findings on every data
  source, the two-agent dependency gap and how it's resolved, and the
  phased build plan.
- **`TECHNICAL_SETUP.md`** — the full system's intended repo structure,
  state schema, and setup steps for *every* agent (most not built here);
  this repo's file layout mirrors it exactly for the two agents that are.

## Status at a glance: real vs. fallback

Both agents' code is done and tested (18 tests, all passing). What each
agent's *output* is actually built on varies piece by piece:

| Agent | Component | Status | Note |
|---|---|---|---|
| Market Reach | Agent code / LangGraph node | ✅ Done | Built, tested, wired into the graph |
| Market Reach | Geocoding (Nominatim) | ✅ Real | Live public API call; not fake data, just unverified end-to-end from this build's sandbox (no network access to it there) |
| Market Reach | POI lookup (Overpass) | ✅ Real | Same as above — real live API, same sandbox caveat |
| Market Reach | LGD disambiguation | 🟡 Real path added, needs your key | `LGD_API_ENABLED` calls the live NAPIX API, but NAPIX is subscribe-and-approve, not instant, and its exact endpoint shape is unverified — see below. Local CSV fallback is still a fake 2-row fixture until you download the real LGD directory |
| Market Reach | Population (Census) | 🟡 Real path added, needs setup | `census.py --build-index` joins real data.gov.in population with real SHRUG centroids — but needs your API key, your resource IDs, and a manually-downloaded SHRUG file first. Falls back to a fake 11-village fixture until then |
| Opportunity | Agent code / LangGraph node | ✅ Done | Built, tested, wired into the graph |
| Opportunity | Retrieval mechanism (FAISS + TF-IDF) | ✅ Done | Real, functional RAG pipeline — works correctly on whatever content you give it |
| Opportunity | Sector report corpus | 🔴 Fallback, no fix path | 4 short text files I invented — not real NABARD/KVIC reports. No API exists for this at all; only fix is manually downloading the real PDFs |
| Opportunity | Saturation classification | 🔴 Fallback method | Uses an OSM POI-density proxy instead of a real Competitor Agent (not built); also inherits Market Reach's population number, real or fake depending on the above |

The "Making the population/geocoding data real" section below has the exact setup steps for each 🟡 row.

## What's actually implemented

| | |
|---|---|
| `module1_feasibility/market_reach_agent.py` | Geocode → LGD disambiguation → Census population radius query → Overpass POI query |
| `module1_feasibility/opportunity_agent.py` | RAG retrieval over a sector-report corpus → saturation classification (POI-density proxy, since no Competitor Agent exists yet) |
| `orchestrator/state.py` | Full `CaseState` schema (Section 3), matching the design doc, so this build is structurally compatible with the other agents if they're added later |
| `orchestrator/graph.py` | A 2-node LangGraph `StateGraph`: `market_reach → opportunity` |
| `data_connectors/{geocoding,census,overpass}.py` | The three data connectors these two agents need |
| `data_connectors/datagovin.py` | Generic data.gov.in API client (free, self-serve) — pulls real Census population records |
| `data_connectors/shrug.py` | Loads real village centroid coordinates from a manually-downloaded SHRUG file (raw Census data has no lat/lon) |
| `census.py --build-index` | Joins the two above into a real `CENSUS_DATA_PATH` CSV, replacing the sample fixture |
| LGD live API path in `geocoding.py` | Optional NAPIX API call for LGD disambiguation, gated behind `LGD_API_ENABLED` — see caveats below |
| `rag/{vector_store,ingest_sector_reports}.py` | FAISS + TF-IDF retrieval pipeline for the Opportunity Agent |
| `run_pipeline.py` | CLI to run both agents end-to-end against one profile |
| `tests/` | Offline, network-free tests for both agents, the full graph, and the new API connectors (18 tests, all passing) |

Everything else in `TECHNICAL_SETUP.md`'s structure (other agents, Modules
2–3, the conversational orchestrator, checkpointing, multilingual layer) is
**not built** — see `IMPLEMENTATION_PLAN.md` Section 2 for the exact scope
boundary.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp config/.env.example config/.env                   # defaults already work out of the box
```

## Running

```bash
# Compile-check the graph
python -m orchestrator.graph --dry-run

# Run both agents end-to-end against a sample profile
python run_pipeline.py --location "Sample Village A" --category dairy
```

`run_pipeline.py` calls the **live public** Nominatim and Overpass
endpoints — see the network note below before relying on this against a
real location.

## Testing

```bash
python -m pytest -v
```

All 18 tests run fully offline against canned Nominatim/Overpass/data.gov.in
responses and local fixture files (see `tests/conftest.py` and the fixtures
in each test file), so they never depend on network access, live rate
limits, real API keys, or real data files.

## Making the population/geocoding data real

`data/census/sample_villages.csv`, `data/lgd/sample_lgd_codes.csv`, and
every file in `data/reference_corpus/` still ship as synthetic fixtures —
but real-data paths now exist for two of the three:

- **Census population**: run `python -m data_connectors.census --build-index`
  after setting `DATA_GOV_IN_API_KEY` (free signup at data.gov.in),
  `CENSUS_RESOURCE_IDS` (the resource_id for each state/district's Census
  2011 dataset — look it up on that dataset's own data.gov.in catalog page),
  and `SHRUG_KEYS_CSV_PATH` (a centroid file you download once from
  devdatalab.org/shrug_download — SHRUG is free but I couldn't confirm a
  stable, unauthenticated auto-download URL for it, so this is a manual
  download, not something the code fetches itself). This replaces
  `sample_villages.csv` with real population figures joined to real
  coordinates on the shared Census village code.
- **LGD disambiguation**: two options. `LGD_API_ENABLED=true` +
  `LGD_API_KEY` calls the live NAPIX LGD API — but NAPIX is a
  subscribe-and-approve government platform, not an instant key, and I
  couldn't reach napix.gov.in to confirm the exact endpoint shape, so
  `_lookup_lgd_via_api()` in `geocoding.py` is written to a best-guess
  contract that needs checking against your own NAPIX Consumer Guidelines
  PDF once you have access. The simpler route: download the real LGD
  directory CSV from lgdirectory.gov.in (free, no approval) and replace
  `data/lgd/sample_lgd_codes.csv` directly — no code change needed.
- **Sector report corpus**: still fully manual — no API exists for
  NABARD/KVIC reports at all. Download the PDFs yourself and drop them in
  `data/reference_corpus/`, then rerun `python -m rag.ingest_sector_reports`.

Every one of these degrades gracefully: if the new settings aren't
configured, everything falls back to exactly what it did before (the
sample fixtures), so the project still runs out of the box either way.

**Live network access wasn't verified from this build environment** — the
sandbox this was built in only permits an allowlisted set of hosts, and
`nominatim.openstreetmap.org` / `overpass-api.de` aren't on it, so
`run_pipeline.py`'s live-API path is untested end-to-end here (the offline
tests cover the actual agent logic instead). Confirm connectivity to both
endpoints from wherever you actually deploy this before relying on it.

**A LangGraph + Pydantic gotcha worth knowing if you extend this graph:**
with the installed LangGraph version (0.2.x) and a Pydantic `BaseModel` as
the state schema, a node that only *mutates* a nested field (e.g.
`state.market_intelligence.market_reach = output`) without reassigning the
top-level field is silently dropped when LangGraph merges the node's return
value back into graph state — Pydantic doesn't mark a field "set" just
because something nested inside it changed. Both agents here work around
this by reassigning the top-level field explicitly
(`state.market_intelligence = market_intelligence`); see the comment in
`orchestrator/graph.py` and in each agent file. Any new node added to this
graph needs to follow the same pattern.

**Rate-limit discipline.** `data_connectors/geocoding.py` and
`overpass.py` both cache in-process and `geocoding.py` self-throttles to
Nominatim's documented 1 request/second ceiling. Both public endpoints'
usage policies discourage real production volume — see
`IMPLEMENTATION_PLAN.md` Section 3 for the self-hosting follow-up.
