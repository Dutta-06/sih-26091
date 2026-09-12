"""CLI Pipeline Runner & Demonstration Tool.

Demonstrates the end-to-end execution of the Hyper-Local Business Advisory
and Financial Structuring Platform (SIH 26091).
"""

from __future__ import annotations

import argparse
import sys
import uuid

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from orchestrator.graph import build_graph
from orchestrator.router import route_conversational_turn
from orchestrator.state import CaseState

console = Console(force_terminal=True, legacy_windows=False)


def print_formatted_report(state: CaseState):
    """Renders a structured, institutional-grade report in the console."""
    console.print()
    console.print(
        Panel.fit(
            "[bold green]HYPER-LOCAL BUSINESS ADVISORY & FINANCIAL STRUCTURING PLATFORM[/bold green]\n"
            "[cyan]National SC/ST/OBC Concessional Lending Scheme Advisory (SIH 26091)[/cyan]",
            border_style="green",
        )
    )

    # 1. Entrepreneur Profile
    profile = state.entrepreneur_profile
    if profile:
        table_prof = Table(title="1. Entrepreneur Profile", show_header=True, header_style="bold magenta")
        table_prof.add_column("Attribute", style="dim")
        table_prof.add_column("Details")
        loc_str = f"{profile.location.village or 'Bhadohi'}, {profile.location.district or 'Bhadohi'}, {profile.location.state or 'Uttar Pradesh'}"
        table_prof.add_row("Location", loc_str)
        table_prof.add_row("Available Margin Capital", f"Rs. {profile.available_capital:,.2f} (10% Self-Contribution)")
        table_prof.add_row("Proposed Activity", profile.business_preference or "Dairy")
        table_prof.add_row("Identified Skills", ", ".join(profile.skills))
        table_prof.add_row("Available Premises", ", ".join(profile.assets))
        console.print(table_prof)

    # 2. Market Intelligence & Feasibility
    feasibility = state.feasibility_record
    market = state.market_intelligence
    if feasibility and market:
        table_feat = Table(title="2. Hyper-Local Feasibility & Market Intelligence", show_header=True, header_style="bold cyan")
        table_feat.add_column("Analysis Dimension", style="bold")
        table_feat.add_column("Verified Findings")
        table_feat.add_column("Confidence", justify="center")

        table_feat.add_row(
            "Market Reach (5-10 km)",
            f"Consumer base: ~{market.market_reach.consumer_base_estimate:,} persons | {len(market.market_reach.distribution_points)} primary distribution hubs identified",
            f"[green]{market.market_reach.source_confidence.upper()}[/green]",
        )
        table_feat.add_row(
            "Opportunity & Niche",
            f"Sub-niche: {market.opportunity.sector_niche} | Saturation: {market.opportunity.saturation_level.upper()} (score: {market.opportunity.saturation_score})",
            f"[green]{market.opportunity.source_confidence.upper()}[/green]",
        )
        table_feat.add_row(
            "Competitor Density",
            f"{market.competitor.estimated_competitor_count} local units ({market.competitor.density_per_10k_population:.2f}/10k pop) | District z-score: {market.competitor.z_score_vs_district:.2f}",
            f"[green]{market.competitor.source_confidence.upper()}[/green]",
        )
        table_feat.add_row(
            "Product Value & Pricing",
            f"Optimal target: Rs. {market.pricing.optimal_target_price:.2f} (Range: Rs. {market.pricing.min_market_price:.2f} - Rs. {market.pricing.max_market_price:.2f})",
            f"[green]{market.pricing.source_confidence.upper()}[/green]",
        )
        table_feat.add_row(
            "Threats & Supply Risk",
            f"{len(market.risk.risk_flags)} critical flags noted | Dry-period drop: {', '.join(market.risk.low_season_months)}",
            f"[green]{market.risk.source_confidence.upper()}[/green]",
        )
        table_feat.add_row(
            "Adversarial Review Verdict",
            f"[bold green]{feasibility.verdict.upper()}[/bold green]: {feasibility.verdict_reasoning}",
            "[green]AUDITED[/green]",
        )
        console.print(table_feat)

    # 3. Deterministic Financial Plan & Scheme Router
    plan = state.financial_plan
    if plan:
        table_fin = Table(title="3. Smart Scheme Calculator & Financial Structuring (Deterministic Core)", show_header=True, header_style="bold yellow")
        table_fin.add_column("Financial Metric", style="bold")
        table_fin.add_column("Computed Amount / Term")
        table_fin.add_column("Governing Formula / Logic")

        table_fin.add_row(
            "Beneficiary Margin Capital",
            f"Rs. {plan.available_margin_capital:,.2f}",
            "Stated 10% Contribution",
        )
        table_fin.add_row(
            "Total Feasible Project Cost",
            f"[bold]Rs. {plan.computed_project_cost:,.2f}[/bold]",
            "Available Margin / 0.10",
        )
        table_fin.add_row(
            "Concessional Loan Eligibility",
            f"[bold green]Rs. {plan.maximum_loan_eligibility:,.2f}[/bold green]",
            "90% of Project Cost",
        )
        table_fin.add_row(
            "Auto-Selected Scheme Tier",
            f"[bold yellow]{plan.scheme_tier.display_name}[/bold yellow]",
            f"Project cost within Rs. 1.40L - 50.00L tier threshold",
        )
        table_fin.add_row(
            "Concessional Interest Rate",
            f"{plan.scheme_tier.interest_rate * 100:.1f}% per annum",
            "Fixed statutory SCA rate",
        )
        table_fin.add_row(
            "Repayment Tenure",
            f"{plan.scheme_tier.tenure_years} Years ({len(plan.repayment_schedule)} Quarters)",
            "Standard amortized repayment cycle",
        )
        table_fin.add_row(
            "Moratorium Holiday Period",
            f"{plan.scheme_tier.moratorium_months} Months ({plan.scheme_tier.moratorium_months // 3} Quarters)",
            "Interest-only payment before regular amortization",
        )
        installment_due = plan.repayment_schedule[2].total_installment if len(plan.repayment_schedule) > 2 else plan.repayment_schedule[0].total_installment
        table_fin.add_row(
            "Quarterly Installment (Regular)",
            f"Rs. {installment_due:,.2f} per quarter",
            "Equal Quarterly Installment (EQI)",
        )
        table_fin.add_row(
            "Working Capital Allocation",
            f"Rs. {plan.working_capital_requirement:,.2f}",
            "20% operating cash reserve",
        )
        console.print(table_fin)

    # 4. Stress Test & Scenario Simulation
    if plan and plan.stress_test_result:
        stress = plan.stress_test_result
        table_stress = Table(title="4. Downside Scenario Stress Testing (Seasonal Dry-Period)", show_header=True, header_style="bold red")
        table_stress.add_column("Stress Parameter")
        table_stress.add_column("Value")
        table_stress.add_row("Simulated Revenue Contraction", f"{stress.revenue_drop_percentage:.0f}%")
        table_stress.add_row("Stressed Quarterly Operating Surplus", f"Rs. {stress.stressed_quarterly_surplus:,.2f}")
        table_stress.add_row("Quarterly Debt Service Due", f"Rs. {stress.quarterly_installment_due:,.2f}")
        table_stress.add_row("Debt Service Coverage Ratio (DSCR)", f"[bold green]{stress.debt_service_coverage_ratio:.2f}x[/bold green]")
        table_stress.add_row("Sustainability Assessment", "[bold green]SUSTAINABLE[/bold green]" if stress.is_sustainable else "[bold red]AT RISK[/bold red]")
        table_stress.add_row("Prudent Action", stress.buffer_recommendation)
        console.print(table_stress)

    # 5. Module 3: Launch & Post-Disbursement Monitoring
    if state.launch_roadmap:
        table_road = Table(title="5. Post-Disbursement Launch Roadmap & Monitoring", show_header=True, header_style="bold blue")
        table_road.add_column("Phase")
        table_road.add_column("Milestone")
        table_road.add_column("Target Timeline")
        table_road.add_column("Status")
        for m in state.launch_roadmap:
            table_road.add_row(
                f"Phase {m.phase_number}",
                m.title,
                f"Week {m.target_week}",
                "[green]DONE[/green]" if m.completed else "[yellow]PENDING[/yellow]",
            )
        console.print(table_road)


