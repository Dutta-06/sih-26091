# Implementation Plan: Market Reach Agent & Opportunity Agent

**Project:** Hyper-Local Business Advisory and Financial Structuring Platform
**Scope of this build:** Two agents only — **Market Reach Agent** and **Opportunity Agent** — extracted from Module 1 (Profiling and Feasibility Assessment) of the full Technical Design Document.
**Status:** Draft v1
**Date:** 2026-09-10

> **Update, 2026-09-12:** Both agents are now built and tested (18 passing tests) as LangGraph nodes — see `README.md` for the code map. Real API integrations have since been added for two of the three fallback data sources flagged below: a data.gov.in client + SHRUG centroid loader for Census population (`python -m data_connectors.census --build-index`), and an optional NAPIX API path for LGD disambiguation (though NAPIX turned out to be a subscribe-and-approve government platform, not an instant free key like data.gov.in — the local LGD CSV remains the simpler, unconditionally-free option). The NABARD/KVIC sector corpus has no API at all and is still 100% manual curation. All three degrade gracefully to the original sample fixtures when unconfigured. See `README.md`'s "Making the population/geocoding data real" section for exact setup steps.

---

## 1. Why only two agents, and what that changes

The source design (Section 5.3, Figure 3) specifies **six** parallel local-intelligence agents feeding a shared case state: Market Reach, Opportunity, Risk, Competitor, Pricing, and Supply Chain. Building only two of them is fully feasible as a standalone system, but it creates one real dependency gap worth flagging up front:

- **Market Reach Agent** is self-contained. Its inputs (a place name + radius) and outputs (population reach, distribution points) don't depend on any other agent. It can be built and tested in complete isolation.
- **Opportunity Agent**, per the original spec, "cross-checks each niche against **local competitor and demand data**" to classify saturation as low/medium/high. That competitor and demand data is the job of the *Competitor Agent* and *Pricing Agent* — neither of which is in scope here.

This plan resolves the gap by having the Opportunity Agent use a **simplified saturation heuristic** for v1 (based on retrieved sector reports + a lightweight, self-contained proxy such as OSM point-of-interest density in the same radius the Market Reach Agent already resolves), clearly labeled as a reduced-confidence estimate. Section 4 below covers this in detail. If the Competitor/Pricing agents are built later, the Opportunity Agent's saturation check can be upgraded to use their real outputs without changing its interface.

---

## 2. Scope summary

| Item | In scope | Out of scope (for this build) |
|---|---|---|
| Market Reach Agent | Yes — full pipeline | — |
| Opportunity Agent | Yes — full pipeline, with simplified saturation proxy | Competitor/Pricing-informed saturation (needs those agents) |
| Orchestrator | Minimal: a script/CLI that takes profile input and calls both agents | Full stateful multi-turn conversational orchestrator, intent routing, session persistence across days/months |
| Shared case state | Minimal JSON schema covering only the fields these two agents read/write | Full case object (financial plan, monitoring record, grievance log, etc.) |
| Conversational / multilingual layer | Not built | Indic ASR/TTS, translation layer (Section 4.3 of source doc) |
| SWOT synthesis, adversarial review, verdict | Not built | Module 1 stages 5.4–5.5 |
| Modules 2 and 3 | Not built | Financial engine, disbursement, monitoring |

---

## 3. Market Reach Agent

**Function (per source spec, Section 5.3 / architecture diagram):** Resolve a stated village/block/district to coordinates, disambiguate repeated place names, estimate population and consumer base within a defined radius, and identify nearby markets and distribution points.

### Pipeline

1. **Geocode** the user-stated location (village/block/district name) to coordinates.
2. **Disambiguate** using official location codes when multiple places share a name across states/districts.
3. **Resolve population** by running a spatial nearest-neighbor / radius query against a village-level population dataset.
4. **Identify POIs** (markets, shops, transport hubs) within the radius.
5. **Output** a structured result: consumer base estimate, distribution points list, confidence labels per figure (Section 2 of source doc requires this).

### Tech stack

| Component | Tool | Notes |
|---|---|---|
| Geocoding | OpenStreetMap **Nominatim** | Public API or self-hosted |
| Location disambiguation | **LGD (Local Government Directory)** codes | Government of India dataset/API |
| Population data | **Census 2011** village-level Primary Census Abstract | Government of India (data.gov.in) |
| Spatial query | `scipy.spatial.KDTree` / `sklearn.neighbors.BallTree` or `geopandas` | Standard, no external dependency |
| POI lookup | **Overpass API** (OSM) | Public API or self-hosted |
| Language/runtime | Python 3.11+ | Matches rest of stack |

