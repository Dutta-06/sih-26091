"""
Purchasing-power proxy adapter, from Socio-Economic Caste Census (SECC)
asset data (TDD Section 8: "Socio-Economic Caste Census asset data" ->
"Estimating regional purchasing power").

BLOCKING GAP, documented rather than guessed: SECC data has no public
live-query API and is distributed as bulk state-wise releases. This
adapter reads a local dataset (SECC_DATASET_PATH) the deployer must
supply, same pattern as the Udyam adapter. Any output from this adapter
is inherently a proxy/estimate, never REAL_DATA for a price — it feeds
the Pricing Agent's ESTIMATED path only.

Expected minimal file schema (deployer maps their extract to these column
names, or adjusts `_COLUMN_MAP`):
    - "District" / "district"
    - "Block" or "Village" (optional, for finer granularity)
    - "AssetIndex" or "asset_index": a normalized 0-1 or 0-100 purchasing
      power proxy score for the area
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.adapters.base import Adapter, AdapterResult
from src.config import settings
from src.schemas import Confidence


class PurchasingPowerAdapter(Adapter):
    name = "SECC asset data (purchasing-power proxy, bulk extract)"

    _COLUMN_MAP = {
        "district": ("District", "district"),
        "asset_index": ("AssetIndex", "asset_index", "Asset_Index"),
    }

    def __init__(self, dataset_path: str | None = None) -> None:
        self._dataset_path = dataset_path or settings.secc_dataset_path

    def _resolve_column(self, header: list[str], candidates: tuple[str, ...]) -> str | None:
        for cand in candidates:
            if cand in header:
                return cand
        return None

    async def get_asset_index(self, district: str | None) -> AdapterResult[float]:
        if not self._dataset_path:
            return AdapterResult.insufficient(
                self.name,
                "SECC_DATASET_PATH is not configured. SECC asset data has no public "
                "live-query API; a bulk dataset extract must be supplied by the deployer.",
            )
        if not district:
            return AdapterResult.insufficient(self.name, "No district provided to look up the asset index.")

        path = Path(self._dataset_path)
        if not path.exists():
            return AdapterResult.insufficient(
                self.name, f"Configured SECC dataset file not found at {self._dataset_path}."
            )

        try:
            with path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                header = reader.fieldnames or []
                col_district = self._resolve_column(header, self._COLUMN_MAP["district"])
                col_index = self._resolve_column(header, self._COLUMN_MAP["asset_index"])

                if not col_district or not col_index:
                    return AdapterResult.insufficient(
                        self.name, "SECC dataset file is missing a recognizable District or AssetIndex column."
                    )

                for row in reader:
                    if row.get(col_district, "").strip().lower() == district.strip().lower():
                        try:
                            return AdapterResult(
                                data=float(row[col_index]),
                                confidence=Confidence.ESTIMATED,
                                source=self.name,
                                limitations=["Asset index is a purchasing-power proxy, not a direct price observation."],
                            )
                        except (TypeError, ValueError):
                            return AdapterResult.insufficient(
                                self.name, f"Asset index value for '{district}' was not numeric."
                            )
        except (OSError, csv.Error) as exc:
            return AdapterResult.insufficient(self.name, f"Failed reading SECC dataset: {exc}")

        return AdapterResult.insufficient(self.name, f"No SECC record found for district '{district}'.")
