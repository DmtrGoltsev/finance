# Wave 2 integration gate

Дата проверки: `2026-05-18`
Reviewer: `W2-INTEGRATION-GATE`
Решение для transactions/transfers/reports live wave: `HOLD`

## Итог

Backend transactions/transfers/reports live implementation сейчас начинать нельзя, если под live понимать смонтированные runtime endpoints с пользовательскими финансовыми данными. Сначала нужно закрыть два интеграционных P0:

- перевести accounts/categories runtime default с `memory` на DB-backed mode и доказать это не только opt-in тестом;
- заменить in-memory credential/session stores на DB-backed auth/session runtime с persistent revocation и production session semantics.

Допустимо начинать только подготовительные, не смонтированные work items: уточнение моделей, repository contracts, тестовых фикстур, negative/golden cases и implementation plan для transactions/transfers/reports. Монтировать `/api/v1/transactions*` и `/api/v1/reports*` до DB/auth gate нельзя: эти endpoints зависят от durable scope, canonical actor UUID, active membership, stale-session denial, transfer atomicity и report filter-before-aggregate.

## Проверенные артефакты

- `apps/backend/src/app/db/session.py`: `FINANCE_BACKEND_ACCOUNTS_CATEGORIES_REPOSITORY_MODE` по умолчанию остается `memory`, `db` включается opt-in.
- `apps/backend/src/app/accounts/router.py`, `apps/backend/src/app/categories/router.py`: DB repositories подключаются только при mode `db`.
- `apps/backend/src/app/auth/runtime.py`: default auth service без secret default-deny; при secret использует `InMemoryCredentialStore` и `InMemorySessionTokenStore`.
- `apps/backend/src/app/auth/router.py`: смонтированы `POST /sessions`, `GET /sessions/current`, `DELETE /sessions/current`; PWA cookie/CSRF не реализован как runtime flow.
- `api/openapi/openapi.yaml`: canonical session surface содержит `POST /sessions`, `GET/DELETE /sessions/current`; `DELETE /sessions` удален.
- `apps/backend/tests/api/test_accounts_categories_db_runtime.py`: opt-in DB runtime privacy/persistence tests есть.
- `apps/backend/tests/auth/test_session_flow.py`: minimal bearer session flow покрыт in-memory harness.
- `apps/backend/tests/api/test_accounts_categories_route_contract.py`: текущий mounted allowlist включает accounts/categories и 3 session routes, transactions/reports исключены.
- `artifacts/evidence/api/accounts-categories-db-runtime.md`: `PASS for opt-in DB runtime slice`, `HOLD for release default`.
- `artifacts/evidence/security/auth-session-foundation.md`: `PASS` для минимального bearer foundation, `HOLD` для release readiness.
- `artifacts/evidence/api/w2-session-contract-sync.md`: Redocly + backend full suite `93 passed`; logout-all post-MVP gap.
- `docs/testing/qa-endpoint-traceability.md`: P0/P1 release gates для auth/session, financial authz, transfers, reports, privacy/cache/logs.

## Evidence snapshot

Свежие локальные проверки reviewer-а:

```text
cd apps/backend
.\.venv\Scripts\python.exe -m pytest -q
=> 93 passed, 1 warning in 4.73s
```

```text
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/api/test_accounts_categories_db_runtime.py tests/auth/test_session_flow.py tests/auth/test_router_contract.py -q
=> 10 passed, 1 warning in 1.87s
```

```text
cd apps/android
.\gradlew.bat assembleDebug testDebugUnitTest
=> BUILD SUCCESSFUL in 1s
```

Android APK exists:

```text
apps/android/app/build/outputs/apk/debug/app-debug.apk
size: 9461995 bytes
```

Android unit XML snapshot:

```text
ApiConfigTest: tests=2 skipped=0 failures=0 errors=0
AppSectionTest: tests=2 skipped=0 failures=0 errors=0
```

Актуальная runtime route inventory из `create_app()`:

