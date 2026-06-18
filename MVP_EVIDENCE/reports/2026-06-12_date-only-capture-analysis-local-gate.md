---
status: local-gate-pass-pending-final-qa
date: 2026-06-12
scope: date-only capture, Analysis, backend/PWA/Android local gate evidence
sanitization: no raw logs, tokens, passwords, cookies, raw API payloads, screenshots, XML, or personal financial data
---

# Local gate evidence: date-only capture and Analysis

This report is a sanitized local release-candidate evidence pack for the Finance MVP date-only capture and Analysis workstream.

It is not final emulator QA evidence and not production deploy/smoke evidence. Final release evidence remains pending until backend deploy/migration/smoke, emulator QA, PWA production deploy/smoke, and final KB closure are completed.

## Local gate status

| Area | Status | Sanitized evidence summary |
|---|---:|---|
| Backend scoped lint | PASS | Scoped `ruff` on changed backend Python files passed. |
| Backend focused tests | PASS | Focused `pytest` suite completed: 76 passed, 7 warnings. |
| Backend full tests | PASS | Full `pytest` suite completed: 253 passed, 9 warnings. |
| PWA tests | PASS | `npm.cmd test` completed with exit code 0: 4 files, 43 tests passed. |
| PWA build | PASS | `npm.cmd run build` completed with exit code 0; Vite build processed 1703 modules. |
| PWA whitespace/conflict check | PASS | `git diff --check` for PWA files completed with exit code 0. |
| Android Kotlin compile | PASS | `compileDebugKotlin` completed with exit code 0. |
| Android unit tests | PASS | `testDebugUnitTest` completed with exit code 0: 75 tests, 0 failures. |
| Android debug APK assembly | PASS | `assembleDebug` completed with exit code 0. |
| Integration review | PASS for P0/P1 blockers | Integration review reports P0/P1 blockers closed. |

## Android artifact

| Field | Value |
|---|---|
| APK path | `apps/android/app/build/outputs/apk/debug/app-debug.apk` |
| SHA256 | `6BF3F5BF6BE78C5D38E6C742210706F08488DB13420C941E641B2F51A8917DFF` |
| Size | `54,235,740` bytes |

## Known warnings and limitations

- Backend focused tests completed with 7 warnings.
- Backend full tests completed with 9 warnings.
- Full `ruff` still has known existing debt outside the changed backend scope and was not rerun as the release gate.
- Remaining QA is not complete: full QA, production deploy evidence, and emulator QA are still pending.
- DevOps preflight requires commit/push before backend deployment.
- Backend deploy/migration must precede emulator QA and PWA production QA.

## Staging and deploy next sequence

1. Commit and push the release-candidate changes.
2. Run backend deployment, apply migration, and complete backend smoke checks.
3. Run emulator QA against the selected APK/build, including date-only capture and Analysis flows.
4. Deploy PWA to production and complete production smoke checks.
5. Update final KB/evidence only after deploy, emulator QA, and production smoke evidence are complete.

## Release-candidate interpretation

Local gates are green for the provided backend, PWA, Android, and integration-review checks. This is a staging candidate for the next release sequence, not a final production release claim.

## Evidence hygiene

This report intentionally excludes raw logs, secrets, cookies, session material, passwords, raw API payloads, screenshots, XML dumps, and personal financial data.
