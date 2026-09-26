# Rejected supplied criteria

## Incorrect criteria

### “E7 causes exactly one overdraft fee to be assessed, on Day 2.” — Rejected

E7 is a Day 5-booked debit with a Day 2 value date. At processing, its value-dated effect makes more than one daily close negative. The implementation assesses fees once per negative account-day, in date order: Day 2 (−AED 370.00 before its fee), Day 4 (−AED 180.00 before its fee, including Day 2's fee), and Day 5 (−AED 205.00 before its fee). Day 3 is positive after the Day 2 fee. This is three fees, not one. The later E9 reversal does not erase those appended fee entries.

### “After E9, all balances and fees return to their pre-E7 values.” — Rejected

E9 appends the equal-and-opposite AED 620.00 entry for E7. It restores the principal movement in value-date balance projections, but fees assessed while E7 was present remain ledger entries. Balance and fee history therefore do not all return to their pre-E7 state. A separate explicit fee-reversal event and policy would be needed to compensate those fees.

### “The three BHD instalments in E10 must each be BHD 3.334.” — Rejected

Three instalments of BHD 3.334 total BHD 10.002, exceeding the BHD 10.000 credit by BHD 0.002. At three decimal places, equal instalments are not representable. The implementation allocates BHD 3.334, 3.333, and 3.333 to reconcile to exactly BHD 10.000.

### “If the rounded daily interest accruals do not sum to the capitalized total, the remainder is discarded.” — Rejected

Discarding a remainder breaks reconciliation. The implementation defines the single Day 6 capitalization as the sum of the already-rounded daily accruals; the rounded accruals therefore sum exactly to the posted credit.

## Criteria accepted or treated as conditional

- The Day 2 balance of −AED 370.00 is correct **when evaluated after E7 is known at the end of Day 5 and before the newly triggered fee is appended**. The final report is later revised by E9 and includes fees.
- Auth-A's AED 185.00 settlement is accepted because it is within its AED 200.00 active hold; AED 15.00 is released.
- An unknown authorization settlement is rejected without moving ledger funds; Auth-Z has no prior authorization.
- A successfully approved hold reduces available balance, not ledger balance. Auth-B's conditional statement is valid, but Auth-B itself is declined in this replay because available balance is negative when E8 is processed.

## Approach abandoned during implementation

- **Require booking-day labels to be nondecreasing.** This was initially enforced as a replay invariant, but the first test run rejected E10: it is listed after the Day 6 E9 event while carrying a Day 5 booking day. The check was removed. The supplied event-list order remains authoritative, and the fee horizon is tracked as the greatest booking day seen so far.

## Other approaches considered and not used

- **Rebuild final balances by netting all signed movements and then derive fees from the final net only.** This loses the fact that fees were assessed when a late posting made prior closes negative and makes a later reversal appear to erase fee history. Event-time append-only fee entries were used instead.
- **Use binary floating point or round each installment independently with no residual allocation.** Both can produce currency drift. `Decimal` and deterministic minor-unit allocation are used.
- **Treat a hold as a debit.** This makes the ledger balance wrong; holds are tracked separately and affect only available balance.
