# ADR-0001: Stack and repository layout

## Status

Accepted for Wave 2 implementation planning.

This ADR closes P1-B01 by selecting one recommended implementation stack, repository layout, auth/session strategy, database/migration approach, API source of truth, test runners, evidence paths, configuration approach, and closed-MVP backup/restore baseline.

P1-B02 remains open for Product/Security approval of exact rate limit values and export file TTL. This ADR records engineering defaults that implementation may make configurable, but release still requires approval and evidence.

## Context

The MVP is a closed manual-entry personal and household finance application with:

- backend web server API;
- PWA/browser client suitable for iPhone use;
- future Android client;
- contract-first API discipline;
- strict deny-by-default authz tests;
- no imports, bank APIs, SMS/push integrations, bank credentials, broker credentials, card data, IBAN/account requisites, or raw bank statements.

Wave 1 contracts establish these non-negotiable invariants:

- `personal` data is owner-only.
- `shared` data is visible only to active members of the same `Household`.
- reports filter visible rows before aggregation.
- `shared_family_report` includes only shared household rows.
- `combined_viewer_overview` includes shared household rows plus the current viewer's personal rows only.
- transfers are same-scope only: `personal_same_owner` and `household_same_household`.
- missing and inaccessible resources use neutral responses.
- logs, audit, telemetry, crash reports, exports, caches, and client states must not disclose hidden data.

There is no existing product code in the repository. The current repository is documentation-only, so the decision favors boring, inspectable, widely supported technology rather than optimizing for an existing implementation.

## Decision

Use a contract-first monorepo with:

- Backend: Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.x, PostgreSQL 16, Alembic migrations, Pydantic DTOs aligned to OpenAPI.
- Web/PWA: TypeScript, React, Vite, TanStack Query, generated OpenAPI client, Playwright and Vitest.
- Android: Kotlin, Jetpack Compose, Retrofit/OkHttp or generated OpenAPI client, Room only for scoped offline/cache state, JUnit/MockWebServer.
- API source of truth: `api/openapi/openapi.yaml` plus JSON Schemas where useful. Generated clients/types are derived from the OpenAPI contract.
- Auth: hybrid session transport. PWA uses HttpOnly Secure SameSite cookies plus CSRF protection. Android uses opaque bearer access tokens and rotating refresh tokens in platform secure storage.
- DB: PostgreSQL with row-level ownership/scope columns enforced by application authz predicates and DB constraints. DB RLS can be evaluated later, but MVP release cannot depend on RLS replacing application predicates.
- Tests: pytest for backend unit/integration/security, Schemathesis or equivalent OpenAPI contract fuzzing, Vitest/Playwright for PWA, JUnit/Compose UI tests for Android, plus security scans and evidence artifacts.
- Evidence: all release proof outputs are written under `artifacts/evidence/**` and referenced from QA/security sign-off docs.

## Repository layout

Recommended monorepo layout:

```text
api/
  openapi/
    openapi.yaml
    overlays/
  schemas/
apps/
  backend/
    src/
      app/
        api/
        auth/
        authz/
        config/
        db/
        domain/
        households/
        accounts/
        transactions/
        reports/
        exports/
        audit/
      tests/
  web-pwa/
    src/
    tests/
  android/
    app/
    gradle/
db/
  migrations/
  seeds/
packages/
  generated/
    web-api-client/
    android-api-client/
  test-fixtures/
qa/
  fixtures/
  traces/
security/
  scans/
  runbooks/
ops/
  backups/
  restore-drills/
artifacts/
  evidence/
    api/
    authz/
    reports/
    transfers/
    privacy/
    client/
    security/
    backups/
    dependencies/
docs/
  architecture/
  compliance/
  planning/
  security/
  testing/
```

Ownership defaults:

- `api/openapi/openapi.yaml` is contract-owned by the API architect.
- generated code under `packages/generated/**` is never hand-edited.
- backend authz predicates live in `apps/backend/src/app/authz/` and are reused by list/detail/search/autocomplete/report/export/debug-like paths.
- QA fixture matrix lives in `qa/fixtures/` and `packages/test-fixtures/`.
- release evidence lives in `artifacts/evidence/**`; docs link to evidence rather than embedding large logs.

## Backend stack

