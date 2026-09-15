"""
SHRUG (Socioeconomic High-resolution Rural-Urban Geographic Platform)
centroid loader, used to attach a lat/lon coordinate to each Census 2011
village -- something the raw Census PCA data doesn't include (see
IMPLEMENTATION_PLAN.md Section 3).

ACCESS NOTE: SHRUG (Development Data Lab, https://www.devdatalab.org/shrug)
is confirmed free (CC BY-NC-SA 4.0) and does not require an account to
browse its docs, but its actual data files are distributed via a download
page (devdatalab.org/shrug_download) rather than a stable, unauthenticated
REST endpoint this code could call automatically -- I could not confirm a
direct programmatic download URL. So this module does not fetch SHRUG data
over the network itself: you download the relevant file (the "keys" module
has a pc11_village_id-to-centroid mapping) from that page once, by hand,
and point SHRUG_KEYS_CSV_PATH at it. This is the same "download once, use
locally" pattern as the Census data itself.

Expected input format: a CSV with (at minimum) a village-id column and
lat/lon columns. Real SHRUG files may ship as .dta (Stata) or with
different column names than assumed here -- settings.shrug_id_field /
shrug_lat_field / shrug_lon_field let you correct the mapping, and a .dta
file can be converted to CSV with `pandas.read_stata(...).to_csv(...)`
before pointing this loader at it.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)


def load_centroids(path: Optional[Path] = None) -> dict[str, tuple[float, float]]:
    """Return {village_id: (lat, lon)} from a SHRUG keys/centroid CSV."""
    csv_path = Path(path or settings.shrug_keys_csv_path) if (path or settings.shrug_keys_csv_path) else None
    if csv_path is None:
        raise ValueError(
            "No SHRUG keys file configured. Set SHRUG_KEYS_CSV_PATH after "
            "downloading a centroid/keys file from "
            "https://www.devdatalab.org/shrug_download -- see "
            "IMPLEMENTATION_PLAN.md Section 3."
        )
    if not csv_path.exists():
        raise FileNotFoundError(f"SHRUG keys file not found at {csv_path}")

    centroids: dict[str, tuple[float, float]] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            village_id = row.get(settings.shrug_id_field)
            lat = row.get(settings.shrug_lat_field)
            lon = row.get(settings.shrug_lon_field)
            if village_id and lat and lon:
                try:
                    centroids[village_id] = (float(lat), float(lon))
                except ValueError:
                    logger.warning("Skipping unparseable SHRUG row for id=%s", village_id)

    logger.info("Loaded %d village centroids from %s", len(centroids), csv_path)
    return centroids
