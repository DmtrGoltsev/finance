# Wave 2 implementation backlog

## Status

Status: planning artifact for orchestration. Stack/repo layout is now fixed by `docs/architecture/decision-records/adr-0001-stack-repo-layout.md`.

Resolved planning blocker:

- P1-B01 is resolved by ADR-0001. Accepted stack: contract-first monorepo; Python 3.12/FastAPI/SQLAlchemy/PostgreSQL/Alembic backend; TypeScript/React/Vite PWA; Kotlin/Jetpack Compose Android; OpenAPI source of truth at `api/openapi/openapi.yaml`; evidence under `artifacts/evidence/**`.

Go for next worker wave:

- W2-02 OpenAPI/schema skeleton.
- W2-03 data model and migrations.
- W2-15 executable QA fixture/harness setup.
- W2-17 security scan/evidence setup.
- W2-18 backup/restore runbook and evidence setup.

Conditional Go after foundation interfaces are available:

- W2-04/W2-05 may start once W2-02/W2-03 expose enough route/model shape for auth/session and predicates.
- W2-06..W2-14 remain sequenced by their ticket dependencies below.

Hold for MVP release until required evidence is present and all P0/P1 gates are closed. Feature workers must follow ADR-0001 and must not reopen stack, repo layout, auth/session transport, DB/migration, OpenAPI, test runner or evidence-path decisions independently.

Current known planning blockers:

- P1-B02 remains open: exact rate-limit values and export file TTL still require Product/Security approval. ADR-0001 provides configurable engineering defaults and release still requires evidence.
- P1-B03 remains open: public launch, formal retention/deletion SLA, backup deletion promise, SaaS/self-hosted commitment, shared-history ownership and jurisdiction remain outside engineering-only authority.

## Fixed invariants

All Wave 2 tickets must preserve these invariants:

- MVP is manual-entry only: no import, bank API, SMS, push, broker connection, external financial credential or raw statement surface.
- Personal accounts, transactions, categories, aggregates, reports, exports, logs, audit payloads, cache and errors are owner-only.
- Shared data is visible only to active members of the same `Household`.
- Invited and former members do not get shared financial access before accept/activation or after `left`/`revoked`.
- `shared_family_report` includes only shared household rows.
- `combined_viewer_overview` includes shared household rows plus current viewer personal rows only.
- Reports, exports, search, autocomplete, pagination, cache and materialization filter visible rows before aggregation, count, sort, facet, cursor or file generation.
- Transfers are same-scope only: `personal_same_owner` and `household_same_household`.
- Personal-to-shared, shared-to-personal, cross-user personal and cross-household shared transfers are denied.
- Missing and inaccessible resources use neutral user-facing responses.
- No hidden counts, hidden facets, hidden placeholders, foreign personal badges, member financial counters or "partially hidden" copy.
- Logs/audit/telemetry/debug output do not contain amounts, balances, descriptions, account/category names, tokens, secrets, raw financial bodies or hidden-side diagnostics.

## Worker wave 2A: unblock planning and foundations

First worker wave status: W2-00 is accepted via ADR-0001, W2-01 is this backlog, and W2-15/W2-17/W2-18 can now move from planning-only into ADR-aligned fixture, scan and runbook setup. W2-00 remains a dependency marker for implementation tickets because workers must explicitly consume ADR-0001.

### W2-00 - Stack and repo layout ADR

- Owner role: tech lead / architect.
- Reasoning level: high.
- Reasoning rationale: cross-cutting stack, auth, DB, test and ownership decisions affect every later worker.
- Dependencies: Wave 1 contracts and Wave 2 plan.
- Stack ADR gate: complete; resolved by ADR-0001.
- Write ownership: `docs/architecture/decision-records/adr-0001-stack-repo-layout.md` and repo layout/config docs assigned by orchestrator.
- Inputs: implementation plan, backend contracts, authz predicates, report/transfer/privacy/client/QA/security docs.
- Outputs: accepted ADR choosing contract-first monorepo, Python/FastAPI/SQLAlchemy/PostgreSQL/Alembic backend, React/Vite PWA, Kotlin/Compose Android, hybrid PWA-cookie/Android-token auth, `api/openapi/openapi.yaml`, pytest/Schemathesis/Vitest/Playwright/JUnit test stack and `artifacts/evidence/**`.
- DoD: met. ADR is accepted by orchestrator and referenced by all code-bearing tickets.
- Required evidence: ADR-0001, ownership map, evidence artifact conventions.
- Escalation triggers: ADR attempts to weaken privacy invariants, allows out-of-scope import/bank/SMS/push, cannot support restore, lacks session revocation strategy, or cannot express filter-before-aggregate tests.

### W2-01 - Wave 2 implementation backlog

