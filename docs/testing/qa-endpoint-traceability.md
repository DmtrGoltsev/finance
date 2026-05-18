# QA traceability endpoints MVP

## Статус и область

Этот документ связывает QA-сценарии `AS-*`, `NEG-*`, `SEC-*`, `PRIV-*` и release gates `RG-*` с endpoint surfaces, API contracts, authz predicates и требуемыми доказательствами для MVP.

Источники:

- `docs/testing/access-security-scenarios.md`
- `docs/architecture/backend-api-contracts.md`
- `docs/architecture/backend-authz-predicates.md`
- `docs/architecture/report-api-contracts.md`
- `docs/architecture/transfer-api-contract.md`
- `docs/security/security-release-checklist.md`
- `docs/compliance/privacy-flows-mvp.md`
- `docs/architecture/client-state-contracts.md`
- `docs/architecture/canonical-api-vocabulary.md`

## W3 API contract sync boundary

Статус на 2026-05-18: canonical OpenAPI для closed MVP отражает только фактически смонтированную runtime surface.

- Sessions: `POST /api/v1/sessions`, `GET /api/v1/sessions/current`, `DELETE /api/v1/sessions/current`.
- Accounts/categories: list, create, autocomplete, detail, patch, delete, archive, restore.
- Transactions: list, create, autocomplete, detail, patch, delete, restore.
- Transfers: только `transactionType=transfer` через `/api/v1/transactions*`; standalone `/api/v1/transfers*` и explicit `/api/v1/transactions/{transactionId}/void` отсутствуют.
- Reports: `summary`, `category-breakdown`, `account-balances`, `cash-flow`, `transactions`.

Широкие строки ниже про users/profile, households, invites, memberships, exports, deletion/leave privacy flows, password reset, import/bank/SMS/push/broker integrations и debug/support остаются traceability backlog/post-MVP release gates. Они не являются published OpenAPI/client surface до отдельной runtime реализации и contract sync.

Базовый QA-инвариант: backend является источником прав. Клиент, route nesting, локальный кэш, search, autocomplete, reports, exports, debug/support output и background jobs не могут расширять видимость. Все финансовые данные фильтруются по access predicate до сортировки, pagination, count, aggregation, export, cache materialization и логирования.

## Endpoint surface coverage

