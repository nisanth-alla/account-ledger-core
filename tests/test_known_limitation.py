"""Documented intentional expected failure for append-only fee history."""

import unittest

from ledger import Ledger
from replay import EVENTS


class KnownLimitationTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_reversing_e7_does_not_erase_fees_already_assessed(self):
        ledger = Ledger().process(EVENTS)
        fees = [entry for entry in ledger.entries if entry.kind == "OVERDRAFT_FEE"]

        # Intentional failing assertion: a naive net-balance model expects the
        # late reversal to erase the fees. The append-only implementation keeps
        # those fee entries; reversing them would require explicit compensating
        # fee-reversal entries and a separately specified policy.
        self.assertEqual([], fees)


if __name__ == "__main__":
    unittest.main()
