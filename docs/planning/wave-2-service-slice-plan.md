# Wave 2 service slice plan

## Executive summary

Recommendation: **Go for the next worker wave** for a narrow accounts/categories service-route slice, with **MVP release still Hold**.

The foundation cleanup review found no P0/P1 blockers for starting the next wave. The backend runtime currently mounts only `/health`, while the canonical OpenAPI contract already defines the accounts/categories API surface. The next wave should convert the first financial route slice from contract to executable backend behavior without implementing transactions, reports, transfers, import/bank/SMS/push, or production auth/session behavior prematurely.

The safest slice shape is:

- Mount only accounts/categories routes under `/api/v1`, plus existing `/health`.
- Use existing authz predicates and active-membership semantics.
- Add a safe route auth boundary that denies by default in the real app and is injectable in tests; do not mount the current auth placeholder as production login.
- Add route-level contract tests that compare mounted backend paths/methods to the accounts/categories OpenAPI subset and prove excluded routes remain unmounted.
- Add minimum DB migration revisions needed for users, households, memberships, accounts, and categories, without overclaiming trigger rules or transaction/report/transfer readiness.
- Produce fresh evidence after implementation.

## Complexity class

**High** overall.

Rationale: this is the first financial route slice and it touches route mounting, DB persistence, membership-scoped privacy, neutral errors, contract tests, and evidence. It is not xhigh as a whole because it must not implement production auth/session, payments, transfers, reports, or release-critical privacy flows. The auth/session integration boundary task itself is **xhigh-gated** because unsafe placeholder mounting or fake token behavior would weaken a production security boundary.

## Fixed invariants

- No P0/P1 blockers are known for starting this worker wave.
- MVP release remains **Hold** until broader release evidence gates are satisfied.
- Personal accounts/categories are owner-only.
- Household/shared accounts and household categories are visible only to active members of the same household.
- Invited, left, and revoked members do not get shared financial access.
- Missing and inaccessible resources return neutral user-facing errors.
- Lists, search, autocomplete, pagination metadata, and route contract tests must not expose hidden counts, hidden facets, hidden placeholders, foreign personal badges, or "partially hidden" copy.
- `sourceType` remains `manual` only; no import, bank API, SMS, push, broker connection, external credential, raw statement, notification-token, or support/debug bypass surfaces may be introduced.
- Accounts/categories slice must not implement transactions, reports, transfers, exports, delete/deactivate, backup/restore behavior, client behavior, or production auth/session issuance.
- Account ownership fields are immutable after creation: `ownershipType`, `ownerUserId`, `householdId`.
- Category scope fields are immutable after creation: `scope`, `ownerUserId`, `householdId`.
- DB migrations may create constraints and indexes for the slice, but must not claim trigger-based immutability or transfer same-scope validation until those triggers are actually implemented and tested.
- Public OpenAPI must not expose `unsupported_cross_scope`; if internal domain enums still contain reserved/non-public values, workers must prevent them from leaking to API schemas or responses.

## Task list

1. **Freeze accounts/categories route subset and ownership map**
   - Confirm the exact OpenAPI subset for accounts/categories:
     - `GET /accounts`
     - `POST /accounts`
     - `GET /accounts/autocomplete`
     - `GET /accounts/{accountId}`
     - `PATCH /accounts/{accountId}`
     - `DELETE /accounts/{accountId}`
     - `POST /accounts/{accountId}/archive`
     - `POST /accounts/{accountId}/restore`
     - `GET /categories`
     - `POST /categories`
     - `GET /categories/autocomplete`
     - `GET /categories/{categoryId}`
     - `PATCH /categories/{categoryId}`
     - `DELETE /categories/{categoryId}`
     - `POST /categories/{categoryId}/archive`
     - `POST /categories/{categoryId}/restore`
   - Confirm no OpenAPI edits are required unless a contract defect is found.
   - Confirm write ownership for `apps/backend/src/app/accounts/`, `apps/backend/src/app/categories/` or selected category module path, tests, and evidence paths.

