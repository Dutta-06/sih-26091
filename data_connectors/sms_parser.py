"""Transaction notification (SMS) parser for consented monitoring (TDD 7.3).

Reads: bank / UPI alert text handed over by the entrepreneur's device (consent is checked by the caller)
Writes: nothing - a pure function returning structured ``TransactionRecord`` values
Tech: regex templates for common Indian bank/UPI alert shapes; raw text is never stored or logged

Only the direction, amount, channel, date and a loan-repayment flag survive parsing.
Account numbers, counterparties, balances and the message text are discarded.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Optional

from orchestrator.state import TransactionRecord

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

_SKIP = re.compile(
    r"\botp\b|one[\s-]?time[\s-]?password|verification code|pre-?approved|apply now|limited period|"
    r"\boffer\b|congratulations|\bwin\b|lucky draw|will be debited|due on|is due|request(ed)? money|collect request",
    re.I,
)
_AMOUNT = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
_CREDIT = re.compile(r"\bcredited\b|\breceived\b|\bdeposited\b|\bcr\b", re.I)
_DEBIT = re.compile(r"\bdebited\b|\bwithdrawn\b|\bpaid\b|\bspent\b|\bsent\b|\bdr\b|\bpurchase\b|\btransferred\b", re.I)
_LOAN = re.compile(r"\bemi\b|\bloan\b|repayment|\binstal+ment\b|\bnach\b|\becs\b", re.I)
_CHANNELS = [
    ("upi", re.compile(r"\bupi\b|\bvpa\b|@[a-z]{2,}", re.I)),
    ("neft_imps", re.compile(r"\bneft\b|\bimps\b|\brtgs\b", re.I)),
    ("cash_deposit", re.compile(r"cash dep|\bcdm\b|cash deposit", re.I)),
    ("atm", re.compile(r"\batm\b|withdrawn", re.I)),
    ("card", re.compile(r"\bcard\b|\bpos\b", re.I)),
]
_DATE_NUM = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})\b")
_DATE_MON = re.compile(r"\b(\d{1,2})[-\s]?([A-Za-z]{3})[a-z]*[-\s,]*(\d{4}|\d{2})\b")


def _year(text: str) -> int:
    y = int(text)
    return y + 2000 if y < 100 else y


def _parse_date(text: str) -> Optional[dt.datetime]:
    for m in _DATE_MON.finditer(text):
        month = _MONTHS.get(m.group(2).lower())
        if month:
            try:
                return dt.datetime(_year(m.group(3)), month, int(m.group(1)), tzinfo=dt.timezone.utc)
            except ValueError:
                continue
    for m in _DATE_NUM.finditer(text):
        try:  # Indian alerts use day-first dates
            return dt.datetime(_year(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def _amount(text: str) -> Optional[float]:
    for m in _AMOUNT.finditer(text):
        if re.search(r"bal|limit", text[max(0, m.start() - 14):m.start()], re.I):
            continue  # available balance / credit limit, not the transaction amount
        value = float(m.group(1).replace(",", ""))
        if value > 0:
            return value
    return None


def parse_one(message: str) -> Optional[TransactionRecord]:
    if not message or _SKIP.search(message):
        return None
    amount = _amount(message)
    credit, debit = _CREDIT.search(message), _DEBIT.search(message)
    if amount is None or not (credit or debit):
        return None
    # "debited from A/c .. credited to VPA .." -> the verb that comes first is the account holder's view
    direction = "credit" if credit and (not debit or credit.start() < debit.start()) else "debit"
    channel = next((name for name, rx in _CHANNELS if rx.search(message)), "other")
    occurred = _parse_date(message) or dt.datetime.now(dt.timezone.utc)
    return TransactionRecord(
        occurred_at=occurred.isoformat(),
        direction=direction,
        amount=round(amount, 2),
        channel=channel,
        is_loan_repayment=direction == "debit" and bool(_LOAN.search(message)),
    )


def parse_notifications(messages: list[str]) -> list[TransactionRecord]:
    """Parse alerts into structured records; unrecognised, OTP and promotional messages are dropped."""
    return [rec for rec in (parse_one(m) for m in messages) if rec is not None]
