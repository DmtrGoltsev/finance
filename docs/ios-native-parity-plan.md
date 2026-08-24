# Native iOS Parity Plan

Date: 2026-06-19

Purpose: working contract for follow-up native iOS implementation agents. This document maps Android behavior to native iOS target files, current status, and verification evidence. It is a parity/test-doc artifact only; it does not authorize PWA/WebView wrappers or app-code edits by documentation agents.

## Native-only invariant

The iOS deliverable for this branch is a native app:

- Use Swift, SwiftUI, UIKit/Foundation/Security/PhotosUI where needed.
- Do not ship a PWA, Capacitor, or WebView wrapper as the native iOS implementation.
- Do not embed `apps/web-pwa/ios/App` as a shortcut for parity. That tree is the existing Capacitor/PWA iOS wrapper and is explicitly out of scope for the native parity target.
- The native target lives under `apps/ios`.
- UI must be built with native SwiftUI/UIKit controls, native navigation, native `PhotosPicker`, native Keychain access, native `URLSession`, and native local persistence when offline-first is implemented.
- API contracts must stay aligned with `api/openapi/openapi.yaml` and Android backend usage, but the iOS client must not store secrets, raw screenshots, raw OCR text, or production financial values in docs or evidence.

## Current native iOS architecture summary

### Target and project layout

Native iOS target:

- `apps/ios/project.yml`: XcodeGen-style project definition, iOS 17.0, Swift 5.9, target `FinanceApp`, bundle `com.codex.FinanceApp`.
- `apps/ios/FinanceApp/App/FinanceApp.swift`: native entry point. Instantiates `AppEnvironment`, `LiveApiClient`, file-backed local store, and sync service, then injects them into root view.
- `apps/ios/FinanceApp/App/FinanceAppView.swift`: root auth gate, `TabView`, five app tabs, FAB quick-add sheet, session restore, dashboard load, manual transaction submit, logout, sync status/sheet, and config-error presentation.
- `apps/ios/FinanceApp/Models/*`: Codable API/domain models for accounts, categories, transactions, reports, planning, capture drafts, session, money, errors.
- `apps/ios/FinanceApp/Networking/ApiClient.swift`: full native protocol covering auth, account/category/asset category/transaction/capture/report/planning endpoints.
- `apps/ios/FinanceApp/Networking/LiveApiClient.swift`: `URLSession` implementation, cookie-based auth transport, CSRF header handling, dashboard aggregation, reports/planning/capture calls.
- `apps/ios/FinanceApp/Networking/CSRFTokenStore.swift`: Keychain-backed CSRF token and session expiry storage.
- `apps/ios/FinanceApp/Networking/RequestBuilder.swift`, `ResponseParser.swift`, `ApiError.swift`: URL/query/body/multipart/error helpers.
- `apps/ios/FinanceApp/Utilities/*`: money/date/dashboard constants and helpers, including `AppEnvironment` base URL resolution.
- `apps/ios/FinanceApp/LocalStore/*`, `apps/ios/FinanceApp/Sync/*`, `apps/ios/FinanceApp/Models/Sync.swift`: native offline/sync foundation with scoped file-backed snapshots, pending mutations, tombstones, device id, sync push/pull service, issues, retry, and online-only policy.
- `apps/ios/FinanceApp/Views/*`: native SwiftUI screens and cards for auth, home, operations, capture, assets, categories, analytics, planning, and shared controls.

Important non-target:

- `apps/web-pwa/ios/App/*` is the Capacitor/PWA wrapper and must not be used to satisfy native iOS parity.

### Current strengths