- Owner role: delivery planner.
- Reasoning level: high.
- Reasoning rationale: decomposes privacy-sensitive work into isolated tickets and prevents ownership collisions.
- Dependencies: Wave 2 plan and Wave 1 contracts.
- Stack ADR gate: complete; backlog consumes ADR-0001 and keeps feature-code tickets dependent on ADR compliance.
- Write ownership: `docs/planning/wave-2-backlog.md`.
- Inputs: all Wave 1 architecture/security/privacy/client/QA contracts and W2 implementation plan.
- Outputs: this backlog with W2-00..W2-19 tickets, dependencies, ownership, evidence, escalation and parallelization.
- DoD: all 20 tickets are orchestration-ready, ADR-aware and bounded by explicit ownership.
- Required evidence: file path, ticket count, explicit Go/Hold status.
- Escalation triggers: required source docs conflict, ownership overlaps cannot be separated, or planner is asked to choose stack.

### W2-15 - QA fixture matrix and API/security harness plan

- Owner role: QA automation engineer.
- Reasoning level: high.
- Reasoning rationale: release evidence depends on consistent A/B/C/Invited/Former fixtures before implementation begins.
- Dependencies: W2-01, ADR-0001; W2-02 for contract-bound executable tests.
- Stack ADR gate: complete; use pytest/Schemathesis for backend/API, Vitest/Playwright for PWA, JUnit/MockWebServer/Compose UI tests for Android.
- Write ownership: `qa/fixtures/`, `packages/test-fixtures/`, `apps/backend/tests/`, client test directories when assigned, `artifacts/evidence/authz/`, `artifacts/evidence/api/`, `artifacts/evidence/reports/`, `artifacts/evidence/transfers/`, `artifacts/evidence/privacy/`.
- Inputs: QA endpoint traceability, report gates, transfer gates, privacy PF-RG gates, security checklist.
- Outputs: fixture matrix, endpoint-to-test mapping, golden response catalog, suite names for RG-01..RG-12, TR-RG-01..10, PF-RG-01..12.
- DoD: every endpoint surface has actor coverage and planned evidence artifact names.
- Required evidence: A/B/C/Invited/Former matrix, stale id/session/export/cache artifact list, traceability table under `artifacts/evidence/**`.
- Escalation triggers: fixture cannot model active/former/invited states, transfer/report fixtures are missing, or tests require hidden data exposure.

### W2-17 - Security evidence inventory and scan plan

- Owner role: Security QA / DevSecOps.
- Reasoning level: xhigh.
- Reasoning rationale: logs, secrets, dependencies and auth evidence are release blockers.
- Dependencies: ADR-0001, W2-15 for scenario IDs.
- Stack ADR gate: complete; use ADR-approved scan families such as gitleaks, pip-audit/equivalent, npm audit/equivalent and Gradle dependency audit.
- Write ownership: `security/`, `ci/`, `artifacts/evidence/security/`, `artifacts/evidence/dependencies/`.
- Inputs: security release checklist, QA traceability, auth/session/reset/invite contracts.
- Outputs: evidence checklist for auth/session/rate limits/CSRF/CORS/logs/audit/secrets/dependencies/out-of-scope inventory.
- DoD: every P0/P1 security release gate has owner, command/tool placeholder, expected artifact path and blocker criteria.
- Required evidence: scan plan, audit/log sample requirements, dependency/SBOM evidence plan, route/schema/config inventory plan.
- Escalation triggers: no acceptable secret-management path, no log redaction strategy, no dependency scan path, or production-like evidence cannot be produced.

### W2-18 - Backup/restore and tenant-boundary evidence plan

- Owner role: Operations engineer.
- Reasoning level: xhigh.
- Reasoning rationale: unsafe or untested restore is a P0 release blocker for financial data.
- Dependencies: ADR-0001 for PostgreSQL backup/restore baseline and evidence paths.
- Stack ADR gate: complete; use ADR-0001 closed-MVP backup/restore baseline.
- Write ownership: `ops/backups/`, `ops/restore-drills/`, `artifacts/evidence/backups/`.
- Inputs: security checklist, privacy flows, QA traceability, W2-00 ADR when available.
- Outputs: backup/restore runbook plan, encrypted backup evidence plan, restore tenant-boundary test design, RPO/RTO acceptance path.
- DoD: restore evidence requirements are clear enough for implementation wave.
- Required evidence: planned backup job proof, encryption/access proof, separate-environment restore report format, tenant-boundary verification checklist.
- Escalation triggers: backup storage too broad, runtime can delete backups, restore cannot be isolated, or deletion/retention promises need legal signoff.

## Worker wave 2B: backend foundations

These tickets run after ADR-0001. They must use the accepted contract-first monorepo and write evidence under `artifacts/evidence/**`.

### W2-02 - Canonical OpenAPI/schema skeleton

