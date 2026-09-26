# Work log

All timestamps are UTC. Entries record work as performed; no historical work has been backfilled.

- 2026-09-26 11:16 UTC — Started the implementation after confirming the project directory did not already exist. Chose Python `Decimal` and a standard-library test suite.
- 2026-09-26 11:16–11:20 UTC — Implemented immutable event/entry records, ordered replay, authorization decisions, value-dated fee scans, reversals, installment allocation, and post-replay interest capitalization. During implementation, rejected final-net fee derivation because it would erase fees after E9.
- 2026-09-26 11:20–11:22 UTC — Added assessment policy, numeric rationale, rejected-criteria analysis, tests, and architecture source. The first execution found that enforcing nondecreasing booking days incorrectly rejected E10, which appears after E9 but is labelled Day 5; removed that check and kept stream order authoritative. Added a test that protects event/entry immutability.
- 2026-09-26 11:25 UTC — Final verification: replay completed; 11 ordinary tests passed and the single documented test reported as an expected failure; `ARCHITECTURE.pdf` was confirmed to be four letter-size pages with all requested sections. Temporary conversion files and Python bytecode caches were removed.