- Native SwiftUI app surface already exists under `apps/ios`.
- Auth/register/session restore uses the cookie + CSRF API flow in `LiveApiClient`.
- Keychain storage exists for CSRF/session expiry.
- Root tabs are icon-only SwiftUI `TabView` items with accessibility labels.
- Manual quick add supports expense, income, transfer, amount, date-only `transactionDate`, and scope selection.
- Expense source account picker filters to `isPaymentAccount == true`.
- Capture/OCR flow uses native `PhotosPicker`, online backend OCR, editable aggregate candidates, category mapping, capture draft creation, editable amount/date before confirm, and explicit confirm/discard.
- Asset/account/category/planning/report API protocols are broad enough for parity implementation.
- Local store and sync foundation are present in native iOS, including `FinanceApiClient.syncPush/syncPull`, pending mutation queue, tombstones, sync issue model, retry service, and a root sync UI.
- Logout/config/analytics fixes are present: visible logout and protected-state wipe path, build-configured API URL resolution with Release config error, and report API category breakdown wiring.
- Asset category UI includes icon selection, investment flag, manual amount, asset type, account linking, account archive/restore.
- Planning UI is present for plan creation, income sources, allocations, history copy, regular/one-off, amount/percent, and savings goals for investment categories.

### Current gaps and risks

- Offline-first foundation is present, but CRUD offline wiring is still in progress and needs Mac/Xcode build/test evidence. Treat account/category wiring as transitional until the offline CRUD agent finishes and proves tab-level integration.
- The local store currently uses file-backed JSON snapshots rather than SwiftData/Core Data/SQLite. This is acceptable for the foundation slice only if schema/versioning, privacy, migration, and durability risks are explicitly tested before release.
- Config guard is present, but Release still requires Mac/Xcode scheme/build evidence that `FINANCE_RELEASE_API_BASE_URL` is set to an approved HTTPS endpoint.
- ATS allows local networking and a `127.0.0.1` HTTP exception for debug/local backend work. This must remain debug/local-only and is a Mac release gate; no production HTTP exception should be added.
- Native iOS has no checked-in unit/UI test targets/files visible in this workspace, so Mac/Xcode implementation agents must add tests rather than relying on documentation review.
- No native iOS app icon/assets audit is documented in this plan; follow-up UI agents should keep native app assets separate from PWA wrapper assets.

## Android parity matrix

Status legend:

- `Implemented`: present in native iOS and mapped to target files.
- `Partial`: present but incomplete or needs contract-level hardening/tests.
- `Missing`: no native iOS implementation found.
- `Blocked on Mac/Xcode`: cannot be fully verified from Windows-only documentation pass.

