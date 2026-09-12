"""
Generic client for the data.gov.in Open Government Data API
(api.data.gov.in), used to pull real Census 2011 village population figures
(TECHNICAL_SETUP.md Section 8.2 / IMPLEMENTATION_PLAN.md Section 3).

Confirmed mechanics: registration is free and self-serve (sign up at
data.gov.in with any email, generate an API key from your profile
immediately -- no approval wait), the API is a simple paginated REST GET,
and there's no published rate limit. This is unlike the LGD/NAPIX API (see
geocoding.py), which is gated behind a subscription-approval workflow.

What this module does NOT solve on its own: each Census "Village/Town-wise
Primary Census Abstract" dataset on data.gov.in is published per state (and
sometimes per district) as a separate resource with its own resource_id --
there's no single all-India resource. You have to look up the resource_id
for each state/district you need from that dataset's own catalog page (the
page has an "API" / "Access API" tab that shows the exact resource_id and a
working example call) and add it to settings.census_resource_ids. This
module can't discover those IDs on your behalf.

The exact field names each resource returns (village name, population,
etc.) also vary by state and haven't been verified against a live response
here -- settings.census_api_*_field let you correct the column-name mapping
without touching this code once you've checked a real response.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)


class DataGovInError(RuntimeError):
    pass


def fetch_resource_records(
    resource_id: str,
    *,
    api_key: Optional[str] = None,
    filters: Optional[dict] = None,
    page_size: int = 100,
    max_records: Optional[int] = None,
    request_delay_seconds: float = 0.3,
    offline_fixture: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Fetch every record from a data.gov.in resource, paginating
    automatically via offset/limit.

    `offline_fixture` returns a canned record list instead of hitting the
    network -- used by tests.
    """
    if offline_fixture is not None:
        return offline_fixture

    key = api_key or settings.data_gov_in_api_key
    if not key:
        raise DataGovInError(
            "DATA_GOV_IN_API_KEY is not set. Register for a free key at "
            "https://data.gov.in (Sign Up -> My Account -> Generate API Key)."
        )

    records: list[dict] = []
    offset = 0
    total = None

    while total is None or offset < total:
        params = {
            "api-key": key,
            "format": "json",
            "offset": offset,
            "limit": page_size,
        }
        if filters:
            for field, value in filters.items():
                params[f"filters[{field}]"] = value

        resp = requests.get(
            f"{settings.data_gov_in_base_url}/resource/{resource_id}",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()

        if payload.get("status") != "ok":
            raise DataGovInError(f"data.gov.in returned non-ok status: {payload}")

        batch = payload.get("records", [])
        records.extend(batch)
        total = int(payload.get("total", len(records)))

        if not batch:
            break
        offset += len(batch)

        if max_records is not None and len(records) >= max_records:
            records = records[:max_records]
            break

        if offset < total:
            time.sleep(request_delay_seconds)

    logger.info("Fetched %d records from data.gov.in resource %s", len(records), resource_id)
    return records