- Owner role: backend API architect.
- Reasoning level: high.
- Reasoning rationale: canonical routes, DTOs, enums and errors must remain aligned across backend, clients and QA.
- Dependencies: ADR-0001, W2-01; coordinates with W2-15.
- Stack ADR gate: complete; source of truth is `api/openapi/openapi.yaml`.
- Write ownership: `api/openapi/openapi.yaml`, `api/openapi/overlays/`, `api/schemas/`, generated outputs under `packages/generated/**` only through approved generator.
- Inputs: backend API contracts, report API contracts, transfer API contract, privacy endpoint mapping, QA traceability.
- Outputs: OpenAPI or equivalent schema skeleton for auth, users/me, households, invites, memberships, accounts, transactions, categories, reports, exports/delete/leave.
- DoD: schema includes canonical names, enum values, neutral errors, pagination envelope and out-of-scope absence.
- Required evidence: schema diff, route inventory, OpenAPI lint/contract output under `artifacts/evidence/api/`.
- Escalation triggers: schema introduces new report modes, unsupported transfer scopes, hidden counts, non-manual source types, or import/bank/SMS/push endpoints.

### W2-03 - Data model and migrations

- Owner role: backend data engineer.
- Reasoning level: high.
- Reasoning rationale: ownership/scope fields and record states are the basis for all predicates and release evidence.
- Dependencies: ADR-0001, W2-02.
- Stack ADR gate: complete; use PostgreSQL 16, SQLAlchemy 2.x and Alembic.
- Write ownership: `apps/backend/src/app/db/`, `apps/backend/src/app/domain/`, `db/migrations/`, `db/seeds/`, `packages/test-fixtures/` seed adapters when assigned.
- Inputs: backend contracts, authz predicates, transfer/report/privacy contracts.
- Outputs: schema/migrations for users, sessions/tokens, households, memberships, invites, accounts, categories, transactions/transfers, exports/deletion/leave, audit metadata.
- DoD: all scope fields are explicit: `ownerUserId`, `householdId`, `ownershipType`, `scope`, membership status, source type, record status and versions.
- Required evidence: migration diff, model review, fixture seed compatibility, no external credential tables, DB test output under `artifacts/evidence/api/` or `artifacts/evidence/authz/`.
- Escalation triggers: model cannot represent owner-only personal data, active membership, same-scope transfer, versioning, soft delete/void, or safe audit boundaries.

### W2-04 - Auth, sessions, reset, invite-token foundation

- Owner role: security backend engineer.
- Reasoning level: xhigh.
- Reasoning rationale: authentication, token storage, rate limits, CSRF/CORS and session revocation are release blockers.
- Dependencies: ADR-0001, W2-02, W2-03; coordinates with W2-15 and W2-17.
- Stack ADR gate: complete; implement in FastAPI/Python with PWA HttpOnly cookie + CSRF support and Android opaque bearer/rotating refresh token support.
- Write ownership: `apps/backend/src/app/auth/`, `apps/backend/src/app/config/`, auth/session/reset tests under `apps/backend/tests/`.
- Inputs: backend API contracts, authz predicates, security checklist, QA traceability.
- Outputs: registration/login/current session/logout/logout all/password reset foundations, token hashing/lifecycle, neutral auth responses, rate-limit configuration hooks, CSRF/CORS hooks as selected by W2-00.
- DoD: auth endpoints and session revocation paths are implemented with neutral responses and sanitized logs.
- Required evidence: auth tests, reset replay/expiry tests, logout/reset revocation tests, configurable rate-limit tests, CSRF/CORS config evidence under `artifacts/evidence/security/`.
- Escalation triggers: plaintext token/password storage, no revocation path, user enumeration, missing rate-limit decision, unsafe cookie/CORS strategy.

### W2-05 - Reusable authz predicate layer

- Owner role: security backend engineer.
- Reasoning level: xhigh.
- Reasoning rationale: predicate equivalence is the core privacy boundary for list/detail/search/report/export/debug.
- Dependencies: ADR-0001, W2-02, W2-03, W2-04.
- Stack ADR gate: complete; implement reusable SQLAlchemy/FastAPI authz predicates.
- Write ownership: `apps/backend/src/app/authz/` and predicate tests under `apps/backend/tests/`.
- Inputs: backend authz predicates, backend contracts, QA traceability.
- Outputs: deny-by-default predicates and visible-scope resolvers for users, households, memberships, invites, accounts, categories, transactions, reports, export, search/autocomplete and debug-like paths.
- DoD: feature workers can call shared predicates instead of duplicating access logic.
- Required evidence: predicate unit/integration tests, missing-vs-inaccessible golden responses, endpoint-to-predicate map under `artifacts/evidence/authz/`.
- Escalation triggers: any endpoint needs a bypass, predicates cannot support filter-before-aggregate, former member access is required, or support/debug needs financial values.

### W2-06 - Household, membership and invite flows

