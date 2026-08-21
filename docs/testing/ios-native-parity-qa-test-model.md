# Native iOS parity QA test model

Дата: 2026-06-19
Статус: тестовая модель и release-gate контракт для native iOS parity. Это не отчет о прогоне и не доказательство прохождения тестов.

## Scope и native-only инвариант

Целевой клиент: native SwiftUI приложение `apps/ios/FinanceApp`, собираемое из `apps/ios/project.yml`.

В scope входят:

- Swift/SwiftUI native UI, `URLSession`, `Security`/Keychain, `PhotosUI/PhotosPicker`, Foundation local persistence and sync layers;
- Android parity для текущего finance MVP: auth, операции, capture/OCR, assets, analytics, planning, offline-first/sync, privacy/security guards;
- проверка соответствия canonical API/DTO из `api/openapi/openapi.yaml` и iOS моделей/клиента;
- Windows-verifiable статические проверки сейчас и Mac/Xcode manual gates позже.

Не входит и не может считаться parity:

- PWA, Capacitor, WebView/WKWebView wrapper;
- переиспользование `apps/web-pwa/ios/App/**` как iOS parity target;
- сохранение raw screenshots, raw OCR text, cookies, CSRF, passwords, production financial values или raw API logs в evidence.

Любой найденный `WKWebView`, `WebView`, `Capacitor`, импорт web-wrapper target или зависимость `apps/web-pwa/ios/App` в native target является P0 release blocker.

## Источники проверки

| Источник | Назначение |
| --- | --- |
| `apps/ios/project.yml` | XcodeGen/project settings, iOS target, build settings, `FINANCE_API_BASE_URL`. |
| `apps/ios/FinanceApp/Info.plist` | bundle metadata, ATS, photo permission, base URL plist injection. |
| `apps/ios/FinanceApp/**/*.swift` | native UI, API client, DTO, Keychain, OCR, local store, sync model. |
| `api/openapi/openapi.yaml` | canonical API paths, DTO field names, enums, sync/capture/report contracts. |
| `apps/android/**` | Android parity behavior and existing release expectations. |
| `docs/testing/mvp-android-qa-test-cases.md` | Android feature regression baseline. |
| `docs/testing/offline-first-release-qa-test-cases.md` | Offline-first syncable/online-only release baseline. |
| `docs/architecture/client-state-contracts.md` | client state, offline, conflict and cache invariants. |
| `docs/compliance/privacy-baseline.md` | privacy constraints for capture/OCR and local/client evidence. |
| `docs/ios-native-parity-plan.md` | native parity implementation map and known gaps. |

Текущий Windows inventory в рабочем дереве показывает native SwiftUI target, `Info.plist`/`project.yml`, `AppEnvironment`, `PhotosPicker`, `FinanceApiClient.syncPush/syncPull`, `FinanceLocalStore`, `FinanceSyncService` и `SyncQueuePolicy`. Это только статический факт наличия поверхностей, а не build/test pass.

## Приоритеты и типы gates

| Метка | Значение |
| --- | --- |
| P0 | Release blocker. Без PASS или явно утвержденного waiver релиз native iOS заблокирован. |
| P1 | High risk. Нужен PASS до публичного TestFlight, waiver допустим только с owner/date. |
| P2 | Regression/quality. Нужен tracking, но не блокирует emergency internal build. |
| W | Windows-verifiable: статический source/docs/API/evidence hygiene gate без Mac/Xcode. |
| M | Mac/Xcode-required: build, simulator, real device, Keychain/cookie, PhotosPicker, offline/restart, signing. |
| A | Automatable later через Swift unit/UI tests. |
| R | Manual release gate. |

## Windows-verifiable checks

Эти checks можно выполнять сейчас на Windows. В evidence сохранять только sanitized summary: command, exit code, counts/status, commit/worktree id, короткий вывод без secrets и без raw payloads.

