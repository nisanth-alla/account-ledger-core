# In-Memory Account Ledger Core

A small, deterministic Python implementation of the six-day account-ledger scenario. It uses only the Python standard library and keeps source events and ledger entries append-only.

## Requirements

- Python 3.10 or newer
- No third-party packages

## Run the event replay

From the repository root:

```bash
python3 replay.py
```

The report is a final value-date view after every supplied source event has been processed and interest has been capitalized. Each day shows account closing ledger balances, fees whose value date is that day, rounded interest for that day, authorization transitions booked that day, and errors booked that day. A late entry may therefore revise a past day's final balance. Fee lines separately show the day the fee was assessed and the event that triggered the assessment.

Interest is calculated from final daily balances before the single Day 6 capitalization entry. Day 6's displayed closing balance includes that credit.

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

All ordinary tests should pass. The suite also reports **one expected failure** (`expected failure`): a deliberately failing assertion that demonstrates why reversing the original debit does not erase already-appended overdraft fee entries. This is intentional and documented in `tests/test_known_limitation.py`; it is not an unreported test failure.

## Rebuild the architecture PDF

`ARCHITECTURE.pdf` is included. To regenerate it after editing `ARCHITECTURE.md`, run `python3 render_architecture_pdf.py` on a machine with Ghostscript's `ps2pdf` command available. This optional export tool is not needed to run the ledger or tests.

## Implementation choices

- `Decimal` is used for all money and interest; rounding is `ROUND_HALF_UP` at the account's currency precision.
- Source events are replayed in the given order. Booking day and value date are stored separately.
- A late money movement causes fee eligibility to be rechecked, in day order, through the latest booking day seen. A fee is appended once for each newly negative account/day. Existing fee entries are never deleted.
- A reversal appends an equal-and-opposite entry for the original movement. It does not reverse fees.
- BHD 10.000 is split into 3.334, 3.333, and 3.333 so the three installments reconcile exactly.

See `AMBIGUITIES.md` for the complete policy decisions, `REJECTED.md` for the supplied criteria this implementation refuses, and `NUMBERS.md` for numeric conventions.