| Surface | Routes | Обязательные подповерхности | Authz predicates | Сценарии | Release gates | QA evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Auth, sessions, reset | `POST /api/v1/users`, `POST /api/v1/sessions`, `GET /api/v1/sessions/current`, `DELETE /api/v1/sessions/current`, `POST /api/v1/password-resets`, `POST /api/v1/password-resets/confirmations`; `DELETE /api/v1/sessions` is post-MVP until revocation-all is safely exposed. | registration, login, current session, logout current session, reset request, reset confirm, rate limit | `isAuthenticated`, `isSelf`, session revocation, reset token verification | AS-REG-01..02, SEC-AUTH-01..03, SEC-RESET-01..02, SEC-RATE-01 | RG-07, RG-08, RG-10, RG-12 | Golden neutral auth/reset responses, session revocation tests, reset token replay/expiry tests, rate-limit output, log scan |
| Users/me | `GET /api/v1/users/me`, `PATCH /api/v1/users/me`, `GET /api/v1/users/me/memberships` | self profile, self update, self memberships, former membership metadata | `isSelf`, `canReadUserProfile`, `canMutateUserProfile` | AS-REG-02, PRIV-DEL-01, PRIV-LEAVE-01 | RG-01, RG-09, RG-10 | Self-only tests, cross-user denial, no email/security fields in household member views |
| Households | `GET /api/v1/households`, `POST /api/v1/households`, `GET /api/v1/households/{householdId}`, `PATCH /api/v1/households/{householdId}`, `POST /api/v1/households/{householdId}/archive` | list, create, detail, update, archive | `canCreateHousehold`, `canReadHousehold`, `canMutateHousehold`, `hasActiveMembership` | AS-FAM-01..03, NEG-MEM-01..02, PRIV-LEAVE-01..02 | RG-01, RG-02, RG-05, RG-09, RG-10 | Active member allow, invited/former/other denial, stale id tests, neutral errors |
| Invites | `GET/POST /api/v1/households/{householdId}/invites`, `GET /api/v1/invites/{inviteId}`, `POST /api/v1/invites/{inviteId}/accept`, `decline`, `revoke`, `resend` | list, create, detail, accept, decline, revoke, resend, replay | `canManageInvite`, `canReadInvite`, `canAcceptInvite`, `canDeclineInvite`, rate limit | AS-FAM-02, NEG-MEM-01, SEC-INV-01..02, SEC-RATE-01 | RG-05, RG-07, RG-08, RG-10 | Invite lifecycle tests, token hash/replay/expiry tests, resend no-token evidence, log scan |
| Memberships | `GET /api/v1/households/{householdId}/memberships`, `GET /api/v1/memberships/{membershipId}`, `POST /api/v1/memberships/{membershipId}/revoke`, `POST /api/v1/memberships/{membershipId}/leave` | list, detail, revoke, leave, session/cache invalidation | `canReadMembership`, `canManageMembership`, `canLeaveHousehold`, `hasActiveMembership` | AS-FAM-01..03, NEG-MEM-01..02, PRIV-LEAVE-01..02 | RG-05, RG-07, RG-09, RG-10 | Active member minimal list, former/invited no financial access, leave invalidates shared caches/sessions |
| Accounts | `GET /api/v1/accounts`, `POST /api/v1/accounts`, `GET/PATCH/DELETE /api/v1/accounts/{accountId}`, `POST /api/v1/accounts/{accountId}/archive`, `restore`, `GET /api/v1/accounts/autocomplete` | list, detail, create, update, archive, restore, delete, search filters, autocomplete | `canCreateAccount`, `canReadAccount`, `canMutateAccount`, `filterReadableAccounts`, `canAutocomplete` | AS-ACC-01..04, NEG-IDOR-01..03, PRIV-VIS-01..02 | RG-01, RG-02, RG-05, RG-10, RG-12 | A/B/C/Invited/Former matrix, list/detail equivalence, hidden id neutral responses, no hidden counts/autocomplete leaks |
| Transactions | `GET /api/v1/transactions`, `POST /api/v1/transactions`, `GET/PATCH/DELETE /api/v1/transactions/{transactionId}`, `POST /api/v1/transactions/{transactionId}/restore`, `GET /api/v1/transactions/autocomplete` | list, detail, create, update, delete, restore, search by q/date/amount/id, autocomplete, referenced ids | `canCreateTransaction`, `canReadTransaction`, `canMutateTransaction`, `filterReadableTransactions`, `canUseCategory`, `canSearch`, `canAutocomplete` | AS-OPS-01..04, AS-CAT-03, NEG-IDOR-04, NEG-CAT-01, NEG-ERR-01..02 | RG-01, RG-02, RG-08, RG-10, RG-12 | Account-scope inheritance tests, referenced-id neutral errors, no partial write, no raw payload logs |
| Transfers | `transactionType = transfer` on `/api/v1/transactions*`; no standalone `/api/v1/transfers*`, no explicit `/api/v1/transactions/{transactionId}/void` in mounted MVP | create, detail, list/search, update, delete as soft-delete/void-equivalent, restore, report inclusion, hidden counterparty | `canUseTransferScope`, `canCreateTransaction`, `canMutateTransaction`, `canReadTransaction`, `canReadReport` | NEG-TRN-01..04, NEG-MEM-01..02, SEC-LOG-02 | RG-02, RG-03, RG-04, RG-05, RG-06, RG-08, RG-10, RG-12, TR-RG-01..10 | Same-scope allow, unsupported scope deny, hidden-side golden errors, atomicity, balance consistency, concurrency, log scan |
| Categories | `GET /api/v1/categories`, `POST /api/v1/categories`, `GET/PATCH/DELETE /api/v1/categories/{categoryId}`, `POST /api/v1/categories/{categoryId}/archive`, `restore`, `GET /api/v1/categories/autocomplete` | list, detail, create, update, archive, restore, delete, search, autocomplete, category assignment | `canReadCategory`, `canMutateCategory`, `canUseCategory`, `filterReadableCategories`, `canAutocomplete` | AS-CAT-01..03, NEG-CAT-01, PRIV-VIS-01..02 | RG-01, RG-02, RG-10, RG-12 | Personal owner-only, household active-member only, autocomplete minimal output, no usage count leak |
| Reports | `GET /api/v1/reports/summary`, `category-breakdown`, `account-balances`, `cash-flow`, `transactions` | report mode validation, summary, breakdown, balances, trend, drill-down, filters, pagination, cache | `canReadReport`, `filterReadableAccounts`, `filterReadableTransactions`, `resolveVisibleCategoryScope` | AS-REP-01..04, NEG-REP-01, PRIV-VIS-01..02, PRIV-EXP-01 | RG-01, RG-02, RG-06, RG-08, RG-10, RG-12 | visibleAccountIds proof, filter-before-aggregate review, no hidden counts/facets snapshots, drill-down detail equivalence, cache key/invalidation tests |
| Exports, delete, leave | `POST/GET /api/v1/exports`, `GET /api/v1/exports/{exportId}`, `GET /api/v1/exports/{exportId}/files`, `POST /api/v1/users/me/deletion-requests`, `GET /api/v1/users/me/deletion-requests/{deletionRequestId}`, `POST /api/v1/households/{householdId}/leave-requests` | export create/list/status/download, deletion request/status, leave request, file TTL, owner-only download | `canExportData`, `isSelf`, `canLeaveHousehold`, session/cache invalidation | PRIV-EXP-01..02, PRIV-DEL-01, PRIV-LEAVE-01..02, NEG-MEM-02 | RG-05, RG-09, RG-10, RG-12, PF-RG-01..12 | Export diff vs visible lists/reports, former export exclusion, self-only deletion, leave invalidation, protected file lifecycle |
| Client, offline, cache | Android/PWA state model, PWA service worker, Android local persistence, report/export/search/autocomplete snapshots | navigation state, offlineReadonly, back stack, service worker cache, local DB, selectors, empty/error wording | Server predicates remain source of truth; client cache keyed by `viewerUserId`, session/access version, `householdId`, report mode, membership/access version | SEC-AUTH-03, NEG-MEM-02, PRIV-LEAVE-01, PRIV-EXP-02 | RG-05, RG-07, RG-09, RG-10, PF-RG-06 | Client snapshot tests, logout/leave/cache-clear tests, no hidden placeholders/counts, no reuse of `combined_viewer_overview` cache across viewers |
| Debug-like, support, logs, audit, backups | No user-facing MVP debug endpoint; any support/admin/debug/internal recalculation/export/report cache path | debug output, support tools, audit read, logs, telemetry, backups, restore, background recalculation | `canAccessDebugData`, `canWriteAuditEvent`, `canRunSystemRecalculation`, operational least privilege | SEC-LOG-01..02, SEC-SECRET-01, SEC-BACKUP-01 | RG-07, RG-08, RG-11, RG-12 | Route inventory proving absent debug bypass or same predicates/redaction, log/audit scans, secret scans, backup/restore evidence |

