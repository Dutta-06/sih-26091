"""
Shared test fixtures. Resets the in-process caches in data_connectors
(module-level dicts, by design -- see their docstrings on Nominatim/Overpass
policy compliance) before every test, so fixture data from one test can't
leak into another test that happens to query the same coordinates.
"""
from __future__ import annotations

import pytest

from data_connectors import geocoding, overpass


@pytest.fixture(autouse=True)
def _reset_connector_caches():
    geocoding._cache.clear()
    overpass._cache.clear()
    yield
    geocoding._cache.clear()
    overpass._cache.clear()