| Feature | Android inventory / behavior | iOS target files / behavior | Current iOS status | Required verification |
| --- | --- | --- | --- | --- |
| Native app invariant | Android is native Kotlin/Compose under `apps/android`; not a web wrapper. | `apps/ios/project.yml`, `apps/ios/FinanceApp/**`. Explicitly exclude `apps/web-pwa/ios/App/**`. | Partial: native target exists; wrapper also exists in repo and must stay non-target. | Windows: path audit proves native Swift files exist and wrapper is separate. Mac: generated/opened Xcode project builds native target without WebView/PWA dependency. |
| Auth: login | Android `FinanceApp.kt` login form calls `FinanceApiClient.login`; secure token store/session restore exists. | `Views/Auth/SignInCard.swift`, `App/FinanceAppView.swift`, `Networking/LiveApiClient.login`. Uses `transport: "pwa_cookie"`, cookie storage, CSRF token save. | Implemented, needs tests. | Unit test mock login envelope saves CSRF; UI smoke logs in and loads dashboard; no password/token in evidence. |
| Auth: register | Android supports register through `register(email,password,displayName)` and accepted/authenticated paths. | `SignInCard.swift`, `FinanceAppView.performRegister`, `LiveApiClient.register`. Password min length uses `FinanceConstants.passwordMinLength`. | Implemented, needs tests. | Unit/UI: password validation, mismatch, accepted and authenticated registration responses. |
| Session restore | Android force-stop/relaunch restore covered by release QA. | `FinanceAppView.restoreSession`, `LiveApiClient.sessionStatus`, `CSRFTokenStore.sessionExpiry`. | Partial: restore API exists; expiry property not visibly used before restore. | Unit: authenticated/unauthenticated/session-expired responses. Device: relaunch online/offline after prior session. |
| Logout wipe | Android release QA requires logout + force-stop relaunch shows login and old session not restored. | `LiveApiClient.logout` clears Keychain token/expiry/cookies. `FinanceAppView` exposes logout and wipes dashboard/message/tab/quick-add/sync state plus protected local stores/mappings. | Partial: logout/config fixes present; needs unit/UI/device evidence and account-switch/offline relaunch proof. | Unit: logout clears token store. UI: tap logout, relaunch, financial UI inaccessible. Offline store verification after offline-first slice. |
| Manual income/expense date-only | Android quick add/manual transactions preserve `transactionDate` date-only. | `QuickAddSheet.transactionDate`, `DatePickerField`, `FinanceAppView.submitQuickAdd`, `TransactionCreateRequest.transactionDate`. | Implemented for quick add expense/income; transfer currently uses selected/default date via same draft path. | Unit: request body includes `transactionDate` `yyyy-MM-dd` and `sourceType: manual`; UI: selected date survives save/display. |
| Manual payment-account filter | Android payment account flag filters expense source accounts. | `AddAccountSheet.isPaymentAccount`, `AccountCreateRequest.isPaymentAccount`, `QuickAddSheet.operationAccounts` filters expense to `isPaymentAccount`. | Implemented for create + expense picker; needs edit coverage. | Unit/UI: non-payment account absent for expense, still available for income/transfer if allowed; account edit preserves/toggles flag. |
| Transfers same-scope | Android validates same scope/currency and creates `transactionType=transfer`. | `QuickAddSheet.compatibleDestinations` filters different id, same currency, same ownership; `FinanceAppView.submitQuickAdd` creates transfer. | Partial: same household id check is implicit through scoped list; needs explicit test. | Unit/UI: personal-to-personal and shared-to-shared work; cross-scope/cross-currency blocked before API. |
| OCR/capture online-only | Android OCR upload is online-only, no raw screenshot/OCR payload in offline queue/evidence. | `OperationsTab.processScreenshot` uses `PhotosPickerItem` data and calls `apiClient.screenshotOcr` directly. No offline queue exists yet. | Partial: online path exists; offline-first slice must explicitly block queueing OCR. | Unit: OCR is not represented as sync mutation. UI: offline tap shows online-only error, no raw image/OCR persisted. |
| OCR editable amount/date | Android capture drafts can update amount/date/account/category before confirm. | `CaptureDraftRow.swift` and `OperationsTab.confirmDraft` send `CaptureDraftUpdateRequest(occurredDate, amount, accountId, categoryId)` before `confirmCaptureDraft`. | Implemented, needs tests. | Unit/UI: edit amount/date then confirm; transaction created only after confirm; discard does not create transaction. |
| OCR aggregate mapping | Android stores category aggregate label mapping safely. | `Views/Capture/CategoryAggregateMappingStore.swift`, `OperationsTab.createAggregateDrafts`, `putCategoryMapping` API method available. | Partial: local store exists; API mapping method exists but local flow currently saves local mapping after draft creation. Confirm privacy expectations for hashing/no raw labels. | Unit/security: store does not persist raw external labels if contract requires hashing; mapping scoped by user/household. |
| Assets/accounts CRUD | Android supports accounts and asset category CRUD with archive/restore. | `AssetsTab.swift`, `AddAccountSheet.swift`, `AccountRow.swift`, `AccountEditDialog.swift`, `AssetCategoryGroupCard.swift`, `AssetCategorySheet.swift`, `LiveApiClient` account/asset endpoints. | Implemented/Partial: visible create/update/archive/restore paths exist; delete/restore asset category UI needs audit. | Unit/UI: create/edit/archive/restore account; create/edit/archive asset category; linked accounts remain visible. |
| Asset categories | Android has `AssetCategory`, groups, manual amount, asset type, investment flag. | `Models/AssetCategory.swift`, `AssetCategorySheet.swift`, `AssetCategoryGroupCard.swift`, `AssetsTab.swift`. | Implemented, needs Xcode build and behavior tests. | UI: create personal/shared asset category with manual amount/currency/type/investment flag; dashboard group totals update. |
| Investment/icon preservation | Android preserves icon keys and investment categories; investment migration exists. | `AssetCategoryIcons.swift`, `AssetCategorySheet.iconKey`, `AssetCategoryUpdateRequest.iconKey`, `PlanningAllocationEditor` investment target type. | Partial: icon fields preserved in normal CRUD; Android atomic investment migration command has no iOS target yet. | Unit: icon key round-trip create/update. Integration: investment totals and planning targets preserve investment category. Offline slice: atomic migration command behavior. |
| Analytics month aggregation | Android report month switcher and report API aggregation. | `AnalyticsTab.reportMonth`, `ReportMonthSwitcher.swift`, `LiveApiClient.getReportSummary/getReportCategoryBreakdown/getReportAccountBalances`. | Partial: summary/balances fetched by month; category card ignores fetched breakdown. | Unit: selected month maps to month start/end. UI/API: summary/category/balance cards reflect report API, not just dashboard page. |
| Analytics category aggregation | Android requires all categories, not truncated local list. | `AnalyticsTab` fetches `getReportCategoryBreakdown`; `CategoryBreakdownCard` accepts `ReportCategoryBreakdown` and can render report items. | Partial: report API wiring present; needs mock/UI proof that fallback local aggregation does not hide categories absent from dashboard page. | Unit: report breakdown with categories absent from dashboard page still displays. |
| Analytics investments | Android displays investments by currency and total from account balances/report. | `AnalyticsSummaryCard.swift`, `CapitalBreakdownCard.swift`, `Assets/InvestmentsCard.swift`, `LiveApiClient.dashboard` maps `investmentsByCurrency`, `investmentsTotal`. | Partial/Implemented: display exists; needs report-source consistency. | UI/API: investment totals match `/reports/account-balances` for selected month/mode/currency. |
| Planning UI | Android planning supports create/update/delete/copy plan, income, allocations, history, target types, savings goals. | `Analytics/Planning/*.swift`, `PlanningView.swift`, `PlanningAllocationEditor.swift`, `LiveApiClient` planning endpoints, `FinanceSyncService.enqueueOptimisticPlanningMutation`. | Implemented/Partial: broad online planning UI exists; exposed native planning mutations now use conservative network fallback for plan create plus income source create/update/confirm/delete and allocation create/update/delete. No exposed native plan update/delete callback exists yet. | Unit/UI: create plan, income source, allocation, confirm income, copy history plan, delete children; offline network failure queues only syncable planning mutations; validation/auth/server errors stay online errors; overview read-only gate. |
| Planning target filtering | Android filters used allocation targets to prevent duplicates. | `PlanningAllocationEditor.usedTargetIds`, `AllocationsCard.swift` target options. | Needs audit/test. | Unit: already used target cannot be selected for duplicate allocation unless editing same allocation. |
| Planning online-only boundaries | Android offline-first test docs mark `copy_plan`, history mutation, target repair as online-only. | `SyncQueuePolicy` marks `copy_plan`, planning history mutation, and planning target repair as online-only; current `copyPlanningPlan` remains an online API call and is not queued by `PlanningView`. | Partial: policy and native copy boundary present; UI/offline attempt behavior still needs tests. | Unit: no pending mutation type for `copy_plan`; UI blocks offline copy/history repair. |
| Bottom nav icon-only | Android bottom nav uses icons for sections. | `FinanceAppView.TabView.tabItem` uses `Image(systemName:)` only plus accessibility labels. | Implemented. | UI: tab bar shows icons without visible text labels if iOS rendering allows; VoiceOver labels present. Screenshot verification on device/simulator. |
| Offline-first local store | Android has Room entities/DAOs, `FinanceLocalDatabase`, `PlanningRepository`, `SyncManager`, `TransactionSyncWorker`, pending mutations, sync state. | Native iOS files exist under `apps/ios/FinanceApp/LocalStore/*`, `apps/ios/FinanceApp/Sync/*`, and `Models/Sync.swift`; file-backed scoped snapshots include schema version, pending mutations, tombstones, sync cursor/state, issues, and wipe paths. | Partial: foundation present; CRUD offline wiring is in progress and must be proven before parity. | Windows: file/API audit after implementation. Mac: unit tests for persistence, restart, pending queue, sync replay. Device: offline create/edit/delete then online convergence. |
| Sync/conflicts | Android has sync push/pull contracts, tombstones, issue sheet, retry/rejected behavior. | `FinanceSyncService`, `SyncQueuePolicy`, `SyncIssue`, root sync sheet, retry action, safe-message filtering, and no destructive overwrite UI are present. | Partial: sync foundation/UI present; conflict and retry behavior need tests and tab-level CRUD integration proof. | Unit: tombstone prevents resurrection; conflict rejection becomes safe issue; retry works for retriable failures; no raw payload/secrets in UI/logs. |
| Logout/account switch local wipe | Android release QA requires protected local state wipe and no cross-user bleed. | Root logout/account-switch workflow clears API auth state, cookies/Keychain, dashboard memory, local store namespace, pending mutations, sync UI state, and OCR mappings through `FinanceSessionDataWiper`. | Partial: wipe path present; needs unit/device proof across logout, account switch, offline relaunch. | Unit/device: user A data/queue inaccessible after logout and after user B login; app relaunch shows login. |
| Config/debug-prod URL guard | Android has BuildConfig URL tests and release QA verifies local debug uses local endpoint and prod build is explicit. | `project.yml` injects Debug local URL and Release `$(FINANCE_RELEASE_API_BASE_URL)`; `Info.plist` carries `FINANCE_API_BASE_URL`; `AppEnvironment` rejects empty/unresolved `$(...)` in Release and exposes a user-facing config error. | Partial: guard/config fixes present; needs Mac/Xcode scheme/unit/release preflight. | Windows: source grep for forbidden hardcoded endpoints in debug/release configs. Mac: unit test for base URL normalization/guard, scheme config test, release build preflight. |