| Gate ID | Priority | Проверка | Команды/метод | Expected |
| --- | --- | --- | --- | --- |
| W-IOS-001 | P0 | Native target exists, no wrapper shortcut | `rg --files apps/ios/FinanceApp`; `rg -n "WKWebView|WebView|Capacitor|apps/web-pwa|SFSafariViewController" apps/ios/FinanceApp apps/ios/project.yml` | Swift files есть; wrapper/WebView references отсутствуют или явно не используются в target. |
| W-IOS-002 | P0 | `project.yml` sanity | Inspect `apps/ios/project.yml` | `platform: iOS`, app target `FinanceApp`, iOS 17.0, Swift 5.9, `INFOPLIST_FILE`, bundle id, no web-wrapper source path. |
| W-IOS-003 | P0 | `Info.plist` sanity | Inspect `apps/ios/FinanceApp/Info.plist` | `FINANCE_API_BASE_URL` injected; `NSPhotoLibraryUsageDescription` exists; ATS does not allow arbitrary loads; `NSAllowsLocalNetworking`/`127.0.0.1` HTTP exception is documented as debug/local only. |
| W-IOS-004 | P0 | Config/base URL guard | `rg -n "FINANCE_API_BASE_URL|http://|https://|finance-api" apps/ios` | Debug/prod URLs are centralized in config; Release without `FINANCE_RELEASE_API_BASE_URL` fails visibly; no accidental local URL in Release; no production HTTP/IP exception without explicit owner waiver and App Store risk note. |
| W-IOS-005 | P0 | OpenAPI path parity | Compare `api/openapi/openapi.yaml` paths with `FinanceApiClient` methods and `LiveApiClient` URLs | Sessions, accounts, categories, transactions, capture-drafts/OCR, reports, planning, sync push/pull are mapped; no unsupported standalone transfer or import/bank/SMS routes. |
| W-IOS-006 | P0 | DTO field parity | `rg -n "transactionDate|isPaymentAccount|occurredDate|captureSource|evidenceHash|iconKey|isInvestment|planning_plans|syncPush|syncPull" apps/ios/FinanceApp api/openapi/openapi.yaml` | iOS DTOs preserve canonical field names, date-only fields, flags, capture fields, sync entity names and report/planning enums. |
| W-IOS-007 | P0 | Sync model inspection | `rg -n "FinanceLocalStore|PendingMutation|SyncQueuePolicy|OnlineOnlySyncOperation|tombstone|retry|rejected|editOrDiscardOnly" apps/ios/FinanceApp` | Syncable domains and online-only domains match offline-first contract; no OCR/capture payload queue; conflicts become issues, not destructive overwrite. |
| W-IOS-008 | P0 | Logout/local wipe surface | `rg -n "logout|wipeProtectedState|wipeAllProtectedData|wipeCurrentUser|Keychain|HTTPCookieStorage|CSRF" apps/ios/FinanceApp` | Logout clears API auth state and visible protected UI; local protected store wipe path exists and is wired before release. |
| W-IOS-009 | P0 | Capture/OCR privacy | `rg -n "PhotosPicker|screenshotOcr|loadTransferable|raw OCR|OCR|CategoryAggregateMappingStore|SHA256" apps/ios/FinanceApp docs` | PhotosPicker upload is user-initiated; raw image/OCR is not stored; category mapping uses hash/keyed storage, not raw external label persistence. |
| W-IOS-010 | P0 | Secrets/artifacts scan | Use file-list/count mode, not value dump: `rg -l "BEGIN PRIVATE KEY|AKIA|xox[baprs]-|ghp_|sk-|csrf|cookie|password|token" docs apps/ios artifacts MVP_EVIDENCE` then manually classify false positives without copying values | No secrets/raw credentials/raw logs in docs or evidence. If a real secret is suspected, stop and escalate; do not paste match text into report. |
| W-IOS-011 | P1 | Doc evidence consistency | Inspect this doc, `docs/ios-native-parity-plan.md`, Android/offline QA docs | Test scope, blocked Mac items, evidence rules and parity matrix stay aligned; stale gaps are marked as historical, not release truth. |
| W-IOS-012 | P1 | Project artifact hygiene | `rg --files apps/ios docs/testing artifacts MVP_EVIDENCE` plus targeted scan of newly added evidence folders | No raw screenshots, raw OCR text, production financial exports, `.xcresult` bundles with secrets, or private signing assets committed. |

## Manual Mac/Xcode future gates

Эти gates заблокированы сейчас из-за отсутствия Mac/Xcode. Они обязательны перед native iOS release sign-off.

