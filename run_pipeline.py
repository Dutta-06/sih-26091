"""CLI runner: one case through the orchestrator graph, reported from the real resulting state.

Usage: python run_pipeline.py --demo
       python run_pipeline.py --capital 12000 --location "Bhadohi, Uttar Pradesh" --category tailoring --reason "I know stitching"
"""

from __future__ import annotations

import argparse
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table

from module1_feasibility.profiling_agent import extract_profile_from_slots
from orchestrator.graph import build_graph, run_case
from orchestrator.router import route_conversational_turn
from orchestrator.state import CaseState

console = Console()
DEMO = {"capital": 100_000.0, "location": "Bhadohi, Uttar Pradesh", "category": "dairy", "reason": "my family keeps buffaloes"}


def _conf(value: str) -> str:
    return f"[green]{value}[/green]" if value == "real" else f"[yellow]{value}[/yellow]"


def _fmt(value, pattern: str = "{:,.0f}", missing: str = "unknown") -> str:
    return missing if value is None else pattern.format(value)


def print_report(state: CaseState) -> None:
    p = state.entrepreneur_profile
    if p:
        t = Table(title="Entrepreneur profile", show_header=False)
        loc = p.location
        place = ", ".join(x for x in (loc.village, loc.block, loc.district, loc.state) if x) or p.location_query
        t.add_row("Location", f"{place} ({loc.resolution_method}, {_conf(loc.source_confidence)})")
        t.add_row("Margin capital", f"Rs {p.available_capital:,.0f}")
        t.add_row("Preference", f"{p.business_preference or '-'}" + (f" because {p.preference_reason}" if p.preference_reason else ""))
        for c in p.constraints:
            t.add_row("Constraint", c)
        console.print(t)

    if state.business_shortlist:
        t = Table(title="Discovery shortlist (top 5)")
        for col in ("Rank", "Activity", "Score", "Notes"):
            t.add_column(col)
        for c in state.business_shortlist[:5]:
            notes = "user preference" if c.is_user_preference else (f"adjacent to {c.adjacent_to}" if c.adjacent_to else "")
            t.add_row(str(c.rank), c.category, f"{c.feasibility_score:.1f}", notes)
        console.print(t)

    mi = state.market_intelligence
    if mi:
        t = Table(title="Market intelligence")
        for col in ("Analysis", "Finding", "Confidence"):
            t.add_column(col)
        t.add_row("Market reach", f"consumers {_fmt(mi.market_reach.consumer_base_estimate)} within {mi.market_reach.radius_km:g} km; "
                  f"{len(mi.market_reach.distribution_points)} distribution points", _conf(mi.market_reach.source_confidence))
        t.add_row("Opportunity", f"{mi.opportunity.sector_niche or '-'}; saturation {mi.opportunity.saturation_level}", _conf(mi.opportunity.source_confidence))
        t.add_row("Competitors", f"{_fmt(mi.competitor.estimated_competitor_count)} nearby; density {_fmt(mi.competitor.density_per_10k_population, '{:.2f}')}/10k; "
                  f"z {_fmt(mi.competitor.z_score_vs_district, '{:+.2f}')} ({mi.competitor.fallback_tier_used})", _conf(mi.competitor.source_confidence))
        t.add_row("Pricing", f"{_fmt(mi.pricing.min_market_price)}-{_fmt(mi.pricing.max_market_price)} {mi.pricing.recommended_price_unit} "
                  f"({mi.pricing.price_source_type})", _conf(mi.pricing.source_confidence))
        t.add_row("Risk", f"severity {mi.risk.overall_severity}; low months {', '.join(mi.risk.low_season_months) or '-'}", _conf(mi.risk.source_confidence))
        t.add_row("Supply chain", f"raw materials {mi.supply_chain.raw_material_availability}; lead time {_fmt(mi.supply_chain.lead_time_days, '{:g} days')}",
                  _conf(mi.supply_chain.source_confidence))
        if mi.missing_branches:
            t.add_row("Missing", ", ".join(mi.missing_branches), "")
        console.print(t)

    r = state.feasibility_record
    if r:
        console.print(f"\n[bold]Feasibility verdict:[/bold] {r.selected_category or '-'} -> [bold]{r.verdict}[/bold]")
        for e in r.rejection_history:
            console.print(f"  attempt {e.attempt_number}: {e.category} {e.verdict}: " + "; ".join(e.reasons))
        if r.alternatives_exhausted:
            console.print("  [red]Alternatives exhausted: no activity passed review. Rejection is a valid outcome.[/red]")
        for line in r.adversarial_critique:
            console.print(f"  - {line}")
        if r.preference_reason_context:
            console.print(f"  context: {r.preference_reason_context}")
        if r.swot.budget_scaling_notes:
            console.print(f"  budget: {r.swot.budget_scaling_notes}")

    plan = state.financial_plan
    if plan:
        if plan.eligibility_status != "eligible":
            console.print(f"\n[red]Not eligible:[/red] {plan.ineligibility_reason}")
        else:
            t = Table(title="Financial plan (deterministic core)", show_header=False)
            t.add_row("Project cost", f"Rs {plan.computed_project_cost:,.0f}")
            t.add_row("Loan eligibility", f"Rs {plan.maximum_loan_eligibility:,.0f}")
            if plan.scheme_tier:
                s = plan.scheme_tier
                t.add_row("Scheme tier", f"{s.display_name}: {s.interest_rate:.2%}, {s.tenure_years} years, {s.moratorium_months} months moratorium")
            t.add_row("Quarterly installment", f"Rs {plan.regular_quarterly_installment:,.0f}")
            t.add_row("Base DSCR", _fmt(plan.base_debt_service_coverage_ratio, "{:.2f}"))
            if plan.stress_test_result:
                st = plan.stress_test_result
                t.add_row("Stress test", f"{st.scenario_name}: min DSCR {st.debt_service_coverage_ratio:.2f}, "
                          f"{st.deficit_quarters} deficit quarters, {'sustainable' if st.is_sustainable else 'at risk'}")
            console.print(t)

    a = state.application_status
    if a:
        console.print(f"\n[bold]Application:[/bold] {a.disbursement_status}"
                      + (f"; next: {a.next_required_prompt or a.next_required_field}" if a.next_required_field else ""))
    if state.launch_roadmap:
        console.print("\n[bold]Launch roadmap[/bold]")
        for m in state.launch_roadmap:
            console.print(f"  week {m.target_week}: {m.title}")
    if state.monitoring_record:
        snap = state.monitoring_record[-1]
        console.print(f"\n[bold]Monitoring:[/bold] health {_fmt(snap.health_score, '{:.0f}')} ({snap.health_band}); {snap.coverage_note}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one case through the orchestrator graph.")
    parser.add_argument("--capital", type=float)
    parser.add_argument("--location", type=str)
    parser.add_argument("--category", type=str)
    parser.add_argument("--reason", type=str)
    parser.add_argument("--demo", action="store_true", help=f"use the demo inputs {DEMO}")
    args = parser.parse_args()
    inputs = dict(DEMO) if args.demo else {}
    inputs.update({k: v for k, v in vars(args).items() if k != "demo" and v is not None})
    missing = [k for k in ("capital", "location", "category") if not inputs.get(k)]
    if missing:
        parser.error(f"missing {', '.join('--' + m for m in missing)} (or use --demo)")

    reason = f" because {inputs['reason']}" if inputs.get("reason") else ""
    message = f"I have Rs {inputs['capital']:.0f} and want to start {inputs['category']} in {inputs['location']}{reason}"
    console.print(f"[cyan]Input:[/cyan] {message}")
    state, reply, run_graph = route_conversational_turn(message)
    console.print(f"[dim]{reply}[/dim]")
    if not run_graph:  # CLI arguments are authoritative even when the text parser misses a slot
        state.entrepreneur_profile = extract_profile_from_slots(
            inputs["location"], inputs["capital"], business_preference=inputs["category"], preference_reason=inputs.get("reason"))
        state.session_meta.requested_stage = "profiling"
    print_report(run_case(build_graph(with_checkpointer=True), state))


if __name__ == "__main__":
    main()
