# Wave 2 foundation review

## Executive summary

Recommendation: **Go for continuing Wave 2 foundation/service-route implementation with P1 cleanup tasks first; Hold for MVP release**.

The Wave 2 foundation is broadly aligned with ADR-0001 and Wave 1 privacy invariants. OpenAPI remains the canonical contract, Redocly lint is clean, the backend FastAPI scaffold has not mounted financial routes prematurely, domain/source enums are manual-only, auth/authz/db/fixture/security/ops work is mostly scaffold or planning-only, and release readiness is not overclaimed.

No P0 blockers were found. P1 blockers remain around canonical enum drift, one public OpenAPI transfer enum shape, unwired placeholder auth route naming, and missing executable backend evidence in the current environment.

## Reviewed artifacts

- `docs/architecture/decision-records/adr-0001-stack-repo-layout.md`
- `docs/planning/wave-2-backlog.md`
- `docs/architecture/wave-2-implementation-plan.md`
- `docs/architecture/wave-1-integration-review.md`
- `api/openapi/openapi.yaml`
- `api/openapi/README.md`
- `docs/architecture/data-model-implementation-plan.md`
- `db/README.md`
- `db/migrations/README.md`
- `db/seeds/README.md`
- `qa/fixtures/owner-member-other-invited-former-v1/manifest.schema.json`
- `qa/fixtures/owner-member-other-invited-former-v1/fixtures.manifest.example.json`
- `qa/fixtures/owner-member-other-invited-former-v1/loader-notes.md`
- `packages/test-fixtures/**`
- `security/evidence-plan.md`
- `ops/backup-restore-plan.md`
- `apps/backend/pyproject.toml`
- `apps/backend/src/app/main.py`
- `apps/backend/src/app/api/router.py`
- `apps/backend/src/app/config/**`
- `apps/backend/src/app/db/**`
- `apps/backend/src/app/domain/**`
- `apps/backend/src/app/auth/**`
- `apps/backend/src/app/authz/**`
- `apps/backend/tests/**`

## Validation performed

- Ran Redocly lint:
  - Command: `npx.cmd --yes @redocly/cli lint api/openapi/openapi.yaml`
  - Result: pass, "Your API description is valid."
- Reviewed OpenAPI route inventory:
  - Server prefix is `/api/v1`.
  - Report modes are exactly `shared_family_report` and `combined_viewer_overview`.
  - `SourceType` enum is exactly `[manual]`.
  - No import, bank API, SMS, push, broker credential, external credential, raw statement, card, IBAN/requisite, or notification-token paths were found.
- Reviewed backend route mounting:
  - `app.main` mounts only `app.api.router` at `/api/v1`.
  - `app.api.router` is empty; no financial routes are implemented in backend yet.
  - Runtime route inventory could not be executed in this environment because `fastapi` is not installed.
- Ran available standard-library tests:
  - `python -m unittest discover -s packages/test-fixtures/tests`: pass, 5 tests.
  - `python -m unittest discover -s apps/backend/tests/domain`: pass, 4 tests.
  - `python -m unittest discover -s apps/backend/tests/auth`: pass, 7 tests.
  - Authz pytest-style functions were invoked directly through a small import runner: pass, 5 predicate tests.
  - `python -m unittest discover -s apps/backend/tests/db`: pass with 5 skipped tests because `sqlalchemy` is unavailable.
- Attempted full backend pytest:
  - `python -m pytest apps/backend/tests`: blocked, `pytest` is not installed.

## Consistency findings

- OpenAPI is still canonical and narrow. It uses `/api/v1`, manual-only source type, the two canonical report modes, visible-before-aggregate report descriptions, same-scope transfer language, neutral error concepts, and no out-of-scope import/bank/SMS/push endpoint surface.
- Backend scaffold has not prematurely implemented financial routes. `apps/backend/src/app/api/router.py` contains only an empty `APIRouter`, and auth placeholder routes are not mounted from `app.main`.
- Domain enums align with OpenAPI for ownership, account/category/transaction types, report modes, source type, record status, membership status, and invite status. `validate_mvp_source_type_for_write` accepts only `manual` and rejects reserved post-MVP source values.
- Auth skeleton preserves the intended security posture: neutral public responses, hashed-token-only storage interfaces, PWA cookie+CSRF contract, Android bearer/refresh contract, redaction helpers, rate-limit defaults marked pending approval, and explicit release blockers for real hash/storage/rate-limit/CSRF/revocation wiring.
- Authz predicates are deny-by-default, owner-only for personal rows, active-member-only for shared rows, deny invited/former shared financial access, resolve the two report modes correctly, enforce same-scope transfer only, and use neutral denial reasons for hidden/missing references.
- DB skeleton includes planned key tables and constraints: users, households, memberships, invites, accounts, categories, transactions, sessions, reset tokens, export jobs, deletion requests, audit events, and outbox events. It includes manual-only source constraints, exactly-one-scope constraints, money as numeric, token hashes, export/deletion/audit/outbox shapes, and TODOs for trigger-only rules.
- Fixture loader uses deterministic synthetic ids, emits sanitized label/id and evidence skeletons, avoids production app imports, and explicitly forbids tokens, token hashes, passwords, secrets, raw bodies, amounts, account/category names, raw export contents, and production config.
- Security and ops artifacts are planning-only and do not claim release readiness. They define evidence requirements, blockers, and paths without creating scan output, backup scripts, production credentials, or release signoff.

## Findings and blockers

