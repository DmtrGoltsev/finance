# Test Matrix MVP

Дата последнего обновления: `2026-05-18`
Сборка / commit / tag: `PENDING: current folder is not a git repo; release-git-worker approved`
Окружение: `local Windows workspace, dev seeded backend, PWA dev/build evidence, Android emulator evidence`

Статусы: `TODO`, `PASS`, `PASS WITH LIMITATIONS`, `PARTIAL`, `FAIL`, `HOLD`, `BLOCKED`, `N/A`.

Важно: эта матрица допускает `PASS` только для доказанного scope. Security/release traceability limitations не отменяют functional MVP GO, но должны быть раскрыты перед публикацией/tag.

| ID | Flow | Платформа | Статус | Evidence | Примечание |
|---|---|---|---|---|---|
| MVP-001 | Demo login/session | Backend, PWA, Android | PASS WITH LIMITATIONS | `MVP_EVIDENCE/reports/2026-05-18_pwa-cookie-csrf-integration-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-native-crud-ux-worker.md` | Dev/demo flow работает; PWA cookie path and Android bearer path covered. |
| MVP-002 | Release-grade session/security | PWA, Android, Backend | PASS WITH LIMITATIONS | `MVP_EVIDENCE/reports/2026-05-18_pwa-cookie-csrf-integration-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-secure-storage-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_release-hardening-evidence-worker.md` | PWA cookie/CSRF, no localStorage bearer and Android encrypted storage evidence exist; backend/Android CVE scanners pending. |
| MVP-003 | Accounts list/read | Backend, PWA, Android | PASS | `MVP_EVIDENCE/reports/2026-05-18_pwa-accounts-categories-transfer-crud-recovery-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-native-crud-ux-worker.md` | Latest accepted Android live proof has `4` accounts; PWA lifecycle screenshots exist. |
| MVP-004 | Accounts CRUD/archive/restore | Backend, PWA, Android | PASS WITH LIMITATIONS | `MVP_EVIDENCE/reports/2026-05-18_pwa-accounts-categories-transfer-crud-recovery-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-native-crud-ux-worker.md` | PWA full CRUD/delete PASS; Android lifecycle controls PASS, deterministic values. |
| MVP-005 | Categories list/read | Backend, PWA, Android | PASS | `MVP_EVIDENCE/reports/2026-05-18_pwa-accounts-categories-transfer-crud-recovery-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-native-crud-ux-worker.md` | Latest accepted Android live proof has `4` categories; PWA lifecycle screenshots exist. |
| MVP-006 | Categories CRUD/archive/restore | Backend, PWA, Android | PASS WITH LIMITATIONS | `MVP_EVIDENCE/reports/2026-05-18_pwa-accounts-categories-transfer-crud-recovery-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-native-crud-ux-worker.md` | PWA full CRUD/delete PASS; Android lifecycle controls PASS, deterministic values. |
| MVP-007 | Transactions list/read | Backend, PWA, Android | PASS | `MVP_EVIDENCE/reports/2026-05-18_pwa-accounts-categories-transfer-crud-recovery-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-native-crud-ux-worker.md` | Latest accepted Android live proof has `7` transactions. |
| MVP-008 | Transactions create/edit/delete/restore | Backend, PWA, Android | PASS WITH LIMITATIONS | `MVP_EVIDENCE/reports/2026-05-18_pwa-accounts-categories-transfer-crud-recovery-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-native-crud-ux-worker.md` | PWA operation lifecycle PASS; Android native transaction controls PASS with deterministic MVP values. |
| MVP-009 | Same-scope transfer lifecycle | Backend, PWA, Android | PASS WITH LIMITATIONS | `MVP_EVIDENCE/reports/2026-05-18_pwa-accounts-categories-transfer-crud-recovery-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-native-crud-ux-worker.md`; `artifacts/evidence/api/w3-transfer-safety-runtime.md` | Transfer lifecycle proven through `/api/v1/transactions` with `transactionType=transfer`; no standalone transfer route required. |
| MVP-010 | Reports summary | Backend, PWA, Android | PASS | `MVP_EVIDENCE/reports/2026-05-18_pwa-accounts-categories-transfer-crud-recovery-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_android-native-crud-ux-worker.md`; `artifacts/evidence/api/w3-report-runtime-safety.md` | PWA report modes PASS; Android report transfer count `3`. |
| MVP-011 | Reports full UX | PWA, Android | PASS WITH LIMITATIONS | `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-reports-modes-desktop.png`; `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-reports-modes-ios.png`; `MVP_EVIDENCE/screenshots/android/2026-05-18_android-native-crud-reports-after-transfer.png` | Screenshots/evidence exist; deeper analytics UX is post-MVP. |
| MVP-012 | Negative privacy case | Backend, PWA, Android | PASS WITH LIMITATIONS | `artifacts/evidence/api/w3-report-runtime-safety.md`; `w3-transfer-safety-runtime.md`; `MVP_EVIDENCE/reports/2026-05-18_release-hardening-evidence-worker.md`; `MVP_EVIDENCE/reports/2026-05-18_pwa-accounts-categories-transfer-crud-recovery-worker.md` | Backend privacy cases pass; stale-session/redaction/no localStorage bearer pass; expanded device cache/back-stack privacy remains follow-up. |
| MVP-013 | Real PostgreSQL/Alembic runtime | Backend/Ops | PASS WITH LIMITATION | `MVP_EVIDENCE/reports/2026-05-18_postgres-alembic-live-proof-worker.md` | Disposable local PostgreSQL + Alembic head passed; no route-level DB-backed sync smoke due missing `psycopg/psycopg2`. |
| MVP-014 | PWA desktop screenshot | PWA desktop | PASS | `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-crud-transfer-overview-desktop.png`; CRUD/transfer/report screenshots under `MVP_EVIDENCE/screenshots/pwa-desktop/` | Reviewer PNG signature check: valid PNG. |
| MVP-015 | iOS/PWA screenshot | iOS-like PWA | PASS WITH LIMITATIONS | `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-account-crud-ios.png`; `2026-05-18_pwa-category-crud-ios.png`; `2026-05-18_pwa-transfer-lifecycle-ios.png`; `2026-05-18_pwa-reports-modes-ios.png` | Valid browser viewport PNG; physical-device scope not separately proven. |
| MVP-016 | Android screenshots | Android | PASS | `MVP_EVIDENCE/screenshots/android/2026-05-18_android-native-crud-*.png`; `MVP_EVIDENCE/test-runs/2026-05-18_android-native-crud-png-validation.txt` | Android native CRUD PNG files are valid. |
| MVP-017 | Build/test package | Backend, PWA, Android | PASS | `MVP_EVIDENCE/reports/2026-05-18_final-mvp-gate-review-2.md`; worker run logs | Fresh reviewer checks: backend `149 passed`; PWA `7 passed` and build; Android unit/build/connected succeeded. |
| MVP-018 | Known limitation disclosure | Product scope | PASS | `MVP_EVIDENCE/MVP_RELEASE_REPORT.md`; `MVP_EVIDENCE/reports/2026-05-18_final-mvp-gate-review-2.md` | Non-MVP features and release-hardening limitations documented. |
| MVP-019 | Final MVP completion gate | Android, iOS/PWA, release evidence | GO | `MVP_EVIDENCE/reports/2026-05-18_final-mvp-gate-review-2.md` | Functional MVP GO; release-git-worker approved. |

