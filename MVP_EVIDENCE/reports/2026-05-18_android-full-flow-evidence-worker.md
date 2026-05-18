# Android full-flow evidence worker

Дата: 2026-05-18

## Итог

PASS: Android UI показывает live данные с backend `http://10.0.2.2:8000` после demo login: счета, категории, операции, отчетную сводку и перевод.

HOLD для full native CRUD UX: в Android UI нет нативных контролов создания/редактирования/удаления сущностей. CRUD не имитировался. Доказан эквивалент read/report flow на live API с transfer seed `TRANSFER_COUNT=1`.

## Изменения

- `apps/android/app/src/main/java/com/finance/mvp/api/ApiClient.kt`
  - `TransactionSummary` расширен `transferScope` и `transferStatus`.
  - `FinanceDashboard` расширен `reportTransferCount`.
  - `dashboard()` дополнительно читает `/api/v1/reports/transactions?...&transactionTypes=transfer`.
- `apps/android/app/src/main/java/com/finance/mvp/ui/FinanceApp.kt`
  - Overview показывает `переводов: 1`.
  - Operations показывает строку перевода: сумма, дата, description, `posted`, `household_same_household`.
  - Reports показывает карточку `Переводы в отчете` с `Report transactions transfer count: 1`.
- `apps/android/app/src/test/java/com/finance/mvp/ui/AppSectionTest.kt`
  - Добавлен unit guard на видимость transfer proof в Overview, Operations и Reports.

## Проверки

- `./gradlew.bat :app:testDebugUnitTest` - PASS, `MVP_EVIDENCE/test-runs/2026-05-18_android-full-flow-evidence-testDebugUnitTest.txt`.
- `./gradlew.bat :app:assembleDebug` - PASS, `MVP_EVIDENCE/test-runs/2026-05-18_android-full-flow-evidence-assembleDebug.txt`.
- `./gradlew.bat :app:connectedDebugAndroidTest` - PASS, 2 tests на `1_Pixel_6_Pro(AVD) - 17`, `MVP_EVIDENCE/test-runs/2026-05-18_android-full-flow-evidence-connectedDebugAndroidTest.txt`.
- API proof - PASS, `MVP_EVIDENCE/test-runs/2026-05-18_android-full-flow-evidence-api-proof.json`.
- PNG validation - PASS, все 4 PNG имеют валидную PNG-сигнатуру, `MVP_EVIDENCE/test-runs/2026-05-18_android-full-flow-evidence-png-validation.txt`.

## Live API proof

- Login: `POST /api/v1/sessions`, bearer token present.
- Accounts: 3.
- Categories: 3.
- Transactions: 3.
- Transfers: 1.
- Transfer id: `bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb`.
- Transfer scope/status: `household_same_household` / `posted`.
- Summary: income `250.0000`, expense `69.7500`, net `180.2500`.
- Report transfer count: 1.

## Android evidence

- Before login screenshot: `MVP_EVIDENCE/screenshots/android/2026-05-18_android-full-flow-evidence-before-login.png`.
- After login overview screenshot: `MVP_EVIDENCE/screenshots/android/2026-05-18_android-full-flow-evidence-after-login-overview.png`.
- Operations transfer screenshot: `MVP_EVIDENCE/screenshots/android/2026-05-18_android-full-flow-evidence-operations-transfer.png`.
- Reports transfer screenshot: `MVP_EVIDENCE/screenshots/android/2026-05-18_android-full-flow-evidence-reports-transfer.png`.
- Overview XML: `MVP_EVIDENCE/test-runs/android-full-flow-evidence-after-login-overview-window.xml`.
- Operations XML: `MVP_EVIDENCE/test-runs/android-full-flow-evidence-operations-transfer-window.xml`.
- Reports XML: `MVP_EVIDENCE/test-runs/android-full-flow-evidence-reports-transfer-window.xml`.

## Remaining gaps

- Full native CRUD UX remains HOLD because Android currently exposes read/dashboard/report surfaces and demo login, not create/edit/delete controls.
- Equivalent proof is PASS: live backend state and Android UI show account/category/transaction/report data, including the seeded transfer count and transfer row.
