# Ambiguities and explicit resolutions

The prompt does not define several timing and edge-case semantics. This implementation chooses the rules below so replay is deterministic. These are model decisions, not claims that every bank must use these policies.

## Booking order, booking day, and value date

- Each event has a booking day and a value date. The supplied list order is the source-event sequence; value date controls balance inclusion. The event list order is maintained even where E10 appears after E9 while carrying a Day 5 booking date. Booking-day labels are therefore not required to be nondecreasing in stream order.
- The replay's current assessment horizon is the greatest booking day encountered so far. When an event changes a ledger balance, fee eligibility is checked for each value date from Day 1 through that horizon, in ascending order.
- The printed balances are final value-date balances after the complete event stream. Day-specific authorization transitions and errors are grouped by their booking day. A historical close can differ between the time it was first seen and the final report.

## Overdraft fees and late events

- The fee trigger uses the account's value-dated close immediately before that day's fee entry. A negative close gets one AED 25.00 entry for that account/day. The newly appended fee is included when assessing later days.
- An earlier day that was positive can become eligible after a late value-dated debit. It can receive a fee when that late event is processed. An already-appended fee is never removed or recomputed.
- In this stream, E7 makes Days 2, 4, and 5 negative by the time it is processed; those three fees are appended with those respective value dates. Day 3 is positive after Day 2's fee. E9 arrives on Day 6 and restores the E7 principal before a Day 6 fee is needed, but does not remove the earlier three fees.
- Fee assessment is triggered after each posted credit, debit, settlement, or reversal. Authorization holds do not change ledger balance and do not trigger a fee scan.

## Authorization lifecycle

- An authorization checks the value-dated ledger balance currently known at that point in event replay, less active holds, and is approved only if applying the new hold leaves available balance at least zero.
- A hold is not a ledger entry. A successful settlement may not exceed the remaining hold; this implementation closes the authorization after one successful settlement and releases its unused remainder.
- Unknown, duplicate, declined, cross-account, missing-amount, nonpositive, and over-hold settlements are rejected without posting a debit. No timeout, cancellation, partial-settlement sequence, or expiry event is supplied; these are outside the scenario.
- Auth-B is declined because E7 and its fee assessments have already been processed when E8 is reached in stream order.

## Reversals and event immutability

- A reversal references one prior posted credit, debit, or settlement, must be for the same account, and appends the equal-and-opposite amount. Its given value date is used; in E9 it is Day 2.
- Reversals do not mutate or delete original events or ledger entries. The model permits only one reversal per source event. Fee entries are independent posted entries and need their own explicit compensating event to be reversed; E9 does not imply that instruction.

## Installments and interest

- E10's BHD 10.000 is a total split among three installments, not BHD 10.000 per installment. Equal integer-fils installments are impossible; the first receives the one-fils remainder.
- Daily interest uses each account's final value-dated close after all source entries and fee entries, but before the interest capitalization entry. It is simple daily interest: accrual does not compound within the six-day window.
- Only positive closing balances earn interest. Each daily amount is rounded to currency precision first; the total of those rounded amounts is posted once as a credit with Day 6 value date. The capitalized amount is defined as that sum, so no remainder is discarded.
- Interest is calculated for Days 1–6, including days with zero or negative balances (which accrue zero). There is no separate holiday or calendar-day adjustment.

## Output and failure handling

- Rejected settlement/authorization operations remain visible as errors and authorization transitions, rather than terminating the full replay. Invalid static configuration or malformed core events raise an exception.
- The report is a teaching/debugging view of final value-dated state plus booking-day decisions; it is not a customer statement or an as-of historical audit report.