## Traceability matrix: scenarios to endpoints, predicates and gates

| Scenario family | Endpoint groups | Endpoint surfaces to test | Authz predicates | Gates | Required proof |
| --- | --- | --- | --- | --- | --- |
| AS-REG | Auth, sessions, users/me, accounts dashboard inputs | registration, login, current session, visible account/report bootstrap | `isAuthenticated`, `isSelf`, `filterReadableAccounts`, `canReadReport` | RG-01, RG-07, RG-10 | C after login sees no A/B data; A sees own personal plus shared AB only |
| AS-FAM | Households, invites, memberships, accounts, transactions, categories, reports | household list/detail, invite pending, membership leave/revoke, all shared financial lists | `hasActiveMembership`, `canReadHousehold`, `canReadMembership`, `canManageInvite` | RG-01, RG-02, RG-05, RG-09 | Active B sees shared AB; Invited and Former do not see shared list/detail/search/report/category/transfer |
| AS-ACC | Accounts | list, detail, autocomplete, state endpoints | `canReadAccount`, `canMutateAccount`, `filterReadableAccounts` | RG-01, RG-02, RG-10 | Owner-only personal account, active-member shared account, Other C neutral denial |
| AS-OPS | Transactions, accounts, categories | create, list, detail, search, update, restore/delete, autocomplete | `canCreateTransaction`, `canReadTransaction`, `filterReadableTransactions`, `canUseCategory` | RG-01, RG-02, RG-10 | Operations inherit account visibility; B cannot see A personal operations through list/detail/search |
| AS-CAT | Categories, transactions | list, detail, autocomplete, category assignment in transaction create/update | `canReadCategory`, `canUseCategory`, `filterReadableCategories` | RG-01, RG-02, RG-10 | Personal categories owner-only; household categories active-member only; foreign category assignment rejected |
| AS-REP | Reports, transactions drill-down, exports | summary, category breakdown, balances, cash-flow, report transactions, export | `canReadReport`, `canReadTransaction`, `canExportData` | RG-01, RG-02, RG-06, RG-08, RG-10 | `shared_family_report` shared-only; `combined_viewer_overview` viewer personal plus shared only; drill-down detail-equivalent |
| NEG-IDOR | Accounts, transactions, categories, reports | direct id, list filters, search by hidden id/text/date/amount, autocomplete | `canReadAccount`, `canReadTransaction`, `canReadCategory`, `canSearch`, `canAutocomplete` | RG-02, RG-10, RG-12 | Missing id and inaccessible id same shape; no hidden counts/facets/timing accepted as release evidence |
| NEG-REP | Reports | report filters, accountIds, categoryIds, householdId, drill-down cursor | `canReadReport`, visibleAccountIds validation, visible category validation | RG-02, RG-06, RG-10, RG-12 | Hidden filters rejected neutrally before aggregation; no hidden totals or breakdown |
| NEG-CAT | Transactions, categories | transaction create/update with foreign categoryId | `canUseCategory`, `canCreateTransaction`, `canMutateTransaction` | RG-02, RG-10 | `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` or safe compatible error without category details |
| NEG-TRN | Transactions as transfer API | create/update/list/detail/report/delete/restore transfer | `canUseTransferScope`, `canMutateTransaction`, `canReadReport` | RG-03, RG-04, RG-06, RG-08, RG-10, TR-RG-01..10 | Personal/shared denied; same-owner personal and same-household shared allowed; no partial write |
| NEG-MEM | Household, membership, all shared financial surfaces, client cache | direct URL, stale ids, stale cursors, old sessions, offline snapshots | `hasActiveMembership`, `canReadHousehold`, `canExportData`, cache/session invalidation | RG-05, RG-09, PF-RG-03, PF-RG-06 | Invited/Former cannot access detail/list/search/report/category/transfer/export/debug via old IDs or cache |
| NEG-ERR | All direct and referenced id endpoints | access-denied errors, validation errors, missing vs inaccessible | neutral error policy | RG-10, RG-12 | Golden snapshots show no object existence, owner, amount, name, description, email, token, stack/SQL detail |
| SEC-AUTH | All protected endpoints | anonymous access, logout, session mixing | `isAuthenticated`, session version/revocation | RG-07, RG-10 | Anonymous receives auth error; logout and reset revoke tokens; B never receives cached A data |
| SEC-RESET | Password reset, sessions | reset request/confirm, replay, expiry, old sessions | reset token verification, session revocation | RG-07, RG-08, RG-10 | Neutral email response, one-time token, no token logs, old sessions rejected |
| SEC-INV | Invites, households, shared financial surfaces | invite token read/accept/decline/revoke/replay, pre-accept app access | invite predicates, `hasActiveMembership` after accept only | RG-05, RG-07, RG-08, RG-10 | Invite token does not grant shared data before active membership; replay rejected |
| SEC-RATE | Auth/reset/invite | login, registration, reset, invite/resend | rate limit controls plus neutral responses | RG-07, RG-10 | 429 or approved throttling evidence without account/member enumeration |
| SEC-LOG | All financial/auth/privacy flows | allow, deny, validation failure, report/export/cache, transfer denial | audit/log boundaries | RG-08, RG-12 | Logs/audit contain safe metadata only; no amounts, names, descriptions, tokens, raw bodies |
| SEC-SECRET | Repo, config, bundles, DB, backups | route inventory, schema/config scan, sourceType rejection | out-of-scope controls | RG-11, RG-12 | No bank/API/SMS/push credentials, no import/bank endpoints, `sourceType = manual` only |
| SEC-BACKUP | Backup/restore/admin | backup access, encryption, restore, tenant boundaries | operational least privilege, restore validation | RG-07, RG-12 | Encrypted backup evidence, restore report, household/personal separation after restore |
| PRIV-VIS | Accounts, transactions, categories, reports, search, autocomplete | list, detail, search, report, export, client state | personal owner predicate, shared active membership predicate | RG-09, RG-10 | Personal A hidden from B/C; shared AB visible to A/B only |
| PRIV-EXP | Exports, reports, lists | export create/status/download, export data diff | `canExportData`, visible rows at generation time | RG-09, PF-RG-01..03, PF-RG-10 | Export equals visible scope; active member export excludes other personal data; former export excludes shared |
| PRIV-DEL | Deletion requests, sessions, memberships, shared history | create/status deletion, deactivation, session/cache cleanup | `isSelf`, deletion flow, `canLeaveHousehold` for membership closure | RG-09, PF-RG-04..05, PF-RG-11..12 | Self-only delete; remaining member sees no deleted user's personal profile/email/security data |
| PRIV-LEAVE | Leave requests, memberships, reports/exports/search/cache | leave, membership left, stale ids, old exports/offline snapshots | `canLeaveHousehold`, cache/session invalidation | RG-05, RG-09, PF-RG-06..08 | Future shared access revoked immediately; shared history remains for active members without former read |