2. **DB migration slice for accounts/categories prerequisites**
   - Create Alembic revision(s) for the minimum tables needed by this slice: users, households, memberships, accounts, categories.
   - Include existing model constraints for exactly-one-scope, record status, active membership indexes, account/category visibility indexes, money numeric shape for accounts, timestamps, and versions.
   - Do not generate transactions/reports/transfers/export/outbox tables unless the orchestrator explicitly broadens this worker wave to a foundation migration ticket.
   - Do not mark TODO trigger rules complete unless implemented with executable migration tests.

3. **Safe auth/session route boundary**
   - Add an authenticated actor dependency/interface for route code that real app execution can use safely.
   - Default behavior must be deny/401 unless a real session verifier is wired.
   - Tests may override the dependency to inject A/B/C/Invited/Former actors.
   - Do not mount `apps/backend/src/app/auth/router.py` placeholder as production auth.
   - Do not issue sessions, cookies, CSRF tokens, bearer tokens, refresh tokens, reset tokens, or invite tokens in this slice.

4. **Accounts service-route implementation**
   - Implement route handlers, DTO mapping, repository/service logic, and router mounting for accounts only.
   - Enforce personal owner-only and shared active-membership visibility for list/detail/search/autocomplete.
   - Enforce create/update/archive/restore/delete using existing account predicates or predicate-equivalent service logic.
   - Enforce immutable ownership fields and neutral referenced-id behavior.
   - Return no hidden counts and no hidden match hints.

5. **Categories service-route implementation**
   - Implement route handlers, DTO mapping, repository/service logic, and router mounting for categories only.
   - Enforce personal owner-only and household active-membership visibility for list/detail/search/autocomplete.
   - Enforce immutable scope fields and neutral referenced-id behavior.
   - Do not expose personal category usage by another member through counts, autocomplete, errors, or logs.
   - Do not implement transaction category usage counts in this slice.

6. **Route-level contract tests**
   - Add tests that introspect the FastAPI app and compare mounted `/api/v1` paths/methods to the accounts/categories OpenAPI subset.
   - Assert `/transactions`, `/reports`, `/exports`, transfer-specific routes, import/bank/SMS/push routes, broker/external credential routes, support/debug bypass routes, and auth placeholder routes are not mounted by this slice.
   - Assert runtime schema includes `/health` plus the intended accounts/categories subset only.

7. **Privacy/authz behavior tests**
   - Add A/B/C/Invited/Former fixture coverage for account and category list/detail/search/autocomplete/create/update/archive/restore/delete.
   - Add missing-id vs inaccessible-id golden response tests.
   - Add no-hidden-count/no-hidden-facet/no-hidden-placeholder tests for list/search/autocomplete.
   - Add immutable ownership/scope mutation tests.
   - Add log/audit boundary assertions if the slice emits audit/log events.

8. **Fresh evidence refresh**
   - Update evidence artifacts after workers run:
     - backend dependency/install status if environment changes;
     - targeted pytest for route/authz/migration tests;
     - full backend pytest;
     - DB migration/autogenerate or upgrade/downgrade evidence for the approved slice;
     - backend route inventory;
     - OpenAPI lint if OpenAPI changes, otherwise record no-schema-change;
     - authz/privacy evidence for accounts/categories.

9. **Integration review for the slice**
   - Review source, tests, route inventory, migration evidence, and privacy behavior.
   - Confirm no P0/P1 blocker was introduced.
   - Confirm release remains Hold.

## Dependencies

- Foundation cleanup review is accepted and reports no P0/P1 blocker for the next wave.
- OpenAPI source of truth is `api/openapi/openapi.yaml`.
- Existing SQLAlchemy model skeleton contains users, households, memberships, accounts, categories, and other planned tables.
- Existing authz predicates define canonical membership states: `invited`, `active`, `left`, `revoked`.
- Existing auth placeholder is intentionally unwired and must remain separate unless a security worker owns full auth implementation.
- Existing evidence shows full backend pytest pass, authz predicate test pass, and runtime route inventory with `/health` only before this slice.