| Gate ID | Priority | Gate | Required checks | Required evidence |
| --- | --- | --- | --- | --- |
| M-IOS-001 | P0 | Native build | Generate/open project from `apps/ios/project.yml`; run clean build for Debug and Release-like config. | Sanitized `xcodebuild` summary, target/config, git SHA/worktree note. |
| M-IOS-002 | P0 | Simulator smoke | Launch on current iPhone simulator; login/register/session restore; navigate all tabs; no crash. | Sanitized screenshots, simulator/iOS version, test notes. |
| M-IOS-003 | P0 | Real device smoke | Install on real iPhone; verify launch, auth, tab navigation, photo permission prompt and network behavior. | Device/iOS version, sanitized screenshots, no device identifiers in public report. |
| M-IOS-004 | P0 | Keychain/cookie/CSRF | Login stores CSRF/session metadata safely; state-changing requests send CSRF; logout/session expiry clears Keychain/cookies and protected UI. | Unit/UI test output or sanitized Charles/proxy summary without token/cookie values. |
| M-IOS-005 | P0 | PhotosPicker/OCR upload | User selects sanitized fixture screenshot; upload happens only online; candidates become editable drafts; confirm creates transaction only after review. | Redacted flow screenshots; storage/log scan summary proving no raw image/OCR persistence. |
| M-IOS-006 | P0 | Offline airplane mode | Toggle Airplane Mode: syncable CRUD works locally where supported; online-only OCR/copy/history repair blocked; UI shows safe pending/offline states. | Screenshots, pending queue counts by entity type, no raw payload. |
| M-IOS-007 | P0 | Local persistence across restart | Create/edit/delete syncable records offline, terminate app, relaunch offline, then reconnect and sync. | Before/restart/after screenshots, sync summary counts, no duplicate rows. |
| M-IOS-008 | P0 | Sync retry/conflicts | Induce retryable network failure and stale-version rejection; retry allowed for failed, rejected requires edit/discard only. | Issue UI screenshots, sanitized response status/error code, absence of force overwrite controls. |
| M-IOS-009 | P0 | Logout/account switch wipe | User A syncs data, logout, login User B, relaunch offline/online. | Evidence that User A local data/queue is wiped or inaccessible; no cross-user bleed. |
| M-IOS-010 | P0 | TestFlight/App Store signing | Archive/export with intended team/profile; validate bundle id, entitlements, ATS, privacy strings, release base URL. Confirm local HTTP ATS exception is not used for production traffic and no non-local production HTTP exception was added. | Archive/export summary, signing identity/profile names redacted if needed, App Store Connect/TestFlight status. |
| M-IOS-011 | P1 | Accessibility/layout | VoiceOver labels for icon-only nav/actions, Dynamic Type, portrait/iPad allowed orientations, long Russian strings. | Simulator/device screenshots and accessibility inspector notes. |

## Feature test matrix

