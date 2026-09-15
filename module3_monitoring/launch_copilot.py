"""Business Launch Copilot (Module 3, TDD 7.2).

Reads: selected activity (catalog licences, key_inputs, buyers, perishable), state.financial_plan (working capital,
       capex, moratorium), supply chain / market reach / pricing / risk intelligence from Module 1
Writes: state.launch_roadmap
Tech: deterministic, sequenced roadmap derived from case state; every milestone starts not completed

Timeline: the launch is fitted before the first principal repayment, i.e. within
(moratorium_months * 4.33 - 2) weeks (minimum 6); without a moratorium in the plan a 12-week window is assumed.
"""

from __future__ import annotations

from typing import Any

from module3_monitoring._case import activity, intel
from orchestrator.state import CaseState, LaunchMilestone

DEFAULT_WINDOW_WEEKS = 12


def _window(state: CaseState) -> tuple[int, str]:
    tier = state.financial_plan.scheme_tier if state.financial_plan else None
    if tier and tier.moratorium_months:
        weeks = max(6, round(tier.moratorium_months * 4.33) - 2)
        return weeks, f"Complete launch by week {weeks}, before principal repayment starts after the " \
                      f"{tier.moratorium_months}-month moratorium."
    return DEFAULT_WINDOW_WEEKS, (f"No moratorium is recorded in the financial plan; a {DEFAULT_WINDOW_WEEKS}-week "
                                  "launch window is assumed.")


def run(state: CaseState) -> dict[str, Any]:
    act = activity(state)
    if not act:
        return {}
    weeks, window_note = _window(state)
    plan = state.financial_plan
    supply, reach, pricing, risk = (intel(state, n) for n in ("supply_chain", "market_reach", "pricing", "risk"))
    inputs = act.get("key_inputs", [])

    licensing = [f"Obtain {lic}." for lic in act.get("licences", [])] or ["Complete Udyam registration."]

    suppliers = [f"Identify at least two sources for {i} and compare quotes." for i in inputs]
    if supply is not None:
        suppliers += [f"Contact {s} (supply-chain analysis, {supply.source_confidence})." for s in supply.major_suppliers[:3]]
        suppliers += [f"Line up a backup for single point of failure: {p}." for p in supply.single_points_of_failure[:2]]

    inventory = []
    if plan and plan.working_capital_requirement > 0:
        inventory.append(f"Plan the first stock of {', '.join(inputs[:3]) or 'inputs'} within the working-capital "
                         f"allocation of Rs {plan.working_capital_requirement:,.0f}.")
    else:
        inventory.append("Working capital is not yet fixed in the financial plan; size the first stock after sanction.")
    if plan and plan.capital_expenditure_allocation > 0:
        inventory.append(f"Complete capital purchases within Rs {plan.capital_expenditure_allocation:,.0f}.")
    if act.get("perishable"):
        inventory.append("Buy perishable inputs in small, frequent lots until sales volume is known.")

    customers = [f"Approach {b} for early orders." for b in act.get("buyers", [])]
    if reach is not None:
        customers += [f"Visit {p.name} ({p.type}" + (f", {p.distance_km:.0f} km" if p.distance_km is not None else "")
                      + ")." for p in reach.distribution_points[:3]]
    if pricing is not None and pricing.optimal_target_price:
        customers.append(f"Launch near Rs {pricing.optimal_target_price:,.0f} {pricing.recommended_price_unit or act.get('price_unit', '')}"
                         f" (pricing analysis, {pricing.source_confidence}).".replace("  ", " "))

    operations = [window_note]
    if risk is not None:
        operations += list(risk.mitigation_strategies[:3])
    operations.append("Consent to transaction-alert monitoring so enterprise health can be tracked against the plan.")

    phases = [
        ("Licences and registrations", "licensing", licensing, 0.25),
        ("Supplier discovery", "supplier_discovery", suppliers, 0.4),
        ("Initial inventory planning", "inventory", inventory, 0.6),
        ("Early customer acquisition", "customer_acquisition", customers, 0.8),
        ("Operations readiness before repayment", "operations", operations, 1.0),
    ]
    return {"launch_roadmap": [
        LaunchMilestone(phase_number=i, title=title, theme=theme, tasks=tasks,
                        target_week=max(1, round(weeks * frac)), completed=False)
        for i, (title, theme, tasks, frac) in enumerate(phases, start=1)
    ]}
