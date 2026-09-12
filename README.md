# Hyper-Local Business Advisory & Financial Structuring Platform (SIH 26091)

An autonomous, agentic advisory platform tailored for first-time rural and semi-urban entrepreneurs applying for concessional credit schemes (under State Channelizing Agencies / Channelizing Agencies).

The platform combines a **hyper-local business feasibility engine**, a **100% deterministic financial structuring & scheme-routing engine**, and a **post-disbursement monitoring layer**, all driven through a stateful multi-agent system built on **LangGraph**.

---

## System Architecture

```
                                [User Turn (Text / Voice)]
                                            │
                                            ▼
                               [orchestrator/router.py]
                        (Slot Filling: Location, Margin, Preference)
                                            │
                                            ▼
                               [orchestrator/graph.py]
                             (LangGraph StateGraph Engine)
                                            │
               ┌────────────────────────────┼────────────────────────────┐
               ▼                            ▼                            ▼
      [Module 1: Feasibility]     [Module 2: Financial]        [Module 3: Monitoring]
    • profiling_agent           • financial_engine           • procurement_coordinator
    • discovery_agent             (100% Deterministic)       • launch_copilot
    • 6 Parallel Intelligence:  • financial_analyst          • ongoing_monitoring
      - market_reach            • scenario_digital_twin      • health_score
      - opportunity             • policy_scheme              • grievance_engine
      - risk                    • documentation              • outcome_learning_loop
      - competitor              • application_tracker
      - pricing
      - supply_chain
    • swot_synthesis (Fan-In)
    • adversarial_review
      (Loop-back on rejection)
```

---

## Key Core Principles

1. **Deterministic Core, Reasoning Periphery:** All scheme routing, project costs, eligibility, interest rates, moratoriums, and quarterly repayment tables are calculated using pure deterministic functions (`module2_financial/financial_engine.py`). Language models explain and contextualize these numbers, but never alter them.
   * **Project Cost:** $\text{Available Margin} / 0.10$
   * **Loan Eligibility:** $90\%$ of Project Cost
   * **Scheme Tiers:**
     * **Micro Finance Scheme** ($\le ₹1.40$ Lakh): 6.5% interest p.a., 3-year tenure, 3-month moratorium (capped at ₹1.25L).
     * **Term Loan Scheme** ($₹1.40\text{L} - ₹50.00\text{L}$): 8.0% interest p.a., 7-year tenure, 6-month moratorium (capped at ₹45L).
2. **Confidence-Labeled Outputs:** Every intelligence finding is explicitly tagged with `source_confidence: "real" | "estimated"`.
3. **Adversarial Red-Team Review:** Self-critique reviewer authorized to output `not_recommended` or `marginal`, triggering a loop back to Business Discovery to redirect beneficiaries away from unviable copycats.
4. **End-to-End Lifecycle:** Persists state across profiling, feasibility, financial structuring, sanction, launch roadmaps, consented SMS transaction monitoring, and grievance escalation.

---

## Directory Layout

```
.
├── orchestrator/                 # Central Multi-Agent Orchestration Layer
│   ├── state.py                  # Canonical CaseState Pydantic schema
│   ├── graph.py                  # 24-node LangGraph StateGraph (Modules 1, 2, 3)
│   ├── router.py                 # Intent routing & conversational slot-filling
│   ├── persistence.py            # Checkpointing & session persistence
│   └── app.py                    # FastAPI service (/session, /pipeline/run)
│
├── module1_feasibility/          # Module 1: Profiling & Feasibility (10 nodes)
├── module2_financial/            # Module 2: Deterministic Financial Engine & Planning (6 nodes)
├── module3_monitoring/           # Module 3: Launch & Post-Disbursement Monitoring (6 nodes)
├── config/                       # Settings & environment variables
├── eval/                         # Evaluation harness & golden regression benchmarks
├── tests/                        # Automated Pytest suite
├── run_pipeline.py               # Interactive CLI demonstration tool
└── requirements.txt              # Project dependencies
```

---

## Getting Started

### 1. Installation

```bash
pip install -r requirements.txt
```

### 2. Verify Graph Compilation & Checkpointing

```bash
python -m orchestrator.graph --dry-run
python -m orchestrator.persistence --test-checkpoint
```

### 3. Run Automated Tests

```bash
python -m pytest tests/
```

### 4. Run Evaluation Harness

```bash
python -m eval.harness --module all
```

### 5. Run Interactive Demo in Terminal

```bash
python run_pipeline.py --demo
```

Or pass custom parameters:
```bash
python run_pipeline.py --capital 100000 --location "Bhadohi, Uttar Pradesh" --category "Dairy Farming"
```

### 6. Start the FastAPI Web Server

```bash
uvicorn orchestrator.app:app --reload --port 8000
```
Interactive API documentation available at `http://localhost:8000/docs`.