### Feasibility notes (researched today)

- **Nominatim (geocoding):** The public instance enforces an absolute max of 1 request/second, and bulk/scripted use is explicitly discouraged (single machine, single thread, mandatory caching, no reselling of results). This is **fine for development and low-volume use**, but the policy itself recommends self-hosting for any real production load. A self-hosted Nominatim instance (Docker image exists, needs an India OSM extract) should be budgeted for as a v1.x task, not v1.0. [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)
- **Overpass API (POIs):** No hard published numeric rate limit, but heavy/production usage is discouraged on the public endpoint and the OSMF steers heavy users toward self-hosting or planet.osm-based alternatives. Same recommendation as Nominatim: public endpoint for dev/prototype, self-hosted for production. [OSMF API Usage Policy](https://operations.osmfoundation.org/policies/api/)
- **LGD codes:** `lgdirectory.gov.in` exposes a "Download Directory" for states/districts/sub-districts/villages and a NAPIX API provider endpoint (`dev.napix.gov.in`), with no apparent registration barrier for basic lookups. **Feasible**, but the API's reliability/documentation quality should be verified hands-on early, since it's a government portal without an SLA.
- **Census 2011 village population data:** Available as free CSV downloads per state on data.gov.in (Primary Census Abstract, village/town-wise). **Important caveat: this is 2011 data — 15 years old as of today.** There is no newer village-level census (the next Census has been delayed nationally). Population estimates will need to be presented as **clearly labeled estimates**, ideally with a simple growth-rate adjustment, not as current fact. This matches the source design's own "confidence-labeled outputs" principle (Section 2).
- **Matching Census village names to Nominatim/LGD identifiers is the single trickiest integration point** — village names are not unique and Census, LGD, and OSM don't share a common ID out of the box. Expect to build a matching/reconciliation step (fuzzy match on name + district + state, validated against LGD codes) as real engineering work, not a data lookup.

**Verdict: Feasible.** All data sources are open and free. The main engineering risk is the name-matching/reconciliation layer between Census, LGD, and OSM data, not availability of the data itself.

---

## 4. Opportunity Agent

**Function (per source spec):** Retrieve realistic sub-niches for the chosen sector from a curated reference collection of sector project reports, then classify saturation as low/medium/high.

### Pipeline

1. **Retrieve** candidate sub-niches for the entrepreneur's chosen sector via a RAG (retrieval-augmented generation) lookup over a curated corpus of sector project reports.
2. **Classify saturation** for each sub-niche. Full spec cross-checks against competitor + demand data (not in scope — see Section 1). This build substitutes a **simplified proxy**: OSM POI density for that business category within the same radius the Market Reach Agent already resolved, normalized by population. Output is explicitly labeled "estimated, based on limited signals" rather than the full-confidence figure the eventual system would produce.
3. **Output** a ranked list of sub-niches with saturation labels and supporting rationale, confidence-labeled per source-document data type (real vs. estimated).

### Tech stack

| Component | Tool | Notes |
|---|---|---|
| Embeddings | Open-source embedding model (e.g. `sentence-transformers`) | Matches "open tooling" principle |
| Vector store | **FAISS** or **Chroma** | Both free, local, no license needed |
| Retrieval | Cosine-similarity search over embedded corpus | Standard RAG pattern |
| Reference corpus | Curated **NABARD** and **KVIC** model project / bankable project reports | See feasibility note below |
| Saturation proxy (v1) | Overpass API POI density (reused from Market Reach Agent) | Stopgap until Competitor/Pricing agents exist |
| Language/runtime | Python 3.11+, LangChain or a lighter custom RAG loop | LangChain optional — a hand-rolled retriever is ~100 lines and avoids a heavy dependency |

### Feasibility notes (researched today)

- **NABARD Model Bankable Projects:** NABARD publishes model project profiles across agriculture, allied, and off-farm sectors on its official site (`nabard.org`) as downloadable documents by sector. **KVIC** similarly publishes project profiles for village/khadi industries. Both are legitimately public, matching the source design's "open data first" principle.
- **This corpus is not an API — it's a document collection that has to be manually assembled.** Someone needs to go sector by sector, download the relevant PDFs, and build the reference set. This is real, bounded curation work (expect on the order of days, not hours, depending on how many sectors the pilot geography needs), and it's a one-time cost that can be incrementally expanded. It should be scoped as its own task in the plan below, not folded silently into "build the RAG pipeline."
- **Embedding model + vector store:** Fully feasible, standard open-source components, no licensing or access concerns at all.
- **Saturation classification without Competitor/Pricing data** is the one place where this two-agent build is meaningfully weaker than the full spec. The POI-density proxy is a reasonable stand-in but will be noisier than the original design (which also normalizes against district/state benchmarks via the Competitor Agent). This should be communicated to end users as a known v1 limitation, consistent with the source document's own "confidence-labeled outputs" and "rejection is a valid outcome" principles.

**Verdict: Feasible**, with two pieces of real work called out honestly: (1) manually curating the NABARD/KVIC reference corpus, and (2) accepting a weaker, clearly-labeled saturation signal until the Competitor/Pricing agents exist.

---

## 5. Shared minimal case state (for these two agents only)

```json
{
  "entrepreneur_profile": {
    "location_query": "string (as stated by user)",
    "resolved_location": {
      "lgd_code": "string",
      "lat": "number",
      "lon": "number",
      "confidence": "real | estimated"
    },
    "business_category": "string"
  },
  "market_reach_output": {
    "population_estimate": "number",
    "population_data_year": 2011,
    "distribution_points": [{"name": "string", "type": "string", "lat": "number", "lon": "number"}],
    "confidence": "real | estimated"
  },
  "opportunity_output": {
    "sub_niches": [
      {
        "name": "string",
        "saturation": "low | medium | high",
        "saturation_basis": "poi_density_proxy",
        "rationale": "string",
        "confidence": "estimated"
      }
    ]
  }
}
```

This is intentionally a subset of the full Section 9 state schema — only the fields these two agents actually read or write.

---

## 6. Phased build plan

| Phase | Deliverable | Depends on |
|---|---|---|
| 0. Setup | Repo structure, Python env, config for API keys/endpoints, `.env` template | — |
| 1. Market Reach Agent MVP | Geocode → disambiguate → population lookup → POI query → structured JSON output, tested against 5–10 known villages | Phase 0 |
| 2. Census/LGD reconciliation | Name-matching layer between Census PCA data, LGD codes, and Nominatim/OSM results | Phase 1 |
| 3. NABARD/KVIC corpus curation | Manually collect and clean project-report PDFs for the pilot sectors/geography | Phase 0 (parallel with 1–2) |
| 4. Opportunity Agent MVP | Embed corpus → build vector store → retrieval → saturation proxy using Market Reach Agent's radius/POI data | Phases 1, 3 |
| 5. Integration | Thin CLI/script orchestrator that runs both agents end-to-end on one profile and writes the shared case state JSON | Phases 2, 4 |
| 6. Validation | Manual spot-check against 3–5 real localities; sanity-check saturation labels with a domain expert if available | Phase 5 |

---

## 7. Risks and open questions

- **Census data staleness (2011)** is a real accuracy limitation, not a solvable engineering problem — it needs to be surfaced to end users, not hidden.
- **Name-matching across Census / LGD / OSM** is the highest-effort engineering task in this plan; budget real time for it rather than treating it as a lookup.
- **Public Nominatim/Overpass endpoints are not meant for production load.** Fine to start with; self-hosting both (or a paid geocoding fallback) should be a known follow-up, not a surprise later.
- **NABARD/KVIC corpus curation is manual, ongoing work.** Coverage will only be as good as what gets curated — worth deciding up front which sectors/regions the pilot actually needs, rather than trying to cover everything.
- **Open question for you:** What pilot geography and business sectors should Phase 1–4 be tested against? This determines how much of the Census/LGD/NABARD/KVIC data needs to be pulled in for v1, and is the biggest scoping lever on timeline.

---

## 8. Overall feasibility verdict

**Both agents are feasible to build with entirely open, free data sources** — no commercial license, credit bureau, or institutional data-sharing agreement is required anywhere in this two-agent scope, consistent with the source document's design principles. Nothing here is blocked. The honest caveats are: government API reliability is unverified until tested hands-on, Census population data is over a decade old, the NABARD/KVIC corpus needs manual curation, and the Opportunity Agent's saturation signal is weaker than the full six-agent design until the Competitor and Pricing agents are eventually built.