- Owner role: backend feature engineer.
- Reasoning level: high.
- Reasoning rationale: active membership gates all shared visibility and cache invalidation.
- Dependencies: ADR-0001, W2-02, W2-03, W2-04, W2-05.
- Stack ADR gate: complete.
- Write ownership: `apps/backend/src/app/households/` and household/invite/membership tests under `apps/backend/tests/`.
- Inputs: backend contracts, authz predicates, privacy flows, QA traceability.
- Outputs: household list/create/detail/update, invite create/list/detail/accept/decline/revoke/resend, membership list/detail/leave/revoke policy hooks.
- DoD: active, invited, left and revoked states behave consistently across shared access.
- Required evidence: active member allow tests, invited/former/other denial tests, invite token lifecycle tests, neutral errors, cache/session invalidation events emitted.
- Escalation triggers: former/invited shared financial access, member limit/role expansion, revoke-active-member policy change, or invite token leakage.

### W2-12 - Cache/session invalidation foundation

- Owner role: platform/security engineer.
- Reasoning level: xhigh.
- Reasoning rationale: stale sessions, reports, exports, search, cursors and offline snapshots can leak former-member shared data.
- Dependencies: ADR-0001, W2-04, W2-05, W2-06; gates W2-10, W2-11, W2-13, W2-14.
- Stack ADR gate: complete; align server versions with PWA TanStack Query keys and Android scoped Room/cache versions.
- Write ownership: `apps/backend/src/app/auth/`, `apps/backend/src/app/authz/`, backend cache/session invalidation helpers and tests; client contract hooks only where assigned.
- Inputs: authz predicates, report cache constraints, privacy flows, client state contracts, security checklist.
- Outputs: membership/session/access-version invalidation for logout, reset, leave/revoke, invite accept/revoke, account/category/transaction mutations, report/export/search/autocomplete caches and cursors.
- DoD: former member cannot keep shared access through stale server or client state.
- Required evidence: invalidation tests, cache key review, session revocation proof, stale id/cursor/export denial proof under `artifacts/evidence/authz/`, `artifacts/evidence/reports/`, `artifacts/evidence/privacy/` and `artifacts/evidence/client/`.
- Escalation triggers: `combined_viewer_overview` cache cannot be viewer-specific, membership version is unavailable, or old exports/cursors remain valid after leave.

## Worker wave 2C: financial features

These tickets implement financial resource behavior after backend foundations in `apps/backend/src/app/**`. They must not alter global auth/session/cache behavior except through approved hooks.

### W2-07 - Accounts and categories

- Owner role: backend feature engineer.
- Reasoning level: high.
- Reasoning rationale: account/category ownership and usage counts can directly leak personal data.
- Dependencies: ADR-0001, W2-02, W2-03, W2-05, W2-06.
- Stack ADR gate: complete.
- Write ownership: `apps/backend/src/app/accounts/`, category module path selected inside `apps/backend/src/app/`, and module tests under `apps/backend/tests/`.
- Inputs: backend API contracts, authz predicates, client state rules, QA traceability.
- Outputs: account and category CRUD/list/search/autocomplete/state endpoints with immutable ownership/scope and neutral referenced-id behavior.
- DoD: personal owner-only and household active-member visibility are enforced for list/detail/search/autocomplete.
- Required evidence: A/B/C/Invited/Former matrix, usage-count leak tests, hidden id golden responses, no hidden counts/autocomplete leaks under `artifacts/evidence/authz/`.
- Escalation triggers: personal category usage by another member leaks, `ownershipType`/`scope` mutation is requested, or filters require hidden counts.

### W2-08 - Income, expense and brokerage transactions

- Owner role: backend feature engineer.
- Reasoning level: high.
- Reasoning rationale: transactions inherit account scope and validate all referenced ids before writes.
- Dependencies: ADR-0001, W2-02, W2-03, W2-05, W2-07.
- Stack ADR gate: complete.
- Write ownership: `apps/backend/src/app/transactions/` excluding transfer-specific lifecycle where W2-09 owns it, and module tests under `apps/backend/tests/`.
- Inputs: backend API contracts, authz predicates, QA traceability.
- Outputs: transaction list/detail/create/update/delete/restore/search/autocomplete for non-transfer MVP types with `sourceType = manual`.
- DoD: referenced accounts/categories are visible and compatible, and failures leave no partial writes.
- Required evidence: transaction authz tests, referenced-id neutral errors, manual-source-only tests, no raw payload log scan inputs under `artifacts/evidence/authz/` and `artifacts/evidence/security/`.
- Escalation triggers: non-manual source type accepted, hidden category/account diagnostics leak, or transaction predicates diverge from reports/export.

### W2-09 - Transfer implementation