| ID | Feature | Priority | Windows-verifiable coverage now | Mac/Xcode/manual coverage later | Pass expectation |
| --- | --- | --- | --- | --- | --- |
| IOS-AUTH-001 | Login/session status | P0 | API methods `login`, `sessionStatus`; cookie/CSRF code inspection; OpenAPI parity. | Login on simulator/device; relaunch with valid session. | Authenticated user lands in native dashboard; no password/token in logs/evidence. |
| IOS-AUTH-002 | Registration | P0 | `register` DTO and UI validation inspection; password min length and accepted/authenticated branches. | Register fresh QA account or mocked backend. | `authenticated` loads app; `accepted` stays safe and does not fake session. |
| IOS-AUTH-003 | Logout wipe | P0 | `logout`, `wipeProtectedState`, Keychain/cookie/local-store wipe paths inspected. | Tap logout, relaunch, back navigation, account switch, offline relaunch. | Auth gate shown; protected UI/memory/local data/queue not accessible. |
| IOS-TXN-001 | Manual expense/income date-only | P0 | `transactionDate` present in `QuickAddDraft` and `TransactionCreateRequest`. | Create transactions with past/future date; inspect display and API payload via test double. | Selected `yyyy-MM-dd` survives save/reload; `sourceType=manual`. |
| IOS-TXN-002 | Manual transfer same-scope | P0 | Transfer picker filters by same currency/ownership; OpenAPI transfer scope inspected. | Try same-scope, cross-currency, cross-scope, same-account cases. | Supported transfer succeeds; unsupported combinations blocked before API or rejected safely. |
| IOS-PAY-001 | Payment account filter | P0 | `isPaymentAccount` in Account DTO/create/update; expense picker filters payment accounts. | Create/edit account flag; expense selector; income/transfer selectors. | Non-payment accounts are absent for expenses and flag persists after edit/sync. |
| IOS-CAP-001 | OCR online-only | P0 | `PhotosPicker` calls `screenshotOcr` directly; `OnlineOnlySyncOperation.screenshotOCR/captureUpload/captureDraft` blocked from queue. | Airplane Mode OCR attempt; online OCR with sanitized image. | OCR/capture upload is not queued offline and raw image/OCR payload is not persisted. |
| IOS-CAP-002 | OCR edit amount/date before confirm | P0 | `CaptureDraftUpdateRequest` includes `occurredDate`, `amount`, `accountId`, `categoryId`; confirm path inspected. | Edit draft amount/date/account/category then confirm; discard path. | Transaction is created only after confirm; edited values are used; discard creates nothing. |
| IOS-CAP-003 | Category mapping privacy | P0 | `CategoryAggregateMappingStore` hashing inspection; no raw label evidence. | Repeat OCR aggregate mapping across app restarts. | Mapping works without storing raw external labels in readable persistence/evidence. |
| IOS-ASSET-001 | Accounts/assets CRUD | P0 | API methods and SwiftUI asset/account sheets inspected. | Create/edit/archive/delete/restore where UI supports; sync/reload. | Scope, currency, balances, links and lifecycle state round-trip safely. |
| IOS-ASSET-002 | Investments/icon preservation | P0 | `iconKey`, `isInvestment`, `investment_migrations` and planning investment target fields inspected. | Create/edit asset category icon/investment flag; sync; analytics/planning reflect it. | Icon key and investment flag survive update, sync, restart and report display. |
| IOS-AN-001 | Analytics month | P0 | `ReportMonthSwitcher` and report start/end calls inspected. | Switch months with fixture data across boundaries/timezones. | Summary/category/balances use selected month, not current dashboard fallback. |
| IOS-AN-002 | Analytics category | P0 | `ReportCategoryBreakdown` is passed into `CategoryBreakdownCard`; fallback path inspected. | Fixture with category outside dashboard page. | Full report API category breakdown renders; no page-truncated local aggregation. |
| IOS-AN-003 | Analytics investments | P1 | `accountBalances.investmentsByCurrency`, dashboard fallback and investment cards inspected. | Fixture with multi-currency investment asset categories. | Investment totals match report/account-balances for selected mode/month/currency. |
| IOS-PLAN-001 | Planning UI online parity | P0 | Planning API methods and SwiftUI planning cards inspected. | Create plan, income, allocations, confirm income, delete children, copy history. | Online planning flows match Android rules and report safe errors. |
| IOS-PLAN-002 | Planning target/savings rules | P1 | Allocation target filters and `investment_asset_category` fields inspected. | Duplicate target, non-investment savings goal, overview read-only cases. | Duplicate/invalid targets are blocked; savings goals only for investment targets. |
| IOS-NAV-001 | Bottom nav icon-only | P1 | `TabView.tabItem` image/accessibility label inspection. | Simulator/device visual check and VoiceOver labels. | Bottom nav presents icon-only visual tabs where iOS permits, with accessible labels. |
| IOS-OFF-001 | Offline local DB/snapshot | P0 | `FinanceLocalStore`, schema version, scoped snapshot, pending mutations, tombstones inspected. | Offline CRUD, app restart, reconnect sync. | Syncable domains persist and converge without duplicate/resurrection. |
| IOS-OFF-002 | Sync issues/retry/conflicts | P0 | `SyncIssue`, `retryAllowed`, `editOrDiscardOnly`, `SyncSafeMessage` inspected. | Network failure and stale-version conflict. | Failed items can retry; rejected items do not offer destructive overwrite. |
| IOS-OFF-003 | Online-only exclusions | P0 | `SyncQueuePolicy.onlineOnlyReason` inspected for OCR/copy/history/target repair. | Offline attempts for OCR, `copy_plan`, history mutation, target repair. | No pending mutation is created; user sees safe online-only explanation. |
| IOS-CONFIG-001 | Config/base URL guard | P0 | `AppEnvironment`, `project.yml`, `Info.plist` inspected; grep for URLs. | Debug/release scheme build and runtime endpoint smoke. | Debug uses explicit local/dev endpoint; release cannot accidentally use local URL; missing `FINANCE_RELEASE_API_BASE_URL` shows a config error; HTTP/IP release endpoint has approved risk decision. |

