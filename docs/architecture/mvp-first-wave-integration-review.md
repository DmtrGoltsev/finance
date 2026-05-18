# MVP first wave integration review

Дата: 2026-05-17
Роль: First Wave Integration Reviewer
Рабочая область: `C:\Users\style\Documents\Codex\Финансы`

## Итог

Вердикт: **PASS для перехода ко второй worker-волне, HOLD для release-ready MVP**.

First wave можно принимать как foundation/skeleton wave: backend DB/auth foundation, API contract guardrails, PWA skeleton, Android skeleton и evidence scaffold в наличии. Но это не готовый MVP-релиз: runtime backend остается узким in-memory accounts/categories slice, auth/session не смонтирован как production flow, transactions/transfers/reports отсутствуют в runtime, Android нельзя собрать в текущей среде из-за отсутствующего Gradle wrapper/Gradle, а `MVP_EVIDENCE` пока содержит структуру и TODO-матрицу без live/device доказательств.

## Проверенные артефакты

- Backend foundation: `apps/backend/src/app/accounts/repository.py`, `apps/backend/src/app/categories/repository.py`, `apps/backend/src/app/accounts/router.py`, `apps/backend/src/app/categories/router.py`, `apps/backend/src/app/api/router.py`, `apps/backend/src/app/api/auth_context.py`, `apps/backend/src/app/auth/**`, `apps/backend/tests/**`.
- Backend evidence: `artifacts/evidence/api/backend-foundation-db-auth.md`, `artifacts/evidence/api/backend-pytest.md`, `artifacts/evidence/api/accounts-categories-route-contract.md`, `artifacts/evidence/api/backend-route-inventory.md`, `artifacts/evidence/authz/accounts-categories-privacy.md`, `artifacts/evidence/security/auth-boundary.md`.
- API contract: `docs/testing/mvp-api-contract-qa-matrix.md`, `apps/backend/tests/api/test_openapi_mvp_manual_first_contract.py`, `api/openapi/openapi.yaml`.
- PWA skeleton: `apps/web-pwa/README.md`, `apps/web-pwa/package.json`, `apps/web-pwa/src/App.tsx`, `apps/web-pwa/src/api/**`, `apps/web-pwa/src/App.test.tsx`, `apps/web-pwa/public/manifest.webmanifest`, existing `apps/web-pwa/dist/**`.
- Android skeleton: `apps/android/README.md`, `apps/android/settings.gradle.kts`, `apps/android/build.gradle.kts`, `apps/android/app/build.gradle.kts`, `apps/android/app/src/main/**`, `apps/android/app/src/test/**`.
- Evidence harness: `MVP_EVIDENCE/README.md`, `MVP_EVIDENCE/release-checklist.md`, `MVP_EVIDENCE/test-matrix.md`, `MVP_EVIDENCE/MVP_RELEASE_REPORT.md`, directories under `MVP_EVIDENCE/reports`, `MVP_EVIDENCE/test-runs`, `MVP_EVIDENCE/screenshots/**`.

## Что принято

- SQLAlchemy-backed adapters for accounts/categories exist and are explicitly scoped as DB foundation, not runtime wiring. Tests cover persistence round-trip, status/version changes, category color, invalid UUID handling and service-layer privacy when services are instantiated with SQLAlchemy repositories.
- Auth/security/session primitives exist as primitives only: CSPRNG token factory, HMAC-SHA256 hashing for high-entropy tokens, redaction helpers, neutral public auth responses, session issuance requiring explicit store/factory/hash backend. Default auth boundary is deny-by-default and auth router remains unmounted.
- Runtime route inventory is honest: FastAPI exposes `/health` plus exactly 16 `/api/v1/accounts*` and `/api/v1/categories*` routes. Auth/session, households/invites/memberships, transactions/transfers, reports, exports and import/bank/SMS/push/broker/debug/support families are absent.
- API contract matrix and contract test correctly preserve manual-only `SourceType = manual`, exactly two report modes, same-scope-only `TransferScope`, excluded route families and a canonical `ErrorEnvelope` requirement.
- PWA skeleton is a Russian React/Vite app shell with MVP sections: session, overview, accounts, categories, operations, transfers, reports. It uses mock data and a typed API abstraction. Light source scan found no user-facing bank/SMS/push/broker surfaces except explicit README non-goal wording.
- Android skeleton is a Kotlin/Compose shell with Russian sections, `ApiConfig`, placeholder API client and `SecureTokenStore` contract with noop implementation. Light source scan found no bank/SMS/push/broker UI surfaces except explicit README non-goal wording and negative test assertions.
- `MVP_EVIDENCE` has the expected Russian checklist/test matrix/report template and screenshot/test-run/report directory structure.