- Owner role: backend feature engineer plus security reviewer.
- Reasoning level: xhigh.
- Reasoning rationale: same-scope validation, hidden-side neutrality, atomicity and concurrency are release gates.
- Dependencies: ADR-0001, W2-02, W2-03, W2-05, W2-07, W2-08.
- Stack ADR gate: complete.
- Write ownership: transfer-specific lifecycle inside `apps/backend/src/app/transactions/`, balance/projection tests under `apps/backend/tests/`, transfer fixtures in `qa/fixtures/` or `packages/test-fixtures/`.
- Inputs: transfer API contract, backend contracts, authz predicates, report contracts, QA traceability.
- Outputs: `transactionType = transfer` create/read/list/update/delete/void/restore behavior with `personal_same_owner` and `household_same_household` only.
- DoD: unsupported transfer scopes are denied neutrally and no validation/auth/concurrency failure causes partial financial effects.
- Required evidence: TR-RG-01..10, golden hidden-side responses, DB/projection atomicity tests, balance consistency tests, concurrency tests, transfer log scan under `artifacts/evidence/transfers/`.
- Escalation triggers: product asks for personal/shared transfer, hidden counterparty leaks in response/logs/timing, cross-currency semantics appear, or half-apply risk remains.

## Worker wave 2D: reports, privacy, client and evidence

These tickets depend on foundations and feature surfaces. Client workers use generated clients from `api/openapi/openapi.yaml` and must not hand-edit generated code under `packages/generated/**`.

### W2-10 - Report implementation

- Owner role: backend/report engineer plus security reviewer.
- Reasoning level: xhigh.
- Reasoning rationale: report aggregation can leak personal data through totals, counts, balances, facets, drill-down or cache.
- Dependencies: ADR-0001, W2-02, W2-03, W2-05, W2-07, W2-08, W2-09, W2-12.
- Stack ADR gate: complete.
- Write ownership: `apps/backend/src/app/reports/`, report cache code, report tests under `apps/backend/tests/`.
- Inputs: report API contracts, authz predicates, transfer contract, QA traceability.
- Outputs: summary, category breakdown, account balances, cash flow and report transactions with shared `visibleAccountIds` resolver.
- DoD: both report modes work and every aggregate/pagination/cache path filters before aggregation.
- Required evidence: REP-RG-01..10, RG-06 proof, drill-down equivalence tests, no hidden counts/facets snapshots, cache key/invalidation tests, report log scan under `artifacts/evidence/reports/`.
- Escalation triggers: new report mode, member comparison, family total including personal rows, cache cannot include viewer/membership versions, or aggregates run before visible filter.

### W2-11 - Export, delete/deactivate and leave privacy flows

- Owner role: privacy backend engineer.
- Reasoning level: xhigh.
- Reasoning rationale: exports, deletion, leave and former-member behavior are privacy release gates.
- Dependencies: ADR-0001, W2-02, W2-03, W2-05, W2-06, W2-07, W2-08, W2-10, W2-12.
- Stack ADR gate: complete.
- Write ownership: `apps/backend/src/app/exports/`, privacy/deletion/leave modules selected inside `apps/backend/src/app/`, privacy tests under `apps/backend/tests/`.
- Inputs: privacy flows MVP, backend contracts, authz predicates, security checklist, QA traceability.
- Outputs: export jobs/files, self deletion/deactivation request, leave request, protected file lifecycle, shared-history-safe anonymization/deactivation hooks.
- DoD: export equals visible scope at generation time; delete is self-only; leave revokes future shared access and old export/shared cache access.
- Required evidence: PF-RG-01..12, export diff, former-member export denial, self-only deletion tests, protected file TTL evidence, privacy signoff/out-of-scope note under `artifacts/evidence/privacy/`.
- Escalation triggers: former shared historical export requested, backup deletion promise needed, support/admin financial access needed, or shared history ownership policy changes.

### W2-13 - PWA state implementation

- Owner role: frontend/PWA engineer.
- Reasoning level: high.
- Reasoning rationale: PWA state, service worker cache and copy can leak hidden data even when backend is correct.
- Dependencies: ADR-0001, W2-02, W2-06, W2-07, W2-08, W2-10, W2-11, W2-12.
- Stack ADR gate: complete; use TypeScript/React/Vite/TanStack Query with generated OpenAPI client.
- Write ownership: `apps/web-pwa/`, PWA tests under `apps/web-pwa/tests/`, generated web client under `packages/generated/web-api-client/` only through generator.
- Inputs: client state contracts, backend/report/transfer/privacy contracts, OpenAPI/schema output.
- Outputs: PWA screens/state for auth, dashboard, accounts, transactions, categories, reports, transfers, household, invites, export/delete/leave with privacy-safe cache/offline behavior.
- DoD: PWA never shows hidden placeholders/counts, forbidden report/transfer options, stale shared data after leave/revoke, or cross-viewer combined report cache.
- Required evidence: PWA snapshot tests, service worker/auth cache tests, logout/session-expired/back-stack tests, leave/revoke offline cleanup tests under `artifacts/evidence/client/`.
- Escalation triggers: UX asks for member financial badges, personal data placeholders, offline mutations without fresh authz, or telemetry/screenshots with financial content.

### W2-14 - Android state implementation