Use Python 3.12 with FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, Uvicorn, and PostgreSQL 16.

Backend implementation rules:

- `/api/v1` is the only MVP API prefix.
- Server derives `currentUserId`, ownership, membership, and scope from authenticated server context and persisted rows, not from client-supplied owner fields.
- All financial queries pass through reusable authz predicates or visible-scope resolvers before sort, pagination, count, aggregation, export, or cache materialization.
- SQLAlchemy queries should make visible filters explicit and testable.
- Password hashing uses Argon2id by default, with bcrypt acceptable only if Argon2id is unavailable in the deployment baseline.
- Redis is optional for rate limit counters and short-lived cache only; PostgreSQL-backed counters are acceptable for closed MVP if concurrency tests pass.

## Web/PWA stack

Use TypeScript, React, Vite, TanStack Query, generated OpenAPI client, Vitest, Testing Library, and Playwright.

PWA rules:

- no session or refresh token in LocalStorage;
- authenticated API responses are not cached by service worker as public assets;
- local cache keys include `viewerUserId`, session/access version, `householdId`, report mode, and membership/access version where applicable;
- logout, session expiry, password reset, account deletion/deactivation, invite accept/revoke, and membership `left`/`revoked` clear protected state and navigation history;
- UI snapshots must prove no hidden placeholders, hidden counts, foreign personal sections, or forbidden report/transfer options.

## Android stack

Use Kotlin, Jetpack Compose, Kotlin coroutines/Flow, Retrofit/OkHttp or generated OpenAPI client, encrypted token storage, and Room only for scoped offline/cache state.

Android rules:

- access token is short-lived and held in memory when possible;
- refresh token is rotating and stored using Android Keystore-backed secure storage;
- cached financial data is scoped by `viewerUserId`, session/access version, `householdId`, report mode, and membership/access version;
- logout, token revocation, password reset, account deletion/deactivation, invite accept/revoke, and membership `left`/`revoked` clear protected Room tables and back stack state;
- offline mutation is out of scope for MVP unless a later decision adds fresh server-side authorization before submit.

## API contract and code generation

`api/openapi/openapi.yaml` is the source of truth for routes, DTO fields, enum values, errors, pagination envelopes, and auth requirements.

Contract rules:

- canonical terms only: `Household`, `Transaction`, `Membership`, `Invite`, `Account`, `Category`, `Report`;
- canonical values only: `reportMode`, `ownershipType`, `scope`, `sourceType = manual`, and the Wave 1 enum sets;
- OpenAPI is reviewed before implementation that changes wire behavior;
- generated clients are produced from OpenAPI for PWA and Android;
- backend tests compare implemented routes and response schemas to OpenAPI;
- post-MVP source values such as `file_import`, `bank_api`, `sms`, and `push` may be reserved vocabulary only; MVP create/update flows reject them.

Suggested tooling:

- OpenAPI lint: Redocly CLI or Spectral.
- Client generation: OpenAPI Generator for Kotlin, `openapi-typescript` or equivalent for web.
- Contract tests: Schemathesis or equivalent against a running backend.

## Auth, sessions, CSRF and CORS

PWA auth:

- HttpOnly, Secure, SameSite=Lax or Strict cookie for the server session or refresh token.
- CSRF token required for state-changing routes when cookie auth is used.
- CSRF token is bound to the authenticated session and rotated on login/logout/password reset.
- Sensitive responses use private/no-store cache headers.

Android auth:

- opaque bearer access token in `Authorization` header;
- rotating refresh token in platform secure storage;
- logout, logout-all, password reset, membership loss, account deletion/deactivation, and suspected compromise revoke relevant tokens server-side.

Shared auth requirements:

- sessions/tokens are revocable and versioned;
- session fixation is prevented by issuing a new session after login and reset;
- invite/reset tokens are one-time, short-lived, random, stored only as hashes, and never logged;
- login/register/reset/invite responses are account-neutral;
- CORS uses explicit allowlist for known PWA origins only;
- wildcard origin with credentials is forbidden;
- Android native traffic is not controlled by browser CORS, but uses HTTPS and the same API auth rules;
- production/staging with real data require HTTPS.

## Database, migrations and seeds

Use PostgreSQL 16 and Alembic migrations under `db/migrations/`.

DB defaults:

