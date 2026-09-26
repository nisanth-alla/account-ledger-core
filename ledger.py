"""Append-only, in-memory account ledger for the six-day assessment scenario."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


ZERO = Decimal("0")
ONE = Decimal("1")
FEE_AED = Decimal("25.00")
DAILY_INTEREST_RATE = Decimal("0.0004")  # 0.04% per day
WINDOW_DAYS = 6


@dataclass(frozen=True)
class AccountSpec:
    account_id: str
    currency: str
    precision: int
    opening_balance: Decimal

    @property
    def quantum(self) -> Decimal:
        return ONE.scaleb(-self.precision)


ACCOUNTS = {
    "ACC-001": AccountSpec("ACC-001", "AED", 2, Decimal("0.00")),
    "ACC-002": AccountSpec("ACC-002", "BHD", 3, Decimal("0.000")),
}


def money(value: Decimal, spec: AccountSpec) -> Decimal:
    """Round a value once to the account currency's representable precision."""
    return value.quantize(spec.quantum, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Event:
    event_id: str
    booked_day: int
    kind: str
    account_id: str
    value_date: int
    amount: Decimal | None = None
    authorization_id: str | None = None
    reverses_event_id: str | None = None
    installments: int = 1


@dataclass(frozen=True)
class Entry:
    entry_id: str
    account_id: str
    value_date: int
    amount: Decimal
    kind: str
    source_event_id: str
    description: str


@dataclass(frozen=True)
class FeeAssessment:
    account_id: str
    value_date: int
    assessed_on_day: int
    balance_before_fee: Decimal
    fee_entry_id: str
    triggered_by_event: str


@dataclass(frozen=True)
class AuthorizationTransition:
    booked_day: int
    event_id: str
    authorization_id: str
    state: str
    detail: str


@dataclass(frozen=True)
class ReplayError:
    booked_day: int
    event_id: str
    message: str


@dataclass
class Authorization:
    authorization_id: str
    account_id: str
    hold_amount: Decimal
    state: str
    created_event_id: str
    settled_amount: Decimal = ZERO

    @property
    def active_hold(self) -> Decimal:
        if self.state == "APPROVED":
            return self.hold_amount - self.settled_amount
        return ZERO


@dataclass(frozen=True)
class InterestAccrual:
    account_id: str
    value_date: int
    eligible_balance: Decimal
    amount: Decimal


class Ledger:
    """Replays source events in stream order and appends derived ledger entries."""

    def __init__(self, accounts: dict[str, AccountSpec] | None = None) -> None:
        self.accounts = dict(accounts or ACCOUNTS)
        self._source_events: list[Event] = []
        self._entries: list[Entry] = []
        self.fee_assessments: list[FeeAssessment] = []
        self.authorization_transitions: list[AuthorizationTransition] = []
        self.errors: list[ReplayError] = []
        self.authorizations: dict[str, Authorization] = {}
        self._events_by_id: dict[str, Event] = {}
        self._reversed_event_ids: set[str] = set()
        self._assessed_fee_days: set[tuple[str, int]] = set()
        self._current_booked_day = 0
        self.interest_accruals: list[InterestAccrual] = []
        self.interest_totals: dict[str, Decimal] = {}

    @property
    def source_events(self) -> tuple[Event, ...]:
        return tuple(self._source_events)

    @property
    def entries(self) -> tuple[Entry, ...]:
        return tuple(self._entries)

    def _spec(self, account_id: str) -> AccountSpec:
        try:
            return self.accounts[account_id]
        except KeyError as exc:
            raise ValueError(f"Unknown account {account_id}") from exc

    def _append_entry(self, entry: Entry) -> None:
        """Append an immutable entry; existing entries are never rewritten."""
        self._entries.append(entry)

    def balance(self, account_id: str, value_date: int) -> Decimal:
        spec = self._spec(account_id)
        total = spec.opening_balance
        for entry in self.entries:
            if entry.account_id == account_id and entry.value_date <= value_date:
                total += entry.amount
        return money(total, spec)

    def active_holds(self, account_id: str) -> Decimal:
        spec = self._spec(account_id)
        total = sum(
            (auth.active_hold for auth in self.authorizations.values()
             if auth.account_id == account_id),
            ZERO,
        )
        return money(total, spec)

    def available_balance(self, account_id: str, value_date: int) -> Decimal:
        spec = self._spec(account_id)
        return money(self.balance(account_id, value_date) - self.active_holds(account_id), spec)

    def _error(self, event: Event, message: str) -> None:
        self.errors.append(ReplayError(event.booked_day, event.event_id, message))

    def _transition(self, event: Event, auth_id: str, state: str, detail: str) -> None:
        self.authorization_transitions.append(
            AuthorizationTransition(event.booked_day, event.event_id, auth_id, state, detail)
        )

    def _add_principal_entry(self, event: Event, amount: Decimal, kind: str, description: str) -> None:
        spec = self._spec(event.account_id)
        rounded = money(amount, spec)
        self._append_entry(
            Entry(event.event_id, event.account_id, event.value_date, rounded,
                  kind, event.event_id, description)
        )

    def _assess_fees_through(self, account_id: str, through_day: int, trigger_event: str) -> None:
        """Append a fee for each newly observed negative close through this day.

        Late value-dated postings can make a previously positive historical close
        negative. Such a day remains eligible until a fee is actually appended.
        Fees already appended are never removed by later corrections or reversals.
        """
        spec = self._spec(account_id)
        if spec.currency != "AED":
            return
        for value_date in range(1, through_day + 1):
            key = (account_id, value_date)
            close_before_fee = self.balance(account_id, value_date)
            if close_before_fee < ZERO and key not in self._assessed_fee_days:
                fee_id = f"FEE-{account_id}-D{value_date}"
                self._append_entry(
                    Entry(fee_id, account_id, value_date, -FEE_AED,
                          "OVERDRAFT_FEE", fee_id,
                          f"Daily overdraft fee assessed for Day {value_date}"),
                )
                self._assessed_fee_days.add(key)
                self.fee_assessments.append(
                    FeeAssessment(account_id, value_date, through_day,
                                  close_before_fee, fee_id, trigger_event)
                )

    @staticmethod
    def _split_amount(total: Decimal, parts: int, spec: AccountSpec) -> list[Decimal]:
        if parts < 1:
            raise ValueError("Installment count must be positive")
        total = money(total, spec)
        units = int(total / spec.quantum)
        sign = -1 if units < 0 else 1
        quotient, remainder = divmod(abs(units), parts)
        amounts = [quotient + (1 if index < remainder else 0) for index in range(parts)]
        return [money(Decimal(sign * units_part) * spec.quantum, spec) for units_part in amounts]

    def _process_credit_or_debit(self, event: Event) -> None:
        assert event.amount is not None
        spec = self._spec(event.account_id)
        direction = ONE if event.kind == "CREDIT" else -ONE
        if event.installments == 1:
            self._add_principal_entry(
                event, direction * event.amount, event.kind,
                f"{event.kind.lower()} posted from {event.event_id}",
            )
        else:
            pieces = self._split_amount(event.amount, event.installments, spec)
            for index, piece in enumerate(pieces, start=1):
                amount = direction * piece
                self._append_entry(
                    Entry(f"{event.event_id}-{index}", event.account_id, event.value_date,
                          money(amount, spec), event.kind, event.event_id,
                          f"{event.kind.lower()} installment {index}/{event.installments}"),
                )
        self._assess_fees_through(event.account_id, self._current_booked_day, event.event_id)

    def _process_authorization(self, event: Event) -> None:
        if event.authorization_id is None or event.amount is None:
            self._error(event, "Authorization requires an ID and hold amount")
            return
        if event.authorization_id in self.authorizations:
            self._error(event, f"Duplicate authorization ID {event.authorization_id}")
            self._transition(event, event.authorization_id, "REJECTED",
                             "duplicate authorization ID")
            return
        spec = self._spec(event.account_id)
        hold = money(event.amount, spec)
        available_before = self.available_balance(event.account_id, event.value_date)
        available_after = money(available_before - hold, spec)
        if hold <= ZERO:
            state = "DECLINED"
            detail = "hold must be positive"
        elif available_after < ZERO:
            state = "DECLINED"
            detail = (f"insufficient available balance: {available_before} before hold, "
                      f"{available_after} after hold")
        else:
            state = "APPROVED"
            detail = f"hold {hold} approved; ledger balance unchanged"
        self.authorizations[event.authorization_id] = Authorization(
            event.authorization_id, event.account_id, hold, state, event.event_id
        )
        self._transition(event, event.authorization_id, state, detail)
        if state == "DECLINED":
            self._error(event, detail)

    def _process_settlement(self, event: Event) -> None:
        auth_id = event.authorization_id
        if auth_id is None or auth_id not in self.authorizations:
            label = auth_id or "<missing ID>"
            message = f"Settlement rejected: authorization {label} is not present in the ledger"
            self._error(event, message)
            if auth_id:
                self._transition(event, auth_id, "SETTLEMENT_REJECTED", message)
            return
        auth = self.authorizations[auth_id]
        if auth.account_id != event.account_id:
            message = f"Settlement rejected: authorization {auth_id} belongs to another account"
            self._error(event, message)
            self._transition(event, auth_id, "SETTLEMENT_REJECTED", message)
            return
        if auth.state != "APPROVED":
            message = f"Settlement rejected: authorization {auth_id} is {auth.state.lower()}"
            self._error(event, message)
            self._transition(event, auth_id, "SETTLEMENT_REJECTED", message)
            return
        if event.amount is None:
            message = "Settlement requires an amount"
            self._error(event, message)
            self._transition(event, auth_id, "SETTLEMENT_REJECTED", message)
            return

        spec = self._spec(event.account_id)
        settlement = money(event.amount, spec)
        remaining_hold = money(auth.hold_amount - auth.settled_amount, spec)
        if settlement <= ZERO or settlement > remaining_hold:
            message = (f"Settlement rejected: amount {settlement} is outside remaining "
                       f"hold {remaining_hold}")
            self._error(event, message)
            self._transition(event, auth_id, "SETTLEMENT_REJECTED", message)
            return

        self._add_principal_entry(event, -settlement, "SETTLEMENT",
                                  f"settlement for authorization {auth_id}")
        auth.settled_amount = money(auth.settled_amount + settlement, spec)
        released = money(auth.hold_amount - auth.settled_amount, spec)
        auth.state = "SETTLED"
        self._transition(event, auth_id, "SETTLED",
                         f"settled {settlement}; released unused hold {released}")
        self._assess_fees_through(event.account_id, self._current_booked_day, event.event_id)

    def _process_reversal(self, event: Event) -> None:
        original_id = event.reverses_event_id
        if original_id is None or original_id not in self._events_by_id:
            message = f"Reversal rejected: original event {original_id or '<missing>'} not found"
            self._error(event, message)
            return
        if original_id in self._reversed_event_ids:
            message = f"Reversal rejected: event {original_id} has already been reversed"
            self._error(event, message)
            return
        original_event = self._events_by_id[original_id]
        if original_event.kind not in {"CREDIT", "DEBIT", "SETTLEMENT"}:
            message = f"Reversal rejected: event {original_id} is not a posted money movement"
            self._error(event, message)
            return
        originals = [entry for entry in self.entries if entry.entry_id == original_id]
        if len(originals) != 1:
            message = f"Reversal rejected: event {original_id} does not have one reversible entry"
            self._error(event, message)
            return
        original = originals[0]
        if original.account_id != event.account_id:
            message = f"Reversal rejected: event {original_id} belongs to another account"
            self._error(event, message)
            return
        if event.value_date < original.value_date:
            message = "Reversal rejected: reversal value date precedes the original value date"
            self._error(event, message)
            return
        spec = self._spec(event.account_id)
        reversal_amount = money(-original.amount, spec)
        self._append_entry(
            Entry(event.event_id, event.account_id, event.value_date, reversal_amount,
                  "REVERSAL", event.event_id, f"reversal of {original_id}"),
        )
        self._reversed_event_ids.add(original_id)
        self._assess_fees_through(event.account_id, self._current_booked_day, event.event_id)

    def process(self, events: Iterable[Event]) -> Ledger:
        for event in events:
            if event.event_id in self._events_by_id:
                raise ValueError(f"Duplicate event ID {event.event_id}")
            if event.account_id not in self.accounts:
                raise ValueError(f"Event {event.event_id} references unknown account {event.account_id}")
            if not 1 <= event.booked_day <= WINDOW_DAYS:
                raise ValueError(f"Event {event.event_id} booked day must be 1..{WINDOW_DAYS}")
            if not 1 <= event.value_date <= WINDOW_DAYS:
                raise ValueError(f"Event {event.event_id} value date must be 1..{WINDOW_DAYS}")

            # Normalize before the immutable source record enters the event log.
            if event.amount is not None:
                event = Event(
                    event.event_id, event.booked_day, event.kind, event.account_id,
                    event.value_date, money(event.amount, self._spec(event.account_id)),
                    event.authorization_id, event.reverses_event_id, event.installments,
                )

            self._events_by_id[event.event_id] = event
            self._source_events.append(event)
            self._current_booked_day = max(self._current_booked_day, event.booked_day)

            if event.kind in {"CREDIT", "DEBIT"}:
                if event.amount is None or event.amount <= ZERO:
                    raise ValueError(f"{event.event_id} must have a positive amount")
                self._process_credit_or_debit(event)
            elif event.kind == "AUTHORIZATION":
                self._process_authorization(event)
            elif event.kind == "SETTLEMENT":
                self._process_settlement(event)
            elif event.kind == "REVERSAL":
                self._process_reversal(event)
            else:
                raise ValueError(f"Unsupported event kind {event.kind!r}")
        return self

    def capitalize_interest(self) -> None:
        """Accrue on final pre-capitalization closes and append one Day 6 credit."""
        if self.interest_accruals:
            raise ValueError("Interest has already been capitalized")
        for account_id, spec in self.accounts.items():
            total = ZERO
            for value_date in range(1, WINDOW_DAYS + 1):
                eligible_balance = self.balance(account_id, value_date)
                raw_accrual = (eligible_balance * DAILY_INTEREST_RATE
                               if eligible_balance > ZERO else ZERO)
                accrual = money(raw_accrual, spec)
                self.interest_accruals.append(
                    InterestAccrual(account_id, value_date, eligible_balance, accrual)
                )
                total += accrual
            total = money(total, spec)
            self.interest_totals[account_id] = total
            if total != ZERO:
                self._append_entry(
                    Entry(f"INT-{account_id}-D6", account_id, WINDOW_DAYS, total,
                          "INTEREST_CAPITALIZATION", "INTEREST-CAPITALIZATION",
                          "Sum of rounded daily accruals capitalized once on Day 6"),
                )

    def entries_for(self, account_id: str, value_date: int | None = None) -> list[Entry]:
        return [entry for entry in self.entries
                if entry.account_id == account_id
                and (value_date is None or entry.value_date == value_date)]

    def fees_for(self, account_id: str, value_date: int) -> list[FeeAssessment]:
        return [fee for fee in self.fee_assessments
                if fee.account_id == account_id and fee.value_date == value_date]