## Negative/security/privacy cases

| ID | Priority | Case | Expected |
| --- | --- | --- | --- |
| IOS-NEG-001 | P0 | Raw screenshot selected through PhotosPicker | Raw image bytes are used transiently for upload only; no file, local snapshot, pending mutation, log, report or evidence copy contains raw screenshot. |
| IOS-NEG-002 | P0 | Raw OCR text/category label | Raw OCR text is not persisted; external labels are transient or hashed/keyed; evidence uses sanitized fixture labels only. |
| IOS-NEG-003 | P0 | Secrets in repo/evidence | Passwords, cookies, CSRF, session ids, private keys, signing credentials and production tokens are never committed or pasted in reports. |
| IOS-NEG-004 | P0 | Destructive conflict resolution | Conflict UI must not offer choose-server, choose-local, force overwrite, or silent last-write-wins for rejected mutations. |
| IOS-NEG-005 | P0 | Cross-user/account bleed | User B must not see User A local snapshots, pending mutations, capture mappings or dashboard after logout/account switch. |
| IOS-NEG-006 | P0 | Hidden data leakage | Reports, search, autocomplete and sync issues must not expose hidden counts, owner hints, raw payloads, stack traces, SQL, ids of inaccessible records, or amounts from other users. |
| IOS-NEG-007 | P0 | Release wrong-environment URL | Release/TestFlight build must not point at localhost/debug endpoint; debug build must not silently point at production without explicit override. |
| IOS-NEG-008 | P1 | Evidence over-capture | Screenshots/logs must not include real personal finance values, raw API bodies, device identifiers, Apple account details or signing secrets. |

## Definition of QA evidence

Evidence is acceptable only if it is reproducible, sanitized and tied to a precise build/worktree state.

Required metadata for every run:

- date/time and timezone;
- git commit SHA plus dirty-worktree note if applicable;
- app target/config, simulator/device model and iOS version when Mac is available;
- backend environment label only, never credentials;
- QA fixture name or synthetic data label, never production personal values;
- PASS/FAIL/BLOCKED/WAIVED per gate with owner/date for any waiver.

Windows evidence may include:

- static grep command names and pass/fail/count summaries;
- selected file paths and line references for code ownership, without raw secrets;
- OpenAPI/DTO parity checklist;
- sync model inspection summary;
- docs/evidence hygiene scan summary.

Mac/Xcode evidence may include:

- sanitized `xcodebuild`/test result summary, not full raw logs if they include env values;
- redacted simulator/device screenshots;
- storage verification by key/file names and counts only, not stored values;
- sync push/pull result counts/status/error codes only, not raw payloads;
- TestFlight/App Store signing status without private key/profile secrets.

Evidence must not include:

- passwords, tokens, cookies, CSRF values, private keys, signing certificates, provisioning profile contents;
- raw screenshots used for OCR or raw OCR text;
- full API request/response bodies from finance data;
- production financial UUIDs, balances, names, merchant labels or household/member identifiers;
- raw device backups, `.xcresult` bundles or logs unless reviewed and redacted.

Recommended evidence root for future run:

```text
MVP_EVIDENCE/ios-native-parity-qa-<YYYYMMDD-HHMMSS>/
```

Minimum files for a future release run:

- `QA_REPORT_SANITIZED.md` with gate table and blockers;
- `WINDOWS_STATIC_CHECKS_SANITIZED.md`;
- `MAC_XCODE_GATES_SANITIZED.md` when Mac is available;
- redacted screenshots under `screenshots-redacted/`;
- no raw logs/secrets/raw OCR artifacts.

## CI-backed closure update (2026-08-21)

The former Mac/Xcode build blocker is closed for compilation and automated tests
on branch `codex/ios-native-personal-parity-20260820`, commit
`96aa58226ad8f80834ea333192ebace7885d69c2`.