- UUID or opaque string ids; public ids must not encode scope or sequence.
- Explicit scope columns: `ownerUserId`, `householdId`, `ownershipType`, `scope`, `membershipStatus`, `recordStatus`.
- Foreign keys and check constraints enforce shape-level invariants.
- Application authz predicates enforce visibility; DB constraints support but do not replace predicate tests.
- Financial money values use decimal-safe storage, never floating point.
- `sourceType = manual` is the only accepted MVP transaction source.
- Seed fixtures model Owner A, Member B, Other C, Invited, Former, personal A/B rows, shared AB rows, foreign household C rows, and allowed/denied transfer cases.

Migration rules:

- migrations touching financial/auth/session/membership tables require rollback notes and fresh backup evidence before production application;
- restore drills must prove ownership and household separation after migration restore.

## Testing and evidence paths

Required runners:

- Backend unit/integration/security: pytest.
- API contract/fuzz: Schemathesis or equivalent against `api/openapi/openapi.yaml`.
- Backend DB tests: pytest with isolated PostgreSQL test database.
- PWA unit/component: Vitest and Testing Library.
- PWA end-to-end/cache: Playwright.
- Android unit/API: JUnit, MockWebServer.
- Android UI/cache: Compose UI tests.
- Dependency/SBOM: pip-audit or equivalent for Python, npm audit or equivalent for web, Gradle dependency audit for Android.
- Secret scan: gitleaks or equivalent.

Evidence artifact paths:

- `artifacts/evidence/api/` for OpenAPI lint, route inventory, schema diff, contract tests.
- `artifacts/evidence/authz/` for A/B/C/Invited/Former predicate matrices and neutral error golden tests.
- `artifacts/evidence/reports/` for `visibleAccountIds` proof, filter-before-aggregate tests, cache key/invalidation tests.
- `artifacts/evidence/transfers/` for TR-RG-01..10, atomicity, concurrency, hidden-side logs.
- `artifacts/evidence/privacy/` for export diff, former-member denial, delete/leave proofs, export file lifecycle.
- `artifacts/evidence/client/` for PWA/Android snapshots, logout/leave cache clear, offline/back-stack tests.
- `artifacts/evidence/security/` for CSRF/CORS config, token/session tests, log/audit scans, secret scans.
- `artifacts/evidence/backups/` for encrypted backup proof, access control proof, restore drill report, tenant-boundary verification.
- `artifacts/evidence/dependencies/` for SBOM and vulnerability scan output.

Release remains Hold until required evidence is attached and P0/P1 gates are closed.

## Rate limits and export TTL defaults

These are engineering defaults pending Product/Security approval. They must be configurable by environment and proven by tests before release.

Starter rate limits:

- registration: 5 attempts per IP per hour, 20 per IP per day;
- login: 5 attempts per account/email per 15 minutes, 20 per IP per 15 minutes, progressive delay after repeated failures;
- password reset request: 3 per email per hour, 10 per IP per hour, neutral accepted response;
- password reset confirmation: 5 invalid token attempts per IP per hour;
- invite create: 10 per household per day and 20 per actor per day;
- invite resend: 3 per invite per hour and 10 per actor per day;
- invite accept/decline token attempts: 10 per IP per hour;
- export job create: 3 per user per hour and 10 per user per day.

Export file TTL default:

- protected export files expire after 24 hours from `readyAt`;
- expired files are inaccessible through API and storage links;
- old export files are invalidated when membership loss would make shared data inaccessible;
- any TTL longer than 24 hours, up to the privacy-flow maximum of 7 days, requires Product/Security approval.

## Secrets, config, logs, backups and restore

Secrets/config:

- environment variables are accepted for local development and closed MVP deployment only when protected by the deployment platform;
- production-like secrets are not committed to repo, markdown, bundles, Docker layers, logs, or issue/chat artifacts;
- required secrets fail closed when missing;
- dev/staging/prod use separate secrets and databases;
- production secret manager choice remains a P2/public-launch decision unless closed MVP deployment requires it earlier.

Logs/audit:

- structured logs include request id, actor id when safe, action, target type/id when safe, scope id when safe, result, and coarse client metadata where allowed;
- logs/audit never include amounts, balances, report totals, transaction descriptions, account/category names, plaintext passwords, reset/invite/session/refresh tokens, secrets, or raw financial request/response bodies;
- denied access logs do not enrich caller-supplied hidden ids with hidden metadata.

