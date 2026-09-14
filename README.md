# Hyper-Local Business Advisory & Financial Structuring Platform (SIH 26091)

An agentic advisory platform for first-time rural and semi-urban entrepreneurs applying for concessional credit
through State Channelising Agencies. It implements `Technical_Design_Document.pdf` (TDD):

* a hyper-local feasibility engine,
* a deterministic financial structuring and scheme-routing engine,
* a post-disbursement monitoring layer,

all driven by one conversational orchestrator built on LangGraph. `TECHNICAL_SETUP.md` gives per-agent setup detail.

## How a case flows

```
user turn (text / voice, English or Indic script)
      │
orchestrator/router.py ── intent + one-at-a-time slot filling (location → capital → activity, + stated reason)
      │  sets session_meta.requested_stage
orchestrator/graph.py  ── entry_router re-enters the stage the user asked for
      │
      ├─ profiling ─ profiling_agent (resolve location, early constraints; > Rs 50L project stops here)
      │     └─ discovery_agent (ranked shortlist; user's own activity first; adjacent alternatives after rejection)
      │          └─ 6 in parallel: market_reach · opportunity · risk · competitor · pricing · supply_chain
      │               └─ swot_synthesis (fan-in, saturation cross-check) ─ adversarial_review
      │                    ├─ viable ─────────────► financial_engine (deterministic)
      │                    ├─ marginal / rejected ► back to discovery (bounded by MAX_FEASIBILITY_ATTEMPTS)
      │                    └─ exhausted ─────────► END ("rejection is a valid outcome")
      │   financial_engine ─ eligible ► financial_analyst ► scenario_digital_twin ► policy_scheme
      │                                   ► documentation ► application_tracker
      │   application_tracker ─ disbursed ► procurement_coordinator ► launch_copilot
      │                         otherwise ► END (case paused; resumes on officer events)
      ├─ application   (answers / documents)        ► documentation ► application_tracker
      ├─ launch        (after disbursement)         ► procurement_coordinator ► launch_copilot
      ├─ monitoring    (consented notifications)    ► ongoing_monitoring ► health_score ► outcome_learning_loop
      ├─ grievance                                  ► grievance_engine ► outcome_learning_loop
      └─ scheme_inquiry                             ► policy_scheme
```

## Core principles and how they are enforced

| TDD principle | Implementation |
|---|---|
| **Deterministic core.** No language model computes eligibility, cost, loan amount, interest, tenure or schedule. | `module2_financial/financial_engine.py` is pure Python with golden tests and branch-covering eval cases. `common/llm.py` may only rephrase a deterministic template, and falls back to it on any failure. |
| **Confidence-labelled outputs** | Every intelligence output has `source_confidence: "real" \| "estimated"`, `sources` and `limitations`. "Real" means read from an open data source during this run. Missing data stays `None` with a limitation, never a plausible default. |
| **Rejection is valid** | The adversarial review applies documented rules, including debt-service coverage from `operating_model.preview_debt_service`. Rejected options are excluded, and adjacent alternatives are proposed up to a bound. |
| **Persistent state** | A single `CaseState`, saved as a SQLite snapshot per session (`orchestrator/stores.py`). The graph can be re-entered at any stage. |
| **Open data first** | Nominatim, LGD tables, Census village tables, Overpass, OSRM, data.gov.in Agmarknet, and Udyam/SECC extracts. There are no commercial dependencies. |
| **Consent and privacy** | SMS monitoring needs `SMS_MONITORING_ENABLED` plus per-case consent. Raw notification text is parsed and discarded. Aadhaar and bank account numbers are stored masked. |

Scheme structure, from the problem statement:
* **Project cost** = margin ÷ 0.10. **Loan** = 90%.
* **Micro Finance** (project ≤ Rs 1.40L): 6.5%, 3 years, 3-month moratorium, loan capped at Rs 1.25L.
* **Term Loan** (≤ Rs 50L): 8%, 7 years, 6-month moratorium, loan capped at Rs 45L.
* Repayment is quarterly, with the moratorium counted inside the tenure.

## What is real data, and what is still an estimate

The platform runs **offline by default** (`DATA_MODE=offline`). In offline mode every Module 1 output is honestly
labelled `estimated`:

