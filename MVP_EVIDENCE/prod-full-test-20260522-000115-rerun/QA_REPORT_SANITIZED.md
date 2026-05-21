# Production Android Emulator QA Report - Sanitized Summary

Date: 2026-05-22 MSK
Verdict: PASS for full production Android retest.

## Target

- Android client commit: `d9ffc75454c57007b465f51b7782c12c52935823` (`d9ffc75`).
- Server production runtime: `808f7278` per release context; no server deploy or cleanup was performed.
- PWA: production finance web endpoint.
- API: production finance API endpoint.
- APK: `apps/android/app/build/outputs/apk/debug/app-debug.apk` built with the production finance API base URL.

## Device / Build / Install

- ADB device: `emulator-5554`, model `sdk_gphone16k_x86_64`.
- `:app:assembleDebug`: PASS, `BUILD SUCCESSFUL` in `android-emulator/logs/assembleDebug.txt`.
- `:app:testDebugUnitTest`: PASS, `BUILD SUCCESSFUL` in `android-emulator/logs/testDebugUnitTest.txt`.
- `:app:connectedDebugAndroidTest`: PASS, `BUILD SUCCESSFUL` in `android-emulator/logs/connectedDebugAndroidTest.txt`.
- `adb install -r`: PASS, `Success` in `android-emulator/logs/adb-install.txt`.
- Local emulator app data was cleared before the manual login flow to prove initial login state.

## Production Smoke

- PWA health: PASS, HTTP 200 in `android-emulator/data/pwa-health.json`.
- API health: PASS, HTTP 200 in `android-emulator/data/api-health.json`.

## Screenshot / XML Evidence Map

Final PNG evidence is under `android-emulator/screenshots/final-valid/`; matching UI XML is under `android-emulator/xml/`.

- App start/login screen: `01-app-start-login-screen.png`.
- Login/auth screen with redacted email and masked password: `02-login-auth-masked-credentials.png`.
- Successful login/dashboard/home: `03-successful-login-dashboard-home.png`, `03b-finance-resumed-dashboard.png`.
- Accounts/assets: `04-accounts-assets.png`.
- Categories/account verification: `05-categories-account-verification.png`.
- Operations before new data: `06-operations-before-new.png`.
- Quick Add sheet and expense entry: `07-quickadd-sheet-initial.png`, `08-expense-entry-ready.png`, `09-expense-submit-visible.png`.
- Expense operation created: `10-expense-operation-created.png`.
- Income operation: `11-income-entry-ready.png`, `12-income-operation-created.png`.
- Transfer operation: `13-transfer-entry-ready.png`, `14-transfer-operation-created.png`.
- Reports/analytics summary: `15-reports-analytics-summary.png`.
- Validation/error states: `16-validation-error-empty-amount.png`, `19-validation-error-empty-login-after-logout.png`.
- Force-stop/relaunch session persistence: `17-force-stop-relaunch-session-persistence.png`.
- Logout: `18-after-logout-login-state.png`.
- Relaunch after logout/no stale financial data: `20-relaunch-after-logout-login-no-stale-data.png`.

## Flow Results

- Login/auth: PASS. QA credentials were read through the existing production QA mechanism; credential values are not included in evidence or reports. Login screenshot has email redacted and password masked.
- Dashboard/home: PASS. Production dashboard loaded after login.
- Accounts/assets: PASS. Assets screen displayed expected account group sections without exposing account names in this sanitized summary.
- Categories/account verification: PASS. Categories screen displayed expected QA category controls without exposing concrete category/account labels in this sanitized summary.
- Expense operation: PASS. A synthetic expense row was created through Android Quick Add.
- Income operation: PASS. A synthetic income row was created through Android Quick Add.
- Transfer operation: PASS. A synthetic transfer row was created through Android Quick Add.
- Reports/analytics: PASS. Analytics reflected updated income, expense, and transfer totals; exact financial values are retained only in raw local evidence.
- Validation/error: PASS. Captured disabled empty-amount save state and empty login validation message after logout.
- Force-stop/relaunch persistence: PASS. After `am force-stop` and cold relaunch, the app returned to authenticated dashboard state without manual relogin.
- Logout: PASS. Explicit logout returned to login state.
- Relaunch after logout: PASS. Force-stop/relaunch after logout showed login state and zero/no stale financial data.

## Production QA Data Created

Synthetic expense/income/transfer rows were created through Android UI; exact values retained only in raw local evidence.

No production cleanup was performed.

## Evidence Quality

- Final PNG validation: PASS, 21/21 valid PNGs, `badCount=0` in `android-emulator/data/png-validation-final-valid.json` and `android-emulator/data/evidence-validation-summary.json`.
- XML credential hygiene: PASS, `emailHitsInXml=0` in `android-emulator/data/evidence-validation-summary.json`.
- Exact QA password scan: PASS, `exactPasswordHits=0` in `android-emulator/data/secret-scan-password-exact.json`.

## Privacy / Evidence Handling

- Raw screenshots, XML dumps, and logs remain local and uncommitted due to privacy policy.
- Concrete financial amounts, account names, emails, UUIDs, tokens, credentials, cookie/session values, and other secret or PII values are omitted or generalized in this sanitized summary.

## Safety Confirmations

- No commit, push, tag, deploy, server/prod cleanup, or production DB direct write was performed.
- No password, token, cookie, session value, or credential value is included in this sanitized report.
- Evidence was not staged.
