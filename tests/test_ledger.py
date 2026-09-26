import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from ledger import ACCOUNTS, Event, Ledger, money
from replay import EVENTS


class LedgerReplayTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger().process(EVENTS)
        self.ledger.capitalize_interest()

    def test_final_aed_closes_include_late_reversal_and_fees(self):
        expected = ["250.00", "225.00", "625.00", "415.00", "390.00", "390.93"]
        actual = [self.ledger.balance("ACC-001", day) for day in range(1, 7)]
        self.assertEqual([Decimal(value) for value in expected], actual)

    def test_late_debit_assesses_each_newly_negative_day_only_once(self):
        assessments = [f for f in self.ledger.fee_assessments if f.account_id == "ACC-001"]
        self.assertEqual([2, 4, 5], [f.value_date for f in assessments])
        self.assertEqual([5, 5, 5], [f.assessed_on_day for f in assessments])
        self.assertEqual([Decimal("-370.00"), Decimal("-180.00"), Decimal("-205.00")],
                         [f.balance_before_fee for f in assessments])

    def test_auth_a_settles_and_releases_unused_hold(self):
        auth = self.ledger.authorizations["Auth-A"]
        self.assertEqual("SETTLED", auth.state)
        self.assertEqual(Decimal("185.00"), auth.settled_amount)
        transition = next(t for t in self.ledger.authorization_transitions
                          if t.authorization_id == "Auth-A" and t.state == "SETTLED")
        self.assertIn("released unused hold 15.00", transition.detail)

    def test_auth_z_is_rejected_without_ledger_entry(self):
        self.assertNotIn("Auth-Z", self.ledger.authorizations)
        self.assertFalse(any(e.source_event_id == "E6" for e in self.ledger.entries))
        self.assertTrue(any("Auth-Z is not present" in e.message for e in self.ledger.errors))

    def test_auth_b_is_declined_when_available_balance_is_negative(self):
        auth = self.ledger.authorizations["Auth-B"]
        self.assertEqual("DECLINED", auth.state)
        self.assertEqual(Decimal("0.00"), auth.active_hold)
        self.assertTrue(any("insufficient available balance" in e.message
                            for e in self.ledger.errors if e.event_id == "E8"))

    def test_bhd_installments_reconcile_to_exact_total(self):
        installments = [e.amount for e in self.ledger.entries
                         if e.source_event_id == "E10"]
        self.assertEqual([Decimal("3.334"), Decimal("3.333"), Decimal("3.333")],
                         installments)
        self.assertEqual(Decimal("10.000"), sum(installments))

    def test_daily_interest_is_rounded_then_capitalized_as_one_credit(self):
        aed = [a.amount for a in self.ledger.interest_accruals
               if a.account_id == "ACC-001"]
        self.assertEqual([Decimal("0.10"), Decimal("0.09"), Decimal("0.25"),
                          Decimal("0.17"), Decimal("0.16"), Decimal("0.16")], aed)
        self.assertEqual(Decimal("0.93"), sum(aed))
        credits = [e for e in self.ledger.entries
                   if e.kind == "INTEREST_CAPITALIZATION"]
        self.assertEqual(2, len(credits))
        self.assertTrue(all(e.value_date == 6 for e in credits))
        self.assertEqual(Decimal("0.008"), self.ledger.interest_totals["ACC-002"])

    def test_source_event_and_reversal_entries_are_both_retained(self):
        original = next(e for e in self.ledger.entries if e.entry_id == "E7")
        self.assertEqual(Decimal("-620.00"), original.amount)
        reversal = next(e for e in self.ledger.entries if e.source_event_id == "E9")
        self.assertEqual(Decimal("620.00"), reversal.amount)
        self.assertIn("E7", [event.event_id for event in self.ledger.source_events])
        with self.assertRaises(FrozenInstanceError):
            self.ledger.source_events[0].booked_day = 6
        with self.assertRaises(AttributeError):
            self.ledger.entries.append(reversal)

    def test_currency_rounding_uses_half_up_at_account_precision(self):
        self.assertEqual(Decimal("1.01"), money(Decimal("1.005"), ACCOUNTS["ACC-001"]))
        self.assertEqual(Decimal("1.006"), money(Decimal("1.0055"), ACCOUNTS["ACC-002"]))

    def test_authorization_hold_changes_available_but_not_ledger_balance(self):
        ledger = Ledger().process(EVENTS[:3])
        self.assertEqual(Decimal("250.00"), ledger.balance("ACC-001", 2))
        self.assertEqual(Decimal("200.00"), ledger.active_holds("ACC-001"))
        self.assertEqual(Decimal("50.00"), ledger.available_balance("ACC-001", 2))

    def test_rejected_unknown_settlement_leaves_funds_untouched(self):
        events = [
            Event("C1", 1, "CREDIT", "ACC-001", 1, Decimal("100.00")),
            Event("S1", 1, "SETTLEMENT", "ACC-001", 1,
                  Decimal("50.00"), authorization_id="missing"),
        ]
        ledger = Ledger().process(events)
        self.assertEqual(Decimal("100.00"), ledger.balance("ACC-001", 1))


if __name__ == "__main__":
    unittest.main()