## Report gates mapping

| Gate | Endpoint scope | Scenarios | Predicate/pipeline invariant | Required evidence |
| --- | --- | --- | --- | --- |
| REP-RG-01 Mode input validation | All `/api/v1/reports/*` | AS-REP-*, NEG-REP-01 | `reportMode`, `householdId`, `startDate`, `endDate`, `timezone` validated without hidden reads | Golden enum/date/household/filter errors |
| REP-RG-02 `shared_family_report` visible accounts | summary, breakdown, balances, cash-flow, drill-down | AS-REP-02, AS-REP-03, PRIV-VIS-02 | active member plus `ownershipType = shared` and requested `householdId` | A/B include only shared AB; C/Invited/Former denied; no personal A/B rows |
| REP-RG-03 `combined_viewer_overview` visible accounts | summary, breakdown, balances, cash-flow, drill-down | AS-REP-04, PRIV-EXP-01 | viewer personal where `ownerUserId = currentUserId` plus selected household shared | A sees shared AB + personal A; B sees shared AB + personal B; no cross-personal aggregates |
| REP-RG-04 Filter before aggregate | All report endpoints plus export/report cache | AS-REP-01..04, NEG-REP-01 | `accountId IN visibleAccountIds` before `SUM`, `COUNT`, `GROUP BY`, balances, trends, pagination, cache | Query/integration proof or reviewed code path plus failing tests for pre-filter aggregate |
| REP-RG-05 Hidden id neutral errors | report filters and drill-down cursors | NEG-REP-01, NEG-ERR-01 | supplied inaccessible/missing account/category/household ids use neutral shape | Golden missing vs inaccessible snapshots |
| REP-RG-06 No hidden counts/facets | all report DTOs and empty states | AS-REP-*, NEG-IDOR-03..04 | no `hiddenCount`, `filteredOutCount`, pre-filter `totalCount`, hidden facets | Schema snapshots and UI state snapshots |
| REP-RG-07 Drill-down equivalence | `/api/v1/reports/transactions`, `/api/v1/transactions/{transactionId}` | AS-REP-04, NEG-IDOR-04 | every drill-down row passes `canReadTransaction` for same actor | For each row, detail readable; hidden personal never appears |
| REP-RG-08 Cache invalidation | report caches/cursors/offline snapshots | NEG-MEM-02, PRIV-LEAVE-01 | cache key includes viewer/scope/membership/access versions | Leave/revoke invalidates reports, cursors and offline snapshots |
| REP-RG-09 Log/audit safety | report allow/deny/cache | SEC-LOG-01..02 | audit has safe metadata only | Log samples or scan output |
| REP-RG-10 Release closure | All report endpoints | RG-06, RG-08, RG-10, RG-12 | P0/P1 report visibility defect blocks release | QA sign-off with linked evidence |

