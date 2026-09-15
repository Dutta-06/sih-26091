"""Procurement Coordinator (Module 3, TDD 7.1).

Reads: state.entrepreneur_profile.location.district, selected activity (catalog key_inputs),
       competitor intelligence from Module 1 (density / count), cross-case procurement store
Writes: procurement store membership for (district, catalog activity); state.procurement_recommendation
Tech: category + district clustering over the cross-case store (orchestrator.stores), separate from CaseState

Only entrepreneurs who actually enrolled through this platform are counted as cluster members; Module 1
competitor counts are reported as the potential peer pool, never as enrolled peers.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from config.settings import settings
from module3_monitoring._case import activity, district, intel
from orchestrator import stores
from orchestrator.state import CaseState, ProcurementRecommendation


def run(state: CaseState) -> dict[str, Any]:
    dist, act = district(state), activity(state)
    if not dist or not act:
        return {}
    items = list(act.get("key_inputs", []))
    stores.join_procurement_cluster(dist, act["id"], state.session_meta.session_id, items)
    members = stores.procurement_cluster_members(dist, act["id"])
    counts = Counter(i for m in members for i in m["items"])
    pooled = [i for i in items if counts[i] >= 2] or items

    ready = len(members) >= settings.procurement_min_peers
    notes = [
        f"{len(members)} entrepreneur(s) enrolled for {act['category']} in {dist} (including this case); "
        f"pooled ordering needs at least {settings.procurement_min_peers}.",
    ]
    if not ready:
        notes.append("Cluster stays open: this case will be matched as other funded entrepreneurs in the "
                     "district enrol. Buy an initial lot individually meanwhile.")
    comp = intel(state, "competitor")
    if comp is not None and (comp.estimated_competitor_count is not None or comp.density_per_10k_population is not None):
        parts = []
        if comp.estimated_competitor_count is not None:
            parts.append(f"{comp.estimated_competitor_count} similar enterprises")
        if comp.density_per_10k_population is not None:
            parts.append(f"{comp.density_per_10k_population:.1f} per 10k population")
        notes.append(f"Module 1 competitor density ({', '.join(parts)}, {comp.source_confidence}) indicates the "
                     "potential peer pool for pooled purchases; those enterprises are not enrolled members.")
    else:
        notes.append("Module 1 competitor density is unavailable, so the potential peer pool is unknown.")

    slug = re.sub(r"[^a-z0-9]+", "-", dist.lower()).strip("-")
    return {"procurement_recommendation": ProcurementRecommendation(
        cluster_id=f"{slug}::{act['id']}",
        district=dist,
        business_category=act["category"],
        pooled_items=pooled,
        enrolled_peer_count=len(members),
        status="ready_to_order" if ready else "insufficient_peers",
        notes=notes,
    )}
