# First Wave Test Summary

Дата: `2026-05-17`
Worker: `W2-EVIDENCE`
Статус: supporting evidence only, not release PASS.

## Summary

| Suite / check | Result | Source |
|---|---|---|
| Backend first-wave pytest | `70 passed, 1 skipped` | `docs/architecture/mvp-first-wave-integration-review.md` |
| PWA Vitest | `2 passed` | `docs/architecture/mvp-first-wave-integration-review.md` |
| Android build/test | `BLOCKED` | `docs/architecture/mvp-first-wave-integration-review.md` |
| API contract tests | `18 passed, 1 skipped` | `docs/architecture/mvp-first-wave-integration-review.md` |
| OpenAPI Redocly lint | `PASS` | `artifacts/evidence/api/openapi-redocly-lint.md` |

## Backend First-Wave Pytest

Recorded result: `70 passed, 1 skipped`.

This proves first-wave backend test coverage for the checked foundation scope. It does not by itself prove release-ready runtime behavior because DB-backed request routing and other runtime flows remain open blockers.

## PWA Vitest

Recorded result: `2 passed`.

This proves the first-wave PWA skeleton tests passed. It does not prove live backend integration, auth/session, CRUD forms, transactions, transfers, reports or screenshots.

## Android Build/Test

Recorded result: `BLOCKED`.

Known blocker: `apps/android/gradlew.bat` and `apps/android/gradle/wrapper/gradle-wrapper.jar` are absent, and local `gradle` is unavailable. W2 placeholder: `MVP_EVIDENCE/test-runs/W2_ANDROID_BUILD_EVIDENCE_TODO.md`.

## API Contract Tests

Recorded result: `18 passed, 1 skipped`.

This preserves canonical OpenAPI/contract expectations, but runtime readiness must not be inferred from contract-only coverage.

## OpenAPI Redocly Lint

Recorded result: `PASS`.

Evidence path: `artifacts/evidence/api/openapi-redocly-lint.md`.

## Open Gaps Before Release

- DB runtime evidence missing.
- Production auth/session evidence missing.
- Transactions/transfers/reports runtime tests missing.
- Android build/test evidence missing.
- Live/device screenshots missing.
