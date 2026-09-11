"""
Udyam Registration open dataset adapter (TDD Section 8: "Udyam Registration
open dataset" -> "Competitor density estimation").

BLOCKING GAP, documented rather than papered over: the TDD names this as a
data source but Udyam Registration does not provide a public live-query
API. The realistic access pattern is a periodic bulk data extract (CSV /
Parquet) that a deployer downloads and places on disk. This adapter reads
such a file if UDYAM_DATASET_PATH is configured; if it is not configured,
or the file is missing/unreadable, it returns INSUFFICIENT_DATA rather
than fabricating a registration count.

Expected minimal file schema (documented, not invented as "the" schema —
deployers must map their actual extract to these column names, or adjust
`_COLUMN_MAP` below):
    - "NIC_Code" or "ncs_code": industry classification code
    - "District": district name
    - "State": state name
    - "EnterpriseName": for informational purposes only, not returned
    - "Latitude" / "Longitude": optional, for spatial filtering
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.adapters.base import Adapter, AdapterResult
from src.config import settings
from src.schemas import Confidence


class UdyamAdapter(Adapter):
    name = "Udyam Registration open dataset (bulk extract)"

    _COLUMN_MAP = {
        "ncs_code": ("NIC_Code", "ncs_code", "nic_code"),
        "district": ("District", "district"),
        "state": ("State", "state"),
        "latitude": ("Latitude", "latitude"),
        "longitude": ("Longitude", "longitude"),
    }

    def __init__(self, dataset_path: str | None = None) -> None:
        self._dataset_path = dataset_path or settings.udyam_dataset_path

    def _resolve_column(self, header: list[str], candidates: tuple[str, ...]) -> str | None:
        for cand in candidates:
            if cand in header:
                return cand
        return None

    async def count_registered_enterprises(
        self,
        district: str | None,
        ncs_code: str | None,
    ) -> AdapterResult[int]:
        if not self._dataset_path:
            return AdapterResult.insufficient(
                self.name,
                "UDYAM_DATASET_PATH is not configured. Udyam Registration has no public "
                "live-query API; a bulk dataset extract must be supplied by the deployer.",
            )

        path = Path(self._dataset_path)
        if not path.exists():
            return AdapterResult.insufficient(
                self.name, f"Configured Udyam dataset file not found at {self._dataset_path}."
            )

        if not district and not ncs_code:
            return AdapterResult.insufficient(
                self.name, "Neither district nor NCS/NIC code provided to filter the Udyam dataset."
            )

        try:
            with path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                header = reader.fieldnames or []
                col_district = self._resolve_column(header, self._COLUMN_MAP["district"])
                col_ncs = self._resolve_column(header, self._COLUMN_MAP["ncs_code"])

                if district and not col_district:
                    return AdapterResult.insufficient(
                        self.name, "Udyam dataset file has no recognizable District column."
                    )
                if ncs_code and not col_ncs:
                    return AdapterResult.insufficient(
                        self.name, "Udyam dataset file has no recognizable NIC/NCS code column."
                    )

                count = 0
                for row in reader:
                    if district and col_district and row.get(col_district, "").strip().lower() != district.strip().lower():
                        continue
                    if ncs_code and col_ncs and row.get(col_ncs, "").strip() != ncs_code.strip():
                        continue
                    count += 1
        except (OSError, csv.Error) as exc:
            return AdapterResult.insufficient(self.name, f"Failed reading Udyam dataset: {exc}")

        return AdapterResult(data=count, confidence=Confidence.REAL_DATA, source=self.name)
