"""
Local CLI to run the two implemented agents (Market Reach + Opportunity)
end-to-end against a sample entrepreneur profile.

Usage:
    python run_pipeline.py --location "Sample Village A, Sample District, Sample State" --category dairy

Note: this hits the live public Nominatim and Overpass endpoints unless you
adapt it to inject offline fixtures (see tests/ for examples), and will
only resolve locations/population figures that exist in whatever
CENSUS_DATA_PATH / LGD_DATA_PATH you've configured -- by default, the
sample fixtures in data/.
"""
from __future__ import annotations

import argparse
import json
import logging
import uuid

from orchestrator.graph import build_graph
from orchestrator.state import CaseState, EntrepreneurProfile, SessionMeta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", required=True, help="Village/block/district name to resolve")
    parser.add_argument("--category", required=True, help="Business category, e.g. 'dairy'")
    parser.add_argument("--capital", type=float, default=100000.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    state = CaseState(
        entrepreneur_profile=EntrepreneurProfile(
            location_query=args.location,
            available_capital=args.capital,
        ),
        selected_business_category=args.category,
        session_meta=SessionMeta(session_id=str(uuid.uuid4())),
    )

    graph = build_graph()
    result = graph.invoke(state)

    # LangGraph may hand back a dict or a CaseState depending on version --
    # normalize either way before printing.
    final_state = result if isinstance(result, CaseState) else CaseState.model_validate(result)

    print(json.dumps(final_state.model_dump(mode="json"), indent=2, default=str))


if __name__ == "__main__":
    main()
