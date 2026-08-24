# Monthly Investment Transfers QA

Дата/время: `2026-07-26 22:18-22:30 MSK`
Worker: `QA/build/documentation`
Scope: backend reports monthly investment transfers fix, Android summary investments mapping, local QA, manual-install APK, KB update.

## Business Rule

- `/reports/summary.investmentsTotal` must mean monthly investment transfers for the selected period/month: only visible incoming `transfer` operations into accounts/categories marked as investment assets.
- `/reports/summary.investmentsTotal` is not the total asset balance and must not be derived from `/reports/account-balances`.
- `/reports/account-balances` remains the asset/account balance endpoint.
- Android Analytics summary investments must read summary data only and must not fallback to account-balances for this metric.

## Test Matrix

| Area | Command | Result | Evidence |
|------|---------|--------|----------|
| Backend targeted reports/assets | `python -m pytest tests/reports tests/asset_categories` | PASS: `25 passed, 8 warnings` | `01-backend-targeted-reports-asset-categories.log` |
| Backend full | `python -m pytest` | PASS: `302 passed, 16 warnings` | `02-backend-full-pytest.log` |
| Android targeted | `.\gradlew.bat :app:testDebugUnitTest --tests com.finance.mvp.api.ApiClientDashboardTest --tests com.finance.mvp.ui.AppSectionTest` | PASS: `BUILD SUCCESSFUL in 7s` | `03-android-targeted-ApiClientDashboard-AppSection.log` |
| Android full unit | `.\gradlew.bat :app:testDebugUnitTest` | PASS: `BUILD SUCCESSFUL in 12s`; XML total `174 tests, 0 failures, 0 errors, 0 skipped` | `04-android-full-testDebugUnitTest.log`, `android-test-results-summary.txt` |
| Android Kotlin compile | `.\gradlew.bat :app:compileDebugKotlin` | PASS: `BUILD SUCCESSFUL in 1s` | `05-android-compileDebugKotlin.log` |
| Android release assemble | `.\gradlew.bat :app:assembleRelease -PfinanceApiBaseUrl=http://45.10.110.42/finance-api` | PASS: `BUILD SUCCESSFUL in 42s` | `06-android-assembleRelease-prod.log` |
| APK align/sign/verify | `zipalign`, `apksigner sign`, `apksigner verify --verbose --print-certs`, final `zipalign -c -p 4` | PASS: v2/v3 verified; final zipalign check exit `0` | `07-*`, `08-*`, `09-*`, `10-*` |
| APK URL scan | generated release `BuildConfig`, extracted APK binary scan | PASS: prod markers `45.10.110.42` and `finance-api` present in APK; local markers `localhost`, `10.0.2.2`, `127.0.0.1` absent | `11-release-BuildConfig.java`, `13-*`, `14-*`, `16-python-binary-url-scan.log` |
| APK metadata | `aapt dump badging` through ASCII temp path | PASS: package `com.finance.mvp`, version `0.1.0`, launchable `com.finance.mvp.MainActivity` | `20-aapt-badging-ascii-path.log` |
| Emulator/adb | PATH `adb`; SDK `platform-tools\adb.exe devices` | SKIPPED: `adb` not in PATH; SDK adb available but no attached devices/emulator; install/launch not run | `17-adb-devices.log`, `18-sdk-adb-devices.log` |

## APK

- Path: `C:\Users\style\Documents\Codex\Финансы\artifacts\apk\finance-android-prod-20260726-221828-MONTHLY-INVESTMENT-TRANSFERS-manual-install.apk`
- SHA256: `46e85ee4e5c6b4b13cf84abd4da22dcffc2642d0e9afd7d6be16f5c40783a9ca`
- Signing: Android Debug certificate for manual install; `apksigner verify` confirms APK Signature Scheme v2/v3.
- Prod API base: `http://45.10.110.42/finance-api`

## Deployment Boundary

- Backend production deploy is REQUIRED for production `/reports/summary.investmentsTotal` to use the new monthly incoming investment transfer semantics.
- This worker did not deploy backend/frontend to production, did not commit, did not push, and did not mutate production data.
- DB migration status was not exercised by this worker; local tests covered the behavior without prod data mutation.

## Risks / Caveats

- Device smoke was not run because no emulator/device was attached.
- Backend/Python warnings are deprecations; no test failure was observed.
- `aapt dump badging` fails when called directly on the repository path because the path contains Cyrillic characters; the same APK passes badging when copied to an ASCII temp path.
