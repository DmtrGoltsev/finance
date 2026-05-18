# Wave 2 gate refresh

Дата проверки: `2026-05-18`
Reviewer/planner: `W2-GATE-REFRESH`
Scope: read-mostly review текущих W2 evidence для решения по W3 `transactions/transfers/reports`.

## Итог

Решение: `PASS` для запуска W3 preflight и gated backend implementation по `transactions/transfers/reports`; `HOLD` для финального MVP release/live exposure этих endpoints до закрытия default DB runtime policy и release-grade evidence.

Старый HOLD из `MVP_EVIDENCE/reports/2026-05-17_wave2-integration-gate.md` больше не блокирует подготовку и реализацию W3 как таковую, потому что его главный auth/session blocker закрыт: DB-backed credential/session adapters, hash-only sessions и canonical UUID actor context получили PASS. Но default accounts/categories runtime все еще `memory`, а `db` остается opt-in до решения по startup/test DB lifecycle и Alembic migration policy. Поэтому W3 можно строить только на DB-backed contracts/fixtures/repositories и держать release-gated до отдельного default DB runtime gate.

## Evidence snapshot

- `artifacts/evidence/security/db-auth-session-persistence-closure.md`: `PASS` для DB-backed auth/session persistence; full backend `100 passed, 1 warning`; credential/session adapters используют DB, sessions hash-only, actor/session/membership IDs возвращаются canonical UUID strings.
- `artifacts/evidence/api/db-runtime-default-gate-closure.md`: `PASS` для opt-in DB route equivalence gate; `HOLD` для default `memory -> db`; full backend `106 passed, 1 warning`; добавлена PostgreSQL migration `20260518_0003` с immutable scope triggers.
- `artifacts/evidence/api/accounts-categories-db-runtime.md`: accounts/categories DB runtime доказан route-level opt-in suite, включая privacy matrix, neutral missing/inaccessible IDs и persistence across app restarts.
- `artifacts/evidence/api/w2-session-contract-sync.md`: session canonical surface синхронизирован с runtime subset; Redocly pass, route contract tests `12 passed`, full backend `93 passed`.
- `apps/backend/tests/api/test_accounts_categories_route_contract.py`: mounted runtime subset все еще фиксирует accounts/categories + current session routes; `transactions/reports` явно в excluded operations.
- Android blocker снят: `assembleDebug testDebugUnitTest` ранее зафиксирован как `BUILD SUCCESSFUL`, APK существует в `apps/android/app/build/outputs/apk/debug/app-debug.apk`.

## Go/Hold decision for W3

`PASS`:

- W3 preflight для `transactions/transfers/reports`: архитектурный план, DB schema/repository review, fixtures, QA matrix, failing/xfail tests, contract guards, report/transfer threat model.
- W3 gated backend implementation: DB-backed services/repositories/tests для transactions, same-scope transfers и reports, если реализация опирается на canonical UUID actor context, DB-backed auth/session contracts и DB fixtures.
- Optional runtime code может быть подготовлен только с явным release gate/default-off policy и с отдельными route inventory guards. Нельзя случайно объявлять это MVP-live surface.

`HOLD`:

- Финальный MVP release/live exposure `/api/v1/transactions*` и `/api/v1/reports/*`.
- Любой PASS, утверждающий production/default DB runtime, пока не закрыты startup DB lifecycle, Alembic migration policy и release evidence.
- Report/transfer release signoff до доказательств filter-before-aggregate, no hidden counts/facets, transfer atomicity, same-scope-only transfer behavior, concurrency и sanitized logs/audit.

## P0/P1 blockers

P0 перед финальным MVP release:

- Default DB runtime policy: решить и доказать startup/test DB lifecycle, auto/manual Alembic migration policy, production-like DB availability; после этого переключить accounts/categories default с `memory` на `db` или формально зафиксировать безопасный deployment override.
- W3 financial runtime: реализовать и доказать transactions CRUD/list/detail/search/autocomplete, same-scope transfers через transactions и report endpoints на DB-backed contracts.
- Transfer safety: `personal_same_owner` и `household_same_household` allow; personal/shared, cross-user personal, cross-household shared deny; no hidden-side diagnostics; no partial writes; balance/projection consistency; concurrency.
- Report safety: visible account resolution до aggregate; no hidden totals/counts/facets; drill-down detail equivalence; cache/cursor scoped by viewer/household/membership/access versions.
- Session/access invalidation for financial surface: logout/current revocation already covered at DB session level, но release evidence должен доказать stale session/cache/cursor/export/offline denial для shared financial data after leave/revoke/reset where applicable.
- PWA/iOS session boundary: если PWA/iOS входят в MVP release surface, cookie/CSRF issuance/verification/rotation либо должны быть реализованы и проверены, либо release scope должен явно сузиться до поддержанного bearer/session поведения.
- Runtime contract alignment: canonical OpenAPI содержит password reset/users/transactions/reports surfaces, но runtime subset пока уже; перед release нужно либо смонтировать и доказать MVP routes, либо документально вывести остаток из release scope.
- Release evidence: live backend/PWA/Android/iOS screenshots or run notes, route inventory, log/audit scan, secret/out-of-scope endpoint scan, final `MVP_RELEASE_REPORT.md`.

P1 / hardening before broad release, не блокирует W3 preflight:

- Rate-limit backend enforcement evidence для auth/reset/invite/session flows.
- Audit sink proof для login/session/security-sensitive/financial deny events.
- SBOM/dependency/CVE scan.
- Backup/restore tenant-boundary evidence.
- Schemathesis/OpenAPI response-shape coverage for mounted approved routes.

## Следующая worker-волна

1. `W3-TTR-PREFLIGHT-PLAN`
   - Role: backend architecture/test design worker
   - Reasoning: `high`
   - Write scope: `docs/architecture/mvp-transactions-transfers-reports-live-plan.md`, `docs/testing/w3-transactions-transfers-reports-qa-plan.md`, `MVP_EVIDENCE/reports/2026-05-17_wave3-preflight-plan.md`
   - DoD: implementation plan maps transactions/transfers/reports to DB-backed auth/session/accounts/categories contracts; route gating/default-off policy explicit; required tests/evidence enumerated.
   - Depends on: current W2 evidence only.

2. `W3-TTR-DB-FIXTURES-CONTRACTS`
   - Role: backend QA/fixtures worker
   - Reasoning: `high`
   - Write scope: `qa/fixtures/**`, `packages/test-fixtures/**`, `apps/backend/tests/fixtures/**`, `apps/backend/tests/transactions/**`, `apps/backend/tests/reports/**`, `docs/testing/**`, `artifacts/evidence/api/w3-ttr-fixtures-contracts.md`
   - DoD: Owner A / Member B / Other C / Invited / Former graph includes personal/shared accounts, categories, transactions, allowed/denied transfers and report buckets; tests are failing/xfail or gated without mounting live routes.
   - Can run parallel with worker 1 after plan skeleton.

3. `W3-TRANSACTIONS-DB-RUNTIME`
   - Role: backend implementation worker
   - Reasoning: `high`
   - Write scope: `apps/backend/src/app/transactions/**`, `apps/backend/src/app/db/models.py`, `db/migrations/**`, `apps/backend/tests/transactions/**`, `apps/backend/tests/api/test_accounts_categories_route_contract.py`, `artifacts/evidence/api/w3-transactions-db-runtime.md`
   - DoD: DB-backed transaction service/repository/API tests prove account-scope inheritance, referenced-id neutral errors, no partial write, manual-only source type. Runtime route exposure remains gated until route inventory decision.
   - Depends on workers 1-2.