| Gate | Result |
| --- | --- |
| GitHub Actions | PASS: run `32523201106` |
| XcodeGen | PASS |
| Debug device build without signing | PASS |
| Release device build without signing | PASS |
| XCTest | PASS: 47/47 |
| Launch UI test | PASS: 1/1 |
| Evidence artifact | `ios-build-test-evidence-32523201106`, inspected |
| Personal-only runtime/API scan | PASS for reachable behavior |
| Physical iPhone install and signing | BLOCKED/NOT RUN in Windows/CI scope |
| Actual production login | BLOCKED until a trusted HTTPS API endpoint is selected |

The project must not solve the production connectivity blocker with an arbitrary
ATS exception. Use an owned HTTPS domain or a trusted short-lived Let's Encrypt
IP-address certificate. Legacy Capacitor remains outside the native target.

See `docs/ios-native-mac-handoff.md` and
`MVP_EVIDENCE/personal-native-ios-final-regression-20260821-234120/SUMMARY_SANITIZED.md`.

## Current `codex/IOS` QA closure (2026-06-19)

**Status:** Windows static QA PASS for native iOS parity docs/source inventory; no FAIL recorded. This is not a Mac/Xcode build or runtime test pass.

| Gate area | Result |
| --- | --- |
| Branch/worktree | `codex/IOS`, `C:\Users\style\Documents\Codex\Финансы-ios`, base `origin/main` commit `66feadd94dbf936faec500f565638973ca270f64` |
| Native-only target | PASS: `apps/ios` SwiftUI/UIKit native target; `apps/web-pwa` PWA/Capacitor wrapper remains out of parity scope |
| Config/auth/session | PASS by static inventory for API config hardening, Release guard, register/session/logout wipe surfaces |
| Transactions/capture | PASS by static inventory for date-only manual transactions, payment-account filtering, editable capture amount/date, OCR/copy online-only boundary |
| Assets/analytics/planning | PASS by static inventory for payment account/assets/investment/icon preservation, analytics month/category/investment wiring, and planning fallback for exposed syncable mutations |
| Offline/sync | PASS by static inventory for local JSON store, pending sync queue, manual sync, sync issues and Russian sync UI |
| Windows failures | None recorded |
| Mac/Xcode gates | BLOCKED: `swift`, `xcodebuild` and `xcodegen` unavailable in the current Windows environment |
| Evidence hygiene | PASS: this QA model records sanitized summary only; no secrets, raw logs, raw screenshots, APKs, raw OCR payloads or evidence binaries |

Future mandatory gates remain: XcodeGen project generation, Debug/Release build, simulator/device flows, Keychain/cookie wipe proof, offline queue backend push/pull convergence, and OCR/copy online-only UX validation.

## Blocked items due to no Mac/Xcode now

Current Windows-only pass cannot prove:

- Xcode project generation/open/build;
- Swift unit/UI test execution;
- simulator launch, real device install, memory/crash behavior;
- native `TabView` visual rendering and VoiceOver behavior;
- Keychain, shared cookie storage, CSRF rotation and logout cookie clearing at runtime;
- `PhotosPicker` permission prompt and real image upload behavior;
- Airplane Mode/network path behavior;
- local persistence across app termination/restart;
- sync replay, retry and conflict UI behavior with real app lifecycle;
- TestFlight/App Store archive, signing, entitlements, ATS/App Review readiness.

Release status must remain `BLOCKED` for any P0 Mac/Xcode gate until real Mac evidence or an explicit owner-approved waiver is attached.

## Recommended execution order

1. Run W-IOS-001 through W-IOS-012 on Windows and close all P0 static blockers.
2. On Mac, run M-IOS-001 build before any simulator/device manual testing.
3. Run simulator auth/navigation/config smoke, then feature tests for transactions, capture, assets, analytics and planning.
4. Run offline/restart/sync conflict gates with sanitized fixtures.
5. Run real-device PhotosPicker/Keychain/cookie gates.
6. Run TestFlight/App Store signing gate only after all P0 functional/privacy gates pass.

## Release exit criteria

Native iOS parity can be signed off only when:

- all P0 Windows gates pass or have approved waiver;
- all P0 Mac/Xcode gates pass or have approved waiver;
- native-only invariant is proven with no WebView/PWA wrapper dependency;
- Android parity matrix P0 rows pass for iOS or have tracked owner-approved gaps;
- offline-first syncable domains and online-only exclusions match the contract;
- negative/security/privacy cases pass;
- evidence package is sanitized and contains no secrets, raw screenshots, raw OCR text or production finance values.
