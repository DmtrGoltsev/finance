# Offline-first release QA test cases

Дата актуализации: 2026-06-18

Роль документа: матрица ручного/full-cycle release QA после offline-first реализации. Документ не является отчетом о прогоне, не содержит секретов и не заменяет автоматизированные targeted gates из `docs/architecture/client-state-contracts.md`.

## Scope

Syncable release scope:

- transactions;
- accounts;
- categories;
- asset_categories;
- planning plans, income sources, allocations;
- atomic `investment_migrations:create` command.

Online-only forever:

- OCR/screenshot upload and screenshot OCR payloads;
- `copy_plan`;
- planning history mutation and target repair workflows;
- destructive conflict resolvers such as choose-server, choose-local, force overwrite.

Release execution order requirement:

1. Run full E2E on local Android emulator `emulator-5554`.
2. Only after local pass, run the same release E2E shape against production.
3. Do not store passwords, tokens, cookies, raw screenshots, raw OCR text, financial UUIDs, or production financial values in evidence.

Android APK selection:

- Local E2E must install `apps/android/app/build/outputs/apk/debug/app-debug.apk` built by `.\gradlew.bat :app:assembleDebug`; its default `BuildConfig.FINANCE_API_BASE_URL` is `http://10.0.2.2:8000`.
- If the local backend uses another host port, rebuild debug with `-PlocalFinanceApiBaseUrl=http://10.0.2.2:<port>`.
- Prod E2E must not reuse the local debug APK. Use an explicit production-config build, for example `.\gradlew.bat :app:assembleRelease -PfinanceApiBaseUrl=http://45.10.110.42/finance-api`, after local E2E passes and prod preflight is approved.

Recommended evidence root per run: `MVP_EVIDENCE/offline-first-release-qa-<YYYYMMDD-HHMMSS>/`.

## Existing QA documents found

| Path | Current use |
| --- | --- |
| `docs/testing/mvp-android-qa-test-cases.md` | Pre-offline-first Android QA cases for auth, dashboard, operations, capture, assets, categories, analytics, quick-add, and session restore. |
| `docs/testing/qa-endpoint-traceability.md` | Endpoint/security/privacy traceability and minimal MVP suites. Useful for authz, cache, transfer, and privacy gates. |
| `docs/architecture/client-state-contracts.md` | Source of truth for client state, offline/cache constraints, syncable and online-only boundaries, tombstones, and conflict UI MVP. |
| `qa/device-qa-android-iphone-checklist-2026-05-18.md` | Historical device checklist; still useful for login/logout, visibility, offline/background and evidence hygiene patterns. |
| `MVP_EVIDENCE/release-checklist.md` | Historical MVP release checklist; not updated by this document because offline-first release needs a fresh pass/fail checklist below. |

## Applicability legend

- `Local`: local backend/PWA plus Android emulator `emulator-5554`.
- `Prod`: production backend/PWA with approved QA account only.
- `Android`: Android app installed on `emulator-5554`.
- `PWA`: browser/PWA surface where applicable.
- `API`: API-level evidence from sanitized logs or targeted test output.

## Test case matrix

