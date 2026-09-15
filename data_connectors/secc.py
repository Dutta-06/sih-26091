"""SECC 2011 asset-index connector: purchasing-power proxy (TECHNICAL_SETUP.md Section 8.8).

SECC has no live-query API; a deployer places a district-level extract at
``SECC_DATASET_PATH`` with columns ``District`` (optional ``State``) and
``AssetIndex`` (share of households owning key assets, as 0-1 or 0-100).
The output is a proxy, never an observed price, so callers label it "estimated".

Mapping (documented modelling choice): ``purchasing_power_index = 0.8 + 0.4 * asset_share``,
so a district at the 50% asset share maps to the national reference 1.0 and the
index is bounded to [0.8, 1.2].
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from common.net import DataUnavailable
from config.settings import settings

_DISTRICT = ("district", "district_name")
_STATE = ("state", "state_name")
_INDEX = ("assetindex", "asset_index", "asset_share")


def _norm(value: Optional[str]) -> str:
    return " ".join((value or "").lower().replace("-", " ").split())


def asset_share_to_index(asset_share: float) -> float:
    share = asset_share / 100.0 if asset_share > 1.0 else asset_share
    return round(0.8 + 0.4 * max(0.0, min(1.0, share)), 3)


def purchasing_power_index(district: Optional[str], state: Optional[str] = None) -> tuple[float, float]:
    """Return ``(asset_share_raw, purchasing_power_index)``; raises ``DataUnavailable``."""
    path = settings.secc_dataset_path
    if not path:
        raise DataUnavailable("secc: SECC_DATASET_PATH not configured")
    if not district:
        raise DataUnavailable("secc: no district to look up")
    path = Path(path)
    if not path.exists():
        raise DataUnavailable(f"secc: dataset file not found at {path}")
    try:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            lowered = {h.strip().lower(): h for h in reader.fieldnames or []}
            col_d = next((lowered[c] for c in _DISTRICT if c in lowered), None)
            col_s = next((lowered[c] for c in _STATE if c in lowered), None)
            col_i = next((lowered[c] for c in _INDEX if c in lowered), None)
            if not col_d or not col_i:
                raise DataUnavailable("secc: dataset lacks District/AssetIndex columns")
            for row in reader:
                if _norm(row.get(col_d)) != _norm(district):
                    continue
                if state and col_s and row.get(col_s) and _norm(row[col_s]) != _norm(state):
                    continue
                try:
                    raw = float(row[col_i])
                except (TypeError, ValueError) as exc:
                    raise DataUnavailable(f"secc: non-numeric asset index for {district}") from exc
                return raw, asset_share_to_index(raw)
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        raise DataUnavailable(f"secc: failed reading dataset ({exc})") from exc
    raise DataUnavailable(f"secc: no record for district '{district}'")
