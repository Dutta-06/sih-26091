"""SMS alert parser tests with synthetic messages (no real account numbers)."""

import datetime as dt

from data_connectors.sms_parser import parse_notifications

SAMPLES = [
    # (message, expected (direction, amount, channel, loan, date) or None)
    ("Rs.2,450.00 credited to A/c XX0001 on 05-08-26 by UPI ref 000011112222. Avl Bal Rs.18,300.50",
     ("credit", 2450.0, "upi", False, dt.date(2026, 8, 5))),
    ("INR 12,000 debited from A/c no. XX0002 on 07/08/2026 NEFT to FEED SUPPLIER. Avl bal INR 4,120",
     ("debit", 12000.0, "neft_imps", False, dt.date(2026, 8, 7))),
    ("Dear Customer, ₹560 received from payer@okaxis via UPI on 09-Aug-26.",
     ("credit", 560.0, "upi", False, dt.date(2026, 8, 9))),
    ("Your a/c XX0003 is debited for Rs 8,945.86 on 10-Aug-2026 towards Loan EMI. NACH ref 99990000",
     ("debit", 8945.86, "other", True, dt.date(2026, 8, 10))),
    ("Rs 2000 withdrawn at ATM from A/c XX0004 on 11/08/26.",
     ("debit", 2000.0, "atm", False, dt.date(2026, 8, 11))),
    ("Cash deposit of Rs.5,000 credited to your account XX0005 on 12-08-2026.",
     ("credit", 5000.0, "cash_deposit", False, dt.date(2026, 8, 12))),
    ("Rs.349 spent on your Card XX0006 at KIRANA POS on 13 Aug 2026.",
     ("debit", 349.0, "card", False, dt.date(2026, 8, 13))),
    ("IMPS: INR 1,500.00 credited to A/c XX0007 from SENDER. Ref 123456.",
     ("credit", 1500.0, "neft_imps", False, None)),
    ("Loan instalment of Rs 3,000 paid via UPI on 14-08-26 for loan a/c XX0008.",
     ("debit", 3000.0, "upi", True, dt.date(2026, 8, 14))),
    ("123456 is your OTP for a transaction of Rs 4,999. Do not share it with anyone.", None),
    ("Congratulations! You are pre-approved for a personal loan of Rs 5,00,000. Apply now.", None),
    ("Your EMI of Rs 8,945 is due on 15-09-2026. Maintain sufficient balance.", None),
]


def test_parses_realistic_alerts():
    records = parse_notifications([m for m, _ in SAMPLES])
    expected = [e for _, e in SAMPLES if e is not None]
    assert len(records) == len(expected)
    for rec, (direction, amount, channel, loan, date) in zip(records, expected):
        assert (rec.direction, rec.amount, rec.channel, rec.is_loan_repayment) == (direction, amount, channel, loan)
        if date:
            assert dt.datetime.fromisoformat(rec.occurred_at).date() == date


def test_missing_date_defaults_to_now_and_no_text_retained():
    rec = parse_notifications([SAMPLES[7][0]])[0]
    assert abs((dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(rec.occurred_at)).total_seconds()) < 60
    dumped = rec.model_dump_json()
    assert "SENDER" not in dumped and "XX0007" not in dumped


def test_ignores_garbage():
    assert parse_notifications(["", "hello", "Rs 500"]) == []
