# Native iOS current-parity QA model

Дата актуализации: 2026-08-22

Целевая ветка: `codex/ios-native-current-parity-20260822`

Финальный одобренный commit: `a5a332093587fc2467383686cca089877d03f90e`

Статус: автоматические gates PASS; physical iPhone/signing и production HTTPS/ATS NOT RUN/BLOCKED.

Этот документ является одновременно тестовой моделью и traceability-матрицей. Он не подменяет ручной прогон на физическом iPhone. Целевой клиент - native SwiftUI target `apps/ios`; legacy Capacitor/PWA target `apps/web-pwa/ios` не входит в native iOS release.

## Источники истины

| Источник | Назначение |
| --- | --- |
| `apps/ios/project.yml` | XcodeGen target и build settings. |
| `apps/ios/FinanceApp/**` | Native UI, secure session, SwiftData и sync. |
| `apps/ios/FinanceAppTests/**` | XCTest для auth, data/sync и UX parity. |
| `apps/ios/FinanceAppUITests/**` | Launch UI smoke. |
| `api/openapi/openapi.yaml` | `ios_bearer`, mobile session и API contract. |
| `.github/workflows/ios-build.yml` | Интегрированный backend/iOS CI gate. |
| `MVP_EVIDENCE/native-ios-current-parity-20260822/SUMMARY_SANITIZED.md` | Sanitized release evidence. |

## Release gates

| Gate | Требование | Статус | Доказательство |
| --- | --- | --- | --- |
| IOS-GIT-001 | Branch и remote указывают на один commit | PASS | `codex/ios-native-current-parity-20260822`, `a5a3320...`. |
| IOS-BE-001 | Backend auth/migration contract | PASS CI | Run `32563222674`: 63 tests, Ruff PASS, одна Alembic head `20260822_0019`; full local backend 313 passed/6 skipped. |
| IOS-BLD-001 | XcodeGen | PASS CI | Run `32563222674`. |
| IOS-BLD-002 | Debug build | PASS CI | Run `32563222674`. |
| IOS-BLD-003 | Release build с безопасным placeholder HTTPS | PASS CI | Доказывает компиляцию, не production connectivity. |
| IOS-TST-001 | XCTest | PASS CI | `77/77`. |
| IOS-UI-001 | Launch UI smoke | PASS CI | `1/1`. |
| IOS-DEV-001 | Apple signing/provisioning и установка на физический iPhone | NOT RUN/BLOCKED | Требуются Mac, Xcode, Team/provisioning и устройство. |
| IOS-NET-001 | Trusted production HTTPS и ATS smoke | NOT RUN/BLOCKED | Production endpoint остаётся plain HTTP; ATS нельзя ослаблять. |

## Traceability новой функциональности

| Requirement | Test ID | Автоматическое доказательство | Статус |
| --- | --- | --- | --- |
| Persistent secure session, пароль не хранится | IOS-AUTH-001 | `SecureSessionTests.testLoginUsesIOSBearerAndPersistsRotatableTokensWithoutPassword`; Keychain `ThisDeviceOnly` tests | PASS CI |
| Single-flight refresh и один retry | IOS-AUTH-002 | `testConcurrent401ResponsesUseOneRefreshAndRetryEachRequestOnce`; second-401 test | PASS CI |
| `403` не стирает сессию/lease | IOS-AUTH-003 | `test403DoesNotClearCredentialsOrInvalidateLease` | PASS CI |
| Offline logout локально завершает сессию | IOS-AUTH-004 | `testOfflineLogoutClearsCredentialsAndInvalidatesExistingLease` | PASS CI |
| A -> logout -> B isolation | IOS-ISO-001 | `testAccountIsolationSurvivesLogoutAThenOpenB`; stale refresh/account tests | PASS CI |
| SwiftData JSON migration/recovery | IOS-DB-001 | legacy snapshot/pending/tombstone migration tests; idempotency and retained recovery paths | PASS CI |
| Transactional local writes/sync | IOS-SYNC-001 | atomic optimistic mutation and rollback tests | PASS CI |
| Stale push/refresh response rejected | IOS-SYNC-002 | stale push after account switch and stale refresh tests | PASS CI |
| Search by word fragment, modal vertical category list | IOS-CAT-001 | `IOSUXParityTests` search/modal/vertical contract | PASS CI |
| Operations newest-first everywhere | IOS-OPS-001 | pagination and stable comparator tests using date/occurredAt/createdAt/id | PASS CI |
| Edit amount/date/category/account | IOS-OPS-002 | `TransactionEditSheet`, edit policy and root update wiring covered by XCTest/static integration | PASS CI; physical UX NOT RUN |
| Pending investments only for selected month | IOS-AN-001 | `testPendingOverlayIncludesOnlySelectedMonthAndInvestmentDestinations` | PASS CI |
| Personal-only UI/API | IOS-PER-001 | personal contract XCTest and launch UI test | PASS CI |
| OCR strictly online-only | IOS-OCR-001 | sync policy, OCR boundary and bearer transport tests | PASS CI; real image NOT RUN |
| Expense account is payment-account only | IOS-PAY-001 | quick expense/editor policy tests | PASS CI |
| Compact month switcher and current-month shortcut | IOS-AN-002 | `testHistoricalMonthShowsCurrentMonthShortcut` | PASS CI; device accessibility NOT RUN |

