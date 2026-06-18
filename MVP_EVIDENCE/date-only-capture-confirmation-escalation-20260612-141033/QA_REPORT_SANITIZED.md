# PASS: capture confirmation UI amount/date edit

Status: PASS
Timestamp: 20260612-141033 Europe/Moscow
Worker role: capture QA escalation limited worker
Scope: Android capture confirmation UI; edit amount and date before confirming screenshot-derived pending draft
Production code changed: no
Commits/pushes/KB edits: no
Secrets/tokens/cookies/raw authentication bodies saved or printed: no

## Executive result
The live Android confirmation flow was completed on `emulator-5554` without registering a new account and without using raw personal receipt data. A synthetic OCR candidate reached the capture confirmation row, the amount was edited to `45.67`, the operation date was changed to `2026-06-11`, and the draft was confirmed. After confirmation, the pending row disappeared and the Operations screen showed the edited amount/date from the refreshed backend-backed dashboard.

## Route and code findings
- No capture-specific Android deep link was found. `AndroidManifest.xml` exposes only `.MainActivity` launcher; `MainActivity.kt` only handles `openPlanning` / `openSection=analytics`.
- A usable approved UI route exists without production code changes: the Operations screen renders `CaptureDraftReviewCard`, refreshes `GET /api/v1/capture-drafts?status=pending`, and shows pending drafts in `CaptureDraftRow`.
- `FinanceApp.kt` confirmation logic validates account/category, normalizes the edited amount/date, calls `PATCH /api/v1/capture-drafts/{draftId}`, then calls `POST /api/v1/capture-drafts/{draftId}/confirm`.
- `CaptureDraftRow` exposes the required UI controls: `Сумма`, `Дата операции`, account/category chips, `Отклонить`, and `Подтвердить`.

## Live execution evidence
- APK path: `C:\Users\style\Documents\Codex\Финансы\apps\android\app\build\outputs\apk\debug\app-debug.apk`
- Expected/local APK SHA-256: `6AEE934A8817055B1738B32E1468D2A4C5415502C224115F9C7953F63EC3D893`
- Installed APK SHA-256 on `emulator-5554`: `6AEE934A8817055B1738B32E1468D2A4C5415502C224115F9C7953F63EC3D893`
- `/etc/finance/qa-owner.env` was absent, so `FINANCE_QA_PASSWORD` was not read or used.
- Existing authenticated Android app session was present; no token was extracted from device storage.
- Initial Operations state after install/launch: authenticated, `Черновики операций` visible, `В выбранном scope нет черновиков...`, no confirmation row.
- A synthetic non-personal OCR image path was attempted through Android Photo Picker. The selected synthetic QA media produced live backend OCR candidates in the app (`Backend OCR сформировал...` / `Категории на скриншоте` visible).
- UI category setup was completed through the app (`Новая`), after which a pending confirmation row appeared.
- Amount edit evidence: `EditText` changed from OCR value to `45.67`; UI dump confirmed `amountEditedVisible=true`.
- Date edit evidence: Material date picker changed `Дата операции` from `2026-06-10` to `2026-06-11`; UI dump confirmed `dateEditedVisible=true`.
- Confirm evidence: tapping `Подтвердить` removed the confirmation row; post-confirm UI dump had `confirmStillVisible=false`, `noDraftsVisible=true`, `operationsHeaderVisible=true`, `amountInOperationsVisible=true`, and `dateInOperationsVisible=true`.

## Verification commands
- Backend focused tests:
  - Command: `.\.venv\Scripts\python.exe -m pytest tests/capture_drafts/test_capture_drafts_runtime.py tests/capture_drafts/test_screenshot_ocr_parser.py tests/capture_drafts/test_screenshot_ocr_endpoint.py -q`
  - Result: `26 passed, 1 warning in 9.91s`
  - Note: running with active `python` first failed during collection because `sqlalchemy` was not installed there; rerun with the project `.venv` passed.
- Android focused JVM tests:
  - Command: `.\gradlew.bat :app:testDebugUnitTest --tests com.finance.mvp.capture.CaptureParserTest --tests com.finance.mvp.api.ApiClientCaptureDraftTest`
  - Result: `BUILD SUCCESSFUL in 14s`

## Automated coverage mapped
- Backend tests cover capture draft create/list/dedup/update/confirm, `occurredDate` date-only handling into confirmed transaction date, screenshot OCR parser, endpoint privacy/no raw OCR persistence, rate limits, and category mapping isolation.
- Android JVM tests cover capture parser behavior and API client request/parse behavior for capture draft create/list/update/confirm/discard flows.
- Live Android UI evidence now covers the missing manual integration path: synthetic screenshot candidate -> pending confirmation row -> edit amount/date -> confirm -> Operations refresh.

## Residual risk
PASS is scoped to the current emulator and existing authenticated QA app session. Because the approved password locator was absent, this run did not prove fresh login from credentials, nor did it use an external API-created draft under the same account. The minimal future hardening remains a test-only seed/deep link or documented parseable OCR fixture so this can be repeated deterministically without depending on Photo Picker media ordering.
