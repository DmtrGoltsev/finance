# Wave 2 foundation cleanup review

## Executive summary

Recommendation: **Go for the next worker wave**.

The prior P1 cleanup blockers from `docs/architecture/wave-2-foundation-review.md` are closed for foundation continuation. Public OpenAPI no longer exposes `unsupported_cross_scope` as a transfer scope, authz membership states are canonical, the auth placeholder route uses canonical `POST /sessions`, and runtime route inventory evidence shows that only `/health` is mounted in the backend app.

No remaining P0/P1 blockers were found for starting the next worker wave. MVP release remains out of scope for this cleanup review and should still depend on the broader release evidence gates.

## P1 cleanup verification

| Previous P1 | Status | Verification |
| --- | --- | --- |
| Public OpenAPI `TransferScope` exposed `unsupported_cross_scope`. | Closed | `api/openapi/openapi.yaml` defines `TransferScope` as only `personal_same_owner` and `household_same_household`. `unsupported_cross_scope` is absent from public OpenAPI search results. Public denial remains represented by `TRANSFER_SCOPE_NOT_SUPPORTED`. |
| Authz `MembershipStatus` included noncanonical `removed`. | Closed | `apps/backend/src/app/authz/predicates.py` defines only `invited`, `active`, `left`, and `revoked`. Repository search of the reviewed surfaces found no authz `removed` status. |
| Auth placeholder used noncanonical `POST /sessions/login`. | Closed | `apps/backend/src/app/auth/router.py` sets `LOGIN_SESSION_ROUTE = "/sessions"`, and `apps/backend/tests/auth/test_router_contract.py` asserts it is not `/sessions/login`. |
| Auth placeholder might be mounted accidentally. | Closed | `apps/backend/src/app/main.py` mounts only `app.api.router` under `/api/v1`; `apps/backend/src/app/api/router.py` is empty. Route inventory evidence confirms no `/api/v1` routes are registered. |
| Executable backend evidence was incomplete. | Closed | Evidence artifacts now show backend dependency install pass, full pytest pass, DB metadata pass, authz pass, runtime route inventory pass, and OpenAPI lint pass. |

## Evidence reviewed

- `docs/architecture/wave-2-foundation-review.md`: prior P1 blocker list and required cleanup context.
- `api/openapi/openapi.yaml`: public `TransferScope`, `MembershipStatus`, `TRANSFER_SCOPE_NOT_SUPPORTED`, canonical `/sessions`, and route surface.
- `apps/backend/src/app/authz/predicates.py`: canonical authz membership states and transfer denial behavior.
- `apps/backend/src/app/auth/router.py`: unwired auth placeholder route constants and neutral placeholders.
- `apps/backend/tests/auth/test_router_contract.py`: contract test guarding `POST /sessions` and rejecting `/sessions/login`.
- `artifacts/evidence/dependencies/backend-dependency-install.md`: backend editable install with dev dependencies passed.
- `artifacts/evidence/api/backend-pytest.md`: full backend pytest passed, including DB metadata tests.
- `artifacts/evidence/authz/backend-authz-tests.md`: authz predicate tests passed.
- `artifacts/evidence/api/backend-route-inventory.md`: runtime route inventory passed with only `/health` in schema and empty `/api/v1`.
- `artifacts/evidence/security/route-inventory/backend-route-inventory.md`: security route inventory passed; no financial, import, bank API, SMS, push, broker credential, raw statement, debug, support, or internal bypass routes are mounted.
- `artifacts/evidence/api/openapi-redocly-lint.md`: Redocly lint passed.

## Remaining blockers

### P0 blockers

None found.

### P1 blockers

None found for starting the next worker wave.

### Release caveat

This review verifies cleanup of the listed P1 foundation blockers only. It does not grant MVP release readiness. Release should still require the planned API, auth/session, privacy, security, backup/restore, client, migration, and production configuration evidence.

## Go/Hold recommendation

**Go** for the next worker wave.

Rationale: all required cleanup checks passed from reviewed source and evidence artifacts, and no financial backend routes are mounted yet. The backend runtime surface remains a foundation scaffold with `/health` only, while OpenAPI stays the canonical contract.

## Recommended next worker wave

1. Implement the first service-route slice for accounts/categories using existing authz predicates and OpenAPI DTO names.
2. Add route-level contract tests that compare mounted backend paths and methods against the intended OpenAPI subset for the slice.
3. Extend auth/session integration only when the worker owns the route mounting and can prove neutral error behavior, hash-only token handling, CSRF/cookie boundaries, and Android bearer behavior.
4. Prepare DB migration revisions for the implemented slice, keeping trigger-only constraints and privacy invariants explicitly tracked.
5. Produce fresh evidence after each slice: dependency environment, targeted pytest, full backend pytest, route inventory, and Redocly lint when OpenAPI changes.

## Definition of done

- Prior P1 cleanup blockers are checked against source files and recorded evidence.
- Public OpenAPI transfer scopes are limited to `personal_same_owner` and `household_same_household`.
- Public transfer denial remains `TRANSFER_SCOPE_NOT_SUPPORTED`.
- Authz membership states are exactly `invited`, `active`, `left`, and `revoked`.
- Auth placeholder route is canonical `POST /sessions` and is not mounted accidentally.
- Evidence proves backend dependency install, full pytest, DB metadata tests, authz tests, runtime route inventory, and OpenAPI lint passed.
- Runtime route evidence shows no mounted financial routes and no import, bank API, SMS, push, broker credential, raw statement, debug, support, or internal bypass routes.
- Go/Hold is explicit for the next worker wave.
