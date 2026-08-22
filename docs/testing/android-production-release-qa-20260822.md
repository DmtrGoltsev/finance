# Android Production Release QA Model - 2026-08-22

## Scope

Release branch `prod/finance-personal-android-backend-20260822`, final Android
source `43f4b1780e3bdcf6891b877fe03ee53971f74500`.

## Required Cases

| ID | Priority | Scenario | Expected result |
| --- | --- | --- | --- |
| AUTH-REL-001 | P0 | Login, force-stop, relaunch | Session is restored without another login; password is not stored |
| AUTH-REL-002 | P0 | Expired access token with valid refresh | One refresh rotation occurs and the original request retries once |
| AUTH-REL-003 | P0 | Two clients refresh the same session concurrently | Single process-wide refresh; rotated session remains valid |
| AUTH-REL-004 | P0 | User A sync overlaps login as user B | A request is stopped; no A data is sent or stored under B |
| AUTH-REL-005 | P1 | Logout while backend is unavailable | Tokens, protected UI, local user data and user work are cleared |
| AUTH-REL-006 | P1 | Late logout A after login B | B session survives; stale A dashboard is not displayed |
| OCR-REL-001 | P1 | OCR upload receives 401 | One refresh and at most one upload retry; no offline queue entry |
| SYNC-REL-001 | P0 | Offline create, reconnect and sync | Pending mutation converges once and remains scoped to the authenticated user |
| INVEST-REL-001 | P0 | Incoming transfer to investment account in selected month | Selected-month investment total includes the transfer, not account balance |
| INVEST-REL-002 | P1 | Transfer outside selected month | Transfer is excluded from the selected-month total |
| OPS-REL-001 | P0 | Mixed dated operations and transfers | Items are ordered transaction date/time, createdAt and ID descending |
| CATEGORY-REL-001 | P1 | Open expense category selector | Vertical scrollable dialog opens; horizontal chip list is absent |
| CATEGORY-REL-002 | P1 | Type a word fragment | Only matching expense categories remain and selection works |
| ACCOUNT-REL-001 | P1 | Payment account appears after refresh | Valid selection is retained; new available payment account is selected immediately |
| DATE-REL-001 | P1 | Create transfer with a chosen date | Chosen date is sent online and retained in offline mutation |
| ANALYTICS-REL-001 | P1 | Open analytics on narrow viewport | Month is one line; previous/current/next controls do not overlap |
| APK-REL-001 | P0 | Inspect manual-install APK | Production URL only, non-debuggable, aligned, valid v2/v3 signature, no abnormal ZIP gaps |
| DEPLOY-REL-001 | P0 | Backend-only workflow dispatch | Backend deploy succeeds, frontend deploy is skipped, migrations remain disabled |

## 2026-08-22 Result

- Unit suite: `167/167` PASS; lint: `0` errors.
- APK binary, signature, alignment, URL and ZIP gates: PASS.
- Emulator production login/install and targeted scenarios: PASS.
- Full UI offline create/reconnect/sync was not rerun on the final APK.
- OCR real-image upload was not run; OCR remains online-only.
- Android 17 Espresso failed in framework setup because
  `InputManager.getInstance()` is unavailable; the instrumentation APK compiles.
- Production backend smoke: health/OpenAPI/login/refresh PASS.

Release evidence: `MVP_EVIDENCE/android-production-release-20260822/SUMMARY_SANITIZED.md`.