## Transfer gates mapping

| Gate | Endpoint scope | Scenarios | Predicate/invariant | Required evidence |
| --- | --- | --- | --- | --- |
| TR-RG-01 Same-scope allow | `POST /api/v1/transactions` with `transactionType = transfer` | NEG-TRN-03..04 positive branches | `personal_same_owner`, `household_same_household` | Automated API tests pass for A own personal accounts and A/B shared AB accounts |
| TR-RG-02 Unsupported scope deny | transfer create/update | NEG-TRN-01..04 negative branches | personal/shared, cross-user personal, cross-household shared denied | Canonical `TRANSFER_SCOPE_NOT_SUPPORTED` or approved neutral response |
| TR-RG-03 Hidden side neutrality | transfer create/update errors/logs | NEG-TRN-01..04, NEG-ERR-02 | no side, owner, account name, balance, household, membership status in response/logs | Golden response and log scan |
| TR-RG-04 Atomicity | transfer create/update/delete/restore | NEG-TRN-*, SEC-LOG-02 | no partial transfer row or one-sided balance/projection on deny/failure | Integration tests with DB/projection assertions |
| TR-RG-05 Balance consistency | transfer lifecycle | NEG-TRN-03..04 | both sides apply/revert consistently for create/update/void/delete/restore | Balance/projection test evidence |
| TR-RG-06 Report safety | reports and exports containing transfers | AS-REP-*, PRIV-EXP-01 | reports filter visible transfers before totals, balances, trend, drill-down, export | Report tests with personal A/B and shared AB transfers |
| TR-RG-07 Membership safety | transfer detail/list/search/restore | NEG-MEM-01..02, PRIV-LEAVE-01 | invited/former cannot create/read/restore shared transfer, even with cached ids | Stale ID/session tests |
| TR-RG-08 Audit/log safety | transfer allow/deny | SEC-LOG-01..02 | no amount, description, account names, balances, tokens, raw payload | Log inspection |
| TR-RG-09 Concurrency | transfer update/restore/void | NEG-TRN-03..04 | stale `version` cannot double-apply, lost-update or half-apply | Concurrency tests |
| TR-RG-10 Escalation closure | product/API decisions | RG-12 | any request for personal/shared, cross-user or cross-household transfer is rejected or escalated | Traceable decision record |

## Security P0/P1 checklist mapping

