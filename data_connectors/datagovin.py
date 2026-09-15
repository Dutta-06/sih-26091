"""data.gov.in Open Government Data API client (used by ``census --build-index``).

Registration is free and self-serve (DATA_GOV_IN_API_KEY). Census 2011
Village/Town-wise Primary Census Abstract data is published per state as
separate resources, so each resource_id must be looked up on its catalog page
and listed in ``settings.census_resource_ids``; field names vary and are mapped
via ``settings.census_api_*_field``.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from common.net import DataUnavailable
from config.settings import settings
from data_connectors import http_request

logger = logging.getLogger(__name__)


class DataGovInError(DataUnavailable):
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
    """All records of a resource (offset/limit pagination). ``offline_fixture`` bypasses the network."""
    if offline_fixture is not None:
        return offline_fixture
    key = api_key or settings.data_gov_in_api_key
    if not key:
        raise DataGovInError("DATA_GOV_IN_API_KEY is not set (free key from data.gov.in -> My Account).")

    records: list[dict] = []
    offset, total = 0, None
    while total is None or offset < total:
        params = {"api-key": key, "format": "json", "offset": offset, "limit": page_size}
        params.update({f"filters[{k}]": v for k, v in (filters or {}).items()})
        payload = http_request("data.gov.in", "GET", f"{settings.data_gov_in_base_url.rstrip('/')}/resource/{resource_id}",
                               params=params).json()
        if payload.get("status") != "ok":
            raise DataGovInError(f"data.gov.in returned non-ok status: {payload.get('message', payload)}")
        batch = payload.get("records", [])
        records.extend(batch)
        total = int(payload.get("total", len(records)))
        if not batch or (max_records is not None and len(records) >= max_records):
            break
        offset += len(batch)
        if offset < total:
            time.sleep(request_delay_seconds)
    logger.info("Fetched %d records from data.gov.in resource %s", len(records), resource_id)
    return records[:max_records] if max_records is not None else records
