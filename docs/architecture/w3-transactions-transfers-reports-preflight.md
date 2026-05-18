# W3 transactions/transfers/reports backend preflight

Дата: 2026-05-17

Статус: preflight/gated implementation plan. W3 разрешен только для подготовки и последующей gated implementation; release остается в HOLD до автоматизированных evidence artifacts.

Запреты этого документа:

- не монтировать runtime routes без отдельного implementation worker и gate;
- не менять PWA/Android/OpenAPI implementation в рамках preflight;
- не расширять MVP за пределы manual transactions, same-scope transfers и двух report modes;
- не добавлять imports, bank API, SMS/push, broker/external credentials, support/debug bypass.

## Текущее состояние

Runtime backend сейчас смонтирован для auth/session, accounts и categories. `transactions`, `reports` и transfer-поведение в публичном runtime не смонтированы.

SQLAlchemy metadata уже содержит planned `transactions` table shape, но Alembic approved revisions создают только prerequisite slice:

- `20260517_0001_accounts_categories_slice.py`: users, households, memberships, accounts, categories;
- `20260518_0002_auth_sessions.py`: sessions;
- `20260518_0003_accounts_categories_immutable_scope_triggers.py`: immutable scope triggers для accounts/categories.

Следовательно W3 должен быть включением backend runtime поверх существующих contracts, а не переизобретением домена.

## Product invariants

- Personal всегда private: personal accounts/categories/transactions видит только `ownerUserId`.
- Shared financial data видят только active members того же `Household`.
- Invited и former не получают shared financial access.
- Report modes строго:
  - `shared_family_report`;
  - `combined_viewer_overview`.
- Transfers strictly same-scope:
  - `personal_same_owner`;
  - `household_same_household`.
- Любая mixed/cross scope transfer попытка deny без hidden-side details.
- Reports filter visible rows before count, sum, group, sort, pagination, balance projection, trend, cache/cursor materialization.

## Defaults без дополнительных вопросов

Вопросы пользователю не требуются: реализацию можно продолжать с безопасными defaults.

Принятые defaults:

- `sourceType = manual` only.
- Money хранится как `Numeric(20, 4)` и отдается decimal string.
- `currency` uppercase ISO 4217; FX conversion out of scope.
- `occurredAt` хранится timezone-aware UTC timestamp.
- `recordStatus`: ordinary reports/lists используют только `active`; deleted/voided history mode out of scope для MVP reports.
- `categoryId` required for income/expense; `categoryId = null` allowed only for transfer and for already visible uncategorized rows if existing contract keeps this bucket.
- Transfer API является specialization of `/api/v1/transactions`, отдельный `/transfers` resource не создается.
- Transfer `DELETE` is soft-delete/void-equivalent for user-facing API; hard delete forbidden.
- Reports are computed read endpoints; no persisted user-visible `Report` resource and no `/reports/{reportId}` route.
- Caches/cursors are optional; if implemented, they must include viewer, report mode, household, membership/access version and filter hash.
- Deny default: missing and inaccessible IDs share neutral public response shape.

## Implementation class

Класс сложности: high.

Причина: затрагиваются financial records, authorization, neutral errors, transfer atomicity, report aggregation order и evidence gates. Кодовые изменения локальны по surface, но privacy blast radius высокий. `xhigh` не требуется до тех пор, пока не вводятся платежи, external credentials, production migration или повторные P0/P1 failures.

## Domain model

### Transaction

Required persisted fields:

| Field | Type | Rule |
| --- | --- | --- |
| `id` | UUID public id | primary key |
| `transaction_type` | text enum | `income`, `expense`, `transfer`, `brokerage`; MVP write path may reject `brokerage` unless already contracted |
| `account_id` | UUID FK accounts | required, primary visible scope source |
| `counterparty_account_id` | UUID FK accounts nullable | required only for `transfer`; null otherwise |
| `category_id` | UUID FK categories nullable | required for `income`/`expense`; null for transfer |
| `amount` | Numeric(20,4) | positive only |
| `currency` | String(3) | uppercase ISO 4217; must match account currency; for transfer must match both accounts |
| `occurred_at` | timestamptz | user event time, stored UTC |
| `description` | text nullable | visible to all users who can read this transaction; never logged raw |
| `source_type` | text enum | `manual` only in MVP |
| `transfer_scope` | text nullable | backend-computed; only `personal_same_owner` or `household_same_household` |
| `transfer_status` | text nullable | `posted` or `voided`; transfer only |
| `record_status` | text enum | `active` or `deleted`; current report input excludes deleted |
| `created_by_user_id` | UUID FK users | actor at create |
| `last_edited_by_user_id` | UUID FK users | actor at last mutation |
| `created_at` | timestamptz | server timestamp |
| `updated_at` | timestamptz | server timestamp |
| `deleted_at` | timestamptz nullable | soft delete marker |
| `version` | bigint | optimistic concurrency |

Derived/public DTO fields:

- `transferScope` returned only for transfer rows;
- `transferStatus` returned only for transfer rows;
- account/category names are not embedded in `TransactionDto`;
- labels must be fetched through already visible account/category endpoints.

### Report

No persisted `reports` table for MVP. Report domain is a request-scoped view:

| Concept | Required fields |
| --- | --- |
| `ReportQuery` | `reportMode`, `householdId`, `startDate`, `endDate`, `timezone`, optional `accountIds`, `categoryIds`, `transactionTypes`, `currency`, `bucket`, `limit`, `cursor`, `sort` |
| `ReportScope` | `viewerUserId = currentUserId`, `householdId`, `reportMode`, `includedAccountIds`, `membershipVersion`, `generatedAt` |
| `VisibleReportDataset` | resolved visible account ids, visible transactions query, visible categories query |
| `ReportPage` | endpoint DTO plus post-visible `hasMore` only; no global `totalCount` |

If materialization is later approved, use a separate gated plan. It must split scope by `personal:{viewerUserId}` and `household:{householdId}` and must never store mixed cross-user personal aggregates.

## DB tables and migrations

### Required W3 migration sequence

1. `20260518_0004_transactions.py`
   - Create `transactions`.
   - Add CHECK constraints equivalent to metadata:
     - valid `transaction_type`;
     - valid `source_type`;
     - `source_type = 'manual'`;
     - `amount > 0`;
     - uppercase 3-letter `currency`;
     - transfer shape: counterparty present, different account, category null, valid transfer scope/status;
     - non-transfer shape: no counterparty, transfer scope/status null;
     - income/expense category requirement if retained by contract;
     - valid `record_status`.
   - Add indexes:
     - `(account_id, occurred_at DESC, record_status)`;
     - `(category_id, occurred_at DESC)` partial where category not null;
     - `counterparty_account_id` partial where not null;
     - `(created_by_user_id, occurred_at DESC)`;
     - `source_type`.
   - Downgrade: drop indexes and table only; no destructive rollback in production-like env without backup.

2. `20260518_0005_transaction_transfer_safety.py`
   - Add DB guard for same-scope transfer and same-currency transfer. CHECK alone is insufficient because it must compare two account rows.
   - Preferred PostgreSQL trigger:
     - on INSERT/UPDATE of `account_id`, `counterparty_account_id`, `transaction_type`, `currency`, `transfer_scope`;
     - load both accounts;
     - allow `personal_same_owner` only if both personal and same `owner_user_id`;
     - allow `household_same_household` only if both shared and same `household_id`;
     - reject personal/shared, cross-user personal, cross-household shared and currency mismatch.
   - Trigger error must be converted by service to safe public envelope; DB error text must not leak hidden account metadata.

3. Optional later migration, not required for first W3 runtime:
   - outbox/report cache invalidation tables if report caching is implemented.
   - audit table migration if runtime audit is not already approved.

### DB implementation notes