## Блокеры и gaps

- **P0 release blocker:** backend runtime is not DB-backed yet. Accounts/categories request handlers still use `InMemoryAccountRepository` / `InMemoryCategoryRepository`; request-scoped SQLAlchemy sessions are not wired into FastAPI routes.
- **P0 release blocker:** production auth/session is not mounted or complete. Credential verification, password hashing, persistent session store, deployment secret wiring, CSRF verification/rotation, refresh-token validation, revocation, audit/log proof and rate-limit enforcement remain open.
- **P0 release blocker:** MVP runtime lacks transactions, same-scope transfers and reports despite canonical OpenAPI coverage. The contract is useful, but runtime readiness must not be inferred from OpenAPI.
- **P0 release blocker:** Android cannot be built or tested in this workspace because `apps/android/gradlew.bat` and `apps/android/gradle/wrapper/gradle-wrapper.jar` are absent and local `gradle` is unavailable.
- **P0 release blocker:** `MVP_EVIDENCE` is scaffold-only for live MVP acceptance. Checklist, matrix and release report remain TODO; no screenshots, device runs, live API run notes or release decision evidence are present.
- **P1 blocker:** runtime error envelopes are not uniformly canonical. Accounts routes return top-level `error`, but categories and auth boundary still rely on FastAPI `detail` shape; the runtime canonical `ErrorEnvelope` test is intentionally skipped.
- **P1 gap:** PWA is mock/skeleton only. No generated OpenAPI client, live auth/session, CRUD/archive/restore forms, transactions/transfers/reports integration or UI privacy-negative evidence yet.
- **P1 gap:** Android is shell only. No generated API client, live flows, encrypted token persistence implementation, emulator/device screenshots or runnable JVM/Compose evidence in the current environment.
- **P1 gap:** security/privacy evidence currently covers accounts/categories and auth boundary only. No proof yet for reports filter-before-aggregate, transfer hidden-side neutrality, transaction referenced-id neutrality, cache/logout/leave invalidation, log/audit scans, dependency scans for PWA/Android, or backup/restore release gates.

## Проверки

