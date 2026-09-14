"""Agmarknet mandi prices via the data.gov.in open data API (TECHNICAL_SETUP.md Section 8.10).

Resource ``settings.commodity_price_resource_id`` (default: "Current Daily Price of
Various Commodities from Various Markets (Mandi)"). Records carry ``state``,
``district``, ``market``, ``commodity``, ``arrival_date`` (dd/mm/yyyy) and
``modal_price`` (INR per quintal). The default resource is a rolling current-day
feed, so history depth depends on the resource configured; the caller sees how
many months actually came back.

    python -m data_connectors.agmarknet --test-connection
"""

from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from typing import Any, Optional

import httpx

from common.net import DataUnavailable, require_live
from config.settings import settings
from orchestrator.state import MonthlyPrice

PAGE_SIZE = 1000
MAX_PAGES = 10
PRICE_UNIT = "INR per quintal (Agmarknet modal price)"


def _month(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(text[:19] if "T" in text else text, fmt).strftime("%Y-%m")
        except ValueError:
            continue
    return None


def _modal(record: dict[str, Any]) -> Optional[float]:
    for key in ("modal_price", "Modal_Price", "modal_x0020_price", "Modal_x0020_Price"):
        if key in record:
            try:
                price = float(record[key])
            except (TypeError, ValueError):
                return None
            return price if price > 0 else None
    return None


def parse_records(records: list[dict[str, Any]], months: int = 36) -> list[MonthlyPrice]:
    """Median modal price per calendar month, oldest first, limited to the latest ``months``."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for rec in records:
        month, price = _month(rec.get("arrival_date") or rec.get("Arrival_Date")), _modal(rec)
        if month and price is not None:
            buckets[month].append(price)
    ordered = sorted(buckets)[-months:] if months > 0 else sorted(buckets)
    return [MonthlyPrice(month=m, modal_price=round(statistics.median(buckets[m]), 2)) for m in ordered]


def _fetch(commodity: str, state: Optional[str], district: Optional[str]) -> list[dict[str, Any]]:
    url = f"{settings.data_gov_in_base_url.rstrip('/')}/resource/{settings.commodity_price_resource_id}"
    params: dict[str, Any] = {
        "api-key": settings.data_gov_in_api_key,
        "format": "json",
        "limit": PAGE_SIZE,
        "filters[commodity]": commodity,
    }
    if state:
        params["filters[state]"] = state
    if district:
        params["filters[district]"] = district
    records: list[dict[str, Any]] = []
    for page in range(MAX_PAGES):
        params["offset"] = page * PAGE_SIZE
        try:
            resp = httpx.get(url, params=params, timeout=settings.http_timeout_seconds)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DataUnavailable(f"agmarknet: request failed ({exc.__class__.__name__}: {exc})") from exc
        batch = payload.get("records") or []
        records.extend(batch)
        total = payload.get("total")
        if len(batch) < PAGE_SIZE or (isinstance(total, int) and len(records) >= total):
            break
    return records


def fetch_monthly_prices(
    commodity: str, state: Optional[str], district: Optional[str], months: int = 36
) -> list[MonthlyPrice]:
    """Monthly modal prices for a commodity; district first, then state-wide. Raises ``DataUnavailable``."""
    require_live("agmarknet")
    if not settings.data_gov_in_api_key:
        raise DataUnavailable("agmarknet: DATA_GOV_IN_API_KEY not configured")
    if not settings.commodity_price_resource_id:
        raise DataUnavailable("agmarknet: COMMODITY_PRICE_RESOURCE_ID not configured")
    if not commodity:
        raise DataUnavailable("agmarknet: no commodity name")
    series: list[MonthlyPrice] = []
    if district:
        series = parse_records(_fetch(commodity, state, district), months)
    if not series:
        series = parse_records(_fetch(commodity, state, None), months)
    if not series:
        raise DataUnavailable(f"agmarknet: no parseable modal prices for '{commodity}' ({district or '-'}, {state or 'all states'})")
    return series


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agmarknet connector check")
    parser.add_argument("--test-connection", action="store_true")
    parser.add_argument("--commodity", default="Wheat")
    parser.add_argument("--state")
    args = parser.parse_args()
    try:
        prices = fetch_monthly_prices(args.commodity, args.state, None)
        print(f"OK: {len(prices)} month(s); latest {prices[-1].month} = {prices[-1].modal_price} {PRICE_UNIT}")
    except DataUnavailable as exc:
        print(f"UNAVAILABLE: {exc}")