Hard gates before route implementation closes:

- Migration approach must be accepted: minimum slice revisions versus broader foundation migration. If broader migration is requested, it must be a separate ownership decision.
- Auth actor boundary must be accepted. If no safe default-deny dependency can be agreed, accounts/categories should remain route-only contract tests and not production-mounted.
- Fixture strategy must provide A/B/C/Invited/Former actors and DB rows.

## Parallelizable work

- Task 1 route subset freeze can run in parallel with Task 2 migration design and Task 3 auth boundary design.
- Task 4 accounts implementation and Task 5 categories implementation can run in parallel after Tasks 1-3 gates are stable.
- Task 6 route contract tests can start as soon as Task 1 defines the expected mounted subset.
- Task 7 privacy/authz tests can start once fixture shape and auth dependency override are available.
- Task 8 evidence refresh can be prepared in parallel but can only complete after implementation and tests.

## Sequential gates

1. Freeze the exact mounted route subset and excluded routes.
2. Decide migration scope and auth actor boundary.
3. Implement migrations and test fixture setup.
4. Implement accounts/categories route modules and mount only those routers.
5. Run route contract tests and privacy/authz tests.
6. Run full backend pytest and route inventory.
7. Refresh evidence artifacts.
8. Run slice integration review and publish Go/Hold.

## Roles and reasoning levels

| Task | Recommended role | Reasoning level | Rationale |
| --- | --- | --- | --- |
| 1. Freeze route subset | Backend API contract engineer | high | Prevents scope creep and route/OpenAPI drift before workers edit code. |
| 2. DB migration slice | Backend data engineer | high | Migration scope affects privacy constraints, ownership fields, rollback, and future slices. |
| 3. Safe auth/session boundary | Security backend engineer | xhigh | Auth/session shortcuts can create a false production security boundary. |
| 4. Accounts implementation | Backend feature engineer | high | First financial resource, privacy-sensitive list/detail/autocomplete behavior. |
| 5. Categories implementation | Backend feature engineer | high | Category visibility and usage-count leaks are privacy-sensitive. |
| 6. Route contract tests | API QA automation engineer | high | Must prove mounted routes match only the intended OpenAPI subset and exclusions. |
| 7. Privacy/authz tests | Security QA engineer | high | A/B/C/Invited/Former and neutral-error evidence are core release gates. |
| 8. Evidence refresh | QA/evidence engineer | medium | Routine command execution and artifact update after implementation, with known evidence paths. |
| 9. Slice integration review | Integration reviewer | high | Cross-checks source, contract, routes, migrations, tests, and residual risk. |

## Definition of done

- The backend mounts `/health` and only the approved accounts/categories `/api/v1` route subset for this slice.
- Runtime route inventory proves no transactions, reports, transfers, exports, import/bank/SMS/push, broker/external credential, support/debug bypass, or auth placeholder routes are mounted.
- Accounts and categories route responses conform to the canonical OpenAPI DTO names, enum values, envelopes, and neutral error shape.
- Personal account/category access is owner-only.
- Shared account and household category access is active-household-member only.
- Invited, left, revoked, and outside users cannot access shared financial data through direct id, list, search, autocomplete, mutation, archived/restored/deleted states, or stale ids.
- Missing and inaccessible direct ids have the same user-facing response shape for sensitive endpoints.
- List/search/autocomplete return only visible rows and do not expose hidden counts, facets, placeholders, or hidden match hints.
- Account ownership and category scope are immutable after creation.
- Migrations create only approved slice tables/constraints/indexes or explicitly documented broader foundation tables if separately authorized.
- DB trigger TODOs are not represented as completed unless implemented and tested.
- Existing auth placeholder remains unmounted unless a separate xhigh auth worker owns real production auth.
- Tests and evidence artifacts are fresh after the slice.
- MVP release status remains **Hold**.