| Severity | Checklist item | Endpoint surfaces | Scenarios/gates | QA evidence |
| --- | --- | --- | --- | --- |
| P0 | Endpoint reads/mutates/exports/aggregates personal data of another user | accounts, transactions, categories, reports, exports, debug | AS-ACC, AS-OPS, AS-CAT, AS-REP, PRIV-VIS, RG-01, RG-02, RG-09 | A/B/C/Invited/Former matrix across list/detail/search/autocomplete/report/export |
| P0 | Non-member gets shared Household data | households, memberships, accounts, transactions, categories, reports, exports | AS-FAM, NEG-IDOR, NEG-MEM, RG-05 | Other C denial and neutral errors for every shared surface |
| P0 | Invited/Former gets shared financial data | all shared surfaces, cache/offline/export | AS-FAM-02..03, NEG-MEM-01..02, PRIV-LEAVE, RG-05, PF-RG-03, PF-RG-06 | Pre-accept and post-left tests with old ids, sessions, cursors, export links, offline snapshots |
| P0 | Report aggregation before access filter | reports, exports, report cache | AS-REP, NEG-REP, RG-06 | visibleAccountIds before aggregate proof and tests |
| P0 | Unsupported transfer allowed | transactions transfer surface | NEG-TRN, RG-03, RG-04, TR-RG-02 | Transfer denial tests and no partial write |
| P0 | Tokens/secrets/plaintext credentials stored or logged | auth, reset, invite, sessions, config, logs, backups | SEC-RESET, SEC-INV, SEC-SECRET, RG-08, RG-11 | Secret scans, token lifecycle tests, log scans |
| P0 | Logs/debug output contains financial values or tokens | all financial/auth/privacy routes, debug-like paths | SEC-LOG, RG-08 | Production-like log/audit scan |
| P0 | Session/access cache not invalidated after logout/reset/leave/revoke | sessions, membership, reports, exports, cache/offline | SEC-AUTH, PRIV-LEAVE, RG-05, RG-07, PF-RG-06 | Revocation and cache invalidation tests |
| P0 | Backup/restore unsafe or absent | backups, restore, operational tools | SEC-BACKUP, RG-07 | Encrypted backup proof, restore test, tenant boundary verification |
| P0 | Out-of-scope import/bank/SMS/push credentials appear | API inventory, schema, config, sourceType | SEC-SECRET, RG-11 | Route/schema/config scan and sourceType rejection tests |
| P1 | Missing rate limit | auth, registration, reset, invite/resend | SEC-RATE, RG-07 | 429/progressive delay evidence with neutral response |
| P1 | User enumeration or non-neutral errors | auth/reset/invite/direct ids/referenced ids | SEC-RESET, SEC-INV, NEG-ERR, RG-10 | Missing vs inaccessible golden tests |
| P1 | Predicates not proven equivalent across surfaces | list/detail/search/autocomplete/report/export/debug | NEG-IDOR, RG-02, RG-10 | Predicate equivalence tests and route inventory |
| P1 | Audit missing for security-sensitive events | auth, membership, account, transaction, report/export, backup/restore | SEC-LOG, RG-08 | Audit schema/replay evidence |
| P1 | Cache/offline snapshots not invalidated | report/export/search/autocomplete/offline | NEG-MEM, PRIV-LEAVE, RG-05, PF-RG-06 | Version-keyed cache and invalidation tests |
| P1 | Transfer deny leaks hidden side | transfer errors/logs | NEG-TRN, RG-10, TR-RG-03 | Golden errors and logs |
| P1 | XSS/injection changes access or leaks diagnostics | filters, search, reports, client text fields | NEG-IDOR, NEG-ERR, SEC-LOG | Injection/security tests and safe diagnostics |
| P1 | Critical/high dependency/auth/crypto CVE | dependency surface | RG-12 | Dependency scan/SBOM |

## Privacy PF-RG mapping

| Gate | Endpoint surfaces | Scenarios | Predicates/rules | Required evidence |
| --- | --- | --- | --- | --- |
| PF-RG-01 Export visible-scope equivalence | `/api/v1/exports*`, list/report sources | PRIV-EXP-01..02 | `canExportData` uses same visible rows as list/report at generation time | Export file diff against visible lists/reports for Owner A, Member B, Other C, Invited, Former |
| PF-RG-02 No other-member personal export | exports, reports, account/category/transaction sources | PRIV-EXP-01, PRIV-VIS-01 | personal rows require `ownerUserId = currentUserId` | Active A/B exports exclude other personal accounts, transactions, categories, reports, balances, free text |
| PF-RG-03 Former member export denied for shared | exports, old export files, sessions, cache | PRIV-EXP-02, NEG-MEM-02 | former member has no shared financial read | After `left`/`revoked`, old ids/jobs/sessions do not return shared data or hints |
| PF-RG-04 Delete/deactivate self-only | deletion request create/status, sessions | PRIV-DEL-01 | `isSelf`, optional fresh auth | Cross-user deletion impossible; no partial writes |
| PF-RG-05 Delete does not expose personal data | shared history after deletion | PRIV-DEL-01, PRIV-LEAVE-02 | neutral deleted-user marker, no profile/email/security data | Review/tests for remaining active member views and reports |
| PF-RG-06 Leave revokes future access | leave request, membership leave, cache/offline/export/report/search | PRIV-LEAVE-01, NEG-MEM-02 | `canLeaveHousehold`, invalidate session/access/report/export/search/autocomplete/offline | Old ids, cursors, export files and offline snapshots blocked |
| PF-RG-07 Shared history integrity | shared reports/history for remaining active member | PRIV-LEAVE-02 | leaving does not delete shared history for active members, former gets no historical read | A can still build shared family report; Former B cannot read shared history |
| PF-RG-08 Neutral errors/no hidden counts | export/deletion/leave/financial direct ids | NEG-ERR-01..02 | neutral error policy | Missing vs inaccessible snapshots for export, deletion request, household, membership, account, transaction, category |
| PF-RG-09 Logs/audit privacy | export/delete/leave allow/deny/failure | SEC-LOG-01..02 | sanitized audit only | Log scan for no amounts, balances, names, descriptions, email plaintext, tokens, raw bodies, export contents |
| PF-RG-10 Export file lifecycle | export file storage/download | PRIV-EXP-01..02 | owner-only, protected, no public link, short TTL | Storage/config evidence and expired file tests |
| PF-RG-11 Retention/backups documented | backups, restore, deletion limits | SEC-BACKUP-01, PRIV-DEL-01 | closed-MVP backup/restore evidence, backup deletion uncertainty documented | Backup/restore report and risk register |
| PF-RG-12 Legal/Product/Security signoff | public launch, retention/deletion SLA, support/admin access, shared history ownership | RG-12 | out-of-scope or signed before release | Sign-off note or explicit out-of-scope decision |

