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

    # --- Population (data_connectors/census.py) ---
    census_data_path: Path = PROJECT_ROOT / "data" / "census" / "sample_villages.csv"

    # --- Points of interest (data_connectors/overpass.py) ---
    overpass_base_url: str = "https://overpass-api.de/api"

    # --- Market Reach Agent ---
    market_reach_radius_km: float = 10.0

    # --- Opportunity Agent / RAG (rag/vector_store.py) ---
    vector_store_path: Path = PROJECT_ROOT / "data" / "vector_store"
    reference_corpus_path: Path = PROJECT_ROOT / "data" / "reference_corpus"
    opportunity_top_k: int = 5


settings = Settings()