def main():
    parser = argparse.ArgumentParser(description="Run the central advisory and financial structuring pipeline.")
    parser.add_argument("--capital", type=float, default=100_000.0, help="Available margin capital in INR (default: 100,000)")
    parser.add_argument("--location", type=str, default="Bhadohi, Bhadohi, Uttar Pradesh", help="Location (Village, Block, District)")
    parser.add_argument("--category", type=str, default="Dairy Farming", help="Proposed business category")
    parser.add_argument("--demo", action="store_true", help="Run the canonical worked demo case")
    args = parser.parse_args()

    console.print("[bold green]Compiling Central Multi-Agent Orchestration Graph...[/bold green]")
    app = build_graph(with_checkpointer=True)

    session_id = f"sess_{str(uuid.uuid4())[:8]}"
    initial_message = (
        f"I have {args.capital:,.0f} rupees available margin capital and want to start a {args.category} in {args.location}"
    )

    console.print(f"[cyan]Processing User Input:[/cyan] \"{initial_message}\"")
    state, response_text = route_conversational_turn(initial_message)
    console.print(f"[dim]{response_text}[/dim]")

    # Run the compiled StateGraph
    config = {"configurable": {"thread_id": session_id}}
    result_state_dict = app.invoke(state, config=config)

    # Format into CaseState object if dict returned
    if isinstance(result_state_dict, dict):
        final_state = CaseState.model_validate(result_state_dict)
    else:
        final_state = result_state_dict

    print_formatted_report(final_state)


if __name__ == "__main__":
    main()