## Test fixture matrix

| Actor | Membership state | Must see | Must not see | Core endpoint probes |
| --- | --- | --- | --- | --- |
| Owner A | active member Household AB, owner personal A | personal account/category/transactions A; shared account/category/transactions AB; own combined overview; shared family report AB | personal B; foreign shared C; hidden counts/facets; unsupported transfers | account/transaction/category list/detail/search/autocomplete; both report modes; export; transfer same-owner and same-household; leave/delete self |
| Member B | active member Household AB | personal B; shared AB; own combined overview; shared family report AB | personal A; foreign shared C; A personal aggregates/categories/balances | same probes as A, mirrored; direct IDs for A personal return neutral deny |
| Other C | no membership in Household AB | own personal C and own Household C data only | any Household AB shared/personal A/B data; AB invites/memberships/reports/exports | direct AB ids, list filters with `householdId=AB`, report filters, export shared request, invite/membership detail |
| Invited | pending invite, no active membership | minimal verified invite context only | shared AB accounts, transactions, categories, reports, exports, member list beyond invite minimum | invite accept/decline/replay; direct AB financial ids before accept; client pre-accept state |
| Former | `left` or `revoked` membership in AB | own personal data; optional minimal self membership metadata | current and historical shared AB financial data; old report/export/search/autocomplete/offline snapshots; member list | stale ids, stale cursors, old sessions, old export files, report cache, transfer restore/read |

Обязательные данные фикстур:

- personal accounts/categories/transactions for A and B;
- two personal accounts for A to test `personal_same_owner`;
- shared accounts/categories/transactions for Household AB;
- two shared accounts for AB to test `household_same_household`;
- foreign shared account/category/transactions for Household C;
- at least one transaction in each report bucket: summary, category breakdown, account balances, cash-flow, drill-down;
- transfer fixtures: allowed personal A->personal A2, allowed shared AB->shared AB2, denied personal A->shared AB, denied shared AB->personal A, denied personal A->personal B, denied shared AB->shared C;
- invite token states: pending, accepted, declined, revoked, expired;
- stale session/cache/export artifacts created before leave/revoke.

## MVP release minimal test suites

| Suite | Scope | Blocking gates | Minimum evidence |
| --- | --- | --- | --- |
| `mvp-auth-session-reset` | auth, sessions, reset, rate limit | RG-07, RG-08, RG-10 | login/register/reset neutral responses, logout/reset token revocation, replay/expiry, rate limit, no token logs |
| `mvp-household-invite-membership` | households, invites, memberships, leave/revoke | RG-05, RG-07, RG-09, RG-10 | active member allow, invited/former denial, invite token lifecycle, leave cache/session invalidation |
| `mvp-financial-authz` | accounts, transactions, categories | RG-01, RG-02, RG-10 | list/detail/search/autocomplete equivalence for A/B/C/Invited/Former; referenced-id neutral errors |
| `mvp-report-safety` | all report endpoints and report cache | RG-06, RG-08, RG-10, RG-12 | both report modes, visibleAccountIds before aggregation, no hidden counts/facets, drill-down detail equivalence, cache invalidation |
| `mvp-transfer-safety` | transfer via transactions | RG-03, RG-04, RG-06, RG-08, RG-10, TR-RG-01..10 | same-scope allow, unsupported deny, hidden-side neutrality, atomicity, balance consistency, concurrency, report safety |
| `mvp-privacy-flows` | export, delete/deactivate, leave, file lifecycle | RG-09, PF-RG-01..12 | export visible-scope diff, former export denial, self-only deletion, leave invalidation, protected file TTL, privacy sign-off |
| `mvp-client-cache-offline` | Android/PWA states, PWA service worker, Android local persistence | RG-05, RG-09, RG-10, PF-RG-06 | no hidden placeholders/counts, neutral errors, logout/leave clears protected state, report cache viewer-specific |
| `mvp-logs-secrets-backups` | logs, audit, telemetry, secrets, backups, restore | RG-07, RG-08, RG-11, RG-12 | log/audit scans, route/schema/config secret scans, out-of-scope endpoint scan, encrypted backup and restore tenant-boundary proof |
| `mvp-debug-bypass-inventory` | debug/support/internal jobs/background recalculation | RG-08, RG-10, RG-12 | prove absent in MVP or prove same predicates/redaction/audit; no raw request/response bodies |

## Coverage checklist by surface type