## Detailed test cases

### Authentication and session

| ID | Priority | Steps | Expected |
| --- | --- | --- | --- |
| IOS-AUTH-001 | P0 | Login through `ios_bearer`; inspect persisted credential model | Access/refresh tokens are device-bound; password is absent. |
| IOS-AUTH-002 | P0 | Trigger concurrent `401` responses | One refresh occurs; every eligible request retries no more than once. |
| IOS-AUTH-003 | P0 | Return `403` for authenticated request | Error is surfaced; credentials, identity and pending data stay intact. |
| IOS-AUTH-004 | P0 | Logout while network request fails | Local credentials and lease are invalidated; protected UI closes. |
| IOS-AUTH-005 | P0 manual | Login, force quit, relaunch on iPhone | User remains signed in without password re-entry. Status: NOT RUN. |

### Account isolation, SwiftData and sync

| ID | Priority | Steps | Expected |
| --- | --- | --- | --- |
| IOS-ISO-001 | P0 | Open A data, logout, open B, receive late A response | B cannot read A snapshot/queue; late A response is rejected. |
| IOS-DB-001 | P0 | Migrate legacy JSON with pending mutation/tombstone twice | Data preserved once; migration idempotent; recovery file retained. |
| IOS-DB-002 | P0 | Fail a SwiftData transaction midway | Entire state rolls back; no partial snapshot. |
| IOS-SYNC-001 | P0 | Push/pull under immutable session lease | Response applies only while user/session/generation lease is current. |
| IOS-SYNC-002 | P0 | Account switch during push or refresh | Stale response never overwrites the new account. |
| IOS-SYNC-003 | P0 manual | Offline create/edit/delete, relaunch, reconnect, sync | Queue survives and converges without duplicates. Status: NOT RUN on device/prod. |

### Operations, categories and analytics

| ID | Priority | Steps | Expected |
| --- | --- | --- | --- |
| IOS-CAT-001 | P0 | Open category button; type a word fragment; scroll | Modal vertical list filters case-insensitively and selection persists. |
| IOS-OPS-001 | P0 | Mix operations with same dates/timestamps and paginate | Order is date descending, then occurredAt, createdAt and id. |
| IOS-OPS-002 | P0 | Edit expense amount, date, category and account | All four values update; only personal payment account and expense category allowed. |
| IOS-PAY-001 | P0 | Mark/unmark payment account and open expense editor | Eligible account list reflects payment flag. |
| IOS-AN-001 | P0 | Queue investment transfer in month M; view M and M-1 | Pending investment appears only in M and only for investment destination. |
| IOS-AN-002 | P1 | Move across months; open historical month | Compact arrows work; current-month shortcut appears and returns to current month. |

### Privacy and product scope

| ID | Priority | Steps | Expected |
| --- | --- | --- | --- |
| IOS-PER-001 | P0 | Inspect launch/UI/API payloads | No `Общее` mode; reports and mutations are personal-only. |
| IOS-OCR-001 | P0 | Attempt OCR offline | No pending mutation or local raw image/OCR payload; safe online-only error. |
| IOS-OCR-002 | P0 manual | Select sanitized screenshot online and confirm edited draft | Upload is transient and transaction is created only after confirmation. Status: NOT RUN on physical device. |
| IOS-SEC-001 | P0 | Scan docs/evidence for credentials and raw payloads | No password, token, cookie, signing asset, raw OCR or production finance payload committed. |

## Full native regression matrix