- Owner role: Android engineer.
- Reasoning level: high.
- Reasoning rationale: Android local persistence, task stack and process restore can leak stale shared data.
- Dependencies: ADR-0001, W2-02, W2-06, W2-07, W2-08, W2-10, W2-11, W2-12.
- Stack ADR gate: complete; use Kotlin/Jetpack Compose with Retrofit/OkHttp or generated OpenAPI client and Room only for scoped cache.
- Write ownership: `apps/android/`, Android tests under `apps/android/app/`, generated Android client under `packages/generated/android-api-client/` only through generator.
- Inputs: client state contracts, backend/report/transfer/privacy contracts, OpenAPI/schema output.
- Outputs: Android screens/state for auth, dashboard, accounts, transactions, categories, reports, transfers, household, invites, export/delete/leave with privacy-safe local storage.
- DoD: Android clears protected state after logout/session expiration/leave/revoke/delete and does not reuse viewer-specific combined report cache.
- Required evidence: Android UI/snapshot tests, local DB/cache cleanup tests, back stack/process death tests, secure storage evidence under `artifacts/evidence/client/`.
- Escalation triggers: personal placeholders or member financial counters requested, account switch leaks cached data, or local storage cannot be scoped by viewer/session/membership version.

### W2-16 - Client snapshot/cache/offline tests

- Owner role: QA client engineer.
- Reasoning level: high.
- Reasoning rationale: client wording and cache states need independent evidence across PWA and Android.
- Dependencies: ADR-0001, W2-13, W2-14; can prepare expected-state checklist after W2-15.
- Stack ADR gate: complete; use Vitest/Playwright for PWA and JUnit/MockWebServer/Compose UI tests for Android.
- Write ownership: `apps/web-pwa/tests/`, `apps/android/app/`, `artifacts/evidence/client/`.
- Inputs: client state contracts, QA traceability, outputs from W2-13 and W2-14.
- Outputs: snapshot/cache/offline suites for no hidden counts/placeholders, neutral errors, report/transfer option safety, logout/leave/revoke cleanup.
- DoD: client evidence maps to RG-05, RG-09, RG-10 and PF-RG-06.
- Required evidence: rendered/snapshot artifacts, cache key tests, service worker/local storage cleanup logs, forbidden copy scan under `artifacts/evidence/client/`.
- Escalation triggers: client cannot inspect cache state, screenshots show hidden hints, or Android/PWA wording diverges on privacy-critical states.

### W2-19 - Wave 2 integration review

- Owner role: integration reviewer.
- Reasoning level: high.
- Reasoning rationale: final review must detect drift across code, contracts, tests, evidence and ownership.
- Dependencies: W2-02..W2-18 complete enough for evidence review; W2-00 and W2-01 as planning inputs.
- Stack ADR gate: after implementation/evidence, not before.
- Write ownership: `docs/architecture/wave-2-integration-review.md` and assigned review evidence index.
- Inputs: all Wave 2 outputs, CI/test artifacts, security/privacy/QA evidence maps, ADRs.
- Outputs: Go/Hold release recommendation, P0/P1 findings, residual risk list, evidence completeness matrix.
- DoD: review confirms invariants, ownership boundaries, endpoint coverage and release evidence or names concrete blockers.
- Required evidence: linked test runs, schema diffs, scan outputs, log samples, backup/restore report, client snapshots, traceability closure.
- Escalation triggers: any P0/P1 release gate lacks evidence, feature code drifted from contracts, or unresolved security/privacy/legal decisions remain.

## Ticket dependency map

Hard dependencies:

- W2-00 is complete and gates all feature-code and executable implementation tickets through ADR-0001 compliance: W2-02..W2-14, W2-16, W2-17 execution, W2-18 execution and W2-19.
- W2-01 depends on source contracts and ADR-0001.
- W2-15 fixture/evidence matrix can proceed now; executable harness depends on W2-02 OpenAPI and relevant app scaffolds.
- W2-17 and W2-18 can proceed with ADR-aligned evidence setup under `artifacts/evidence/**`.
- W2-02 and W2-03 precede backend implementation.
- W2-04 and W2-05 gate W2-06..W2-12.
- W2-06 gates shared household, membership, invite and former-member behavior.
- W2-07 gates W2-08, W2-09 and W2-10.
- W2-08 gates W2-09 and report drill-down completeness.
- W2-09 gates transfer-safe report/export evidence.
- W2-12 gates W2-10, W2-11, W2-13 and W2-14 for cache/session safety.
- W2-10 gates report-related export evidence and client report states.
- W2-11 gates privacy evidence and client export/delete/leave states.
- W2-13 and W2-14 gate W2-16.
- W2-19 runs after implementation and evidence collection.

Pre-ADR work now complete:

- W2-00 is accepted as ADR-0001.
- W2-01 is finalized in this file.
- W2-15/W2-17/W2-18 no longer need to stay planning-only.

Can run now after ADR-0001:

- W2-02, W2-03, W2-15 harness setup, W2-17 scan/evidence setup and W2-18 backup/restore runbook setup.
- W2-04 and W2-05 once enough W2-02/W2-03 shape exists.

Must still wait for upstream implementation dependencies:

- W2-06 waits for W2-04/W2-05.
- W2-07 waits for W2-05/W2-06.
- W2-08 waits for W2-07.
- W2-09 waits for W2-08.
- W2-10 waits for W2-09 and W2-12 before closure.
- W2-11 waits for W2-10 and W2-12 before closure.
- W2-13/W2-14 wait for schema and relevant backend/client contract hooks.
- W2-16 waits for W2-13/W2-14 executable surfaces.
- W2-19 waits for implementation and evidence.

## Parallelization plan

First worker wave 2A status:

- W2-00 is complete via ADR-0001.
- W2-01 is complete when this file is accepted.
- W2-15, W2-17 and W2-18 can continue directly into ADR-aligned setup.

Early implementation wave:

- Run W2-02, W2-03, W2-15 executable harness setup, W2-17 scan setup and W2-18 runbook setup in parallel.
- Start W2-04 and W2-05 after enough schema/data foundations exist.
- Start W2-06 after W2-04/W2-05 skeletons expose session/current-user and membership predicates.

Feature wave:

- Run W2-07 after W2-05 and W2-06.
- Run W2-08 after W2-07.
- Run W2-09 after W2-08, with security review before integration.
- W2-10 can start report skeleton after W2-07/W2-08 but cannot close until W2-09 and W2-12 evidence exists.
- W2-11 can start after W2-10 APIs are stable but cannot close without W2-12 and privacy evidence.

Client/evidence wave:

- Run W2-13 and W2-14 in parallel after W2-02 schemas and relevant backend behavior are stable or mocked by approved generated clients.
- Run W2-16 in parallel with late W2-13/W2-14 once test hooks are agreed.
- Run W2-17 and W2-18 evidence execution throughout implementation, then freeze evidence before W2-19.
- Run W2-19 only after all blocking evidence artifacts are available.

## Ownership map

| Ticket | Write ownership | Collision guard |
| --- | --- | --- |
| W2-00 | `docs/architecture/decision-records/adr-0001-stack-repo-layout.md` | Complete; does not implement feature code |
| W2-01 | `docs/planning/wave-2-backlog.md` | Does not edit contracts or ADR |
| W2-02 | `api/openapi/openapi.yaml`, `api/openapi/overlays/`, `api/schemas/`, generated `packages/generated/**` through generator | One schema generator owner |
| W2-03 | `apps/backend/src/app/db/`, `apps/backend/src/app/domain/`, `db/migrations/`, `db/seeds/` | No API handler edits |
| W2-04 | `apps/backend/src/app/auth/`, `apps/backend/src/app/config/`, auth tests | No financial feature business logic |
| W2-05 | `apps/backend/src/app/authz/` and predicate tests | No feature route behavior except adapters |
| W2-06 | `apps/backend/src/app/households/` and module tests | No global cache/session internals beyond approved hooks |
| W2-07 | `apps/backend/src/app/accounts/`, category module path, module tests | No transaction/report mutation logic |
| W2-08 | `apps/backend/src/app/transactions/` non-transfer behavior and tests | No transfer lifecycle ownership |
| W2-09 | Transfer lifecycle inside `apps/backend/src/app/transactions/`, balance/projection tests, transfer fixtures | No report aggregation ownership |
| W2-10 | `apps/backend/src/app/reports/`, report cache and report tests | No mutation endpoints |
| W2-11 | `apps/backend/src/app/exports/`, privacy/deletion/leave modules and tests | No auth/session internals beyond approved invalidation hooks |
| W2-12 | Backend cache/session invalidation modules and cache key helpers | No product feature routes except integration hooks |
| W2-13 | `apps/web-pwa/`, `apps/web-pwa/tests/`, generated web client via generator | No backend contract edits except generated client use |
| W2-14 | `apps/android/`, Android tests, generated Android client via generator | No backend contract edits except generated client use |
| W2-15 | `qa/fixtures/`, `packages/test-fixtures/`, harness and evidence mapping | No production code unless orchestrator grants testability hook |
| W2-16 | `apps/web-pwa/tests/`, `apps/android/app/`, `artifacts/evidence/client/` | No production client changes unless assigned |
| W2-17 | `security/`, `ci/`, `artifacts/evidence/security/`, `artifacts/evidence/dependencies/` | No feature behavior changes |
| W2-18 | `ops/backups/`, `ops/restore-drills/`, `artifacts/evidence/backups/` | No app feature behavior changes |
| W2-19 | Integration review document/evidence index | No implementation edits |

Shared contract docs under `docs/architecture/*contracts*.md`, `docs/security/*`, `docs/compliance/*` and `docs/testing/*` are read-only for implementation workers unless the orchestrator assigns a documentation-update ticket.

