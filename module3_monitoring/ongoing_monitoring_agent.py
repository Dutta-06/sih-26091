"""Ongoing Monitoring Agent (Module 3, TDD 7.3).

Reads: state.session_meta.pending_transactions (parsed by data_connectors.sms_parser), state.financial_plan,
       state.application_status.disbursement_date, seasonal profile (risk intel or catalog)
Writes: state.monitoring_record (appends one HealthSnapshot), state.session_meta (pending_transactions cleared)
Tech: consent-gated aggregation of structured transaction records; raw SMS text never reaches this node

Approximate creditworthiness index (0-100, NOT a credit score), computed over calendar weeks of the period:
    regularity  = share of weeks with at least one non-loan credit
    consistency = max(0, 1 - CV) where CV = std / mean of weekly credit totals
    repayment   = 1.0 paid | 0.8 not_due | 0.5 grace_period or unknown | 0.0 overdue
    index       = 100 * (0.4 * regularity + 0.3 * consistency + 0.3 * repayment)
It is left ``None`` when the period covers fewer than two weeks.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any, Optional

from config.settings import settings
from module3_monitoring._case import activity, intel, parse_ts
from orchestrator.state import CaseState, HealthSnapshot, TransactionRecord

MIN_PERIOD_DAYS = 7  # a shorter window is treated as one week so pro-rata baselines stay meaningful
DAYS_PER_QUARTER = 91.25
_REPAYMENT_FACTOR = {"paid": 1.0, "not_due": 0.8, "grace_period": 0.5, "unknown": 0.5, "overdue": 0.0}


def _seasonal_factor(state: CaseState, start: dt.date, days: int) -> float:
    risk = intel(state, "risk")
    index = list(getattr(risk, "seasonal_index", []) or [])
    if len(index) < 12:
        index = list((activity(state) or {}).get("seasonal_profile") or [])
    if len(index) < 12:
        return 1.0
    return sum(index[(start + dt.timedelta(days=i)).month - 1] for i in range(days)) / days


def _installment(state: CaseState, start: dt.date, days: int, repaid: float) -> tuple[float, str]:
    plan = state.financial_plan
    if plan is None or plan.eligibility_status != "eligible":
        return 0.0, "unknown"
    scale = days / DAYS_PER_QUARTER
    disbursed = parse_ts(state.application_status.disbursement_date) if state.application_status else None
    entry = None
    if disbursed and plan.repayment_schedule:
        quarter = int((start - disbursed.date()).days // DAYS_PER_QUARTER) + 1
        entry = next((q for q in plan.repayment_schedule if q.quarter_number == quarter), None)
    full = plan.regular_quarterly_installment or max(
        (q.total_installment for q in plan.repayment_schedule if not q.is_moratorium), default=0.0)
    if entry is not None:
        full = entry.total_installment
    due = round(full * scale, 2)
    if entry is not None and entry.is_moratorium:
        return due, "not_due"
    if full <= 0:
        return 0.0, "unknown"
    if repaid >= 0.95 * min(full, due):
        return due, "paid"
    if days >= DAYS_PER_QUARTER:
        return due, "overdue"
    return due, "grace_period" if repaid > 0 else "unknown"


def creditworthiness_index(credits: list[TransactionRecord], start: dt.date, days: int, status: str) -> Optional[float]:
    weeks = math.ceil(days / 7)
    if weeks < 2:
        return None
    totals = [0.0] * weeks
    for t in credits:
        ts = parse_ts(t.occurred_at)
        if ts:
            totals[min(weeks - 1, max(0, (ts.date() - start).days // 7))] += t.amount
    regularity = sum(1 for v in totals if v > 0) / weeks
    mean = sum(totals) / weeks
    cv = math.sqrt(sum((v - mean) ** 2 for v in totals) / weeks) / mean if mean > 0 else float("inf")
    consistency = max(0.0, 1.0 - cv)
    return round(100 * (0.4 * regularity + 0.3 * consistency + 0.3 * _REPAYMENT_FACTOR[status]), 1)


def run(state: CaseState) -> dict[str, Any]:
    meta = state.session_meta
    if not (settings.sms_monitoring_enabled and meta.consent_sms_monitoring):
        return {}
    txns = list(meta.pending_transactions)
    if not txns:
        return {}
    dates = [d.date() for d in (parse_ts(t.occurred_at) for t in txns) if d]
    today = dt.datetime.now(dt.timezone.utc).date()
    start, end = (min(dates), max(dates)) if dates else (today, today)
    days = max(MIN_PERIOD_DAYS, (end - start).days + 1)

    credits = [t for t in txns if t.direction == "credit" and not t.is_loan_repayment]
    revenue = sum(t.amount for t in credits)
    expenses = sum(t.amount for t in txns if t.direction == "debit" and not t.is_loan_repayment)
    repaid = sum(t.amount for t in txns if t.direction == "debit" and t.is_loan_repayment)
    due, status = _installment(state, start, days, repaid)

    projection = state.financial_plan.operating_projection if state.financial_plan else None
    baseline = 0.0
    if projection and projection.annual_revenue:
        baseline = projection.annual_revenue * days / 365 * _seasonal_factor(state, start, days)

    snapshot = HealthSnapshot(
        period_label=f"{start.isoformat()} to {end.isoformat()} ({days} days)",
        transactions_parsed=len(txns),
        reported_revenue=round(revenue, 2),
        projected_baseline_revenue=round(baseline, 2),
        reported_expenses=round(expenses, 2),
        operating_surplus=round(revenue - expenses, 2),
        installment_due=due,
        loan_installment_status=status,
        approximate_creditworthiness_index=creditworthiness_index(credits, start, days, status),
        is_consent_verified=True,
    )
    return {
        "monitoring_record": [*state.monitoring_record, snapshot],
        "session_meta": meta.model_copy(update={"pending_transactions": []}),
    }
