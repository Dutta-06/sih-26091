"""Open-data connectors. Every network call goes through ``common.net.require_live``."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from common.net import DataUnavailable, require_live
from config.settings import settings

logger = logging.getLogger(__name__)

_RETRYABLE = {429, 500, 502, 503, 504}
MAX_BACKOFF_SECONDS = 5.0


_warned_placeholder = False


def user_agent() -> str:
    global _warned_placeholder
    ua = settings.nominatim_user_agent
    if "set-your-email-here" in ua and not _warned_placeholder:
        _warned_placeholder = True
        logger.warning("NOMINATIM_USER_AGENT still contains the placeholder contact; "
                       "OSM usage policy requires a real contact address before live use.")
    return ua


def http_request(source: str, method: str, url: str, **kwargs: Any) -> httpx.Response:
    """One request (plus at most one retry after a short backoff on 429/5xx).

    Raises ``DataUnavailable`` in offline mode or when the source keeps failing.
    """
    require_live(source)
    kwargs.setdefault("timeout", settings.http_timeout_seconds)
    for attempt in (1, 2):
        try:
            resp = httpx.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise DataUnavailable(f"{source}: request failed ({exc})") from exc
        if resp.status_code in _RETRYABLE and attempt == 1:
            try:
                wait = float(resp.headers.get("Retry-After", 2.0))
            except ValueError:
                wait = 2.0
            logger.warning("%s returned HTTP %s; retrying once", source, resp.status_code)
            time.sleep(min(max(wait, 0.0), MAX_BACKOFF_SECONDS))
            continue
        if resp.status_code >= 400:
            raise DataUnavailable(f"{source}: HTTP {resp.status_code}")
        return resp
    raise DataUnavailable(f"{source}: no response")  # pragma: no cover