| ID | Area | Priority | Automated gate | Required device verification |
| --- | --- | --- | --- | --- |
| IOS-REG-001 | Registration | P0 | `ios_bearer` registration and session installation XCTest | Register a fresh personal user over production HTTPS. |
| IOS-HOME-001 | Dashboard | P1 | Personal filtering, pagination, totals and top-category tests | Inspect layout, long Russian labels and all-category drill-down. |
| IOS-TXN-001 | Manual income/expense | P0 | Date-only serialization and strict payload tests | Create income and expense with past/current dates. |
| IOS-TXN-002 | Transfer/investment | P0 | Selected-month investment and account-policy tests | Transfer into an investment account; verify balance and monthly analytics after sync. |
| IOS-TXN-003 | Delete and offline replay | P0 | Tombstone/coalescing/pull tests | Delete offline, relaunch, reconnect and confirm no resurrection. |
| IOS-ASSET-001 | Account CRUD | P0 | Strict sync payload and personal ownership tests | Create/edit/archive/restore account and payment flag. |
| IOS-ASSET-002 | Asset categories | P1 | Personal/investment filtering and sync contract tests | Edit name/icon/investment flag; verify account links remain visible. |
| IOS-CAT-002 | Expense categories | P1 | Expense-only/personal contract and picker tests | Create/edit/archive/restore; verify no income/shared selectors. |
| IOS-AN-003 | Summary/category breakdown | P1 | Selected-month query, aggregation and descending order tests | Compare month totals and category drill-down with server data. |
| IOS-PLAN-001 | Monthly planning | P1 | Planning decode/history and sync payload tests | Create/edit plan, income source and allocation; verify plan/fact/deviation. |
| IOS-OFF-001 | Cold-start offline read | P0 | Persisted session/snapshot and network-failure queue tests | Force quit offline; protected cached UI opens without login overlay. |
| IOS-OFF-002 | Manual sync/issues | P0 | Retry/quarantine/conflict decision tests | Reconnect and sync; verify counts, retry and edit/discard-only states. |
| IOS-CAP-001 | OCR confirmation | P0 | OCR boundary and editable draft model tests | Online sanitized image, edit amount/date/category/account, then confirm. |
| IOS-NAV-001 | Native navigation | P1 | Launch UI personal-only smoke | Exercise every tab, VoiceOver labels and Dynamic Type. |
| IOS-CONFIG-001 | Release configuration | P0 | Release build and URL guard | Trusted production HTTPS health/login/refresh; no ATS exception. |

Rows without physical evidence remain manual release gates even when their model
or contract is covered by XCTest.

## Worker and integration evidence

| Stream | Commit/run | Result |
| --- | --- | --- |
| Backend `ios_bearer` contract | Final `a5a3320`; full backend 313 passed/6 skipped; CI auth/migration 63 | PASS; migrations through `20260822_0019` not deployed to production |
| Secure iOS session | `13bff57b`; run `32554005096` | Debug/Release PASS, XCTest 57/57, UI 1/1 |
| SwiftData/account sync | `640f93e2`; run `32554343934` | Debug/Release PASS, XCTest 52/52, UI 1/1 |
| UX parity | `ba195e2`; run `32552813248` | PASS |
| Final approved branch | `a5a3320`; run `32563222674` | Backend CI 63, iOS 77/77, UI 1/1, Debug/Release PASS; reviewer APPROVE |

Worker runs prove their isolated branches. Final code/CI status is based only on
run `32563222674` at exact SHA
`a5a332093587fc2467383686cca089877d03f90e`.

## Closed reviewer findings

| Cycle | Finding | Final evidence/status |
| --- | --- | --- |
| 1 | 72-hour offline cap was not applied during Keychain restore | FIXED; real restore path enforces the cap and clears credentials without deleting scoped financial data |
| 1 | Refresh rotation did not extend session lifetime | FIXED and superseded by separate access/refresh expiry model |
| 1 | Offline edit/delete did not update analytics before sync | FIXED; queued edit/delete and month movement are covered |
| 1 | Logout could race with committed refresh | FIXED; stable session-bound revoke proof is used |
| 2 | Refresh was unreachable after access expiry | FIXED; access TTL is 15 minutes, sliding refresh/session TTL is 30 days, 401 -> refresh -> one retry is covered |
| 2 | Partial edit -> delete sync retained stale analytics baseline | FIXED; dependent delete is rebased to applied edit payload/version |
| 2 | Uncategorized expense edit/delete left category breakdown stale | FIXED; canonical `uncategorized` delta is applied |

Final independent reviewer verdict: **APPROVE for code/CI**. No P0/P1 code
finding remains open in the reviewed scope.

## External blockers and non-results

- **Physical iPhone/signing: NOT RUN/BLOCKED.** There is no signed IPA or device evidence. Mac, Xcode, Apple Team/provisioning and a connected iPhone are required.
- **Production HTTPS/ATS: NOT RUN/BLOCKED.** Current production API is plain HTTP. Release must use an owned trusted HTTPS endpoint. `NSAllowsArbitraryLoads` or broad production ATS exceptions are prohibited.
- **Production backend deploy: PREFLIGHT BLOCKED / NOT PERFORMED.** GitHub
  environment `production` reports `protection_rules=[]`; local branch
  `prod/release-finance-ios-backend-20260822` is not pushed; production DB is
  still `20260618_0017`; health is HTTP 200; HTTPS/FQDN is absent. Migration
  head `20260822_0019` is CI-tested but not proven on live production DB.
- **Physical OCR and end-to-end offline convergence: NOT RUN.** Automated boundaries pass; device behavior must still be evidenced.

## Definition of Done for final device release

1. Trusted production HTTPS health, login, refresh and API smoke PASS without ATS exceptions.
2. App signed and installed through Xcode on the target iPhone.
3. Force-quit session restore, offline logout and A -> B isolation PASS on device.
4. Full manual operation/category/payment/investment/month flows PASS.
5. Offline queue survives relaunch and converges after reconnect.
6. OCR online-only flow passes with sanitized fixture and no raw payload persistence.
7. Sanitized evidence records exact commit, build, device/iOS version and results without secrets.