Backups/restore for closed MVP:

- PostgreSQL automated encrypted backups at least daily;
- closed MVP RPO <= 24 hours and RTO <= 24 hours unless Operations approves stricter values;
- backup storage is isolated from runtime app credentials; runtime app cannot delete backups;
- backups are not copied to local development, public buckets, issue trackers, chat attachments, or unprotected file shares;
- restore is tested on a separate environment before release;
- restore evidence proves personal ownership and `Household` boundaries are preserved.

## Consequences

Positive consequences:

- one stack decision unblocks backend, API, QA, PWA, Android, security, and ops planning;
- OpenAPI remains the source of truth across backend, PWA, and Android;
- auth/session strategy supports browser security and native mobile storage without forcing one transport onto both clients;
- PostgreSQL and Alembic give inspectable migrations and reliable restore drills;
- evidence paths make release gates auditable instead of ad hoc.

Tradeoffs:

- FastAPI commonly generates OpenAPI from code, so the team must enforce contract-first discipline through `api/openapi/openapi.yaml`, linting, generated clients, and contract tests.
- Hybrid PWA/Android auth requires two client storage implementations and shared server revocation logic.
- Android is future-ready but not required to block the first backend/PWA skeleton if orchestrator sequences delivery that way.
- DB RLS is not selected as the MVP source of authorization; this keeps implementation simpler but requires strict application predicate tests.

## Alternatives considered

1. TypeScript/NestJS backend with Prisma.
   - Rejected for MVP default because NestJS tends to push code-first OpenAPI and Prisma migrations can make complex predicate/query review less transparent than explicit SQLAlchemy/Alembic for this privacy-heavy domain.

2. Kotlin/Spring backend to align with Android.
   - Rejected for MVP default because it increases backend ceremony and slows early contract iteration without a current codebase benefit.

3. PWA-only first with no Android stack decision.
   - Rejected because product scope includes future Android and client-state contracts already require Android/PWA consistency.

4. Backend-only repo with clients in separate repositories.
   - Rejected because shared OpenAPI, generated clients, fixtures, and evidence paths are safer in one monorepo during closed MVP.

5. JWT-only auth for both PWA and Android.
   - Rejected because browser token storage raises avoidable PWA risk; HttpOnly cookies plus CSRF are safer for PWA, while bearer tokens fit Android secure storage.

## Remaining decisions

Remaining P1 decisions:

- P1-B02: final Product/Security-approved rate limit values and export file TTL.
- P1-B03: deletion/retention/backups/public-launch legal policy, including backup deletion promises and formal retention/deletion SLA.
- Final deployment target for closed MVP if it changes secret manager, HTTPS, backup, or restore implementation.
- Formal approval of production/staging secret manager if platform protected env vars are not sufficient.

Remaining P2 decisions:

- public launch model: SaaS, self-hosted, or hybrid;
- jurisdiction/compliance model and formal privacy policy;
- 2FA/passkeys;
- HSTS/public hardening schedule;
- session management UI for users;
- monitoring/SIEM scope;
- support/admin/debug tooling, if any;
- DB RLS as defense-in-depth;
- balance storage strategy: persisted `currentBalance`, cached projection, or computed read model;
- Android offline mutation support;
- backup deletion semantics after account deletion;
- post-MVP imports, bank APIs, SMS/push, broker integrations, FX/revaluation, tax analytics, and investment analytics.

## Definition of done

P1-B01 is done when:

- this ADR is present at `docs/architecture/decision-records/adr-0001-stack-repo-layout.md`;
- it selects one recommended stack instead of listing only options;
- it defines repository layout and ownership-sensitive directories;
- it fixes backend framework, DB, migration tool, OpenAPI source of truth, auth/session transport, CSRF/CORS strategy, test runners, evidence paths, config/secrets approach, and backup/restore baseline;
- it records rate limit and export TTL engineering defaults as pending Product/Security approval;
- it keeps imports, bank APIs, SMS/push, bank credentials, broker credentials, external financial credentials, raw bank statements, and notification credentials out of MVP;
- it lists remaining P1/P2 decisions explicitly.