## Supporting Results

- Backend fresh reviewer full pytest: `149 passed, 3 warnings in 15.02s`.
- PWA fresh reviewer run: `2 test files passed`, `7 tests passed`; build succeeded.
- Android fresh reviewer run: `:app:testDebugUnitTest`, `:app:assembleDebug`, `:app:connectedDebugAndroidTest` succeeded.
- PWA recovery E2E: account/category/operation/transfer lifecycle PASS; transfer visible `count=6`; reports PASS; localStorage empty.
- Android native live proof: accounts `4`, categories `4`, transactions `7`, transfers `3`, report transfer count `3`.
- PNG validation: new PWA/iOS-like and Android native screenshots valid.

## Remaining Evidence / Release Follow-up

- Create release candidate commit/tag in a real git repository.
- Run backend Python and Android/JVM CVE scans with approved tooling or record explicit waiver.
- Optionally run physical iPhone validation for PWA.
- Optionally expand Android arbitrary edit forms beyond deterministic MVP controls.
- Optionally add deeper client/device privacy cache/back-stack/offline smoke.

## Критерии прохождения release

- Functional MVP criteria are met for current accepted scope.
- Public publication/tag must wait for `release-git-worker` safety gates: curated staging, secret scan, exclusion of local caches/build debris, release notes with limitations, and explicit visibility decision.

