"""
Base adapter contract.

Every external data dependency (TDD Section 8) is wrapped in an adapter
that returns an AdapterResult so agents never touch raw HTTP/file-parsing
logic directly and never have to decide confidence labeling themselves —
the adapter that actually knows whether the data was real, estimated, or
missing decides that.

Design rule enforced here: adapters NEVER raise on "no data found" /
"endpoint unreachable" — they return INSUFFICIENT_DATA with a limitations
note. They MAY raise on programming errors (bad config, malformed
response) since those are bugs, not data-availability facts.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

from src.schemas import Confidence

T = TypeVar("T")


@dataclass
class AdapterResult(Generic[T]):
    data: Optional[T]
    confidence: Confidence
    source: str
    limitations: list[str] = field(default_factory=list)

    @classmethod
    def insufficient(cls, source: str, reason: str) -> "AdapterResult[Any]":
        return cls(data=None, confidence=Confidence.INSUFFICIENT_DATA, source=source, limitations=[reason])


class Adapter(abc.ABC):
    """Marker base class. Concrete adapters implement their own fetch
    method with a domain-specific signature (queries differ too much
    across geocoding / dataset lookups / pricing / routing to force one
    generic `fetch(**kwargs)` signature)."""

    name: str