| Input | Offline (default) | Live (`DATA_MODE=live` + configuration) |
|---|---|---|
| Location | Sample LGD / Census tables, then district HQ or state coordinates | Nominatim + LGD disambiguation |
| Population | Sample Census table, or state density × area | Census village abstract (`python -m data_connectors.census --build-index`) |
| POIs, competitors, suppliers | Skipped (named places are never invented) | Overpass; Udyam CSV at `UDYAM_DATASET_PATH` |
| Prices and seasonality | Catalog reference range × purchasing-power tier; catalog seasonal profile | Agmarknet via `DATA_GOV_IN_API_KEY` (24+ months: seasonal decomposition) |
| Road distance | Unavailable (never assumed short) | OSRM at `OSRM_BASE_URL` |
| Sector niches, risk taxonomy, scheme rules | TF-IDF retrieval over `data/reference_corpus`, `data/risk_taxonomy` and `data/scheme_guidelines` | Same; replace the SAMPLE corpus with published NABARD/KVIC reports |
| Business economics | `data/reference/business_catalog.json` (indicative planning assumptions) | To be calibrated with real project reports |
| Outcome learning | 408 synthetic seed records (`is_synthetic: true`), down-weighted | Real outcomes accumulate from grievances and health snapshots |

Known gaps:
* Web-search competitor extraction is not implemented; that tier is recorded as unavailable.
* The Indic translation and ASR models (AI4Bharat) load only when `INDIC_TRANSLATION_ENABLED=true` and `transformers` is installed. Without them, Devanagari keywords are still understood directly, and replies stay in English.

## Getting started

```bash
pip install -r requirements.txt
cp config/.env.example config/.env           # optional: live data, API keys, LLM provider

python -m orchestrator.graph --dry-run        # compile graph (23 nodes)
python -m orchestrator.persistence --init-db  # create the SQLite store
python -m synthetic_data.seed_outcomes        # cold-start outcome seed (tagged synthetic)
python -m pytest                              # offline test suite
python -m eval.harness --module all           # golden financial cases + confidence compliance
python run_pipeline.py --demo                 # CLI report
python run_pipeline.py --capital 12000 --location "Mirzapur, Uttar Pradesh" --category "tailoring" --reason "I know stitching"
uvicorn orchestrator.app:app --reload --port 8000   # API docs at http://localhost:8000/docs
```

### API

| Endpoint | Purpose |
|---|---|
| `POST /session` | Conversational turn (creates or resumes a case) |
| `POST /session/{id}/voice` | Audio turn (501 unless Indic ASR is enabled) |
| `POST /pipeline/run` | Direct programmatic run |
| `GET /state/{id}` | Full case state |
| `POST /application/{id}/field` | Answer a form field or declare documents |
| `POST /application/{id}/event` | Officer events: `start_verification`, `sanction`, `disburse`, `reject`, ... |
| `POST /monitoring/{id}/consent`, `POST /monitoring/{id}/notifications` | Consent-gated cash-flow monitoring |
| `POST /grievance/{id}` | Log an issue with its case context |
| `POST /feedback`, `POST /survey` | Funded-entrepreneur feedback and resident surveys (TDD 5.6) |
| `GET /map/{id}`, `GET /map/{id}/view` | GeoJSON and Leaflet map of market reach and competitors |
| `GET /health` | Service status and graph node count |

## Directory layout

```
orchestrator/        state.py (CaseState) · graph.py · router.py · language.py · persistence.py · stores.py · app.py
module1_feasibility/ profiling · discovery · market_reach · opportunity · risk · competitor · pricing · supply_chain · swot_synthesis · adversarial_review
module2_financial/   financial_engine (deterministic) · operating_model · financial_analyst · scenario_digital_twin · policy_scheme · documentation · application_tracker
module3_monitoring/  procurement_coordinator · launch_copilot · ongoing_monitoring · health_score · grievance_engine · outcome_learning_loop
data_connectors/     geocoding · census · overpass · udyam · agmarknet · secc · osrm · sms_parser · datagovin · shrug
rag/                 vector_store (TF-IDF) · ingest_sector_reports · ingest_risk_taxonomy · ingest_scheme_docs
common/              reference data helpers · network gate · optional LLM client
data/                reference catalog and state table · sample corpora · risk taxonomy · scheme guidelines · synthetic seed
eval/ · tests/ · synthetic_data/ · config/
```

## Credits

This integrates work from the team's feature branches onto the main architecture:
* market reach, opportunity and geo connectors: Vedant Khanna
* competitor, pricing and supply chain: Navya Minocha
* risk and documentation agents: Vinay Kumar Goyal
* financial analyst and scenarios: Paarth Manchanda
* policy agent and application tracker: Aahan