## Implementation slices and ownership

Follow-up agents should keep slices small and produce evidence per slice. Suggested order:

| Slice | Owner role | Reasoning level | Dependencies | Scope | Definition of done | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| S0 Native build/test harness | iOS Foundation Agent | high | none | Generate/open native iOS project, add unit/UI test targets if absent, add mock API client fixtures, prove app builds. | Native `FinanceApp` builds on Mac/Xcode; no PWA/WebView target dependency; first smoke tests run. | Xcode build log, test log, screenshot of native app launch. |
| S1 Config and URL guard | iOS Platform/Security Agent | xhigh | S0 | Replace hardcoded base URL with build/scheme config; add debug/prod guard tests. | Debug and release base URLs are explicit, testable, and cannot silently point at wrong environment. | Unit test output; source grep summary with no forbidden hardcoded endpoint outside config docs. |
| S2 Auth/logout/session wipe | iOS Auth Agent | xhigh | S0, S1 | Add visible logout, cookie/Keychain clear, root state wipe, session expiry behavior, account-switch hygiene. | Login/register/session restore/logout pass; relaunch after logout shows auth gate; no protected state survives in memory/local store namespace. | Unit/UI logs; sanitized simulator screenshots. |
| S3 Manual operations parity | iOS Operations Agent | medium | S0-S2 | Harden quick add date-only, payment account filter, transfer compatibility, request encoding. | Expense/income/transfer create with date-only and correct account/category/scope; incompatible choices blocked before API. | Unit/UI tests for request bodies and selectors. |
| S4 Capture/OCR parity | iOS Capture Agent | high | S0-S3 | Confirm online-only OCR boundary, editable amount/date/account/category, discard, mapping privacy. | OCR never queues offline; confirm only after user review; raw image/OCR text not persisted; category mapping meets privacy contract. | Unit/UI tests; storage/log scan summary; sanitized OCR flow screenshots with fixture-safe data. |
| S5 Assets/investments/icons | iOS Assets Agent | medium | S0-S3 | Account/asset category CRUD, icon round-trip, investment flag/totals, account payment flag edit. | CRUD lifecycle works; icon/investment/payment fields persist and display; linked account/category behavior stable. | Unit/API integration logs; UI screenshots. |
| S6 Analytics API parity | iOS Analytics Agent | medium | S0-S5 | Make month/category aggregation render report API results, not only dashboard transaction page; verify investments. | Month switcher drives report endpoints; all category breakdown items and investment totals display from report data. | Mock API tests for category not in local dashboard list; UI screenshot. |
| S7 Planning online parity | iOS Planning Agent | high | S0-S6 | Harden online planning create/update/delete/copy, duplicate target filtering, overview gate, savings goal rules. | Planning online flows match Android UX/business rules; `copy_plan` remains online workflow. | Unit/UI tests for target filtering, create/update/delete/copy, savings goals. |
| S8 Offline-first foundation | iOS Sync/Storage Agent | xhigh | S0-S7 | Add native local store, device id, sync pull/push, pending queue, tombstones, entity schemas, no OCR queue. | Syncable domains persist offline and replay safely; online-only domains blocked; storage scoped to authenticated user/household. | Persistence tests, sync tests, restart tests, schema migration tests. |
| S9 Conflict UI and release QA | iOS QA/Integration Agent | xhigh | S8 | Add failed/rejected issue UI, retry, no destructive resolvers, final parity QA checklist. | Offline/online transitions, conflicts, logout wipe, account switch, and release gates pass or have approved waiver. | Test logs, simulator/device screenshots, sanitized release report. |