- Keep account/category immutable scope triggers in place.
- Do not use DB constraints as the only authorization mechanism; service predicates remain mandatory.
- For transfer mutations, service transaction boundary must include transaction row and both balance/projection effects if persisted `current_balance_amount` is updated.
- On deny/validation failure there must be no transaction row, no one-sided balance change and no audit allow event.

## Route subset

### Transactions

Mount only this subset after tests and gate are ready:

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/transactions` | list/search visible transactions |
| `POST` | `/api/v1/transactions` | create manual income/expense/transfer |
| `GET` | `/api/v1/transactions/autocomplete` | minimal visible suggestions only |
| `GET` | `/api/v1/transactions/{transactionId}` | visible detail |
| `PATCH` | `/api/v1/transactions/{transactionId}` | update mutable fields with full authz revalidation |
| `DELETE` | `/api/v1/transactions/{transactionId}` | soft delete / void-equivalent |
| `POST` | `/api/v1/transactions/{transactionId}/restore` | restore if still same-scope visible |
| `POST` | `/api/v1/transactions/{transactionId}/void` | explicit void if implementation distinguishes it |

Do not mount `/transfers`.

### Reports

Mount only computed read endpoints:

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/reports/summary` | totals by visible currency |
| `GET` | `/api/v1/reports/category-breakdown` | visible category buckets and visible `transactionCount` |
| `GET` | `/api/v1/reports/account-balances` | visible account balances only |
| `GET` | `/api/v1/reports/cash-flow` | visible bucket trend only |
| `GET` | `/api/v1/reports/transactions` | drill-down equivalent to transaction predicates |

Do not mount `/api/v1/reports/{reportId}`.

## Service/repository boundaries

### Files/modules to create by implementation workers

Expected backend module shape:

- `app/transactions/schemas.py`
- `app/transactions/repository.py`
- `app/transactions/service.py`
- `app/transactions/router.py`
- `app/reports/schemas.py`
- `app/reports/repository.py`
- `app/reports/service.py`
- `app/reports/router.py`

### Transactions repository

Repository responsibilities:

- map DB rows to persistence records;
- offer query builders that accept already resolved visible account IDs;
- perform create/update/delete/restore inside caller-provided SQLAlchemy session;
- lock or version-check transfer rows and affected account rows for balance/projection safety;
- never decide authorization by itself.

Recommended methods:

- `list_by_visible_accounts(visible_account_ids, filters, page)`;
- `get(transaction_id)`;
- `create(record)`;
- `save(record, expected_version)`;
- `soft_delete(transaction_id, expected_version)`;
- `restore(transaction_id, expected_version)`;
- `apply_transfer_balance_delta(source_account_id, counterparty_account_id, amount, direction, expected_versions)`.

### Transactions service

Service responsibilities:

- authenticate actor from request context;
- validate primitive request shape before hidden resource reads;
- resolve account/category references with authz predicates;
- compute transfer scope server-side;
- enforce `sourceType = manual`;
- coordinate DB transaction boundary;
- convert missing/inaccessible/unsupported cases to safe envelopes;
- emit sanitized audit/outbox events if those systems are mounted.

Service must not expose:

- hidden account/category/transaction existence;
- account owner/household/name/balance in transfer denials;
- raw `description`, `amount`, account/category names in logs/audit.

### Reports repository

Repository responsibilities:

- build visible transactions query only from `effectiveAccountIds`;
- aggregate only after visible account filter;
- return endpoint-specific projections;
- avoid pre-filter `COUNT`, `SUM`, `GROUP BY`, balance min/max or facet queries;
- provide drill-down rows with the same transaction DTO projection as `/transactions`.

Recommended methods:

- `resolve_shared_family_account_ids(actor, household_id)`;
- `resolve_combined_viewer_account_ids(actor, household_id)`;
- `validate_account_filter_subset(effective_visible_ids, supplied_ids)`;
- `validate_category_filter_subset(mode, visible_transactions_query, supplied_ids)`;
- `summary(query)`;
- `category_breakdown(query)`;
- `account_balances(query)`;
- `cash_flow(query)`;
- `drill_down(query, page)`.

