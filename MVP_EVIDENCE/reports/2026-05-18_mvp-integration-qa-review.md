# MVP integration QA review

Дата: `2026-05-18`
Worker: `MVP-INTEGRATION-QA-REVIEW`
Рабочая папка: `C:\Users\style\Documents\Codex\Финансы`
Evidence folder: `C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE`

## Решение

- MVP demo/handoff: `PASS WITH LIMITATIONS`.
- Release-ready: `HOLD`.

Обоснование: backend, PWA и Android имеют достаточный локальный live-demo контур для передачи следующему владельцу/parent orchestration: backend full suite зеленый, PWA test/build зеленые, Android assemble/unit test зеленые, dev backend и PWA dev server отвечают, PWA/iOS-like screenshots валидны. Но release-ready PASS ставить нельзя: остаются security/session gaps, нет real PostgreSQL/Alembic live evidence, frontend/mobile не доказывают полный CRUD/transfer/report сценарий, Android PNG screenshots повреждены как изображения, iOS screenshot является browser viewport, а не финальным device evidence.

## Проверенные evidence

Основные отчеты:

- `MVP_EVIDENCE/reports/2026-05-18_backend-dev-surface-seed.md`
- `MVP_EVIDENCE/reports/pwa-live-api-worker-report.md`
- `MVP_EVIDENCE/reports/2026-05-18_android-live-api-worker.md`
- `MVP_EVIDENCE/reports/2026-05-17_wave2-gate-refresh.md`
- `MVP_EVIDENCE/reports/2026-05-17_w3-ttr-preflight.md`
- `artifacts/evidence/api/w3-api-contract-sync.md`
- `artifacts/evidence/api/w3-transactions-db-runtime.md`
- `artifacts/evidence/api/w3-transfer-safety-runtime.md`
- `artifacts/evidence/api/w3-report-runtime-safety.md`
- `artifacts/evidence/api/db-runtime-default-gate-closure.md`

## QA verification run by reviewer

Commands run on `2026-05-18`:

```text
cd apps/backend
.\.venv\Scripts\python.exe -m pytest -q
=> 143 passed, 3 warnings in 12.33s
```

```text
cd apps/web-pwa
npm.cmd test
=> 2 test files passed, 4 tests passed

npm.cmd run build
=> vite build succeeded
```

```text
cd apps/android
.\gradlew.bat :app:testDebugUnitTest
=> BUILD SUCCESSFUL in 2s

.\gradlew.bat :app:assembleDebug
=> BUILD SUCCESSFUL in 2s
```

Live smoke:

- `GET http://127.0.0.1:8000/health` returned `200`, body `{"status":"ok"}`.
- `http://127.0.0.1:5174` returned `200`.
- Demo login with `transport=android_bearer` returned bearer token and actor `11111111-1111-4111-8111-111111111111`.
- `GET /api/v1/accounts` returned `2` items.
- `GET /api/v1/transactions` returned `2` items.
- `GET /api/v1/reports/summary?reportMode=combined_viewer_overview&householdId=22222222-2222-4222-8222-222222222222&currency=USD` returned income `250.0000`, expense `69.7500`, net `180.2500`.

Reviewer note: an earlier smoke using `mode=combined_viewer_overview` returned `422`; correct runtime query parameter is `reportMode`.

## Screenshot verification

Valid PNG evidence:

- `MVP_EVIDENCE/screenshots/pwa-desktop/pwa-live-api-desktop.png`: non-empty, valid PNG, `1440x900`.
- `MVP_EVIDENCE/screenshots/pwa-desktop/pwa-live-api-diagnostic.png`: non-empty, valid PNG, `1440x900`.
- `MVP_EVIDENCE/screenshots/ios-pwa/pwa-live-api-ios.png`: non-empty, valid PNG, `390x1514`.
- `MVP_EVIDENCE/test-runs/pwa-live-api-smoke.png`: non-empty, valid PNG, `1280x800`.

Android screenshot files exist and are non-empty, but are not valid PNG images as stored:

- `MVP_EVIDENCE/screenshots/android/2026-05-18_android-live-api-smoke.png`
- `MVP_EVIDENCE/screenshots/android/2026-05-18_android-live-api-after-login.png`
- `MVP_EVIDENCE/screenshots/android/2026-05-18_android-live-api-final.png`

The Android files begin with bytes `FF FE FD FF 50 00 4E 00...` instead of the PNG signature `89 50 4E 47 0D 0A 1A 0A`; `System.Drawing.Image.FromFile` rejects them. Android XML evidence is useful and confirms live API text, but final visual screenshot evidence must be regenerated.

## Status by area

