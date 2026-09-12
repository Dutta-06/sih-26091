"""Application configuration loaded from environment or defaults."""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(extra="ignore", env_file=".env", env_file_encoding="utf-8")

    # API / LLM Keys
    LLM_API_KEY: str = "mock-key"
    LLM_MODEL: str = "gemini-1.5-flash"
    DATA_GOV_IN_API_KEY: str = "mock-data-gov-key"

    # Endpoints
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    OVERPASS_BASE_URL: str = "https://overpass-api.de/api/interpreter"
    OSRM_BASE_URL: str = "http://localhost:5000"

    # Persistence
    CHECKPOINT_BACKEND: str = "memory"  # "memory" or "sqlite"
    SQLITE_DB_PATH: str = "orchestrator_sessions.db"

    # Monitoring Settings
    SMS_MONITORING_ENABLED: bool = True
    APP_ENV: str = "development"


settings = Settings()