### Reports service

Service responsibilities:

- validate report mode/date/timezone/filter enum shape;
- require active membership for selected `householdId`;
- resolve `visibleAccountIds` by mode;
- reject hidden supplied filters neutrally;
- call repository aggregations only after visibility resolution;
- shape DTO without hidden counts/facets/placeholders;
- scope any cache/cursor to viewer/mode/household/membership version/filter hash.

## Authz predicates

Required reusable predicates:

| Predicate | Purpose |
| --- | --- |
| `canReadTransaction(actor, transactionId)` | detail/read for a specific transaction |
| `canMutateTransaction(actor, transactionId, mutation)` | update/delete/restore after current row is visible |
| `filterReadableTransactions(actor, filters)` | list/search base filter; builds visible account ids first |
| `canUseTransactionAccount(actor, accountId, action)` | source account allow for create/update |
| `canUseTransactionCategory(actor, categoryId, resolvedAccountScope, transactionType)` | category compatible and visible |
| `canUseTransferScope(actor, sourceAccount, counterpartyAccount)` | allow only same-owner personal or same-household shared |
| `canReadReport(actor, reportMode, householdId)` | mode precondition and active membership |
| `resolveReportVisibleAccountIds(actor, reportMode, householdId)` | mode-specific visible accounts |
| `validateReportFilterIds(actor, mode, visibleAccountIds, accountIds, categoryIds)` | neutral reject for missing/wrong/hidden ids |

Predicate rules:

- Personal account/category/transaction: `owner_user_id == currentUserId`.
- Shared account/category/transaction: active membership in `household_id`.
- Invited/left/revoked memberships do not grant shared financial access.
- For transfer, both sides must be readable/mutable in the same resolved scope before write.
- For reports, `householdId` never widens personal scope; `combined_viewer_overview` adds only current viewer personal rows.

## Evidence tests

Minimum test families before runtime route release:

### Fixtures/contracts worker

- OpenAPI canonical route subset matches mounted runtime subset after gates.
- Schema only exposes MVP transaction/report fields.
- Fixtures include Owner A, Member B, Other C, Invited, Former.
- Golden neutral errors normalize missing vs inaccessible IDs.
- No hidden-count snapshot schema fields exist.

### Transactions DB runtime worker

- Alembic migration creates `transactions` with required constraints/indexes.
- SQLAlchemy metadata matches migration.
- Create/list/detail/update/delete/restore for visible personal and shared transactions.
- Foreign `accountId` and `categoryId` references deny neutrally.
- List/search/autocomplete filter by visible account ids before text/date/amount/sort/pagination.
- DB runtime matches in-memory/service tests if in-memory fallback remains.

### Transfer safety worker

- Allow `personal_same_owner`.
- Allow `household_same_household`.
- Deny personal->shared and shared->personal with `TRANSFER_SCOPE_NOT_SUPPORTED`.
- Deny cross-user personal and cross-household shared with no hidden-side details.
- Invited/former cannot create/read/restore shared transfers.
- Missing and inaccessible counterparty responses have safe public shape.
- Denied validation/authz/currency/concurrency does not write partial transfer or one-sided balance.
- Stale `version` cannot double-apply transfer effects.
- Logs/audit scan contains no amount, description, account names, balances, tokens or raw bodies.

### Report runtime safety worker

- Both report modes for Owner A and Member B.
- Other C, Invited and Former denied/empty behavior for AB.
- `shared_family_report` includes only AB shared accounts.
- `combined_viewer_overview` includes AB shared plus current viewer personal; excludes other member personal.
- `visibleAccountIds` artifact captured before aggregation.
- Supplied hidden/missing/wrong-mode account/category filters reject neutrally.
- Summary/category/balance/cash-flow/drill-down have no hidden counts/facets.
- Drill-down rows all pass `/transactions/{transactionId}` for same actor.
- Report cache/cursor, if implemented, invalidates on membership/account/category/transaction changes.

