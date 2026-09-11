"""
Environment configuration for all adapters.

DATA_MODE defaults to "mock" so the prototype runs entirely from the
local SQLite database. Set DATA_MODE=real only when live adapters
are intentionally enabled.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:

    # ============================================================
    # DATA MODE
    # ============================================================

    # "mock" -> use ONLY local SQLite mock database
    # "real" -> use live external adapters
    data_mode: str = os.environ.get(
        "DATA_MODE", "mock"
    ).strip().lower()

    # ============================================================
    # MOCK DATABASE
    # ============================================================

    mock_db_path: str = os.environ.get(
        "MOCK_DB_PATH",
        str(
            Path(__file__).resolve().parent.parent
            / "data"
            / "mock.db"
        ),
    )

    # ============================================================
    # OVERPASS
    # ============================================================

    overpass_base_url: str = os.environ.get(
        "OVERPASS_BASE_URL",
        "https://overpass-api.de/api/interpreter",
    )

    overpass_timeout_seconds: float = float(
        os.environ.get(
            "OVERPASS_TIMEOUT_SECONDS",
            "25",
        )
    )

    # ============================================================
    # UDYAM
    # ============================================================

    udyam_dataset_path: str | None = os.environ.get(
        "UDYAM_DATASET_PATH"
    )

    # ============================================================
    # DATA.GOV.IN COMMODITY PRICES
    # ============================================================

    data_gov_in_api_key: str | None = os.environ.get(
        "DATA_GOV_IN_API_KEY"
    )

    data_gov_in_base_url: str = os.environ.get(
        "DATA_GOV_IN_BASE_URL",
        "https://api.data.gov.in/resource",
    )

    commodity_price_resource_id: str | None = os.environ.get(
        "COMMODITY_PRICE_RESOURCE_ID"
    )

    # ============================================================
    # SECC
    # ============================================================

    secc_dataset_path: str | None = os.environ.get(
        "SECC_DATASET_PATH"
    )

    # ============================================================
    # OSRM
    # ============================================================

    osrm_base_url: str = os.environ.get(
        "OSRM_BASE_URL",
        "https://router.project-osrm.org",
    )

    osrm_is_public_demo: bool = (
        os.environ.get("OSRM_BASE_URL") is None
    )


settings = Settings()