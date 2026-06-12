# Android Final QA Report - Sanitized

Status: FAIL_WITH_BLOCKED_CAPTURE

Scope: exact debug APK D401 final smoke/micro-QA on live emulator. No code, KB, git commit, or push changes were made. Local QA evidence only.

Evidence folder:

C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\date-only-capture-analysis-qa-final-D401-20260612-130029

Emulator: emulator-5556
Package: com.finance.mvp

## 1. APK install / identity

Result: PASS

- APK path: C:\Users\style\Documents\Codex\Финансы\apps\android\app\build\outputs\apk\debug\app-debug.apk
- File SHA256: D401636F98A6E82D445902DBA25C5FF9D016C9D587F865B0EBB33F0BB2CFA0C4
- Install command target: emulator-5556
- Install status: Success
- Installed base.apk SHA256: d401636f98a6e82d445902dba25c5ff9d016c9d587f865b0ebb33f0bb2cfa0c4
- Evidence: install_status.json

## 2. Assets edit dialogs

Result: FAIL

| Check | Result | Evidence | Notes |
| --- | --- | --- | --- |
| Broker account-backed edit | PASS | 02_broker_edit.png, 02_broker_edit.xml | Shows Название, Брокер, checked Инвестиция; no icon picker; no manual amount field. |
| Card account-backed edit | PASS | 03_card_edit.png, 03_card_edit.xml | Shows Название, Карта, Инвестиция; no icon picker; no manual amount field. |
| Legacy manual-only Металл edit | FAIL | 04_metal_edit_initial.png, 04_metal_edit_initial.xml, 05_metal_row_tap.png, 05_metal_row_tap.xml | Pencil edit dialog shows Название + Инвестиция only. Expected readable Ручная сумма field is absent, so changing/saving/reopening manual amount could not be completed. Row tap only expands Нет счетов / Добавить счёт; no manual amount there either. |

Defect: ANDROID-D401-METAL-MANUAL-AMOUNT-MISSING - legacy Металл manual-only edit dialog still lacks Ручная сумма.

## 3. Payment account filter

Result: PASS

Setup: created sanitized QA account QANONPAYD401 under Банк with Счёт для оплаты unchecked.

| Check | Result | Evidence | Notes |
| --- | --- | --- | --- |
| Non-payment account fixture | PASS | 12_add_bank_account_filled_unchecked.png, 13b_nonpay_account_after_wait.png | QANONPAYD401 created with payment flag unchecked and visible under Банк. |
| Expense account list excludes unchecked account | PASS | 14_expense_accounts_initial.png, 14_expense_accounts_initial.xml, 15_expense_accounts_after_swipe.png, 15_expense_accounts_after_swipe.xml | Expense account chips include checked accounts such as QA Брокер RUB and QA Карта RUB; QANONPAYD401 is absent from XML. |
| Income is not blocked by payment filter | PASS | 18_income_accounts_second_swipe.png, 18_income_accounts_second_swipe.xml | Income account chips include QANONPAYD401 • Личное. |

## 4. Date-only manual operation / analysis

Result: PASS

Created sanitized income: amount 7.89 RUB, account QANONPAYD401, category QA Доход RUB, date selected through calendar as 15.05.2026.

| Check | Result | Evidence | Notes |
| --- | --- | --- | --- |
| Date picker/input path | PASS | 20_date_picker_open.png, 21_date_picker_may.png, 22_date_picker_may15_selected.png, 23_quick_add_date_set.png | Calendar changed date from 12.06.2026 to 15.05.2026. |
| Operation uses date-only | PASS | 28_operations_after_analysis_may.png, 28_operations_after_analysis_may.xml | Operation row shows 2026-05-15 • QA Доход RUB and +7,89 RUB. |
| Analysis uses date-only month | PASS | 26_analysis_current_month.png, 27_analysis_may2026.png, 27_analysis_may2026.xml | June analytics remains Доходы 50 000,00 RUB; May 2026 analytics shows Доходы 7,89 RUB for period 2026-05-01 - 2026-05-31. |

## 5. Capture confirmation

Result: BLOCKED_CAPTURE_FIXTURE

No pending draft/fixture without personal data was available in the live app. Operations screen evidence shows В выбранном scope нет черновиков на проверку after refresh; no amount/date edit and confirm could be performed safely.

Related existing sanitized capture report:

C:\Users\style\Documents\Codex\Финансы\MVP_EVIDENCE\date-only-capture-confirmation-qa-20260612-100149\QA_REPORT_SANITIZED.md

## Final status by requested item

| Item | Status |
| --- | --- |
| 1. Exact APK install and SHA | PASS |
| 2. Assets dialogs | FAIL |
| 3. Payment account filter | PASS |
| 4. Date-only manual operation/analysis | PASS |
| 5. Capture confirmation | BLOCKED_CAPTURE_FIXTURE |

## Defects

1. ANDROID-D401-METAL-MANUAL-AMOUNT-MISSING: legacy Металл edit dialog lacks Ручная сумма, blocking manual amount change/save/reopen verification.

## Sanitization

No secrets, tokens, cookies, passwords, raw auth payloads, or personal data were intentionally logged. Text evidence was scanned separately in secret_scan_summary.json.