## Worker split

### W3-TTR-FIXTURES-CONTRACTS

Reasoning: medium.

Scope:

- tests and docs/evidence only;
- update route inventory tests only when implementation worker mounts routes;
- prepare fixture loader/golden snapshot structure.

Write scope:

- `apps/backend/tests/**`;
- `artifacts/evidence/**` or `MVP_EVIDENCE/**`;
- `docs/testing/**` if needed.

Must not write:

- runtime service/router code;
- migrations.

Definition of done:

- fixture labels and golden expectations exist;
- route subset assertions are ready for gated mount;
- privacy matrix obligations map to concrete tests.

### W3-TTR-TRANSACTIONS-DB-RUNTIME

Reasoning: high.

Scope:

- transaction domain DTOs/schemas;
- transaction repository/service/router;
- Alembic `transactions` migration;
- mount `/transactions` only after tests are green.

Write scope:

- `apps/backend/src/app/transactions/**`;
- `apps/backend/src/app/api/router.py`;
- `apps/backend/src/app/db/models.py` only if metadata drift is discovered;
- `db/migrations/versions/*transactions*.py`;
- transaction tests/evidence.

Definition of done:

- mounted transaction routes match contract;
- missing/inaccessible direct and referenced ids neutral;
- list/detail/search/autocomplete equivalent predicates;
- no excluded out-of-scope routes mounted.

### W3-TTR-TRANSFER-SAFETY

Reasoning: high.

Scope:

- transfer validation in transaction service;
- transfer DB guard/trigger if not done in DB runtime worker;
- transfer atomicity/balance behavior;
- transfer evidence.

Write scope:

- `apps/backend/src/app/transactions/**`;
- `db/migrations/versions/*transfer*.py`;
- transfer tests/evidence.

Definition of done:

- same-scope allow and unsupported-scope deny gates green;
- no partial write on all denied cases;
- logs/audit sanitized;
- report safety handoff fixture rows available.

### W3-TTR-REPORT-RUNTIME-SAFETY

Reasoning: high.

Scope:

- report schemas/repository/service/router;
- shared visible account resolver with transaction predicates;
- report evidence for filter-before-aggregate.

Write scope:

- `apps/backend/src/app/reports/**`;
- `apps/backend/src/app/api/router.py`;
- report tests/evidence.

Definition of done:

- both report modes green for A/B;
- C/Invited/Former denied/empty behavior green;
- no hidden counts/facets/placeholders;
- drill-down predicate equivalence proven.

## Required proof before release

Release remains HOLD until all are attached:

- backend pytest command output for W3 transaction/report/transfer suites;
- Alembic migration test output for transaction/transfer migrations;
- route inventory showing only approved W3 routes mounted;
- golden neutral error snapshots;
- no-hidden-count response snapshots;
- transfer atomicity/concurrency evidence;
- report filter-before-aggregate evidence with visibleAccountIds;
- log/audit scan evidence;
- P0/P1 risk register closed or explicitly still blocking release.

## Risks and escalation triggers

Escalate to Product/Security/Privacy before implementation continues if:

- product requests personal data of another member in any report;
- personal<->shared transfer is requested;
- cross-user personal or cross-household shared transfer is requested;
- former members need historical shared reads through API/export/report/cache;
- report materialization cannot be keyed by viewer/household/membership version;
- support/admin/debug needs financial values;
- imports, bank/SMS/push, broker/external credentials or FX conversion enter scope;
- QA repeatedly finds neutral error, report aggregation, transfer atomicity or log redaction failures.

Blocking implementation gaps known now:

- none requiring user decision.

Release blockers still present:

- W3 runtime routes absent by design;
- W3 automated evidence absent;
- transaction migration absent from approved Alembic revisions;
- transfer DB same-scope guard absent;
- report runtime and filter-before-aggregate evidence absent.
