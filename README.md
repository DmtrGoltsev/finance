# Finance MVP Monorepo

> **Current client status.** The user-facing client mode is personal-only. Android production is released; native iOS code and CI are approved, but physical-iPhone signing, installation, and login smoke have not been performed. `household`, `shared`, and `membership` remain legacy backend/domain/wire-compatibility vocabulary and are not a currently available user mode. This transition is documented in `docs/current-status.md` and `MVP_EVIDENCE/native-ios-current-parity-20260822/SUMMARY_SANITIZED.md` at immutable documentation ref `201b78bf0f8a59681d187bf2925e956950abbada`; deployed production code remains `db7ebdd41a35018ae59e1fc4f5c5e38f0ed37de6`.

The repository retains the original closed-MVP specification for a manual-entry personal and household finance product. That historical specification describes owner-only personal data and shared household data with strict visibility boundaries; it must not be read as the current client feature set.

## Chosen Stack

ADR-0001 selects a contract-first monorepo:

- Backend: Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.x, PostgreSQL 16, Alembic, Pydantic.
- Web/PWA: TypeScript, React, Vite, TanStack Query, generated OpenAPI client, Vitest, Playwright.
- Android: Kotlin, Jetpack Compose, Retrofit/OkHttp or generated OpenAPI client, Room only for scoped offline/cache state.
- API source of truth: `api/openapi/openapi.yaml`, with generated clients/types derived from the contract.
- Evidence: release proof outputs under `artifacts/evidence/**`.

The repo now contains the MVP implementation surface: FastAPI backend, React/Vite
PWA, Android client sources, Alembic migrations, pytest/Vitest coverage, QA
fixtures, security docs, and ops runbooks. The API remains contract-first, and
feature work must preserve the privacy invariants below.

## Source-of-Truth Docs

- `docs/architecture/decision-records/adr-0001-stack-repo-layout.md`
- `docs/architecture/wave-2-implementation-plan.md`
- `docs/architecture/client-state-contracts.md` - client-state, sync, offline-first, and conflict UI contracts.
- `docs/product/ux-quorum-design-decision-ru.md`
- `docs/user-guide-ru.md`
- `MVP_EVIDENCE/reports/2026-05-18_ux-screenshot-checklist.md`
- `docs/current-status.md` - current deployed release, migrations and residual gates.
- `docs/ios-native-mac-handoff.md` - native iOS architecture and signing handoff.
- `docs/ios-native-mac-codex-install-prompt.md` - copy-paste task for Codex on a new Mac.
- `MVP_EVIDENCE/native-ios-current-parity-20260822/SUMMARY_SANITIZED.md` - final iOS/production evidence.
- Wave 1 architecture, security, compliance, and testing docs under `docs/**`

## Privacy Invariants

- Personal data is owner-only.
- The shared-data rules below remain backend/API compatibility invariants; they do not expose a shared user mode in the current clients.
- Shared data is visible only to active members of the same `Household`.
- Reports, exports, search, autocomplete, pagination, caches, counts, and aggregates must filter visible rows before any aggregation or materialization.
- `shared_family_report` includes only shared household rows.
- `combined_viewer_overview` includes shared household rows plus the current viewer's personal rows only.
- Transfers are same-scope only: `personal_same_owner` or `household_same_household`.
- Missing and inaccessible resources return neutral responses.
- Logs, audit, telemetry, crash reports, exports, caches, and client states must not disclose hidden data.
- MVP excludes file imports, bank APIs, bank credentials, broker credentials, card data, IBAN/account requisites, raw bank statements, SMS interception, and push/notification interception.
- MVP also excludes report-preview/file-import flows, SMS/push import pipelines, bank API ingestion, and broker API ingestion.
- The remaining capture-draft flow is user-initiated: OCR from a user-selected screenshot runs on-device on Android, while PWA/iOS browser uses temporary upload to the self-hosted backend OCR endpoint. Screenshots/raw OCR are not persisted, raw external OCR category labels are transient only, a structured draft is created for review, and a transaction is created only after the user confirms or edits the draft.
- OCR/screenshot upload is intentionally online-only: do not queue capture/OCR/screenshot operations through sync, and do not store raw images, raw OCR text, or OCR payloads in offline Room/pending storage.
- Offline-first scope is intentionally bounded. Backend/Android sync currently covers transactions, accounts, categories, asset categories, planning plans/income sources/allocations, and the single atomic investment migration command. `copy_plan`, planning history mutation, target repair workflows, and OCR/screenshot upload remain online-only.

## Repository Areas

- `apps/backend/` - FastAPI backend with auth/session, accounts, categories, transactions, reports, capture drafts, server-side screenshot OCR, DB repositories, and focused tests.
- `apps/web-pwa/` - React/Vite PWA for manual finance workflows and user-confirmed screenshot OCR capture drafts.
- `apps/android/` - Kotlin/Compose Android client with on-device screenshot OCR capture behavior.
- `api/openapi/` - canonical OpenAPI contract.
- `db/` - Alembic migrations and database implementation materials.
- `qa/` - fixtures and expected outputs for release evidence.
- `security/` - security scans, checklists, and privacy review materials.
- `ops/` - backup, restore-drill, and operations materials.

## Local Verification

Use focused commands for the area being changed:

- Backend tests: from `apps/backend`, run `.\.venv\Scripts\python.exe -m pytest ...`.
- Backend lint: prefer targeted `.\.venv\Scripts\python.exe -m ruff check ...` for changed sync/offline modules; full-backend ruff may still fail on legacy unrelated files and is not by itself evidence against the offline-first scope.
- PWA tests: from `apps/web-pwa`, run `npm test -- ...`.
- Android tests: use `.\gradlew.bat :app:testDebugUnitTest` from `apps/android`.
- Android APK gate: use `.\gradlew.bat :app:assembleDebug`, then verify the produced APK is a readable ZIP before sharing or installing it.

Do not add production deploy changes or release evidence churn unless a task
explicitly owns that work.
