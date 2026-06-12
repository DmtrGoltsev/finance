# Android QA Report: legacy Metal manual amount fix

Дата: 2026-06-12
Папка: `MVP_EVIDENCE/date-only-capture-analysis-qa-metal-fix-20260612-133358`

## Scope

- Android source/tests/evidence only.
- No backend/PWA/KB/git/deploy changes.
- No secrets, tokens, cookies, passwords, raw auth payloads captured or stored intentionally.

## APK

- Path: `C:\Users\style\Documents\Codex\Финансы\apps\android\app\build\outputs\apk\debug\app-debug.apk`
- SHA256: `6AEE934A8817055B1738B32E1468D2A4C5415502C224115F9C7953F63EC3D893`

## Root Cause

The D401 evidence for `Металл` was not an `AssetCategoryUiRow`. It was rendered through the legacy `AssetCategoryCard` path from `AssetSummary(kind=Metal, balance=0, count=0)` with no linked active accounts.

Previous tests modeled the persisted category row shape (`AssetCategoryUiRow` with manual/account totals), so they exercised `AssetCategoryGroupCard` and passed. On the real D401 APK the edit button opened the legacy group dialog, which only had group name and investment checkbox. That is why `Ручная сумма` was absent on device.

D401 evidence used for comparison:

- `MVP_EVIDENCE/date-only-capture-analysis-qa-final-D401-20260612-130029/04_metal_edit_initial.xml`: `Металл` dialog had `Название группы`, `Металл`, `Инвестиция`, `Отмена`, `Сохранить`; no `Ручная сумма`, no `Иконка`.
- `MVP_EVIDENCE/date-only-capture-analysis-qa-final-D401-20260612-130029/05_metal_row_tap.xml`: `Металл` row showed `Нажмите чтобы добавить`, `0,00 RUB`, `Нет счетов в этой категории`; this matches legacy no-account `AssetCategoryCard`, not persisted category UI.

## Android Changes

- `apps/android/app/src/main/java/com/finance/mvp/ui/FinanceApp.kt`
  - Added legacy manual-only detection for Metal summaries with zero count and no active linked accounts.
  - Added manual amount field and save path in the legacy group edit dialog only for that manual-only Metal shape.
  - Save creates a persisted manual asset category, preserving normal legacy rename/migration behavior for other groups.
  - No icon picker was added to legacy edit dialogs.
- `apps/android/app/src/test/java/com/finance/mvp/ui/AppSectionTest.kt`
  - Added D401-shape tests for legacy Metal summary with no accounts.
  - Added non-name-based coverage: behavior keys off `AssetKind.Metal`, not display text.
  - Added Broker/Card negative coverage with active linked accounts.

## Build And Tests

- Focused JVM: `.\gradlew.bat testDebugUnitTest --tests "com.finance.mvp.ui.AppSectionTest"` - PASS.
- Full Android JVM: `.\gradlew.bat testDebugUnitTest` - PASS.
- Debug APK build: `.\gradlew.bat assembleDebug` - PASS.

## Emulator QA

Devices:

- `emulator-5556`: install succeeded, but the preserved D401 session was unavailable; app landed on login/empty state. Not used for behavioral QA.
- `emulator-5554`: install succeeded and session was usable. Behavioral QA performed here.

Metal flow on `emulator-5554`:

- `02_assets.xml/png`: `Металл` legacy row now shows `Ручная 0,00 USD`; other empty legacy groups remain non-manual.
- `03_metal_edit_initial.xml/png`: `Металл` edit dialog shows readable `Ручная сумма`, no `Иконка`.
- Edited manual amount from `0` to `7.77`, saved.
- `04_metal_saved_assets.xml/png`: `Металл` became persisted manual category with `Ручная 7,77 USD` and `7,77 USD`.
- `05_metal_reopen_edit.xml/png`: repeat edit shows `Ручная сумма` value `7.7700`, no `Иконка`.

Broker/Card negative checks:

- `06_card_edit.xml/png`: empty legacy `Карта` dialog has no `Ручная сумма`, no `Иконка`.
- `07_broker_edit.xml/png`: empty legacy `Брокер` dialog has no `Ручная сумма`, no `Иконка`.
- `15_card_account_created.xml/png`: created account-backed `Карта` with sanitized test account `QACardD401`.
- `16_card_account_backed_group_edit.xml/png`: account-backed `Карта` group edit has no `Ручная сумма`, no `Иконка`.
- `20_broker_account_created.xml/png`: created account-backed `Брокер` with sanitized test account `QABrokerD401`.
- `21_broker_account_backed_group_edit.xml/png`: account-backed `Брокер` group edit has no `Ручная сумма`, no `Иконка`.

## Sanitization

- Test account names are synthetic: `QACardD401`, `QABrokerD401`.
- No authentication payloads or headers were captured.
- Text secret scan summary: `secret_scan_summary.json`.

## Remaining Risks

- `emulator-5556` did not preserve the original D401 session, so final behavioral QA used `emulator-5554` with equivalent app state created through UI.
- Existing emulator data was mutated by QA test accounts and manual Metal category creation.