### P0 blockers

None found.

### P1 blockers

1. `api/openapi/openapi.yaml` exposes `unsupported_cross_scope` in the public `TransferScope` component even though MVP transfer scopes are same-scope only and the schema description calls unsupported an internal validation/result value.
   - Risk: generated clients may treat `unsupported_cross_scope` as a legitimate public transaction transfer scope.
   - Required fix: remove `unsupported_cross_scope` from the public `TransferScope` schema or move it to a separate internal/non-wire validation result schema. Keep public denial represented by `TRANSFER_SCOPE_NOT_SUPPORTED`.

2. `apps/backend/src/app/authz/predicates.py` defines `MembershipStatus.REMOVED = "removed"`, but OpenAPI, domain enums, DB enums, fixture schema, and planning docs use only `invited`, `active`, `left`, and `revoked`.
   - Risk: future predicate tests or adapters may reintroduce a legacy noncanonical state.
   - Required fix: remove `removed` or isolate it behind an explicit legacy-migration adapter that cannot reach public contracts or new DB rows.

3. `apps/backend/src/app/auth/router.py` has unwired placeholder route `POST /sessions/login`, while OpenAPI canonical login is `POST /sessions`.
   - Risk: if a future worker mounts this router as-is, backend route inventory will drift from OpenAPI.
   - Required fix: align placeholder route names with OpenAPI before any router mounting, or keep this file explicitly non-mounted until W2-04 replaces it.

4. Executable backend evidence is incomplete in the current environment.
   - `pytest`, `fastapi`, and `sqlalchemy` are unavailable to this reviewer environment.
   - Runtime route inventory, health endpoint test, full pytest run, and DB metadata assertions could not be fully proven here.
   - Required fix: next foundation worker should install/use the backend dependency environment and produce route inventory plus full test output under the planned evidence paths.

## Evidence gaps

- No backend runtime route inventory evidence because FastAPI is unavailable locally.
- No full backend pytest output because pytest is unavailable locally.
- DB model metadata tests skipped because SQLAlchemy is unavailable locally.
- No Schemathesis or equivalent contract/fuzz evidence yet.
- No generated PWA/Android client dry-run evidence yet.
- No auth/session storage, password hash, token hash, CSRF enforcement, rate-limit enforcement, or revocation evidence yet; current code correctly marks these as release blockers.
- No DB migration revision evidence yet; Alembic environment exists, but production revision files are intentionally absent.
- No trigger evidence for immutable account/category scope, transfer same-scope/same-currency, or max active household member enforcement.
- No real seed execution evidence; fixture loader is runner-neutral and does not seed DB.
- No security scan, dependency/SBOM, secret scan, log/audit sample, or out-of-scope source/config scan evidence yet.
- No backup execution, encrypted backup proof, access control proof, restore drill, or tenant-boundary restore verification yet.

## Go/Hold recommendation

**Go** for continuing Wave 2 foundation and service-route implementation, with the P1 cleanup items assigned at the start of the next worker wave. The current artifacts are suitable for W2-04/W2-05-style foundation continuation once workers consume the cleanup findings and use the real backend dependency environment.

**Hold** for MVP release. Release remains blocked until executable backend/API/authz/security/privacy/client/backup evidence exists and all P0/P1 gates are closed.

## Recommended next worker wave

1. API contract cleanup worker: remove or isolate public `unsupported_cross_scope`, re-run Redocly lint, and produce schema diff/route inventory evidence.
2. Authz cleanup worker: remove noncanonical `removed` membership status from predicates or quarantine it as migration-only, then rerun authz predicate tests.
3. Auth route foundation worker: align auth placeholder route paths with OpenAPI before mounting and keep neutral response/hash-only/token lifecycle blockers explicit.
4. Backend environment/evidence worker: run backend dependencies, full `pytest`, runtime route inventory, DB metadata tests, and capture evidence under `artifacts/evidence/api/` and `artifacts/evidence/authz/`.
5. DB migration planning worker: keep SQLAlchemy metadata aligned, prepare first Alembic revisions, and explicitly track trigger-only blockers for immutability, transfer same-scope/same-currency, and active member limits.

## Residual risks

- Report implementation may later aggregate before visible-scope filtering unless workers centralize visible account resolution.
- `combined_viewer_overview` cache can leak if not keyed by viewer, session/access version, household, report mode, membership/access version, and filters.
- Transfer denial can leak hidden-side existence through error shape, logs, timing, validation order, or client copy.
- Former/invited users can regain shared access through stale sessions, cursors, exports, caches, offline snapshots, or restore artifacts if W2-12/W2-16/W2-18 evidence is incomplete.
- DB constraints support shape but do not replace application predicates; release cannot depend on DB metadata alone.
- Security/ops remain plans until scan, backup, restore, dependency, log/audit, CSRF/CORS, and rate-limit artifacts exist.

## Definition of done

Wave 2 foundation review is done when:

- OpenAPI canonical invariants are checked: `/api/v1`, exactly two report modes, `sourceType = manual`, same-scope transfers, and no import/bank/SMS/push routes.
- Backend scaffold is checked for premature financial route implementation.
- Domain/auth/authz/db/fixture/security/ops artifacts are checked against Wave 1 and ADR-0001 invariants.
- P0/P1 blockers, evidence gaps, dependency gaps, and residual risks are explicitly named.
- Go/Hold is split between continued foundation/service-route implementation and MVP release.
- A concrete next worker wave is recommended.
