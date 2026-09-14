"""Network gate shared by all data connectors.

Connectors must call :func:`live_enabled` before any outbound request so that
``DATA_MODE=offline`` (the default, and what the test-suite uses) never touches
the network. Failures in live mode raise :class:`DataUnavailable`, which agents
catch and turn into a labeled estimate plus a ``limitations`` entry.
"""

from __future__ import annotations

from config.settings import settings


class DataUnavailable(RuntimeError):
    """Raised when a real data source cannot be used in this run."""


def live_enabled() -> bool:
    return settings.data_mode == "live"


def require_live(source: str) -> None:
    if not live_enabled():
        raise DataUnavailable(f"{source}: skipped (DATA_MODE=offline)")