| Surface type | Required coverage | Primary suites |
| --- | --- | --- |
| List | accounts, transactions, categories, households, memberships, exports | `mvp-financial-authz`, `mvp-household-invite-membership`, `mvp-privacy-flows` |
| Detail | account, transaction, category, household, membership, invite, export job, deletion request | `mvp-financial-authz`, `mvp-household-invite-membership`, `mvp-privacy-flows` |
| Search | account/transaction/category search filters, report drill-down filters | `mvp-financial-authz`, `mvp-report-safety` |
| Autocomplete | accounts, transactions, categories | `mvp-financial-authz`, `mvp-client-cache-offline` |
| Report | summary, category breakdown, account balances, cash-flow, report transactions | `mvp-report-safety` |
| Export | export create/list/status/download/file lifecycle | `mvp-privacy-flows` |
| Debug-like | debug/support output, logs, audit, telemetry, background jobs, backups, offline snapshots | `mvp-debug-bypass-inventory`, `mvp-logs-secrets-backups`, `mvp-client-cache-offline` |

## Uncovered and risk list

### P0/P1 gaps

No explicit uncovered P0/P1 endpoint surface was found in the reviewed contracts. The source documents consistently require deny-by-default, personal owner-only access, active membership for shared data, report filtering before aggregation, same-scope transfers only, neutral errors, sanitized logs, no out-of-scope bank/import credentials, and former/invited denial.

Release still has evidence gaps until implementation test artifacts exist. These are expected QA proof obligations, not newly discovered contract conflicts:

- P0/P1 evidence gap: no actual automated test output is attached yet for RG-01..RG-12, TR-RG-01..10 or PF-RG-01..12.
- P0/P1 evidence gap: no route inventory is attached yet proving absence of debug/support bypass endpoints or out-of-scope import/bank/SMS/push endpoints.
- P0/P1 evidence gap: no log/audit/secret/dependency/backup/restore scan output is attached yet.
- P1 evidence gap: no concrete rate limit values are fixed in the reviewed contracts; release requires configured limits and test output.
- P1 evidence gap: exact auth stack, CSRF strategy and token/cookie storage are implementation decisions; release requires config evidence.
- P1 evidence gap: exact export file TTL is not fixed in API contract; privacy flow recommends short-lived protected storage, for example no more than 7 days, and release requires configured lifecycle evidence.

### Risks to watch during implementation

- Report implementation joins household members before resolving visible accounts and leaks personal rows through totals, balances, breakdown, trend, drill-down, export or cache.
- `combined_viewer_overview` cache is keyed only by `householdId` and leaks one viewer's personal rows to another viewer.
- Transfer denial distinguishes hidden counterparty details in response, timing, logs or validation `details`.
- Transfer write applies one side of balance/projection before authz, state, currency or concurrency checks complete.
- Search/autocomplete returns hidden matches, hidden counts, facets, suggestions or cursor metadata.
- Former member retains shared data through stale session, offline snapshot, report cache, export file or old cursor.
- Client empty/error copy implies that hidden data exists, for example "часть данных скрыта" or "у другого участника есть личные счета".
- Debug/support/admin/internal recalculation paths reuse service privileges without visible-scope predicates and redaction.
- Logs, crash reports or telemetry collect raw query payload, screenshots, transaction descriptions, amounts, account/category names or tokens.
- Out-of-scope source types or endpoints for imports, bank API, SMS/push, broker credentials or raw bank statements appear in implementation.

### Escalation triggers

Escalate to Product/Security/Privacy/Legal/Operations before release if any of these occur:

- product asks to show another household member's personal accounts, transactions, categories, balances, aggregates, reports or exports;
- product asks to allow personal/shared, cross-user personal or cross-household shared transfers;
- former members need historical shared access after `left`/`revoked`;
- support/admin/debug tooling needs financial values or hidden user data;
- report/export/debug cache cannot be scoped and invalidated by viewer, household, membership and access versions;
- public launch, SaaS/self-hosted commitment, jurisdiction, formal retention/deletion SLA, backup deletion promise, 2FA/passkeys or production secret manager becomes part of MVP;
- restore fails, backup storage is too broad, backup is incomplete or tenant boundaries are not preserved;
- repeated QA failure appears in access predicates, report aggregation, transfer neutrality/atomicity, cache invalidation, logs or privacy flows.

## Definition of Done trace

| DoD item | Status in this document |
| --- | --- |
| AS/NEG/SEC/PRIV/RG scenarios are linked to endpoint surfaces | Done in traceability matrix and endpoint coverage tables. |
| Coverage exists for list/detail/search/autocomplete/report/export/debug-like surfaces | Done in endpoint surface coverage and surface-type checklist. |
| Report gates are included | Done in Report gates mapping. |
| Transfer gates are included | Done in Transfer gates mapping. |
| Security checklist P0/P1 gates are linked to QA evidence | Done in Security P0/P1 checklist mapping. |
| Privacy PF-RG gates are linked to QA evidence | Done in Privacy PF-RG mapping. |
| Fixture matrix includes Owner A, Member B, Other C, Invited, Former | Done in Test fixture matrix. |
| Minimal MVP test suites are listed | Done in MVP release minimal test suites. |
| Uncovered/P0/P1 gaps are explicit | Done: no uncovered contract P0/P1 surface found; evidence gaps listed separately. |
