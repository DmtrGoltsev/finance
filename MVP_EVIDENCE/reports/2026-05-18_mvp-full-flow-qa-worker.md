# MVP full-flow QA worker report

Дата: `2026-05-18`
Worker: `MVP-FULL-FLOW-QA`
Рабочая папка: `C:\Users\style\Documents\Codex\Финансы`

## Итог

Demo/handoff: `GO / PASS WITH LIMITATIONS`

Release-ready: `HOLD / NOT READY`

Причина: backend, PWA build/tests, Android build/unit/connected tests, PostgreSQL/Alembic proof, PWA cookie/CSRF, Android secure storage и PNG screenshots имеют доказательства. Но полный пользовательский CRUD/archive/restore UX и live transfer UX для PWA/Android не доказаны; transfer seed в свежем live smoke отсутствует (`TRANSFER_COUNT=0`). Поэтому финальный release review должен оставаться `HOLD`, без фиктивного PASS.

## Свежие проверки

| Область | Статус | Evidence | Результат |
|---|---|---|---|
| Backend full pytest | PASS | `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-backend-pytest.txt` | `149 passed, 3 warnings`, `EXIT_CODE=0` |
| PWA tests | PASS | `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-pwa-npm-test.txt` | `2 passed`, `5 tests passed`, `EXIT_CODE=0` |
| PWA build | PASS | `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-pwa-npm-build.txt` | `vite build` succeeded, `EXIT_CODE=0` |
| Android unit tests | PASS | `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-android-unit.txt` | `BUILD SUCCESSFUL`, `EXIT_CODE=0` |
| Android assembleDebug | PASS | `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-android-assembleDebug.txt` | `BUILD SUCCESSFUL`, `EXIT_CODE=0` |
| Android connectedDebugAndroidTest | PASS | `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-android-connectedDebugAndroidTest.txt` | `Finished 2 tests on 1_Pixel_6_Pro(AVD) - 17`, `BUILD SUCCESSFUL`, `EXIT_CODE=0` |
| API live smoke | PASS WITH LIMITATIONS | `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-api-smoke-corrected.txt` | PWA cookie login `201`, bearer current session `200`, accounts `2`, categories `3`, transactions `2`, transfer `0`, reports `200` |
| PWA browser smoke | PASS WITH LIMITATIONS | `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-pwa-5174-browser-smoke.txt`; `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_mvp-full-flow-pwa-5174-desktop.png` | Live dashboard rendered on allowed dev origin `http://127.0.0.1:5174`; screenshot shows session/accounts/operations |
| PNG validation | PASS | `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-png-validation.txt` | All discovered PNG files under `MVP_EVIDENCE/screenshots/**` are valid images with non-zero dimensions |

## Fresh live smoke details

Corrected API smoke:

```text
PWA_COOKIE_LOGIN_STATUS=201 CSRF_PRESENT=True ACCESS_TOKEN_PRESENT=False
BEARER_LOGIN_STATUS=201 ACCESS_TOKEN_PRESENT=True
CURRENT_SESSION_STATUS=200
ACCOUNTS_COUNT=2 CATEGORIES_COUNT=3 TRANSACTIONS_COUNT=2 TRANSFER_COUNT=0
REPORT_MODE=shared_family_report STATUS=200 INCOME=0.0000 EXPENSE=69.7500 NET=-69.7500
REPORT_MODE=combined_viewer_overview STATUS=200 INCOME=250.0000 EXPENSE=69.7500 NET=180.2500
```

Notes:

- Изолированная PWA на `18101` не использовалась как PASS evidence, потому что dev CORS разрешает только `5173/5174`; соответствующий screenshot показывает ошибку live API и учитывается только как диагностический PNG.
- Browser smoke на `5174` использован как актуальное PWA UI evidence: screenshot визуально подтверждает live session, accounts и operations.

## CRUD / transfer / report UX status

| Flow | Статус | Обоснование |
|---|---|---|
| Accounts list/read UX | PASS WITH LIMITATIONS | PWA screenshot и Android evidence показывают live dashboard/list data. |
| Categories list/read UX | PASS WITH LIMITATIONS | UI-код PWA/Android отображает категории из dashboard; отдельный свежий screenshot именно вкладки категорий не снимался. |
| Transactions list/read UX | PASS WITH LIMITATIONS | PWA screenshot показывает операции; API smoke возвращает `2` transactions. |
| Accounts/categories/transactions full CRUD/archive/restore UX | HOLD | В PWA `App.tsx` и Android `FinanceApp.kt` видны read/list dashboard controls, но нет create/edit/delete/archive/restore форм или actions. |
| Transfer UX | HOLD | Backend safety tests есть, но fresh live smoke вернул `TRANSFER_COUNT=0`; PWA отображает transfer list/empty state, но live transfer scenario/screenshot не доказан. |
| Reports UX | PASS WITH LIMITATIONS | API reports для двух режимов проходят; PWA имеет report mode UI, Android показывает totals, но полный набор report-mode screenshots не собран. |

## Screenshots summary

Fresh validation подтвердил валидность PNG:

- Android: `MVP_EVIDENCE/screenshots/android/*.png` валидны, `1440x3120`.
- PWA desktop: валидны, включая `2026-05-18_mvp-full-flow-pwa-5174-desktop.png`.
- iOS-like PWA: валидны, включая `2026-05-18_pwa-cookie-csrf-ios.png`.

Диагностические screenshots `2026-05-18_mvp-full-flow-final-pwa-desktop.png` и `2026-05-18_mvp-full-flow-isolated-pwa-desktop.png` являются валидными PNG, но не являются PASS evidence для PWA UX, потому что отражают CORS/port diagnostic state.

## Закрытые прежние блокеры

- PWA cookie/CSRF: PASS, см. `MVP_EVIDENCE/reports/2026-05-18_pwa-cookie-csrf-integration-worker.md`.
- Android secure storage: PASS, см. `MVP_EVIDENCE/reports/2026-05-18_android-secure-storage-worker.md`.
- PostgreSQL/Alembic live proof: PASS, см. `MVP_EVIDENCE/reports/2026-05-18_postgres-alembic-live-proof-worker.md`.
- Android PNG validity: PASS, см. `MVP_EVIDENCE/test-runs/2026-05-18_mvp-full-flow-png-validation.txt`.

## Оставшиеся release blockers

| ID | Severity | Статус | Блокер | Что нужно для снятия |
|---|---|---|---|---|
| RB-004 | P0 | OPEN | Client full CRUD/archive/restore UX evidence | Реальные PWA/Android сценарии create/edit/delete/archive/restore или утвержденное сужение release scope. |
| RB-005 | P0 | OPEN | Transfer live UX evidence | Seed/scenario с transfer item или созданием перевода + screenshots/run notes на PWA/Android. |
| RB-007 | P1 | OPEN | Release traceability | Зафиксировать release candidate commit/tag; рабочая папка не является git repo. |
| RB-008 | P1 | OPEN | Release hardening evidence | SBOM/dependency/CVE scan, log/audit redaction proof, stale session/cache/cursor/export/offline denial proof. |

## Evidence readiness

Evidence folder is ready for handoff review with limitations: свежие test logs, browser screenshot, PNG validation и worker report находятся в `MVP_EVIDENCE/**`. Release-ready folder is not complete until open blockers above are closed or formally scoped out.