## Release evidence map

| Evidence area | Primary tickets | Required evidence |
| --- | --- | --- |
| Canonical API/schema | W2-02, W2-19 | `artifacts/evidence/api/`: schema diff, route inventory, canonical enums/errors, out-of-scope endpoint absence |
| Auth/session/reset/invite | W2-04, W2-06, W2-15, W2-17 | `artifacts/evidence/security/`: neutral auth/reset responses, token lifecycle, session revocation, rate limits, CSRF/CORS evidence |
| Authz equivalence | W2-05, W2-07, W2-08, W2-10, W2-11, W2-15 | `artifacts/evidence/authz/`: list/detail/search/autocomplete/report/export predicate mapping and missing-vs-inaccessible golden tests |
| Accounts/categories/transactions | W2-07, W2-08, W2-15 | `artifacts/evidence/authz/`: A/B/C/Invited/Former matrix, referenced-id neutrality, no hidden counts, manual source only |
| Transfers | W2-09, W2-10, W2-15, W2-17 | `artifacts/evidence/transfers/`: TR-RG-01..10, hidden-side neutrality, atomicity, balance consistency, concurrency, log safety |
| Reports | W2-10, W2-12, W2-15, W2-17 | `artifacts/evidence/reports/`: REP-RG-01..10, `visibleAccountIds` before aggregation, no hidden counts/facets, drill-down equivalence, cache invalidation |
| Privacy flows | W2-11, W2-12, W2-15, W2-18 | `artifacts/evidence/privacy/`: PF-RG-01..12, export diff, former export denial, self-only deletion, leave invalidation, protected file TTL |
| Client state/cache | W2-13, W2-14, W2-16 | `artifacts/evidence/client/`: snapshots for no hidden placeholders/counts, neutral errors, forbidden report/transfer options, logout/leave cleanup |
| Logs/audit/secrets/dependencies | W2-17 | `artifacts/evidence/security/`, `artifacts/evidence/dependencies/`: log/audit scans, secret scans, dependency/SBOM, route/schema/config out-of-scope scan |
| Backup/restore | W2-18 | `artifacts/evidence/backups/`: encrypted backup proof, isolated storage proof, separate-environment restore report, tenant-boundary verification |
| Final review | W2-19 | Go/Hold recommendation, P0/P1 status, evidence completeness matrix, residual risk register |

## Escalation rules

Escalate immediately to orchestrator and the relevant Product/Security/Privacy/Legal/Operations reviewer if any worker observes:

- Another member's personal accounts, transactions, categories, reports, balances, aggregates, exports, free text or placeholders are requested or exposed.
- Report computation uses hidden rows before visible-scope filtering.
- A report mode beyond `shared_family_report` and `combined_viewer_overview` is requested.
- A cache key for `combined_viewer_overview` is not viewer-specific.
- Personal-to-shared, shared-to-personal, cross-user personal or cross-household shared transfer is requested or accepted.
- Transfer denial reveals hidden counterparty side, owner, account name, household, membership status, balance or diagnostics.
- Former or invited member can access shared financial data through old ids, sessions, cursors, exports, cache, offline snapshots or restore artifacts.
- Missing and inaccessible resources produce different user-facing shape for sensitive endpoints.
- Hidden counts, hidden facets, hidden placeholders, member financial badges or "partially hidden" copy appear.
- Logs/audit/telemetry/debug output include financial values, descriptions, account/category names, tokens, secrets, raw bodies or hidden-side details.
- Imports, bank API, SMS/push, broker credentials, external credentials or raw statements enter routes, schema, config, logs, backups or tests.
- Restore fails, backup is incomplete, backup storage is too broad, or tenant boundaries are not proven.
- Public launch, SaaS/self-hosted, jurisdiction, formal retention/deletion SLA, backup deletion promise, 2FA/passkeys, production secret manager or support/admin financial access becomes required.
- Repeated QA failures occur in authz predicates, report aggregation, transfer atomicity/neutrality, cache invalidation, logs or privacy flows.

## Definition of done

Wave 2 backlog is done when:

- W2-00..W2-19 are present with owner role, reasoning level, dependencies, write ownership, inputs, outputs, DoD, required evidence and escalation triggers.
- ADR-0001 is consumed, P1-B01 is marked resolved, and remaining P1-B02/P1-B03 blockers are explicit.
- First worker wave 2A and later implementation waves 2B-2D are separated.
- Feature-code tickets do not choose stack and list W2-00 as dependency.
- Invariants are fixed: personal privacy, two report modes, filter-before-aggregate, same-scope transfers, neutral errors and no hidden counts.
- Release evidence maps cover RG-01..RG-12, TR-RG-01..10 and PF-RG-01..12 plus logs/secrets/dependencies/backups/restore.
- Ownership map prevents overlapping writes and flags shared contract docs as read-only unless separately assigned.
- Go/Hold recommendation is explicit for the next worker wave.
