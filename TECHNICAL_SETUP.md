# Technical Setup

This document describes how to set up, configure, and run the prototype locally. It is organized to mirror the architecture in the technical design document: one section per orchestration layer, and one subsection per agent or deterministic node, so that each feature unit in the design maps to exactly one setup section here.

> **Scope note (added):** This repository currently implements only the **Market Reach Agent** (5.3) and **Opportunity Agent** (5.4) sections below, plus the shared orchestration/state/config scaffolding needed to run them as LangGraph nodes. Every other section (all other agents, Modules 2 and 3, the multilingual layer, the FastAPI app) is documented here for future reference and integration compatibility, but is not built yet. See `IMPLEMENTATION_PLAN.md` for the two-agent build's scope and feasibility notes.

## Table of Contents

1. [Repository Structure](#1-repository-structure)
2. [Core Framework Setup](#2-core-framework-setup)
3. [Shared Case State Schema](#3-shared-case-state-schema)
4. [Orchestration Layer](#4-orchestration-layer)
5. [Module 1 — Profiling and Feasibility Assessment](#5-module-1-profiling-and-feasibility-assessment)
6. [Module 2 — Financial Structuring and Funding Preparation](#6-module-2-financial-structuring-and-funding-preparation)
7. [Module 3 — Launch and Post-Disbursement Monitoring](#7-module-3-launch-and-post-disbursement-monitoring)
8. [Data Source Provisioning](#8-data-source-provisioning)
9. [Running Locally](#9-running-locally)
10. [Evaluation Harness](#10-evaluation-harness)
11. [Contribution Conventions](#11-contribution-conventions)

---

## 1. Repository Structure

The repository is organized so that each agent or deterministic node from the design document has its own module, grouped by the module lane it belongs to. This keeps the codebase's structure traceable back to the architecture diagrams.

```
.
├── orchestrator/
│   ├── graph.py                  # LangGraph StateGraph definition, wires all nodes below
│   ├── router.py                 # intent classification, slot filling
│   ├── state.py                  # shared case state schema (Pydantic)
│   └── persistence.py            # checkpointing / session resume
│
├── module1_feasibility/
│   ├── profiling_agent.py
│   ├── discovery_agent.py
│   ├── market_reach_agent.py
│   ├── opportunity_agent.py
│   ├── risk_agent.py
│   ├── competitor_agent.py
│   ├── pricing_agent.py
│   ├── supply_chain_agent.py
│   ├── swot_synthesis.py
│   └── adversarial_review.py
│
├── module2_financial/
│   ├── financial_engine.py       # deterministic, no LLM calls
│   ├── financial_analyst_agent.py
│   ├── scenario_digital_twin.py
│   ├── policy_scheme_agent.py
│   ├── documentation_agent.py
│   └── application_tracker.py
│
├── module3_monitoring/
│   ├── procurement_coordinator.py
│   ├── launch_copilot.py
│   ├── ongoing_monitoring_agent.py
│   ├── health_score_agent.py
│   ├── grievance_engine.py
│   └── outcome_learning_loop.py
│
├── data_connectors/
│   ├── geocoding.py               # Nominatim + LGD disambiguation
│   ├── census.py                  # Census 2011 spatial lookup
│   ├── overpass.py                # OSM Overpass POI queries
│   ├── udyam.py                   # Udyam Registration dataset loader
│   ├── agmarknet.py                # data.gov.in commodity price API client
│   ├── osrm.py                     # routing distance client
│   ├── secc.py                     # SECC asset-index proxy loader
│   └── sms_parser.py               # on-device transaction notification parser (consent-gated)
│
├── rag/
│   ├── ingest_sector_reports.py    # NABARD / KVIC corpus ingestion
│   ├── ingest_risk_taxonomy.py
│   ├── ingest_scheme_docs.py       # scheme guideline RAG corpus
│   └── vector_store.py             # embedding + retrieval wrapper
│
├── synthetic_data/
│   └── seed_outcomes.py            # cold-start synthetic outcome generator (Section 9)
│
├── eval/
│   ├── harness.py
│   ├── golden_cases/
│   └── metrics.py
│
├── config/
│   ├── .env.example
│   └── settings.py
│
├── requirements.txt
└── TECHNICAL_SETUP.md
```

Each agent file exposes a single callable node function with the signature `def run(state: CaseState) -> CaseState`, so it can be registered directly as a LangGraph node without an adapter layer.

---
## 2. Core Framework Setup

Install the orchestration framework and confirm the graph compiles before wiring individual agents:

```bash
pip install langgraph langchain langchain-core pydantic
```

`orchestrator/graph.py` builds a `StateGraph` over the shared case state, registers every node from Modules 1–3, and defines the conditional edges described in the design document's control-flow summary (fan-out to the six parallel agents, fan-in to the shared state, the rejection loop back to business discovery, and the outcome-learning feedback loop). Run the following to verify the graph compiles without executing any agent logic:

```bash
python -m orchestrator.graph --dry-run
```

---
## 3. Shared Case State Schema

All agents read and write a single typed state object, defined in `orchestrator/state.py`. Each field below corresponds to one section of the state model in the design document:

```python
class CaseState(BaseModel):
    entrepreneur_profile: EntrepreneurProfile | None = None
    business_shortlist: list[BusinessCandidate] = []
    market_intelligence: MarketIntelligence | None = None      # 6-agent fan-in output
    feasibility_record: FeasibilityRecord | None = None
    financial_plan: FinancialPlan | None = None
    application_status: ApplicationStatus | None = None
    monitoring_record: list[HealthSnapshot] = []
    grievance_log: list[GrievanceEntry] = []
    session_meta: SessionMeta
```

Each `MarketIntelligence` sub-field (`market_reach`, `opportunity`, `risk`, `competitor`, `pricing`, `supply_chain`) carries a `source_confidence: Literal["real", "estimated"]` tag, as required by the design document's confidence-labeling principle. Define these sub-schemas before implementing any agent, since every agent module in Sections 7–9 imports from `orchestrator/state.py`.

---
## 4. Orchestration Layer

**Folder:** `orchestrator/`
**Files:** `graph.py`, `router.py`, `state.py`, `persistence.py`

| Setup step | Command / action |
|---|---|
| Install dependencies | `pip install langgraph langchain-core` |
| Define the state schema | implement `CaseState` per [Section 3](#3-shared-case-state-schema) |
| Implement intent routing | `router.py` — classify each incoming user turn as continue / jump / clarify |
| Wire the graph | `graph.py` — register all agent nodes, define conditional edges |
| Configure checkpointing | set `CHECKPOINT_BACKEND` and `CHECKPOINT_DB_URL` in `.env`; for a multi-day pilot use `postgres` instead of `sqlite` |
| Multilingual layer | install AI4Bharat models per [Section 8.9](#89-multilingual-layer-ai4bharat) before enabling voice input |

Verify session persistence works before building any agent:

```bash
python -m orchestrator.persistence --test-checkpoint
```

---
## 5. Module 1 — Profiling and Feasibility Assessment

**Folder:** `module1_feasibility/`

### 5.1 Entrepreneur Profiling Agent
- **File:** `profiling_agent.py`
- **Reads:** raw conversational input (text or ASR transcript)
- **Writes:** `state.entrepreneur_profile`
- **Tech:** LLM structured extraction (function-calling against a Pydantic schema) plus the Indic NLU pipeline from [Section 8.9](#89-multilingual-layer-ai4bharat)
- **Setup:** define the `EntrepreneurProfile` schema first; implement extraction as a single LLM call with the schema passed as the tool/function definition
- **Config:** uses `LLM_API_KEY` / `SELF_HOSTED_LLM_ENDPOINT` from `.env`

### 5.2 Business Discovery Agent
- **File:** `discovery_agent.py`
- **Reads:** `state.entrepreneur_profile`
- **Writes:** `state.business_shortlist`
- **Tech:** rule-based multi-factor scoring engine over market, cost, competition, and infrastructure signals
- **Setup:** implement `score_candidate(profile, category) -> float` as a pure function first, independent of any LLM call, so it can be unit-tested against fixed inputs
- **Dependency:** calls `data_connectors/overpass.py` and `data_connectors/census.py` for local signal inputs

### 5.3 Market Reach Agent
- **File:** `market_reach_agent.py`
- **Reads:** `state.business_shortlist` (selected candidate), `state.entrepreneur_profile.location`
- **Writes:** `state.market_intelligence.market_reach`
- **Tech:** Nominatim geocoding, LGD code disambiguation, spatial nearest-neighbor query (KD-tree/BallTree) over the Census 2011 population grid, Overpass QL for nearby markets
- **Setup:** see [Section 8.1](#81-geocoding-nominatim--lgd) through [8.3](#83-points-of-interest-osm-overpass)
- **Output contract:** `{ population_within_radius, distribution_points: list[POI], source_confidence }`

### 5.4 Opportunity Agent
- **File:** `opportunity_agent.py`
- **Reads:** `state.business_shortlist`, `state.market_intelligence.competitor` (for cross-checking)
- **Writes:** `state.market_intelligence.opportunity`
- **Tech:** RAG pipeline (embedding model plus a vector store) over the NABARD/KVIC sector report corpus; cosine-similarity retrieval; rule-based saturation classifier
- **Setup:** run `rag/ingest_sector_reports.py` once before first use — see [Section 8.6](#86-rag-corpus-ingestion)

### 5.5 Risk Agent
- **File:** `risk_agent.py`
- **Reads:** `state.market_intelligence` (partial, for cross-referencing)
- **Writes:** `state.market_intelligence.risk`
- **Tech:** OSRM shortest-path routing for supply-chain distance risk; `statsmodels.tsa.seasonal_decompose` on Agmarknet price history for seasonal demand risk; RAG over a curated risk-taxonomy knowledge base for structural risk
- **Setup:** requires OSRM running locally ([Section 8.5](#85-routing-osrm)) and the risk-taxonomy corpus ingested ([Section 8.7](#87-risk-taxonomy-knowledge-base))
- **Dependency:** `pip install statsmodels`

### 5.6 Competitor Agent
- **File:** `competitor_agent.py`
- **Reads:** `state.business_shortlist`, `state.entrepreneur_profile.location`
- **Writes:** `state.market_intelligence.competitor`
- **Tech:** tiered fallback chain — Udyam Registration dataset query, then Overpass, then a web-search extraction fallback — implemented as a `RunnableWithFallbacks` chain; z-score normalization against district/state benchmarks
- **Setup:** load the Udyam dataset per [Section 8.4](#84-registered-enterprises-udyam); implement each fallback tier as an independent function so the chain can be tested tier by tier

### 5.7 Pricing Agent
- **File:** `pricing_agent.py`
- **Reads:** `state.business_shortlist`, `state.entrepreneur_profile.location`
- **Writes:** `state.market_intelligence.pricing`
- **Tech:** direct Agmarknet API lookup for agri-linked categories; SECC asset-index regression proxy plus a web-search fallback with LLM extraction for non-agri categories
- **Setup:** requires `DATA_GOV_IN_API_KEY`; see [Section 8.8](#88-purchasing-power-proxy-secc)
- **Output contract:** every price figure must be tagged `source_confidence: "real" | "estimated"`

### 5.8 Supply Chain Agent
- **File:** `supply_chain_agent.py`
- **Reads:** `state.market_intelligence.competitor`, `state.business_shortlist`
- **Writes:** `state.market_intelligence.supply_chain`
- **Tech:** graph traversal over a modeled supplier-transport-buyer chain; LLM reasoning over the structured node and edge data to surface vulnerabilities
- **Setup:** model the chain as a small directed graph (`networkx` recommended); no external data source required beyond outputs already in state

### 5.9 SWOT Synthesis
- **File:** `swot_synthesis.py`
- **Reads:** all six `state.market_intelligence` sub-fields (fan-in)
- **Writes:** `state.feasibility_record.swot`
- **Tech:** structured-output generation (Pydantic schema) grounded by a light RAG pull against a sector-typical SWOT pattern corpus
- **Setup:** this node has no data connector of its own; it only fires once all six Module 1 agents above have written to state — implement the fan-in check as an explicit LangGraph conditional edge, not a manual wait

### 5.10 Adversarial (Red-Team) Review
- **File:** `adversarial_review.py`
- **Reads:** `state.feasibility_record.swot`
- **Writes:** `state.feasibility_record.verdict`, `state.feasibility_record.rejection_history` (if rejected)
- **Tech:** self-critique / red-team LLM prompting pattern, authorized to output `not_recommended` and force a return to Business Discovery
- **Setup:** implement as a separate LLM call from SWOT synthesis, with an explicit system instruction to look for reasons the business would fail rather than to summarize strengths
- **Control flow:** on `not_recommended` or `marginal`, the graph edge routes back to `discovery_agent.py` with the rejected candidate excluded from re-ranking

---
## 6. Module 2 — Financial Structuring and Funding Preparation

**Folder:** `module2_financial/`

### 6.1 Financial Engine
- **File:** `financial_engine.py`
- **Reads:** `state.entrepreneur_profile.available_capital`, `state.feasibility_record.verdict`
- **Writes:** `state.financial_plan.project_cost`, `.loan_eligibility`, `.scheme_tier`, `.repayment_schedule`
- **Tech:** deterministic Python functions only — no LLM call in this module
- **Setup:** implement and unit-test independently of the rest of the pipeline first, since every other Module 2 node depends on its output being correct:

```python
def compute_project_cost(available_capital: float) -> float:
    return available_capital / 0.10

def route_scheme_tier(project_cost: float) -> SchemeTier:
    if project_cost <= 140_000:
        return SchemeTier(name="micro_finance", rate=0.065, tenure_years=3, moratorium_months=3)
    elif project_cost <= 5_000_000:
        return SchemeTier(name="term_loan", rate=0.08, tenure_years=7, moratorium_months=6)
    raise ValueError("project cost outside supported scheme range")
```

- **Testing:** write golden-value unit tests for the worked example in the problem statement (₹1,00,000 capital → ₹10,00,000 project cost → ₹9,00,000 loan) before integrating with the graph

### 6.2 Financial Analyst Agent
- **File:** `financial_analyst_agent.py`
- **Reads:** `state.financial_plan`, `state.market_intelligence.pricing`
- **Writes:** `state.financial_plan.analyst_commentary`
- **Tech:** LLM function-calling over the structured Financial Engine output plus market/pricing data
- **Setup:** pass the Financial Engine's output as a tool result to the LLM call; never allow this agent to overwrite `financial_engine.py` outputs, only annotate them

### 6.3 Scenario / Digital Twin
- **File:** `scenario_digital_twin.py`
- **Reads:** `state.financial_plan`, `state.market_intelligence.risk` (seasonal curve)
- **Writes:** `state.financial_plan.stress_test_result`
- **Tech:** scenario simulation (deterministic low-season case, optionally extended to Monte Carlo) driven by the seasonal revenue curve from the Risk Agent
- **Setup:** implement the low-season scenario as a parameterized function of the same seasonal_decompose output already computed in `risk_agent.py`; avoid recomputing it

### 6.4 Policy / Scheme RAG Agent
- **File:** `policy_scheme_agent.py`
- **Reads:** `state.financial_plan.scheme_tier`
- **Writes:** `state.financial_plan.policy_explanation`
- **Tech:** RAG over scheme guideline documents (embedding model plus vector retrieval)
- **Setup:** run `rag/ingest_scheme_docs.py` once before first use, see [Section 8.6](#86-rag-corpus-ingestion)
- **Constraint:** this agent must never write to `state.financial_plan.scheme_tier` — eligibility is owned exclusively by `financial_engine.py`

### 6.5 Documentation Agent
- **File:** `documentation_agent.py`
- **Reads:** `state.entrepreneur_profile`, `state.financial_plan`
- **Writes:** `state.application_status.form_data`
- **Tech:** voice-first conversational form-filling; Indic ASR/TTS models; template auto-fill from case state
- **Setup:** depends on [Section 8.9](#89-multilingual-layer-ai4bharat) being configured; define form templates (Udyam registration, KYC, loan application) as structured field maps keyed to `CaseState` paths

### 6.6 Application Tracker and Disbursement
- **File:** `application_tracker.py`
- **Reads:** `state.application_status`
- **Writes:** `state.application_status.checklist`, `.disbursement_status`
- **Tech:** rule-based checklist state machine
- **Setup:** define the checklist states (`complete`, `pending`, `missing`) and the verification → sanction → disbursement transitions as an explicit enum-based state machine, not free-form strings

---
## 7. Module 3 — Launch and Post-Disbursement Monitoring

**Folder:** `module3_monitoring/`

### 7.1 Procurement Coordinator
- **File:** `procurement_coordinator.py`
- **Reads:** `state.market_intelligence.competitor` (density data), `state.entrepreneur_profile.location`
- **Writes:** shared procurement-cluster record (cross-case, not per-case state — see note below)
- **Tech:** spatial/category clustering over competitor-density data to pool bulk orders
- **Setup:** this is the one node that reads across multiple entrepreneurs' cases rather than a single case's state; implement its clustering store separately from `CaseState` (e.g. a lightweight table keyed by `(district, business_category)`)

### 7.2 Business Launch Copilot
- **File:** `launch_copilot.py`
- **Reads:** `state.feasibility_record`, `state.financial_plan`
- **Writes:** `state.monitoring_record` (initial launch roadmap entry)
- **Tech:** LLM planning agent generating a sequenced roadmap from case state
- **Setup:** no external data connector; purely a structured-output generation step over existing state

### 7.3 Ongoing Monitoring Agent
- **File:** `ongoing_monitoring_agent.py`
- **Reads:** on-device transaction notification messages
- **Writes:** `state.monitoring_record` (periodic cash-flow snapshots)
- **Tech:** on-device SMS parsing (regex/NER on transaction templates), strictly consent-gated
- **Setup:** implemented via `data_connectors/sms_parser.py`; this node must check `SMS_MONITORING_ENABLED` and a per-entrepreneur consent flag before reading any notification data, and must degrade gracefully (skip this agent) when consent is not present
- **Constraint:** never persist raw SMS text — parse and discard, storing only the derived structured transaction fields

### 7.4 Health Score and Early Warning
- **File:** `health_score_agent.py`
- **Reads:** `state.monitoring_record`, `state.financial_plan` (original plan for comparison)
- **Writes:** `state.monitoring_record[-1].health_score`, `.early_warning_flag`
- **Tech:** rule-based anomaly scoring comparing actuals against the original plan; approximate creditworthiness index derived from the same signal
- **Setup:** define the scoring thresholds as configuration, not hard-coded constants, so they can be tuned without a code change

### 7.5 Grievance Engine
- **File:** `grievance_engine.py`
- **Reads:** conversational input flagged as an issue/complaint
- **Writes:** `state.grievance_log`
- **Tech:** ticketing state machine with rule-based routing to human mentors
- **Setup:** define a simple ticket schema (`issue_type`, `status`, `assigned_mentor`, `resolution`) and a routing table; human mentor assignment can start as a static lookup table for the pilot

### 7.6 Outcome Learning Loop
- **File:** `outcome_learning_loop.py`
- **Reads:** `state.grievance_log`, `state.monitoring_record`
- **Writes:** updates to the ranking/risk priors used by `discovery_agent.py` and `risk_agent.py`
- **Tech:** synthetic data seed for cold start; feedback-driven prior updates to ranking and risk models
- **Setup:** run `synthetic_data/seed_outcomes.py` once before first deployment to populate a plausible cold-start dataset; every record it generates must be tagged `is_synthetic: true` so it can be filtered out or down-weighted once genuine outcome data accumulates
- **Important:** do not let this loop silently blend synthetic and real records without the tag — downstream ranking logic should read the tag explicitly

---
## 8. Data Source Provisioning

### 8.1 Geocoding (Nominatim + LGD)
```bash
# public Nominatim endpoint is rate-limited; for pilot-scale use it directly
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
```
Download the LGD (Local Government Directory) village/block/district code tables from `lgdirectory.gov.in` into `data/lgd/` for disambiguation logic in `geocoding.py`.

### 8.2 Population (Census 2011)
Download the village-level Census 2011 dataset (via data.gov.in) into `data/census/`. Build a spatial index once at startup:
```bash
python -m data_connectors.census --build-index
```

### 8.3 Points of Interest (OSM Overpass)
No setup beyond the public endpoint for pilot scale. For heavier query volume, self-host an Overpass instance via Docker and point `OVERPASS_BASE_URL` at it.

### 8.4 Registered Enterprises (Udyam)
Download the periodically published Udyam Registration open dataset from data.gov.in / msme.gov.in into `data/udyam/`. Load and index by PIN code, district, and NIC code:
```bash
python -m data_connectors.udyam --build-index
```

### 8.5 Routing (OSRM)
```bash
docker run -t -v "${PWD}/data/osrm:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/region.osm.pbf
docker run -t -v "${PWD}/data/osrm:/data" osrm/osrm-backend osrm-partition /data/region.osrm
docker run -t -v "${PWD}/data/osrm:/data" osrm/osrm-backend osrm-customize /data/region.osrm
docker run -t -i -p 5000:5000 -v "${PWD}/data/osrm:/data" osrm/osrm-backend osrm-routed --algorithm mld /data/region.osrm
```
Set `OSRM_BASE_URL=http://localhost:5000`.

### 8.6 RAG Corpus Ingestion
```bash
python -m rag.ingest_sector_reports --source data/nabard_kvic_pdfs/
python -m rag.ingest_risk_taxonomy --source data/risk_taxonomy/
python -m rag.ingest_scheme_docs --source data/scheme_guidelines/
```
Each ingestion script chunks the source documents, generates embeddings, and writes to `VECTOR_STORE_PATH`.

### 8.7 Risk Taxonomy Knowledge Base
Curate a small structured document set covering supply-chain, seasonal, and structural risk patterns (single-buyer dependency, etc.) in `data/risk_taxonomy/` before running the ingestion script above.

### 8.8 Purchasing Power Proxy (SECC)
Download SECC 2011 asset-index data from `secc.gov.in` (or its data.gov.in mirror) into `data/secc/`.

### 8.9 Multilingual Layer (AI4Bharat)
```bash
pip install transformers torch
python -m config.download_indic_models  # pulls IndicTrans2, Indic ASR, Indic TTS checkpoints
```
These are open-weight models; no API key is required. GPU is recommended for acceptable ASR/TTS latency but not required for text-only translation.

### 8.10 Agmarknet Commodity Prices
Register for a free API key at `data.gov.in`, set `DATA_GOV_IN_API_KEY`, and verify:
```bash
python -m data_connectors.agmarknet --test-connection
```

---
## 9. Running Locally

```bash
cp config/.env.example config/.env   # fill in LLM provider, data.gov.in API key, and other values
python -m orchestrator.persistence --init-db
uvicorn orchestrator.app:app --reload --port 8000
```

Send a test conversational turn:
```bash
curl -X POST http://localhost:8000/session \
  -H "Content-Type: application/json" \
  -d '{"message": "I have 1 lakh rupees and want to start a dairy business near <village>"}'
```

---
## 10. Evaluation Harness

**Folder:** `eval/`

- `golden_cases/` holds fixed input/expected-output pairs for the deterministic Financial Engine (highest priority — these must never regress) and representative cases for each Module 1 agent's output shape.
- `metrics.py` scores agent outputs against golden cases for structural correctness (does the output match its Pydantic schema, are confidence tags present) separately from content quality (which requires human or LLM-assisted review).
- Run the full suite before every merge to a shared branch:
```bash
python -m eval.harness --module all
```
- Run a single module during agent development:
```bash
python -m eval.harness --module module1_feasibility
```

---
## 11. Contribution Conventions

- One agent per file, matching the module/section numbering in this document. If a new agent is added, add both a code file and a corresponding subsection here in the same pull request.
- Every agent function must declare its `Reads` and `Writes` state paths in a module-level docstring, matching the format used in Sections 7–9 above.
- Deterministic nodes (currently only the Financial Engine) must contain no LLM calls and must have 100% branch coverage in `eval/golden_cases/`.
- Any new external data dependency must be added to [Section 8](#8-data-source-provisioning) with a setup script, and must be open or free-tier self-serve — this repository does not accept dependencies that require a paid or gated data license.