Parallelization:

- After S0, S1 and S2 should be sequential because auth/session safety depends on configuration behavior.
- S3, S5, S6, and S7 can run partly in parallel once S0-S2 are stable, but integration should merge in order S3 -> S5 -> S6 -> S7 to avoid dashboard/model drift.
- S4 can run parallel with S5/S6 if it does not alter shared API models beyond capture types.
- S8 must wait for core online domain flows to stabilize.
- S9 must follow S8.

## Windows-verifiable checks vs Mac/Xcode blockers

### Windows-verifiable checks

These can be checked from this repository without Xcode:

- `apps/ios/FinanceApp/**` exists and contains Swift native app files.
- `apps/web-pwa/ios/App/**` is separate and not referenced as the native parity target.
- `apps/ios/project.yml` declares iOS 17.0, Swift 5.9, native app target.
- Source grep confirms whether hardcoded base URLs remain in native iOS files.
- Source grep confirms whether local store/sync files exist after S8.
- Source grep confirms whether `FinanceApiClient` includes sync `push/pull` methods after S8.
- Documentation/test docs can be reviewed for no secrets, no raw screenshots, no APK modifications, and no raw OCR text.
- Swift source can be reviewed for request field names such as `transactionDate`, `isPaymentAccount`, `captureSource`, `occurredDate`, `iconKey`, `isInvestment`, planning target fields, and CSRF header usage.

