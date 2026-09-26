#!/usr/bin/env python3
"""Replay the assessment event stream and print a six-day account report."""

from decimal import Decimal

from ledger import ACCOUNTS, Event, Ledger


EVENTS = [
    Event("E1", 1, "CREDIT", "ACC-001", 1, Decimal("1200.00")),
    Event("E2", 1, "DEBIT", "ACC-001", 1, Decimal("950.00")),
    Event("E3", 2, "AUTHORIZATION", "ACC-001", 2,
          Decimal("200.00"), authorization_id="Auth-A"),
    Event("E4", 3, "CREDIT", "ACC-001", 3, Decimal("400.00")),
    Event("E5", 4, "SETTLEMENT", "ACC-001", 4,
          Decimal("185.00"), authorization_id="Auth-A"),
    Event("E6", 4, "SETTLEMENT", "ACC-001", 4,
          Decimal("180.00"), authorization_id="Auth-Z"),
    Event("E7", 5, "DEBIT", "ACC-001", 2, Decimal("620.00")),
    Event("E8", 5, "AUTHORIZATION", "ACC-001", 5,
          Decimal("90.00"), authorization_id="Auth-B"),
    Event("E9", 6, "REVERSAL", "ACC-001", 2,
          reverses_event_id="E7"),
    Event("E10", 5, "CREDIT", "ACC-002", 5,
          Decimal("10.000"), installments=3),
]


def render_report(ledger: Ledger) -> str:
    lines = [
        "IN-MEMORY ACCOUNT LEDGER — FINAL VALUE-DATE REPORT",
        "Balances reflect all source events and appended fees; Day 6 includes interest capitalization.",
        "Fee assessment day is when the late value-dated event was processed, not the fee value date.",
        "",
    ]

    for day in range(1, 7):
        lines.append(f"DAY {day}")
        for account_id, spec in ACCOUNTS.items():
            closing = ledger.balance(account_id, day)
            lines.append(f"  {account_id} ({spec.currency}) closing ledger: {closing:.{spec.precision}f}")
            day_fees = ledger.fees_for(account_id, day)
            if day_fees:
                for fee in day_fees:
                    fee_amount = next(e.amount for e in ledger.entries
                                      if e.entry_id == fee.fee_entry_id)
                    lines.append(
                        f"    fee: {abs(fee_amount):.{spec.precision}f} {spec.currency}; "
                        f"trigger close before fee {fee.balance_before_fee:.{spec.precision}f}; "
                        f"assessed on Day {fee.assessed_on_day} after {fee.triggered_by_event}"
                    )
            else:
                lines.append("    fee assessments: none")

            day_interest = next(a for a in ledger.interest_accruals
                                if a.account_id == account_id and a.value_date == day)
            lines.append(
                f"    daily interest: {day_interest.amount:.{spec.precision}f} "
                f"on eligible close {day_interest.eligible_balance:.{spec.precision}f}"
            )

        transitions = [t for t in ledger.authorization_transitions if t.booked_day == day]
        if transitions:
            lines.append("  authorization states (transitions booked this day):")
            for transition in transitions:
                lines.append(f"    {transition.authorization_id}: {transition.state} — {transition.detail}")
        else:
            lines.append("  authorization states: no transitions")

        errors = [error for error in ledger.errors if error.booked_day == day]
        if errors:
            lines.append("  errors:")
            for error in errors:
                lines.append(f"    {error.event_id}: {error.message}")
        else:
            lines.append("  errors: none")
        lines.append("")

    lines.append("INTEREST CAPITALIZATION")
    for account_id, spec in ACCOUNTS.items():
        total = ledger.interest_totals[account_id]
        lines.append(
            f"  {account_id}: rounded daily accruals sum to {total:.{spec.precision}f} "
            f"{spec.currency}; one credit posted on Day 6"
        )

    lines.append("")
    lines.append("AUTHORIZATION FINAL STATES")
    for auth_id, auth in ledger.authorizations.items():
        spec = ACCOUNTS[auth.account_id]
        lines.append(
            f"  {auth_id}: {auth.state}; hold {auth.hold_amount:.{spec.precision}f} "
            f"{spec.currency}; settled {auth.settled_amount:.{spec.precision}f}"
        )

    return "\n".join(lines)


def main() -> None:
    ledger = Ledger().process(EVENTS)
    ledger.capitalize_interest()
    print(render_report(ledger))


if __name__ == "__main__":
    main()
