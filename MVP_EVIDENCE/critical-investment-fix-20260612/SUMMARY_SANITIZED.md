# Critical Investment Fix Closure

Status: PASS
Date: 2026-06-12
Scope: Android critical regression `Брокер -> Инвестиция -> Сохранить`

## Root Cause

Android sent `iconKey` in `POST /api/v1/asset-categories`, while the deployed OpenAPI contract for `AssetCategoryCreateRequest` is strict with `additionalProperties=false`. Backend validation failed before create/link, so marking a broker group as investment could not complete.

## Fix Summary

- Create asset-category payload no longer includes `iconKey`.
- The investment conversion/link flow was verified through Android unit/build gates and live emulator QA.
- The project commit is pending; do not record a commit hash until git-agent creates it.

## Project Files Expected In Closure

- `apps/android/app/src/main/java/com/finance/mvp/ui/FinanceApp.kt`
- `apps/android/app/src/test/java/com/finance/mvp/ui/AppSectionTest.kt`
- `apps/android/app/src/main/java/com/finance/mvp/api/ApiClient.kt`
- `apps/android/app/src/test/java/com/finance/mvp/api/ApiClientPlanningAllocationTest.kt`

## Build And Unit Evidence

- `compileDebugKotlin`: PASS, exit 0.
- `testDebugUnitTest`: PASS, 71 tests, exit 0.
- `assembleDebug`: PASS, exit 0.

## APK Artifact

- Source APK: `apps/android/app/build/outputs/apk/debug/app-debug.apk`
- Release artifact: `artifacts/apk/finance-mvp-newd-0.1.0-debug.apk`
- SHA256: `B6960DB5D13198405984C027746343432CB95B0C08BB24F54D6A7FCD5061DCC7`
- Size: `54235740` bytes
- Signing: debug-signed, not release-signed

## QA Evidence

- Quick critical-path QA: `MVP_EVIDENCE/critical-investment-qa-quick-20260612-013822/QA_REPORT_SANITIZED.md`
- Harness QA: `MVP_EVIDENCE/critical-investment-qa-harness-20260612-015225/HARNESS_REPORT_SANITIZED.md`

Quick QA result:

- Status: PASS.
- Live serial: `emulator-5556`.
- APK SHA256 matched expected.
- After save and restart, linked asset category id is present.
- `linkedAssetCategory.isInvestment=True`.
- `investmentCategories.count=1`.
- Totals: `150000.0000 RUB`.
- No `Validation failed` evidence in the PASS run.
- Secret scan: PASS; no raw auth credential evidence stored.

Harness result:

- Status: PASS.
- Live serial: `emulator-5556`.
- Device selection, APK hash verification, install, launch and bounded UI probe passed.
- The harness specifically guards against the earlier stale-serial/non-return failure mode.

## Known Caveats

- APK is debug-signed, not release-signed.
- This closure does not claim a backend deploy; the fix is Android payload compatibility with the deployed strict OpenAPI contract.
- Previous evidence folders `critical-investment-qa-20260612-003254` and `critical-investment-qa-20260612-010747` are historical failed/incomplete context only, not final PASS evidence.
- No secrets, raw auth headers or raw request payloads are included in this summary.

## Curated Staging Recommendation

Stage this summary, the final APK artifact, the four Android modified files listed above, and the relevant KB notes updated for this closure. Do not stage `rules.md`, unrelated old evidence, or failed/incomplete evidence folders as green proof.