- Backend full test suite:
  - Command: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` from `apps/backend`.
  - Result: `70 passed, 1 skipped, 1 warning in 1.75s`.
  - Skip is the expected runtime `ErrorEnvelope` TODO in `test_openapi_mvp_manual_first_contract.py`.
  - Warning is the known `pytest_asyncio` deprecation warning for Python 3.14.
- Backend targeted review suite:
  - Command: `.\.venv\Scripts\python.exe -m pytest tests\api\test_openapi_mvp_manual_first_contract.py tests\api\test_accounts_categories_route_contract.py tests\api\test_auth_context.py tests\db\test_sqlalchemy_accounts_categories_repositories.py tests\auth\test_security_primitives.py -q -p no:cacheprovider`.
  - Result: `20 passed, 1 skipped, 1 warning in 0.34s`.
- PWA unit tests:
  - Command: `npm.cmd run test` from `apps/web-pwa`.
  - Result: `1 passed` test file, `2 passed` tests.
- PWA TypeScript check:
  - Command: `npm.cmd exec tsc -- -p tsconfig.json`.
  - Result: pass, no compiler output.
- PWA build:
  - Existing `apps/web-pwa/dist/**` is present.
  - I did not rerun `npm run build` because it writes generated build artifacts outside the allowed review write scope.
- Android build/test:
  - `Test-Path .\gradlew.bat`: `False`.
  - `Test-Path .\gradle\wrapper\gradle-wrapper.jar`: `False`.
  - `Get-Command gradle`: not found.
  - Gradle assemble/unit tests were not runnable.
- Forbidden surface scans:
  - PWA scan for bank/SMS/push/broker/import user-facing terms only found README non-goal wording.
  - Android scan only found README non-goal wording and tests asserting absence of non-MVP SMS/push/broker terms.
  - Backend route/evidence tests assert absence of import, bank API, SMS, push, broker, external credential, raw statement, debug/support bypass route families.

## Риски приватности и безопасности

- Current backend privacy proof is partial: accounts/categories list/detail/autocomplete and immutable ownership/scope probes are covered for owner/member/other/invited/former actors; transactions, transfers, reports, exports, cache/offline and client state are not covered yet.
- Auth boundary is safe as a closed default, but the application is not usable as a production authenticated MVP until real credential/session plumbing exists.
- Canonical error shape drift is a client and privacy risk: mixed `error` vs `detail` responses complicate generated clients and may create inconsistent denial handling.
- PWA service worker exists, but there is no evidence yet for authenticated API cache isolation, logout clearing or shared-device behavior.
- Android has a token storage contract only; the noop implementation must not be mistaken for secure persistence.
- Evidence harness currently avoids raw sensitive payloads, but there is no log/audit/secret scan proving that backend/PWA/Android runtime surfaces avoid tokens, credentials, raw financial request bodies or hidden object diagnostics.

## Рекомендация Go/Hold

**GO/PASS to second worker wave**: the first wave produced enough foundation and guardrails for parallel implementation workers to continue.

**HOLD for MVP release readiness**: do not present this as release-ready until P0 blockers are closed and evidence is refreshed with runtime/live/device proofs.

## Следующая worker-волна

- Backend persistence integration worker.
  - Write scope: `apps/backend/src/app/accounts/**`, `apps/backend/src/app/categories/**`, `apps/backend/src/app/db/**`, `apps/backend/tests/**`, relevant `artifacts/evidence/api/**`.
  - Goal: request-scoped DB-backed accounts/categories routes, UUID/public-id strategy, transaction boundaries, route tests proving persistence and privacy.
- Backend auth/session worker.
  - Write scope: `apps/backend/src/app/auth/**`, `apps/backend/src/app/api/auth_context.py`, `apps/backend/src/app/config/**`, `apps/backend/tests/auth/**`, `apps/backend/tests/api/**`, security evidence.
  - Goal: production-grade auth/session mounting or explicit non-release gate with credential verification, hashing, persistent stores, CSRF/PWA, Android bearer/refresh, rate limits, revocation and audit/log proof.
- Backend transactions/transfers/reports worker.
  - Write scope: new or existing `apps/backend/src/app/transactions/**`, `apps/backend/src/app/reports/**`, related schemas/services/tests/evidence.
  - Goal: manual-only transactions, same-scope transfers, report modes and filter-before-aggregate evidence without import/bank/SMS/push/broker scope creep.
- API error envelope hardening worker.
  - Write scope: backend API error adapter/middleware, accounts/categories routers/services tests, contract tests.
  - Goal: all mounted failure responses use canonical top-level `ErrorEnvelope`; unskip runtime envelope test.
- PWA live integration worker.
  - Write scope: `apps/web-pwa/src/**`, `apps/web-pwa/tests/**` or equivalent, PWA evidence/screenshots.
  - Goal: generated/typed client, live auth/session state, accounts/categories/transactions/transfers/reports MVP flows, no non-MVP surfaces, desktop PWA evidence.
- Android build and integration worker.
  - Write scope: `apps/android/**`, Android evidence/screenshots.
  - Goal: add Gradle wrapper or documented reproducible Gradle path, make unit tests runnable, wire generated/typed API client, implement platform-backed token storage, produce emulator/device evidence.
- MVP evidence/QA worker.
  - Write scope: `MVP_EVIDENCE/reports/**`, `MVP_EVIDENCE/test-runs/**`, `MVP_EVIDENCE/screenshots/**`, `MVP_EVIDENCE/MVP_RELEASE_REPORT.md`, `MVP_EVIDENCE/test-matrix.md`, `MVP_EVIDENCE/release-checklist.md`.
  - Goal: convert TODO matrix/checklist into evidence-backed PASS/BLOCKED/FAIL status with screenshots, logs, run notes and explicit known limitations.