```text
GET    /health
POST   /api/v1/sessions                  include_in_schema=False
GET    /api/v1/sessions/current          include_in_schema=False
DELETE /api/v1/sessions/current          include_in_schema=False
16 schema-included accounts/categories routes
fallback /api/v1/{path:path}
```

Важно: `artifacts/evidence/api/backend-route-inventory.md` от `2026-05-17T12:14:16+03:00` устарел по auth/session части, потому что там session routes еще отсутствуют. Более свежий `w2-backend-contract-cleanup.md` и текущий тест route inventory уже учитывают 3 mounted session routes.

## Go/Hold decision

Decision: `HOLD` for transactions/transfers/reports live implementation.

Причина: текущий backend здоров как foundation (`93 passed`) и Android build разблокирован, но live financial operations нельзя строить поверх:

- opt-in DB runtime, где default все еще `memory`;
- in-memory auth credential/session adapters;
- отсутствующего PWA cookie/CSRF runtime при PWA/iOS-PWA MVP surface;
- незакрытых stale-session/cache/report/export invalidation gates.

Разрешенный `GO`: подготовительная worker-волна без mounted live routes.

Запрещенный до P0 closure `GO`: runtime mounting для `/api/v1/transactions`, `/api/v1/transactions/{id}`, transfer behavior через transactions, `/api/v1/reports/*`.

## P0/P1 blockers

P0 для MVP release и для старта live transactions/transfers/reports:

- Default DB runtime: accounts/categories default остается `memory`; `db` доказан только opt-in через `FINANCE_BACKEND_ACCOUNTS_CATEGORIES_REPOSITORY_MODE=db`.
- DB-backed auth/session: credentials, sessions, session revocation и actor resolution сейчас in-memory; нет DB session adapter для `users/memberships/sessions`.
- PWA cookie/CSRF: OpenAPI и security docs требуют cookie+CSRF для PWA, но runtime реализует только minimal Android-style bearer foundation.
- Session invalidation semantics: нет logout-all/revocation-all, reset revocation, membership leave/revoke cache/session invalidation proof.
- Transactions/transfers/reports runtime отсутствует; OpenAPI/predicates есть, endpoints не смонтированы.
- Transfer release gates: same-scope allow, unsupported deny, hidden-side neutrality, atomicity, balance consistency, concurrency и report safety еще не доказаны runtime tests.
- Report release gates: filter-before-aggregate, no hidden totals/counts/facets, drill-down/detail equivalence и cache invalidation еще не доказаны runtime tests.
- Privacy/security evidence: нет release-grade log/audit scan, stale IDs/sessions/cursors/export/offline snapshots proof для full financial surface.

P1 для MVP release, не блокирует подготовительные workers:

- Rate-limit enforcement для auth/reset/invite/session flows: contracts/hooks есть, backend counter evidence нет.
- Audit sink proof для login/session/security-sensitive events.
- DB trigger hardening для immutable account ownership/category scope, если service-level checks уже есть, но DB-level protection еще нет.
- Fresh evidence hygiene: `MVP_EVIDENCE/test-runs/W2_DB_RUNTIME_EVIDENCE_TODO.md`, `W2_ANDROID_BUILD_EVIDENCE_TODO.md` и старый backend route inventory не отражают уже выполненные W2 проверки.
- Runtime response schema/fuzz/Schemathesis-equivalent coverage против canonical OpenAPI для mounted routes.
- Dependency/SBOM/CVE scans для release candidate.

## Следующая worker-волна

1. `W2-DB-DEFAULT-RUNTIME-GATE`
   - Role: backend integration worker
   - Reasoning: `high`
   - Write scope: `apps/backend/src/app/db/session.py`, `apps/backend/src/app/accounts/router.py`, `apps/backend/src/app/categories/router.py`, `apps/backend/src/app/config/settings.py`, `apps/backend/tests/api/test_accounts_categories_db_runtime.py`, `apps/backend/tests/accounts/**`, `apps/backend/tests/categories/**`, `artifacts/evidence/api/accounts-categories-db-runtime.md`, `MVP_EVIDENCE/test-runs/W2_DB_RUNTIME_EVIDENCE_TODO.md`
   - DoD: default runtime DB-backed, memory only explicit test/dev override, full backend green, route-level restart durability/privacy matrix green.