| ID | Platform | Preconditions | Steps | Expected | Evidence | Local/Prod | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OFF-AUTH-001 | Android, PWA, API | Fresh app/browser state, registered QA user exists; no stored session. | Open app, login with approved QA credentials, wait for dashboard/sync bootstrap. | Login succeeds; session is established; initial pull loads only visible data; no password/token appears in logs, screenshots, XML, localStorage dump, or evidence. | Sanitized screenshot after login, API status summary, secret scan result. | Local, Prod | P0 |
| OFF-AUTH-002 | Android, PWA, API | New test email available; registration enabled. | Register with valid email/password/display name; complete first session bootstrap. | Registration returns authenticated or accepted neutral flow per environment; if authenticated, dashboard loads with isolated empty/seeded QA data only. | Sanitized register flow notes, response status only, no password. | Local, Prod if registration allowed | P0 |
| OFF-AUTH-003 | Android, PWA | User is logged in and has local synced data. | Logout, press Back/Home/reopen app, relaunch process/browser tab. | Financial UI and local protected snapshots are wiped or inaccessible; login screen shown; old session cannot restore data. | Before/after screenshots with values redacted, local protected state check, secret scan. | Local, Prod | P0 |
| OFF-AUTH-004 | Android | User logged in; valid session stored in secure storage. | Force-stop app, relaunch while online, then while offline with last valid local state. | Online relaunch restores session and pulls; offline relaunch shows only current viewer's valid local data with offline state, not stale previous-user data. | Emulator command log, screenshots, sanitized app log. | Local, Prod | P0 |
| OFF-AUTH-005 | Android, PWA, API | User logged in; backend can revoke/expire session or QA can use invalid token state. | Expire/revoke session, refresh app/API, attempt sync push. | Client transitions to signed-out/session-expired; pending protected sync does not leak payload; retry requires login. | API 401 summary, UI screenshot, local queue status counts only. | Local, Prod | P0 |
| OFF-TXN-001 | Android, API | User logged in; visible account and compatible category exist. | Go offline, create expense with date, category, account, payment account where supported; return online and sync. | Transaction is visible locally as pending, then synced; date is preserved as selected date; account/category/payment account references remain correct. | Screenshots pending/synced, sanitized sync push/pull summary, created row id redacted. | Local, Prod | P0 |
| OFF-TXN-002 | Android, API | Synced income exists with visible account/category. | Go offline, edit amount/date/category/account/payment account/note; restart app; return online and sync. | Local edit survives restart, replays once, version aligns with server; no duplicate transaction. | Before/after screenshots, sync issue count, API list count redacted. | Local, Prod | P0 |
| OFF-TXN-003 | Android, API | Synced transaction exists. | Go offline, delete transaction; restart; verify it stays hidden; return online and sync; pull again. | Delete/tombstone prevents resurrection before and after pull; server no longer lists active transaction or returns neutral unavailable. | UI screenshot, sync push response status, pull result summary. | Local, Prod | P0 |
| OFF-TXN-004 | Android, API | Deleted/restorable transaction exists if restore is supported. | Restore transaction offline, sync online, refresh dashboard/reports. | Restored transaction returns with original date/scope references; reports update after pull; no hidden data appears. | Screenshots, sanitized report totals delta without raw amounts. | Local, Prod | P1 |
| OFF-TXN-005 | Android, API | Two same-scope accounts exist; transfer support available through transactions. | Offline create same-scope transfer; then try unsupported personal/shared or cross-user/cross-household combination if selector/API allows. | Same-scope transfer syncs atomically; unsupported scope is rejected neutrally and does not create partial rows. | Sync result, neutral error screenshot, DB/API count summary without ids. | Local, Prod | P0 |
| OFF-TXN-006 | Android, API | Transaction with existing server version loaded locally. | Create server-side conflicting edit, then replay stale offline update. | Conflict/rejection appears in sync issues; UI does not overwrite server silently and does not expose raw hidden payload. | Failed/rejected sheet screenshot, response status/error code only. | Local, Prod | P0 |
| OFF-ACC-001 | Android, API | Logged in; no network. | Create account offline with name, currency, asset category, payment-account flag, scope. Reconnect and sync. | Account appears locally pending, then synced; scope and payment flag preserved; account visible only to allowed viewer/scope. | Pending/synced screenshots, sanitized sync result. | Local, Prod | P0 |
| OFF-ACC-002 | Android, API | Synced account exists with linked transactions. | Offline edit name, asset category, payment-account flag; attempt unsupported currentBalance edit through sync if possible. | Supported fields sync; offline currentBalance mutation is rejected safely per contract; linked transactions remain intact. | UI screenshot, rejection summary, no balances in logs. | Local, Prod | P0 |
| OFF-ACC-003 | Android, API | Synced account exists. | Offline archive/delete account; restart; reconnect and sync; pull. | Account stays archived/deleted locally and after server pull; tombstone/state prevents resurrection; dependent UI remains stable. | Screenshots, sync/pull summary. | Local, Prod | P0 |
| OFF-ACC-004 | Android, API | Archived/deleted account is restorable in test data. | Restore offline, sync, refresh dashboard/account selectors. | Account returns to active selectors only after successful sync or approved local pending state; hidden/foreign accounts never appear. | Selector screenshots, sync result. | Local, Prod | P1 |
| OFF-CAT-001 | Android, API | Logged in; offline mode. | Create personal and household categories offline for income and expense. Reconnect and sync. | Categories sync with correct type/scope; selectors show only compatible visible categories. | Category list screenshots, sync summary. | Local, Prod | P0 |
| OFF-CAT-002 | Android, API | Synced category exists and is used by transaction. | Offline edit category name/icon/color if supported; create transaction referencing edited category; sync. | Edited category and transaction reference converge without duplicate category; transaction keeps compatible category. | Screenshots, sanitized API list summary. | Local, Prod | P1 |
| OFF-CAT-003 | Android, API | Synced category exists. | Offline archive/delete category; restart; sync; pull; try transaction create with archived/deleted category. | Category remains unavailable after pull; transaction form prevents or server rejects use neutrally. | Screenshots, rejection summary. | Local, Prod | P0 |
| OFF-ASSETCAT-001 | Android, PWA, API | Logged in; offline for Android; PWA checked online if no local-first support. | Create asset category with icon/color/order; sync Android; verify PWA after pull/refresh. | Asset category is synced and visible across supported clients; PWA does not claim offline mutation if not implemented. | Android screenshots, PWA screenshot if applicable, sync result. | Local, Prod | P0 |
| OFF-ASSETCAT-002 | Android, API | Synced asset category linked to account. | Offline edit/archive/restore/delete asset category; sync; refresh accounts/investment UI. | Lifecycle state converges; linked accounts show safe fallback or restored category; no broken investment totals. | Screenshots, sync summary, report/investment card redacted. | Local, Prod | P0 |
| OFF-PLAN-001 | Android, API | Logged in; offline; planning module enabled. | Create monthly personal plan offline with currency/month; add income source and allocation; restart before sync; reconnect. | Plan/income/allocation are local-first, survive restart, replay in dependency order, and align to server response. | Planning screenshots pending/synced, sync order summary. | Local, Prod | P0 |
| OFF-PLAN-002 | Android, API | Household active membership and shared planning allowed. | Create household plan offline; sync as active member; verify another active member if fixture allows. | Active household scope is respected; personal data of other member is not exposed; household plan visible to allowed member after pull. | Sanitized screenshots per actor, no values/ids. | Local, Prod with safe fixture | P0 |
| OFF-PLAN-003 | Android, API | Plan with income sources and allocations exists. | Offline update income source amount/source/day and allocation target/mode/value; sync. | Updates replay after parent plan is known; derived summary recalculates; no duplicate child rows. | Screenshots, sync result, summary delta redacted. | Local, Prod | P0 |
| OFF-PLAN-004 | Android, API | Plan with child rows exists. | Offline delete income source/allocation/plan; restart; pull before replay if possible; then sync. | Tombstones suppress resurrection between pull and replay; after sync, deleted rows do not reappear. | Before/restart/pull/sync screenshots, tombstone status counts. | Local, Prod | P0 |
| OFF-PLAN-005 | Android, API | Deleted planning row exists and restore is supported. | Restore plan/income/allocation offline; sync and pull. | Restore reactivates intended row only; stale tombstone is cleared/updated; no hidden or duplicate row appears. | Screenshots, sync summary. | Local, Prod | P1 |
| OFF-PLAN-006 | Android, PWA, API | Network unavailable; source plan exists. | Try `copy_plan` while offline; then run `copy_plan` online. | Offline `copy_plan` is blocked/not queued with clear online-only messaging; online copy uses server workflow and respects target attention rows. | Offline blocked screenshot, online success screenshot, pending queue shows no `copy_plan`. | Local, Prod | P0 |
| OFF-PLAN-007 | Android, API | Plan history and target repair surfaces reachable if exposed. | Attempt to mutate planning history or target repair offline. | No offline mutation is queued; UI blocks or API rejects as online-only/derived workflow. | Screenshot, pending queue status, response code. | Local, Prod | P1 |
| OFF-INV-001 | Android, API | Legacy/unlinked investment-like accounts exist; offline mode. | Start investment migration offline; inspect pending item; reconnect and sync. | Exactly one `investment_migrations:create` command is queued; not separate account/asset category mutations; backend applies atomically. | Pending mutation type screenshot/log, sync response summary. | Local, Prod with dedicated QA data | P0 |
| OFF-INV-002 | Android, API | Migration command pending; network flaky. | Interrupt sync mid-flight, retry failed command. | Retry uses same command/idempotency identity where available; command is applied once or safely reported already applied; no partial migration. | Failed then retry screenshots, server response status, no raw payload. | Local, Prod | P0 |
| OFF-INV-003 | Android, API | Conflicting server state: version/category/account mismatch. | Replay stale migration command. | Command is rejected atomically; conflict UI shows rejected issue with safe explanation; reports/accounts remain consistent. | Rejected sheet screenshot, account/category summary redacted. | Local, Prod with safe fixture | P0 |
| OFF-CONFLICT-001 | Android | At least one failed sync mutation can be induced by network/server unavailable. | Create offline mutation, force failed replay, open sync issue sheet. | Failed/rejected sheet is discoverable; failed item displays safe status and retry action; no raw request payload or secrets. | Sheet screenshot, sanitized logs. | Local, Prod | P0 |
| OFF-CONFLICT-002 | Android | Failed sync item exists and server is healthy again. | Tap retry for failed item; wait for pull/refresh. | Retry replays failed item and clears issue on success; dependent local UI updates from server response. | Before/after issue count, screenshot. | Local, Prod | P0 |
| OFF-CONFLICT-003 | Android | Rejected sync item exists from validation/authz conflict. | Open issue detail and look for resolver controls. | Rejected item has safe explanation and no destructive choose-server/choose-local/force overwrite controls. | Screenshot proving resolver absence, UX note. | Local, Prod | P0 |
| OFF-OCR-001 | Android, PWA, API | App offline; screenshot/capture entry point visible. | Try OCR/screenshot upload offline. | Operation is blocked or remains unsubmitted; no screenshot/raw OCR/OCR payload enters Room, pending queue, logs, or telemetry. | Offline UI screenshot, pending queue scan summary, log scan. | Local, Prod | P0 |
| OFF-OCR-002 | Android, PWA, API | Online; QA screenshot fixture is sanitized. | Run screenshot OCR online; confirm or discard draft. | OCR only runs online; transaction is created only after user confirm/edit; raw screenshot/raw OCR text are not persisted in evidence or offline queue. | Sanitized flow screenshots, storage/log scan summary. | Local, Prod if approved | P0 |
| OFF-OCR-003 | Android, PWA | OCR draft exists or OCR failed. | Logout and relaunch; inspect capture/draft UI and local state. | Draft visibility follows authenticated API/local safe state; raw OCR/screenshot data is not recoverable after logout. | Logout/relaunch screenshot, secret/raw payload scan. | Local, Prod | P0 |
| OFF-NET-001 | Android | User logged in; local data loaded. | Toggle offline/online multiple times during create/edit/delete sync. | UI clearly shows pending/offline/failed states; no duplicate submissions; final state converges after stable online. | Timeline notes, screenshots, sync counts. | Local, Prod | P0 |
| OFF-NET-002 | Android | Pending mutations across multiple entity types exist. | Restart app while offline, verify pending state; reconnect and sync. | Queue survives restart for syncable operations only; dependency order preserves parent/child planning and referenced account/category rules. | Queue count by entity type, screenshots. | Local, Prod | P0 |
| OFF-NET-003 | Android | User A has local synced data. | Logout, login as different QA user on same emulator, inspect all screens and offline state. | User B sees only B data; A snapshots/queue are wiped or inaccessible; no PWA/Android cache bleed. | Screenshots per user with redaction, local storage/DB scope check. | Local, Prod with isolated QA users | P0 |
| OFF-NET-004 | Android, API | Shared household membership can be revoked/left in fixture. | Load shared data, go offline, revoke/leave membership server-side, relaunch/refresh online. | Shared offline snapshots are invalidated after membership/access version refresh; former user cannot keep shared data. | Before/after screenshots, neutral denial status. | Local, Prod with safe fixture/waiver | P0 |
| OFF-PWA-001 | PWA | PWA served from local/prod URL; browser cache can be inspected. | Load app, login/logout, refresh, hard reload, check service worker/cache behavior. | PWA does not cache authenticated API responses as public assets; logout clears protected UI; HTTP/IP limitation is recorded if service worker install is unavailable. | Browser devtools notes, screenshots, cache inventory summary. | Local, Prod | P1 |
| OFF-PWA-002 | PWA | PWA online; Android has synced offline-first changes. | Refresh PWA after Android sync for transactions/accounts/categories/asset categories/planning. | PWA reflects server state for shared backend entities and does not show local-only pending Android rows before sync. | PWA screenshots, Android sync completion evidence. | Local, Prod | P1 |
| OFF-PWA-003 | PWA | PWA offline or network blocked. | Try transactions/accounts/categories/planning mutations in PWA. | PWA either supports only its implemented safe online path or blocks offline mutation without queuing unsupported workflow; no false success. | Screenshot, network/offline note. | Local, Prod | P1 |
| OFF-PROD-001 | Android, PWA, API | Production QA account prepared out-of-band; no secrets in repo/evidence. | Login to prod, create unique QA-tagged data across syncable domains, sync, verify visibility, then record cleanup decision. | Prod data is isolated to QA account/household; no other user data visible; cleanup/retention is explicitly tracked without storing secrets. | Sanitized prod report, data labels redacted, cleanup decision row. | Prod | P0 |
| OFF-PROD-002 | Android, PWA, API | Two prod QA accounts/households available or approved waiver. | Cross-check direct ids/search/autocomplete/report filters using own and other QA fixture data. | Missing/inaccessible resources return neutral responses; no hidden counts, names, amounts, or membership hints. | API status matrix, UI screenshots redacted. | Prod | P0 |
| OFF-PROD-003 | Android, API | Local E2E on `emulator-5554` has passed. | Install/prod-config app on `emulator-5554`, run auth/session, syncable CRUD, conflict, OCR online-only smoke. | Prod run uses production API/PWA only after local pass; no deploy occurs; evidence is sanitized and secret-free. | Release QA checklist rows completed with evidence links. | Prod | P0 |

