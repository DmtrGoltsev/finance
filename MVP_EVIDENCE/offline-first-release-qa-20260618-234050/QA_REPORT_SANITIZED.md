# Offline-first release local QA sanitized report

Date: 2026-06-18
Target: local Android emulator emulator-5554 + local backend 127.0.0.1:8000 / 10.0.2.2:8000
Result: PASS

## Preflight
- APK: apps/android/app/build/outputs/apk/debug/app-debug.apk
- SHA256: 6198C11414630C5602C7AB255B7611412EFB2BBCC20F0E60E420EF3DF29CBC83
- BuildConfig.FINANCE_API_BASE_URL: http://10.0.2.2:8000
- Emulator: emulator-5554 device
- Backend health: PASS, local dev seed app on 127.0.0.1:8000
- Prod endpoint check: PASS, no 45.10.110.42 or /finance-api hits in sanitized log scan

## Device/UI evidence
- Auth/login: PASS. Seed login API works; UI login passed with a safe local user. Password not recorded.
- Session restore: PASS. Force-stop/relaunch restored authenticated dashboard before logout.
- Offline/online transition: PASS smoke. Offline refresh and online refresh screenshots captured; no prod endpoint observed.
- Logout wipe/back-stack: PASS. After logout + force-stop/relaunch, login screen shown and old session not restored.
- Navigation/basic regression: PASS smoke. Dashboard and bottom nav present; sync/logout/FAB visible while authenticated.

## API and local-first coverage
- Accounts CRUD/payment flag: PASS via local API smoke.
- Categories CRUD: PASS via local API smoke.
- Asset categories CRUD: PASS via local API smoke.
- Transactions create/update/delete/restore with date/category/account/payment account: PASS via local API smoke.
- Planning create/update/delete/copy_plan online: PASS via seeded planning API smoke.
- Investment migration command online atomic path: PASS via seeded API smoke.
- OCR/screenshot online-only: PASS via backend capture tests and sync rejection smoke.
- Sync tombstones/offline queue/conflict primitives: PASS via Android unit gates + backend sync/tombstone tests.

## Automated gates
- Android debug URL/sync/planning/local DB/capture targeted unit gates: PASS (Gradle BUILD SUCCESSFUL).
- Backend targeted offline-first/API gates: PASS after correct OCR rerun; 142 selected tests passed before OCR fixture rerun, OCR/capture suite 26 passed.

## Notes
- A first planning smoke against the newly registered local user hit 404 because app.dev_seed wires planning to a separate seeded planning DB. The same planning flow passed with the documented seed actor. Treated as harness/runtime split, not product bug.
- Conflict UI destructive resolver absence was covered by sync/UI unit tests and backend rejection paths; no destructive choose-server/choose-local/force-overwrite controls were exercised manually.
- No prod deploy and no prod endpoint use.

## Bugs/blockers
- Product blockers: none found in local scope.
- Harness caveat: live dev_seed planning data is actor-specific to the seed surface; fresh registered users are suitable for auth/API CRUD but not for seeded planning target coverage.

## Readiness
Local gates are green enough to proceed to prod preflight resolution, subject to approved prod QA credentials and production-config APK only.