2. `W2-AUTH-DB-SESSION-ADAPTERS`
   - Role: security backend worker
   - Reasoning: `xhigh`
   - Write scope: `apps/backend/src/app/auth/**`, `apps/backend/src/app/api/auth_context.py`, `apps/backend/src/app/db/models.py`, `db/migrations/**`, `apps/backend/tests/auth/**`, `apps/backend/tests/api/test_auth_context.py`, `artifacts/evidence/security/auth-session-foundation.md`
   - DoD: credential lookup, session storage, revocation and actor memberships come from DB-backed adapters; tokens/passwords hash-only at rest; stale/revoked/expired sessions denied.

3. `W2-PWA-COOKIE-CSRF-SESSION`
   - Role: security backend/PWA boundary worker
   - Reasoning: `xhigh`
   - Write scope: `apps/backend/src/app/auth/**`, `apps/backend/src/app/api/**`, `apps/backend/src/app/config/settings.py`, `apps/backend/tests/auth/**`, `apps/backend/tests/api/**`, `artifacts/evidence/security/csrf-cors/**`
   - DoD: PWA cookie session issuance/verification/logout, CSRF binding/rotation and negative CSRF tests; Android bearer behavior remains covered.

4. `W2-SESSION-INVALIDATION-RATE-AUDIT`
   - Role: security/privacy worker
   - Reasoning: `xhigh`
   - Write scope: `apps/backend/src/app/auth/**`, `apps/backend/src/app/db/**`, `apps/backend/tests/auth/**`, `apps/backend/tests/security/**`, `artifacts/evidence/security/**`
   - DoD: logout current/all decision finalized, reset/leave/revoke invalidation hooks, rate-limit evidence, sanitized audit/log proof.

5. `W2-EVIDENCE-REFRESH`
   - Role: evidence/QA worker
   - Reasoning: `medium`
   - Write scope: `artifacts/evidence/api/backend-route-inventory.md`, `artifacts/evidence/security/route-inventory/backend-route-inventory.md`, `MVP_EVIDENCE/test-runs/W2_DB_RUNTIME_EVIDENCE_TODO.md`, `MVP_EVIDENCE/test-runs/W2_ANDROID_BUILD_EVIDENCE_TODO.md`, `MVP_EVIDENCE/reports/**`, `MVP_EVIDENCE/test-matrix.md`, `MVP_EVIDENCE/release-checklist.md`
   - DoD: evidence files match current W2 state: backend `93 passed`, Android build success, current route inventory includes 3 session routes and excludes transactions/reports.

6. `W3-TRANSACTIONS-TRANSFERS-REPORTS-PREFLIGHT`
   - Role: backend architecture/test design worker
   - Reasoning: `high`
   - Write scope: `docs/architecture/mvp-transactions-transfers-reports-live-plan.md`, `docs/testing/**`, optional skipped tests under `apps/backend/tests/transactions/**`, `apps/backend/tests/reports/**`
   - DoD: implementation plan and failing/xfail contract tests for transactions/transfers/reports, but no mounted runtime routes until workers 1-4 pass.

После workers 1-4 pass можно запускать live implementation wave:

- `W3-TRANSACTIONS-DB-RUNTIME`: `apps/backend/src/app/transactions/**`, transaction DB repositories, tests.
- `W3-TRANSFER-SAFETY`: same-scope transfer validation/atomicity/balance/concurrency tests.
- `W3-REPORT-RUNTIME`: report queries with visibleAccountIds before aggregate, drill-down equivalence, no hidden counts/facets.

## Вопросы пользователю

Сейчас обязательных вопросов пользователю нет.

Нужно только внутреннее gate-решение от parent/orchestrator: принять `HOLD` для live transactions wave и запустить P0 closure workers выше. Product/Security вопросы появятся позже, если будет запрос на personal/shared transfers, former-member historical access, public launch, retention/deletion SLA, support/admin visibility или production secret manager.
