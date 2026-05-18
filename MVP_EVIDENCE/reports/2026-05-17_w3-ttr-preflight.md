# W3 TTR preflight evidence report

Дата: 2026-05-17

Worker: `W3-TTR-PREFLIGHT-PLAN`

Scope:

- transactions/transfers/reports backend implementation planning;
- privacy/safety matrix;
- worker split and evidence obligations.

Files written:

- `docs/architecture/w3-transactions-transfers-reports-preflight.md`
- `docs/testing/w3-ttr-privacy-safety-matrix.md`
- `MVP_EVIDENCE/reports/2026-05-17_w3-ttr-preflight.md`

Runtime code changes: none.

Implementation files changed: none.

Findings:

- Current mounted runtime remains accounts/categories/session only.
- `transactions` table shape exists in SQLAlchemy metadata, but approved Alembic revisions do not create transaction runtime persistence yet.
- Transfers are modeled as `transactionType = transfer` through `/api/v1/transactions`, not as separate `/transfers`.
- Reports are computed read endpoints with only `shared_family_report` and `combined_viewer_overview`.
- Release must remain HOLD until W3 tests/evidence prove transaction privacy, transfer atomicity/same-scope safety and report filter-before-aggregate behavior.

Defaults accepted:

- no user question is blocking implementation;
- `sourceType = manual`;
- same-currency transfers only;
- no FX conversion;
- no persisted report resource in MVP;
- deny-by-default for unsupported transfer scope;
- neutral missing/inaccessible errors;
- no hidden counts/facets/placeholders.

Next worker tasks:

1. `W3-TTR-FIXTURES-CONTRACTS`
   - Write scope: tests/evidence/docs only.
   - Deliver fixture graph, golden neutral snapshots, no-hidden-count snapshots and route subset assertions.

2. `W3-TTR-TRANSACTIONS-DB-RUNTIME`
   - Write scope: `apps/backend/src/app/transactions/**`, `apps/backend/src/app/api/router.py`, `db/migrations/versions/*transactions*.py`, tests/evidence.
   - Deliver transaction migration, repository/service/router, route mount and transaction privacy tests.

3. `W3-TTR-TRANSFER-SAFETY`
   - Write scope: transaction transfer validation, transfer DB guard/migration, transfer tests/evidence.
   - Deliver same-scope allow, unsupported deny, hidden-side neutrality, no partial write, concurrency and log/audit safety.

4. `W3-TTR-REPORT-RUNTIME-SAFETY`
   - Write scope: `apps/backend/src/app/reports/**`, `apps/backend/src/app/api/router.py`, report tests/evidence.
   - Deliver both report modes, visibleAccountIds proof, filter-before-aggregate proof, drill-down equivalence and no-hidden-count snapshots.

Blockers/questions:

- No user-facing questions block implementation.
- Release blockers remain: runtime routes absent, transaction migration absent, transfer DB guard absent, report runtime absent, automated W3 evidence absent.