4. `W3-TRANSFER-SAFETY`
   - Role: backend security/privacy worker
   - Reasoning: `xhigh`
   - Write scope: `apps/backend/src/app/transactions/**`, `apps/backend/tests/transactions/**`, `apps/backend/tests/reports/**`, `artifacts/evidence/api/w3-transfer-safety.md`, `artifacts/evidence/security/w3-transfer-log-scan.md`
   - DoD: TR-RG-01..10 evidence for same-scope allow, unsupported deny, hidden-side neutrality, atomicity, balance consistency, membership safety, concurrency and logs.
   - Depends on worker 3 transaction core; can design tests in parallel with worker 3, final PASS sequential after core implementation.

5. `W3-REPORT-RUNTIME-SAFETY`
   - Role: backend data/privacy worker
   - Reasoning: `xhigh`
   - Write scope: `apps/backend/src/app/reports/**`, `apps/backend/tests/reports/**`, `apps/backend/tests/transactions/**`, `artifacts/evidence/api/w3-report-runtime-safety.md`
   - DoD: REP-RG-01..10 evidence for both report modes, visibleAccountIds before aggregate, no hidden counts/facets, drill-down equivalence, cache/cursor invalidation policy.
   - Depends on transaction fixtures/core; can start query design in parallel with transfer tests after worker 2.

6. `W2-DB-DEFAULT-RUNTIME-POLICY`
   - Role: backend integration/ops worker
   - Reasoning: `xhigh`
   - Write scope: `apps/backend/src/app/db/**`, `apps/backend/src/app/config/**`, `apps/backend/tests/db/**`, `apps/backend/tests/api/**`, `db/migrations/**`, `ops/**`, `artifacts/evidence/api/db-runtime-default-policy.md`, `MVP_EVIDENCE/test-runs/W2_DB_RUNTIME_EVIDENCE_TODO.md`
   - DoD: startup/test DB lifecycle and Alembic migration policy decided and proven; default DB runtime release gate can move from HOLD to PASS or carry a documented deployment override.
   - Should run in parallel with W3 preflight; must finish before final MVP release/live signoff.

7. `W2/W3-SESSION-PWA-INVALIDATION-EVIDENCE`
   - Role: security/session boundary worker
   - Reasoning: `xhigh`
   - Write scope: `apps/backend/src/app/auth/**`, `apps/backend/tests/auth/**`, `apps/backend/tests/security/**`, `apps/web-pwa/**` only if PWA runtime changes are needed, `artifacts/evidence/security/session-pwa-invalidation.md`
   - DoD: PWA cookie/CSRF decision/evidence, stale session/cache/cursor/export denial policy, reset/leave/revoke invalidation proof for financial surfaces or explicit MVP scope exception.
   - Should run before release candidate; can run parallel with W3 implementation.

Рекомендуемый порядок: 1 -> 2 -> 3; workers 4 и 5 стартуют после test fixtures/core skeleton; worker 6 стартует немедленно параллельно; worker 7 стартует параллельно после parent scope decision по PWA/iOS session boundary.

## Вопросы пользователю

Сейчас обязательных вопросов пользователю нет: W3 можно запускать с текущими ограничениями.

Вопрос к parent/orchestrator, не к end-user: подтвердить scope W3 как `preflight + gated implementation`, а не `release/live exposure`. Если parent хочет включать PWA/iOS в финальный MVP, отдельно зафиксировать, что cookie/CSRF session boundary является release P0.

Final to parent: `PASS` для W3 transactions/transfers/reports preflight и gated backend implementation; `HOLD` для финального live/release exposure. Next workers: `W3-TTR-PREFLIGHT-PLAN`, `W3-TTR-DB-FIXTURES-CONTRACTS`, `W3-TRANSACTIONS-DB-RUNTIME`, `W3-TRANSFER-SAFETY`, `W3-REPORT-RUNTIME-SAFETY`, параллельно `W2-DB-DEFAULT-RUNTIME-POLICY` и `W2/W3-SESSION-PWA-INVALIDATION-EVIDENCE`. Главные blockers: default DB runtime policy, financial runtime safety evidence, transfer/report privacy gates, PWA/iOS session boundary if in MVP, final release evidence.