| Area | Status | Evidence | QA note |
|---|---|---|---|
| Backend automated tests | PASS | Reviewer run: `143 passed, 3 warnings`; `artifacts/evidence/api/w3-api-contract-sync.md` | Current local full suite is greener/newer than previous `140/139/134` snapshots. |
| Backend transactions runtime | PASS for backend test scope | `artifacts/evidence/api/w3-transactions-db-runtime.md` | Backend runtime and tests exist; frontend/mobile full CRUD evidence is not complete. |
| Backend transfer safety | PASS for backend test scope | `artifacts/evidence/api/w3-transfer-safety-runtime.md` | Same-scope transfer safety tested in backend; dev seed/screens do not demonstrate transfer UX. |
| Backend reports runtime | PASS for backend test scope | `artifacts/evidence/api/w3-report-runtime-safety.md` | Runtime tests pass; release still needs full frontend/mobile evidence and privacy/cache/export gates as applicable. |
| DB runtime policy | PASS for safe MVP policy, HOLD for release PostgreSQL flip | `artifacts/evidence/api/db-runtime-default-gate-closure.md` | No live PostgreSQL + Alembic upgrade evidence in this workspace. |
| PWA automated test/build | PASS | `MVP_EVIDENCE/test-runs/pwa-live-api-npm-test.txt`, `pwa-live-api-npm-build.txt`, reviewer run | Uses bearer token in `localStorage`, which remains release blocker. |
| PWA live demo | PASS for demo/handoff | `MVP_EVIDENCE/reports/pwa-live-api-worker-report.md`, PWA screenshots | Demonstrates live accounts/transactions/report summary via dev backend. |
| Android build/unit | PASS | `MVP_EVIDENCE/reports/2026-05-18_android-live-api-worker.md`, reviewer Gradle runs | Build and unit tests pass. |
| Android emulator smoke | PARTIAL | Android XML files | XML confirms live API data; PNG screenshots are corrupted as images. |
| Release checklist | HOLD | `MVP_EVIDENCE/release-checklist.md` | Release gates remain open. |

## Remaining release blockers

- Secure token storage: PWA stores bearer token in `localStorage`; Android `TokenStore` is in-memory. Need approved PWA cookie/CSRF or explicit scope exception, plus Android encrypted storage if Android is release surface.
- PWA cookie/CSRF: backend has bearer flow; release evidence for HttpOnly cookie session, CSRF binding/rotation and negative CSRF tests is absent.
- Real PostgreSQL/Alembic evidence: no live PostgreSQL service, no `alembic upgrade head` proof, no table/trigger verification against PostgreSQL, no production-like startup/fail-fast evidence.
- Transfer live demo evidence: backend transfer safety tests pass, but seeded live demo has no transfer transaction and screenshots do not prove transfer UX.
- Frontend/mobile full CRUD: backend CRUD exists for accounts/categories/transactions, but PWA/Android evidence is dashboard/read-heavy; create/edit/archive/restore/delete flows are not proven on clients.
- Final device screenshots: PWA desktop and iOS-like browser viewport screenshots are valid; Android PNG files must be regenerated; iOS/PWA still needs final device/simulator decision if in release scope.
- Release candidate traceability: current folder is not a git repository from reviewer shell, and commit/tag is not fixed in MVP evidence.
- Broader hardening evidence: SBOM/dependency/CVE scan, sanitized log/audit proof, cache/cursor/export/offline stale-access denial and production secrets/deployment checks are not present.

## Recommended next workers

1. `MVP-RELEASE-POSTGRES-ALEMBIC-GATE`
   - Role: backend/ops integration worker.
   - Reasoning: `xhigh`.
   - DoD: live PostgreSQL available, Alembic upgraded to head, tables/triggers verified, production-like app startup/fail-fast evidence captured.

2. `MVP-PWA-SESSION-SECURITY`
   - Role: security backend/PWA worker.
   - Reasoning: `xhigh`.
   - DoD: PWA cookie/CSRF decision implemented or explicit release scope exception approved; no bearer token in localStorage for release scope.

3. `MVP-ANDROID-DEVICE-EVIDENCE`
   - Role: Android QA worker.
   - Reasoning: `medium`.
   - DoD: regenerate valid PNG screenshots from emulator/device, include overview/accounts/categories/transactions/reports and transfer state if in demo scope.

4. `MVP-FRONTEND-FULL-FLOW-QA`
   - Role: PWA/Android QA worker.
   - Reasoning: `high`.
   - DoD: client-side CRUD, transfer and report flows tested with live backend or explicitly marked out of release scope.

5. `MVP-RELEASE-HARDENING-EVIDENCE`
   - Role: security/release QA worker.
   - Reasoning: `xhigh`.
   - DoD: dependency/security scan, log/audit redaction proof, stale session/cache/export/offline denial proof and final release report update.
