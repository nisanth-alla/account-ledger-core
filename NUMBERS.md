# Numeric choices

| Value or convention | Chosen value | Why this value, not half? |
|---|---:|---|
| Assessment window | 6 days | The scenario explicitly defines Day 1 through Day 6; it is not a tunable business constant. |
| ACC-001 currency precision | AED, 2 decimal places | Specified by the scenario. Storing at one decimal place would lose valid fils; using half the precision (one decimal) is not a representable AED ledger. |
| ACC-001 opening balance | AED 0.00 | Specified opening balance. |
| ACC-002 currency precision | BHD, 3 decimal places | Specified by the scenario. Reducing to 2 decimals would discard the third BHD decimal and make the installment reconciliation impossible. |
| ACC-002 opening balance | BHD 0.000 | Specified opening balance. |
| Overdraft fee | AED 25.00 per qualifying account-day | Specified fee. Half (AED 12.50) would implement a different product rule. |
| Daily interest rate | 0.04% = 0.0004 | Specified rate. Half (0.02%) would understate the stated accrual. |
| Interest day count | One application per displayed day | The prompt says daily interest over the six-day window and provides no calendar/day-count convention. No extra day is inferred. |
| Rounding mode | `ROUND_HALF_UP` | The prompt requires currency precision but does not name a tie-breaking mode. Half-up is an explicit, familiar choice for this illustrative ledger; changing to half-even would be a different rule at exact ties. |
| Interest accrual precision | Rounded once per day to account precision | Required so daily accruals are the values that sum to the capitalization. No unrounded residual is silently carried. |
| BHD installment count | 3 | Specified by E10. |
| BHD installment allocation | 3.334, 3.333, 3.333 | BHD 10.000 contains 10,000 fils, which cannot be divided into three identical integer-fils amounts. The first installment receives the one-fils remainder; assigning it to any other installment would be equally valid but would require a different documented convention. |
| Authorization amount Auth-A | AED 200.00 | Specified hold. |
| Auth-A settlement | AED 185.00 | Specified settlement; the AED 15.00 difference is released, not booked. |
| Authorization amount Auth-B | AED 90.00 | Specified hold request. It is declined because the available balance at processing is negative; the amount is not placed on hold. |
| Auth-Z settlement attempt | AED 180.00 | Specified attempt. It is rejected as an unknown authorization; no debit is created. |
| E7 debit and E9 reversal | AED 620.00 each, opposite signs | E7 specifies the debit; E9 reverses that exact movement. No fee reversal is inferred from the principal reversal. |

## Derived totals

- When E7 is processed on Day 5, fee-trigger closes (including earlier fee entries as they are appended in date order) are AED −370.00 on Day 2, AED −180.00 on Day 4, and AED −205.00 on Day 5. Three AED 25.00 fees are appended. E9 later restores E7's principal but not those fee entries.
- Final AED pre-interest closes are AED 250.00, 225.00, 625.00, 415.00, 390.00, and 390.00. Rounded daily interest is AED 0.10, 0.09, 0.25, 0.17, 0.16, and 0.16, totaling AED 0.93.
- ACC-002 has BHD 10.000 on each of Days 5 and 6 before interest capitalization. Rounded daily accruals are BHD 0.004 on each day and capitalize as one BHD 0.008 Day 6 credit.
