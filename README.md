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

## What's actually implemented

| | |
|---|---|
| `module1_feasibility/market_reach_agent.py` | Geocode → LGD disambiguation → Census population radius query → Overpass POI query |
| `module1_feasibility/opportunity_agent.py` | RAG retrieval over a sector-report corpus → saturation classification (POI-density proxy, since no Competitor Agent exists yet) |
| `orchestrator/state.py` | Full `CaseState` schema (Section 3), matching the design doc, so this build is structurally compatible with the other agents if they're added later |
| `orchestrator/graph.py` | A 2-node LangGraph `StateGraph`: `market_reach → opportunity` |
| `data_connectors/{geocoding,census,overpass}.py` | The three data connectors these two agents need |
| `rag/{vector_store,ingest_sector_reports}.py` | FAISS + TF-IDF retrieval pipeline for the Opportunity Agent |
| `run_pipeline.py` | CLI to run both agents end-to-end against one profile |
| `tests/` | Offline, network-free tests for both agents and the full graph (6 tests, all passing) |

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

All 6 tests run fully offline against canned Nominatim/Overpass responses
(see `tests/conftest.py` and the fixtures in each test file), so they never
depend on network access, live rate limits, or real data files.

## Important caveats before using this on anything real

**Sample data only.** `data/census/sample_villages.csv`,
`data/lgd/sample_lgd_codes.csv`, and every file in
`data/reference_corpus/` are synthetic fixtures written for this
prototype — not real Census, LGD, or NABARD/KVIC data. Every module that
reads them says so in its docstring and tags its output
`source_confidence: "estimated"` accordingly. See `IMPLEMENTATION_PLAN.md`
Sections 3–4 for exactly what has to be sourced/curated to replace them.

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
