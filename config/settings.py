"""Central configuration, loaded from environment variables / config/.env.

TECHNICAL_SETUP.md Sections 8-9. Defaults run the whole platform offline with
no API keys: every connector that would need the network or a downloaded
dataset degrades to a documented estimate that is labeled ``"estimated"``.
Set ``DATA_MODE=live`` (and the relevant keys/paths) to use real open data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(PROJECT_ROOT / "config" / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Runtime mode -------------------------------------------------------
    # "offline": never touch the network; use local tables/fixtures + labeled estimates.
    # "live":    call open data endpoints (Nominatim, Overpass, OSRM, data.gov.in)
    #            with timeouts, falling back to offline estimates on failure.
    data_mode: Literal["offline", "live"] = "offline"
    http_timeout_seconds: float = 12.0
    app_env: str = "development"

    # --- LLM (reasoning periphery only; never computes figures) -------------
    # "none" uses deterministic templates. "ollama" uses a self-hosted open model.
    llm_provider: Literal["none", "ollama"] = "none"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    llm_timeout_seconds: float = 60.0

    # --- Geocoding (data_connectors/geocoding.py) ---------------------------
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "sih26091-advisory-prototype/0.2 (contact: set-your-email-here)"
    nominatim_min_interval_seconds: float = 1.0
    lgd_data_path: Path = PROJECT_ROOT / "data" / "lgd" / "sample_lgd_codes.csv"
    lgd_api_enabled: bool = False
    lgd_api_base_url: str = "https://dev.napix.gov.in/nic/lgd"
    lgd_api_key: Optional[str] = None

    # --- Population (data_connectors/census.py) -----------------------------
    census_data_path: Path = PROJECT_ROOT / "data" / "census" / "sample_villages.csv"
    state_reference_path: Path = PROJECT_ROOT / "data" / "reference" / "state_reference.json"
    data_gov_in_api_key: Optional[str] = None
    data_gov_in_base_url: str = "https://api.data.gov.in"
    census_resource_ids: dict[str, str] = {}
    census_api_village_code_field: str = "village_code"
    census_api_village_name_field: str = "village_name"
    census_api_district_field: str = "district_name"
    census_api_state_field: str = "state_name"
    census_api_population_field: str = "tot_p"
    shrug_keys_csv_path: Optional[Path] = None
    shrug_id_field: str = "pc11_village_id"
    shrug_lat_field: str = "latitude"
    shrug_lon_field: str = "longitude"

    # --- Points of interest (data_connectors/overpass.py) -------------------
    overpass_base_url: str = "https://overpass-api.de/api"

    # --- Registered enterprises (data_connectors/udyam.py) ------------------
    udyam_dataset_path: Optional[Path] = None

    # --- Commodity prices (data_connectors/agmarknet.py) --------------------
    commodity_price_resource_id: str = "9ef84268-d588-465a-a308-a864a43d0070"

    # --- Purchasing power proxy (data_connectors/secc.py) -------------------
    secc_dataset_path: Optional[Path] = None

    # --- Routing (data_connectors/osrm.py) ----------------------------------
    osrm_base_url: str = "http://localhost:5000"

    # --- Module 1 -----------------------------------------------------------
    market_reach_radius_km: float = 10.0
    business_catalog_path: Path = PROJECT_ROOT / "data" / "reference" / "business_catalog.json"
    max_feasibility_attempts: int = 3  # rejection loop bound (TDD 5.5)

    # --- RAG (rag/vector_store.py) ------------------------------------------
    vector_store_path: Path = PROJECT_ROOT / "data" / "vector_store"
    reference_corpus_path: Path = PROJECT_ROOT / "data" / "reference_corpus"
    risk_taxonomy_path: Path = PROJECT_ROOT / "data" / "risk_taxonomy"
    scheme_guidelines_path: Path = PROJECT_ROOT / "data" / "scheme_guidelines"
    opportunity_top_k: int = 5

    # --- Persistence (orchestrator/persistence.py) --------------------------
    checkpoint_backend: Literal["memory", "sqlite"] = "sqlite"
    sqlite_db_path: Path = PROJECT_ROOT / "data" / "runtime" / "platform.db"

    # --- Module 3 -----------------------------------------------------------
    sms_monitoring_enabled: bool = True
    health_score_thresholds_path: Path = PROJECT_ROOT / "config" / "health_thresholds.json"
    synthetic_outcomes_path: Path = PROJECT_ROOT / "data" / "synthetic" / "seed_outcomes.json"
    procurement_min_peers: int = 3

    # --- Multilingual layer (orchestrator/language.py) ----------------------
    indic_translation_enabled: bool = False
    indic_translation_model: str = "ai4bharat/indictrans2-indic-en-dist-200M"
    indic_asr_model: str = "ai4bharat/indicwav2vec-hindi"


settings = Settings()
