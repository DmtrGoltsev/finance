# BLOCKED_CAPTURE_FIXTURE_DETAILED: Android capture confirmation date-only QA

Status: BLOCKED
Timestamp UTC: 20260612-100149
Worker role: Android/backend QA-unblock limited subagent
Scope: capture confirmation screen, edit amount and occurredDate/transactionDate date-only, confirm, verify saved transaction
Production code changed: no
Commits/pushes/KB edits: no
Secrets/tokens/cookies/raw auth payloads saved or printed: no

## Executive result
Live Android confirmation could not be completed in this run. The blocker is not a missing backend structured draft path: POST /api/v1/capture-drafts is an approved sanitized path and backend tests prove update+confirm carries edited mount and occurredDate into transaction mount and 	ransactionDate. The live UI path was blocked after reasonable attempts by a combination of non-parseable live OCR fixture behavior and remote auth registration rate limiting during synthetic-account setup.

## Environment evidence
- Workspace: C:\Users\style\Documents\Codex\Финансы
- Android package: com.finance.mvp
- Target emulator used: emulator-5554
- Workspace debug APK SHA-256: B0EC81FFBBA6738EB12692A1EF9B8820DCDCB8881EFE9D535621EADC6E124358
- Installed emulator-5554 APK SHA-256 checked earlier in run: B0EC81FFBBA6738EB12692A1EF9B8820DCDCB8881EFE9D535621EADC6E124358
- Backend base probed by APK/default config: http://45.10.110.42/finance-api
- /health returned HTTP 200; unauthenticated /api/v1/sessions/current returned HTTP 401 as expected.

## Existing code paths checked
- Android capture picker flow: FinanceApp.processScreenshotCapture() sends selected image to piClient.screenshotOcr(...), then createScreenshotAggregateDrafts() calls piClient.createCaptureDraft(...) only after a category is selected.
- Android confirmation row: CaptureDraftRow exposes Сумма, Дата операции, account/category chips, and Подтвердить; confirmCaptureDraft(...) patches mount, occurredDate, ccountId, categoryId, then posts /confirm.
- Android API client endpoints checked in code:
  - GET /api/v1/capture-drafts?status=pending
  - POST /api/v1/capture-drafts
  - PATCH /api/v1/capture-drafts/{draftId}
  - POST /api/v1/capture-drafts/{draftId}/confirm
  - POST /api/v1/capture-drafts/screenshot-ocr
- Backend endpoints checked in code/tests:
  - POST /capture-drafts/screenshot-ocr returns structured candidates only, not raw OCR text.
  - POST /capture-drafts accepts sanitized structured screenshot candidates.
  - PATCH /capture-drafts/{draftId} updates mount and occurredDate while pending.
  - POST /capture-drafts/{draftId}/confirm creates manual expense transaction with 	ransactionDate derived from occurredDate.

## Attempts performed
1. Read AGENTS.md, Ru_OrchestratorRules.md, Ru_SubagentFirstFinishNew.md; acted as limited subagent and did not launch subagents.
2. Verified active emulators and installed APK hash for emulator-5554.
3. Created a synthetic non-personal image fixture containing only ASCII test text:
   - Finance Analysis, Expenses, QA Capture Test, 12.34 USD, 1 operations.
   - Synthetic image SHA-256: 35B7007ADEB9231CA1080B27AEC109123663ACF5FCCE6CF97CE0718554C7F12E.
4. Added the image to emulator MediaStore and selected it through Android Photo Picker.
5. Android returned: Backend OCR не нашёл расходов на скриншоте; no candidate/draft appeared from OCR.
6. Checked /etc/finance/qa-owner.env; it was absent, so no provided QA owner password was used.
7. Attempted synthetic live API setup without printing credentials:
   - temporary registration via POST /api/v1/users,
   - synthetic payment account,
   - synthetic expense category,
   - sanitized structured screenshot draft via POST /api/v1/capture-drafts.
8. Initial UI login automation had two harness issues found and corrected:
   - normal db input text was unreliable for email/password; switched to installed com.android.adbkeyboard/.AdbIME.
   - pm clear exposed Android notification permission dialog; added explicit dismissal.
9. Before a final clean end-to-end retry could complete, remote backend registration returned TOO_MANY_REQUESTS. No further synthetic account/token could be obtained safely in-process.

## Unit/JVM coverage verified in this run
- Backend focused tests:
  - Command: python -m pytest tests/capture_drafts/test_capture_drafts_runtime.py tests/capture_drafts/test_screenshot_ocr_parser.py tests/capture_drafts/test_screenshot_ocr_endpoint.py -q
  - Result: 26 passed, 1 warning
  - Covers create/list/dedup/update/confirm, date-only occurredDate -> transactionDate, screenshot OCR parser, endpoint privacy/no raw writes, rate limits, and mapping isolation.
- Android JVM focused tests:
  - Command: ./gradlew.bat :app:testDebugUnitTest --tests com.finance.mvp.capture.CaptureParserTest --tests com.finance.mvp.api.ApiClientCaptureDraftTest
  - Result: BUILD SUCCESSFUL
  - Covers Android capture parser and API client request/parse behavior for capture draft flows.

## Minimal input needed to finish live PASS
Any one of the following would unblock a clean live confirmation pass:
1. A parseable synthetic image fixture known to produce at least one candidate through the live backend OCR engine, ideally checked into QA fixtures or documented with expected OCR output.
2. A test-only approved seed endpoint or helper that creates a pending screenshot capture draft for the currently logged-in Android QA account without raw OCR/image input.
3. Restored access to /etc/finance/qa-owner.env with FINANCE_QA_PASSWORD, or a temporary reset of the remote registration rate limit, so a synthetic account can be created once and driven through Android UI with backend verification.

## Definition of done not met
Not met: live Android confirmation screen did not complete edit mount=45.67, edit date to 2026-06-11, tap Подтвердить, and verify backend transaction in the same live authenticated account.

## Residual risk
Backend and Android unit/JVM coverage is strong for the contract, but the live Android integration remains unproven because no live parseable candidate/draft was available to the app at the end of the run.