## Required evidence

- `artifacts/evidence/api/backend-route-inventory.md`: updated runtime route inventory showing `/health` plus the approved accounts/categories subset only.
- `artifacts/evidence/api/backend-pytest.md`: full backend pytest pass after the slice.
- Targeted pytest evidence for accounts/categories route behavior and route contract tests, under `artifacts/evidence/api/`.
- Targeted authz/privacy evidence for A/B/C/Invited/Former scenarios, neutral errors, immutable ownership/scope, and no hidden counts, under `artifacts/evidence/authz/`.
- Migration evidence under `artifacts/evidence/api/` or a migration-specific evidence path chosen by the orchestrator: revision list, upgrade run, downgrade/rollback notes, and metadata/constraint verification.
- OpenAPI lint evidence if `api/openapi/openapi.yaml` changes; otherwise a no-schema-change note in the route contract evidence.
- If audit/log behavior is added, log-safety evidence showing no amounts, balances, descriptions, account/category names, tokens, secrets, raw request/response bodies, or hidden-side diagnostics.

## Risks and escalation triggers

- Escalate if a worker needs to mount auth placeholder routes, issue tokens, accept cookies/CSRF/bearer tokens, or simulate production login without real storage, hashing, revocation, and rate-limit enforcement.
- Escalate if the migration worker cannot avoid generating unrelated tables from full SQLAlchemy metadata and the orchestrator has not approved a broader foundation migration.
- Escalate if any route needs transactions, reports, transfers, exports, import, bank API, SMS, push, broker/external credentials, raw statements, support/debug, or admin financial read behavior.
- Escalate if personal data for one user is requested or exposed to another household member.
- Escalate if invited, left, or revoked users can access shared financial records through old ids, lists, search, autocomplete, route timing, logs, or cache assumptions.
- Escalate if neutral missing-vs-inaccessible behavior diverges in user-facing shape.
- Escalate if hidden counts, hidden facets, hidden placeholders, member financial counters, or "partially hidden" copy appears.
- Escalate if public API schemas or generated DTOs expose non-public transfer scope values such as `unsupported_cross_scope`.
- Escalate if DB migrations claim immutability or transfer trigger protection that is only present as TODO comments.
- Escalate on repeated failures in authz predicate use, route contract inventory, migration upgrade/downgrade, or privacy scenario tests.

## Recommended execution order

1. **Contract/route inventory planner worker**: freeze the accounts/categories OpenAPI subset, excluded route list, ownership map, and route inventory expected output.
2. **Data migration worker**: implement and test the minimum approved Alembic revisions for users/households/memberships/accounts/categories, with rollback notes and no trigger overclaim.
3. **Security boundary worker**: add the safe authenticated-actor route dependency, default-deny behavior, and test override pattern without mounting auth placeholder or issuing sessions.
4. **Accounts worker and categories worker in parallel**: implement route modules, services/repositories, DTO mapping, and module tests once the migration and auth boundary are usable.
5. **API contract QA worker**: implement runtime route contract tests and OpenAPI subset comparisons.
6. **Authz/privacy QA worker**: implement A/B/C/Invited/Former, neutral-error, immutable-field, and no-hidden-count tests.
7. **Evidence worker**: run targeted/full tests, migration checks, route inventory, and lint/no-schema-change evidence.
8. **Integration reviewer**: review the completed slice and issue Go/Hold for the next wave.

## Go/Hold

**Go** for the next worker wave, limited to accounts/categories service-route slice, route-level contract tests, safe auth/session boundary, approved DB migrations, and fresh evidence.

**Hold** for MVP release.

**Hold** for production auth/session integration unless a dedicated xhigh security worker implements real credential verification, token generation, hashing, storage, revocation, CSRF/cookie behavior, Android bearer/refresh behavior, rate limits, and audit/log evidence.

**Hold** for transactions, reports, transfers, exports, import/bank/SMS/push, broker/external credential, backup/restore, client state, and support/debug financial access in this slice.
