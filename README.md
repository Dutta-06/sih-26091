# Hyper-Local Business Advisory — Module 1 Local Intelligence (partial)

Scratch-built implementation of three of the six Module 1 "local
intelligence" agents from the Technical Design Document (Section 5.3):

- **Competitor Agent** (`src/agents/competitor_agent.py`)
- **Pricing Agent** (`src/agents/pricing_agent.py`)
- **Supply Chain Agent** (`src/agents/supply_chain_agent.py`)

Orchestrated with **LangGraph** as a parallel fan-out / fan-in graph
(`src/graph.py`), writing into a single shared case-state object
(`src/schemas.py::CaseState`) modeled on TDD Section 9.

## Scope and what is intentionally NOT here

This is a from-scratch build — there was no existing repository to extend.
Only the three requested agents, the state model, and the orchestration
seam around them are implemented. Market Reach, Opportunity, Risk, the
SWOT synthesis, adversarial review, and everything in Modules 2 and 3 are
**not implemented**. `MarketIntelligence` is deliberately left open
(`extra="allow"`) so those agents can attach their own keys later without
touching this code.

## Blocking gaps in the data layer (documented, not papered over)

The TDD names several data sources in Section 8 without giving concrete
endpoints, resource ids, or credentials. Per the "never fabricate" rule,
those adapters are implemented as real interfaces that **require deployer
-supplied configuration** and return `INSUFFICIENT_DATA` until it's
provided, rather than pretending to have working defaults:

| Source (TDD Section 8) | Reality | What you must supply |
|---|---|---|
| Udyam Registration open dataset | No public live-query API exists | `UDYAM_DATASET_PATH` — a bulk CSV/Parquet extract |
| Government commodity price open data API | Category named, not a specific dataset | `DATA_GOV_IN_API_KEY` + `COMMODITY_PRICE_RESOURCE_ID` |
| SECC asset data (purchasing-power proxy) | No public live-query API exists | `SECC_DATASET_PATH` — a bulk extract |
| Open-source routing engine | Diagram names OSRM but not a host | Defaults to the public OSRM **demo** server (rate-limited, not production-safe); set `OSRM_BASE_URL` to your own instance |

Two sources are real, public, and keyless out of the box, no setup needed:
**OpenStreetMap Overpass API** and (with the above OSRM caveat) routing.

The **web-search extraction fallback tier** shown in the architecture
diagram's Competitor Agent tech note is not implemented — no web-search
provider is wired into this codebase, and guessing one would mean
fabricating an API. It's a documented gap; the agent returns
`INSUFFICIENT_DATA` for that tier explicitly.

## Confidence labeling

Every agent output carries `confidence: REAL_DATA | ESTIMATED |
INSUFFICIENT_DATA` plus a `limitations` list explaining exactly why, per
TDD Section 2 ("Confidence-labeled outputs"). Nothing in this codebase
invents a number to fill a gap — every numeric field is either sourced
from a real adapter response or explicitly `None`.

## Running

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in what you have; everything else degrades to INSUFFICIENT_DATA
pytest -q
```

All 13 tests run fully offline against mocked adapters — no network calls
happen during `pytest`.

## Using the graph

```python
from src.graph import run_market_intelligence
from src.schemas import CaseState, SelectedBusiness

case_state = CaseState(
    case_id="case-001",
    entrepreneur_profile={
        "location": {
            "district": "Meerut", "state": "Uttar Pradesh",
            "latitude": 28.9845, "longitude": 77.7064,
        },
        "available_capital": 150000,
    },
    selected_business=SelectedBusiness(name="Grocery", sector="grocery"),
)

updated_state = await run_market_intelligence(
    case_state,
    commodity=None,               # set for agricultural commodities
    base_reference_price=None,    # required for the pricing ESTIMATED tier
)
print(updated_state.market_intelligence.competitor)
print(updated_state.market_intelligence.pricing)
print(updated_state.market_intelligence.supply_chain)
```

## Persistence

`src/state_store.py::InMemoryCaseStateStore` is a **dev/test placeholder
only** — it does not survive a process restart. TDD Section 4.1 requires
checkpointing across gaps of days or months; swap in a real
`CaseStateStore` implementation (e.g. a database-backed store, or a
LangGraph durable checkpointer) before this goes anywhere near production.
