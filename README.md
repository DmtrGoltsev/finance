# Finance MVP Monorepo

Closed MVP for a manual-entry personal and household finance product. The product tracks owner-only personal finance data and shared household finance data while preserving strict visibility boundaries between users.

## Chosen Stack

ADR-0001 selects a contract-first monorepo:

- Backend: Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.x, PostgreSQL 16, Alembic, Pydantic.
- Web/PWA: TypeScript, React, Vite, TanStack Query, generated OpenAPI client, Vitest, Playwright.
- Android: Kotlin, Jetpack Compose, Retrofit/OkHttp or generated OpenAPI client, Room only for scoped offline/cache state.
- API source of truth: `api/openapi/openapi.yaml`, with generated clients/types derived from the contract.
- Evidence: release proof outputs under `artifacts/evidence/**`.

This scaffold intentionally contains README and ignore files only. Do not add `package.json`, `pyproject.toml`, Gradle files, generated clients, or production code until a worker is assigned ownership for that area.

## Source-of-Truth Docs

- `docs/architecture/decision-records/adr-0001-stack-repo-layout.md`
- `docs/architecture/wave-2-implementation-plan.md`
- `docs/product/ux-quorum-design-decision-ru.md`
- `docs/user-guide-ru.md`
- `MVP_EVIDENCE/reports/2026-05-18_ux-screenshot-checklist.md`
- Wave 1 architecture, security, compliance, and testing docs under `docs/**`

## Privacy Invariants

- Personal data is owner-only.
- Shared data is visible only to active members of the same `Household`.
- Reports, exports, search, autocomplete, pagination, caches, counts, and aggregates must filter visible rows before any aggregation or materialization.
- `shared_family_report` includes only shared household rows.
- `combined_viewer_overview` includes shared household rows plus the current viewer's personal rows only.
- Transfers are same-scope only: `personal_same_owner` or `household_same_household`.
- Missing and inaccessible resources return neutral responses.
- Logs, audit, telemetry, crash reports, exports, caches, and client states must not disclose hidden data.
- MVP excludes file imports, bank APIs, bank credentials, broker credentials, card data, IBAN/account requisites, raw bank statements, SMS interception, and push/notification interception.
- The remaining capture-draft flow is user-initiated: OCR from a user-selected screenshot stays local/on-device, creates a structured draft for review, and a transaction is created only after the user confirms or edits the draft.

## Repository Areas

- `apps/backend/` - future FastAPI backend.
- `apps/web-pwa/` - future React/Vite PWA.
- `apps/android/` - future Kotlin/Compose Android client.
- `packages/` - future generated clients and shared test fixtures.
- `security/` - future security scans and runbooks.
- `ops/` - future backup and restore-drill materials.

## Next Setup Steps

1. API worker creates `api/openapi/openapi.yaml` as the contract source of truth.
2. DB worker creates migration and seed planning under `db/`.
3. QA worker creates fixture and evidence harness scaffolding.
4. Backend, PWA, and Android workers add dependency manifests only after ownership is assigned.
5. Security and Ops workers define scan, backup, and restore evidence workflows before release gates.