## Release QA checklist and pass/fail tracking template

Copy this table into the release report for each execution. Keep secrets out of the report; use only out-of-band credential locations when needed.

| Gate ID | Gate | Required result | Local status | Local evidence | Prod status | Prod evidence | Owner | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RQA-00 | Preflight hygiene | Git SHA/build id captured; no deploy/full E2E already running in another worker; evidence root created. | Not run |  | Not run |  | QA lead |  |
| RQA-01 | Secret handling | No passwords/tokens/cookies/raw screenshots/raw OCR/production values stored in docs, logs, screenshots, XML, reports. | Not run |  | Not run |  | QA lead |  |
| RQA-02 | Local first | Full local E2E on Android `emulator-5554` completes before production E2E starts. | Not run |  | N/A |  | QA lead |  |
| RQA-03 | Auth/session | Register/login/logout/session restore/session expiry/logout wipe pass. | Not run |  | Not run |  | QA lead |  |
| RQA-04 | Transactions | Offline/local-first CRUD, date/category/account/payment account, transfer scope, restart, sync and conflict pass. | Not run |  | Not run |  | QA lead |  |
| RQA-05 | Accounts | Offline/local-first create/update/archive/delete/restore, payment-account flag and visibility pass. | Not run |  | Not run |  | QA lead |  |
| RQA-06 | Categories | Offline/local-first category CRUD, type/scope compatibility and tombstone/restore behavior pass. | Not run |  | Not run |  | QA lead |  |
| RQA-07 | Asset categories | Offline/local-first asset category CRUD and account/investment UI convergence pass. | Not run |  | Not run |  | QA lead |  |
| RQA-08 | Planning | Plans/income sources/allocations local-first CRUD, tombstones, restart and pull/replay convergence pass. | Not run |  | Not run |  | QA lead |  |
| RQA-09 | Planning online-only | `copy_plan`, planning history mutation and target repair are blocked offline and not queued. | Not run |  | Not run |  | QA lead |  |
| RQA-10 | Investment migration | `investment_migrations:create` is queued as one atomic command; retry/conflict behavior is safe. | Not run |  | Not run |  | QA lead |  |
| RQA-11 | Conflict UI MVP | Failed/rejected sheet exists; retry works for failed; rejected has no destructive resolver. | Not run |  | Not run |  | QA lead |  |
| RQA-12 | OCR/screenshot online-only | Offline OCR/screenshot is not queued; online OCR stores no raw screenshot/OCR payload locally/evidence-side. | Not run |  | Not run |  | QA lead |  |
| RQA-13 | Offline/online transitions | Network toggles, app restart, force-stop, session restore and queue replay converge without duplicates. | Not run |  | Not run |  | QA lead |  |
| RQA-14 | Logout/account switch wipe | Logout and different-user login clear protected local state, back stack, PWA cache and pending data. | Not run |  | Not run |  | QA lead |  |
| RQA-15 | PWA regression | PWA remains online-functional, reflects synced backend state, and does not publicly cache authenticated API responses. | Not run |  | Not run |  | QA lead |  |
| RQA-16 | Prod account isolation | Prod QA data remains isolated; cross-account/household probes are neutral; cleanup/retention decision recorded. | N/A |  | Not run |  | QA lead |  |
| RQA-17 | Evidence closure | All P0 rows have PASS or explicit approved waiver; P1 failures have owner/risk decision; screenshots/logs sanitized. | Not run |  | Not run |  | QA lead |  |

Status values: `PASS`, `FAIL`, `BLOCKED`, `WAIVED`, `N/A`, `Not run`.

Release must remain blocked if any P0 gate is `FAIL` or `BLOCKED` without an explicit owner-approved waiver.

## Remaining evidence gaps before release sign-off

- This document defines test cases only; it does not provide execution evidence.
- Local E2E on Android `emulator-5554` remains required before production E2E.
- Production E2E must use approved QA credentials without storing secrets.
- PWA offline mutation behavior is listed as regression/compatibility coverage because the offline-first implementation scope is Android/backend sync; any PWA offline-first claim needs separate implementation evidence.
- Membership revoke/leave and multi-account production isolation require safe fixtures or explicit waiver if production fixture setup is not approved.
