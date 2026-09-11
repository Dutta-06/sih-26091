from __future__ import annotations

import pytest

from src.schemas import CaseState, SelectedBusiness


@pytest.fixture
def base_case_state() -> CaseState:
    return CaseState(
        case_id="case-001",
        entrepreneur_profile={
            "location": {
                "village": "Rampur",
                "block": "Sadar",
                "district": "Meerut",
                "state": "Uttar Pradesh",
                "latitude": 28.9845,
                "longitude": 77.7064,
            },
            "available_capital": 150000,
        },
        selected_business=SelectedBusiness(name="Grocery", sector="grocery"),
    )
