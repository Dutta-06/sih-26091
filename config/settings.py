"""
Central configuration, loaded from environment variables / config/.env
(TECHNICAL_SETUP.md Sections 8-9).

All defaults point at the SAMPLE fixture data shipped in data/ so the
project runs with zero configuration for local development and testing.
Override via config/.env (copy config/.env.example) before pointing at real
data sources.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / "config" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Geocoding (data_connectors/geocoding.py) ---
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = (
        "rural-advisory-agents-prototype/0.1 (contact: set-your-email-here)"
    )
    nominatim_min_interval_seconds: float = 1.0
    lgd_data_path: Path = PROJECT_ROOT / "data" / "lgd" / "sample_lgd_codes.csv"

    # --- LGD live API (NAPIX) -- optional, see data_connectors/geocoding.py ---
    # NAPIX is a government API-exchange platform gated behind a
    # subscribe-and-approve workflow, not an instant self-serve key like
    # data.gov.in -- see IMPLEMENTATION_PLAN.md for the status of this path.
    # Disabled by default; the local LGD_DATA_PATH CSV is used until you have
    # a real subscriber key and set lgd_api_enabled=true.
    lgd_api_enabled: bool = False
    lgd_api_base_url: str = "https://dev.napix.gov.in/nic/lgd"
    lgd_api_key: str | None = None

    # --- Population (data_connectors/census.py) ---
    census_data_path: Path = PROJECT_ROOT / "data" / "census" / "sample_villages.csv"

    # --- Census + SHRUG build-index pipeline (data_connectors/datagovin.py,
    # shrug.py; wired into `python -m data_connectors.census --build-index`)
    # Free, self-serve, confirmed working mechanism -- see IMPLEMENTATION_PLAN.md.
    data_gov_in_api_key: str | None = None
    data_gov_in_base_url: str = "https://api.data.gov.in"
    # Maps a label (state or district name, your choice) -> the data.gov.in
    # resource UUID for that Census 2011 Village/Town-wise Primary Census
    # Abstract dataset. Get each resource_id from that dataset's own catalog
    # page on data.gov.in (look for the "API" tab / "Access API" button --
    # it shows the exact resource_id and a working example URL).
    census_resource_ids: dict[str, str] = {}
    # Column-name overrides: data.gov.in's exact field names vary per
    # resource/state. Confirm against one real API response and adjust here
    # rather than in code.
    census_api_village_code_field: str = "village_code"
    census_api_village_name_field: str = "village_name"
    census_api_district_field: str = "district_name"
    census_api_state_field: str = "state_name"
    census_api_population_field: str = "tot_p"

    # Local path to a SHRUG file providing pc11_village_id -> lat/lon
    # centroids (a CSV; see IMPLEMENTATION_PLAN.md for how to obtain one from
    # devdatalab.org/shrug_download -- no confirmed stable auto-download URL,
    # so this is a manually-placed file, not fetched over HTTP by this code).
    shrug_keys_csv_path: Path | None = None
    shrug_id_field: str = "pc11_village_id"
    shrug_lat_field: str = "latitude"
    shrug_lon_field: str = "longitude"

    # --- Points of interest (data_connectors/overpass.py) ---
    overpass_base_url: str = "https://overpass-api.de/api"

    # --- Market Reach Agent ---
    market_reach_radius_km: float = 10.0

    # --- Opportunity Agent / RAG (rag/vector_store.py) ---
    vector_store_path: Path = PROJECT_ROOT / "data" / "vector_store"
    reference_corpus_path: Path = PROJECT_ROOT / "data" / "reference_corpus"
    opportunity_top_k: int = 5


settings = Settings()
