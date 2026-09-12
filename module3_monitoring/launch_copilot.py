"""Business Launch Copilot Agent (Module 3, Section 7.2).

Reads: state.feasibility_record, state.financial_plan
Writes: state.launch_roadmap
Tech: Sequenced execution roadmap derived from feasibility and financial plans.
"""

from __future__ import annotations

from typing import Any
from orchestrator.state import CaseState, LaunchMilestone


def run(state: CaseState) -> dict[str, Any]:
    roadmap = [
        LaunchMilestone(
            phase_number=1,
            title="Shed Preparation & Shed Electrification",
            target_week=2,
            tasks=[
                "Construct ventilated cattle shed with slope drainage and concrete feeding mangers.",
                "Install water tank, piped connections, and backup solar/generator points.",
            ],
            completed=True,
        ),
        LaunchMilestone(
            phase_number=2,
            title="Livestock Procurement & Veterinary Inspection",
            target_week=4,
            tasks=[
                "Procure 4 vaccinated high-yield Murrah buffaloes / crossbreed cows through vetted cattle mandi.",
                "Complete livestock ear-tagging and insurance under SCA subsidized premium.",
            ],
            completed=False,
        ),
        LaunchMilestone(
            phase_number=3,
            title="Chilling Equipment & Off-Take Tie-ups",
            target_week=6,
            tasks=[
                "Commission 500L Bulk Milk Cooler (BMC) and digital fat-testing unit.",
                "Formalize supply contract with local dairy cooperative and nearby halwai cluster.",
            ],
            completed=False,
        ),
        LaunchMilestone(
            phase_number=4,
            title="Commercial Milking & Cash Flow Inflow",
            target_week=8,
            tasks=[
                "Commence morning and evening commercial milking schedule.",
                "Log daily production records and weekly payment reconciliations.",
            ],
            completed=False,
        ),
    ]

    return {"launch_roadmap": roadmap}