### Final Windows static status for `codex/IOS`

As of 2026-06-19, the current native iOS worktree status is:

- Branch/worktree: `codex/IOS` at `C:\Users\style\Documents\Codex\Финансы-ios`, based on `origin/main` commit `66feadd94dbf936faec500f565638973ca270f64`.
- Native-only invariant: still satisfied at the documentation contract level. The parity target is `apps/ios`; the PWA/Capacitor tree under `apps/web-pwa` remains separate and is not a release shortcut.
- Implemented scope now includes API config hardening/Release guard, auth/register/session/logout wipe improvements, date-only manual transactions, payment-account filtering, online-only OCR/capture with editable amount/date, assets/investments/icon preservation, analytics month/category/investment wiring, planning fallback for exposed syncable mutations, icon-only tabs, local JSON store, pending sync queue, manual sync, sync issues and Russian sync UI.
- Windows static QA result: PASS, with no FAIL recorded for the static source/docs pass.
- Current release boundary: native iOS release sign-off remains blocked only by Mac/Xcode-required gates. `swift`, `xcodebuild` and `xcodegen` were unavailable in the current Windows environment, so build, simulator/device, Keychain/cookie, offline backend push/pull and OCR/copy online-only UX runtime proof must be produced later on Mac.
- Documentation/evidence boundary: no secrets, raw logs, raw screenshots, raw OCR payloads, APKs or evidence binaries are recorded by this plan.

Recommended Windows commands:

```powershell
rg --files apps/ios
rg "WebView|WKWebView|Capacitor|apps/web-pwa|http://|https://" apps/ios docs/ios-native-parity-plan.md
rg "syncPush|syncPull|PendingMutation|SyncManager|SwiftData|CoreData|SQLite" apps/ios
rg "transactionDate|isPaymentAccount|occurredDate|iconKey|isInvestment|X-CSRF-Token" apps/ios
```

### Mac/Xcode blockers

These require Mac/Xcode or an iOS simulator/device and cannot be fully proven by this Windows documentation pass:

- Generate/open/build native Xcode project from `apps/ios/project.yml`.
- Run Swift unit tests and SwiftUI UI tests.
- Verify native `TabView` visual behavior and icon-only tab rendering on iPhone/iPad.
- Verify Keychain, cookie storage, CSRF rotation, and app relaunch behavior on simulator/device.
- Verify `PhotosPicker` permissions and screenshot upload behavior.
- Verify local persistence behavior for SwiftData/Core Data/SQLite once implemented.
- Verify offline/online network transitions, force-stop/relaunch, logout wipe, and account switch on simulator/device.
- Verify release/debug build configuration guard with real Xcode schemes/configurations.

## Definition of done for this branch

The branch can be considered done when:

- This parity contract exists and stays updated as implementation slices land.
- The native-only invariant is enforced: the iOS parity target is `apps/ios/FinanceApp`, not `apps/web-pwa/ios/App`.
- Native iOS builds on Mac/Xcode from `apps/ios` with no WebView/PWA wrapper dependency.
- Auth/register/session restore/logout wipe are implemented and tested.
- Manual expense/income/transfer creation preserves date-only semantics and scope/account/category rules.
- Expense account selection respects `isPaymentAccount`.
- OCR/capture is online-only, uses native screenshot selection, stores no raw screenshot/OCR payload, and creates transactions only after editable review and confirm.
- Assets, asset categories, investment flags, icons, and linked accounts round-trip through API and UI.
- Analytics month/category/investment displays come from report APIs and are not truncated by dashboard page limits.
- Planning online UI supports create/update/delete/copy/history/allocations/income sources and enforces target/savings rules.
- Offline-first iOS local store/sync/conflict behavior reaches Android contract parity for syncable domains, while OCR/copy_plan/history repair remain online-only.
- Debug/prod API URL configuration has tests/guards and no accidental hardcoded wrong-environment endpoint.
- Windows-verifiable checks pass, and Mac/Xcode blockers have attached build/test/device evidence.
- Evidence remains sanitized: no secrets, no raw screenshots, no raw OCR text, no APK/raw evidence modification, no production financial values.
