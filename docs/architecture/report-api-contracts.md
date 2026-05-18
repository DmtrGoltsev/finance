# Контракты Report API MVP

## 1. Статус и границы

Документ фиксирует backend-контракт W1-04 для `Report` API. Он уточняет `backend-api-contracts.md`, `backend-authz-predicates.md` и `access-model.md` для отчетов, агрегаций, drill-down и кэширования.

Канонические режимы:

- `shared_family_report` - отчет только по shared-данным выбранного `Household`.
- `combined_viewer_overview` - обзор по shared-данным выбранного `Household` плюс personal-данным текущего `viewerUserId`.

Запрещено добавлять режим, который показывает personal-данные другого участника прямо или косвенно. Personal второго участника не раскрывается через detail, aggregates, totals, counts, breakdowns, trends, balances, facets, drill-down, export, cache или error responses.

## 2. Общий query contract

Все endpoints требуют authenticated session и используют `currentUserId` из backend auth context. Клиент не передает `viewerUserId`; backend устанавливает `viewerUserId = currentUserId`.

Общие query params:

| Param | Required | Values / format | Правило |
| --- | --- | --- | --- |
| `reportMode` | yes | `shared_family_report`, `combined_viewer_overview` | Другие значения дают `INVALID_ENUM_VALUE`. |
| `householdId` | yes | resource id | Требует active `Membership`; не расширяет доступ. |
| `startDate` | yes | `YYYY-MM-DD` | Inclusive date-only boundary в `timezone`. |
| `endDate` | yes | `YYYY-MM-DD` | Inclusive date-only boundary; `endDate >= startDate`. |
| `timezone` | yes | IANA timezone | Обязателен для календарных периодов. |
| `accountIds` | no | comma-separated ids or repeated query param | Все id должны быть видимыми в выбранном mode. |
| `categoryIds` | no | comma-separated ids or repeated query param | Все id должны быть видимыми/допустимыми в выбранном mode. |
| `transactionTypes` | no | `income`, `expense`, `transfer`, `brokerage` | Allowlist enum; не расширяет scope. |
| `currency` | no | ISO 4217 uppercase | Сужает видимые rows; без FX-конвертации. |
| `status` | no | default `active` | `archived`/`deleted` только если endpoint явно поддерживает history mode; MVP reports по умолчанию не включают deleted. |

Дополнительные query params для cash flow:

| Param | Required | Values / format | Правило |
| --- | --- | --- | --- |
| `bucket` | no | `day`, `week`, `month` | Default `month`; bucket границы считаются в `timezone`. |

Дополнительные query params для drill-down:

| Param | Required | Values / format | Правило |
| --- | --- | --- | --- |
| `limit` | no | integer, default 50, max 100 | Применяется после visible filter. |
| `cursor` | no | opaque string | Не содержит открытые ids, суммы или query text. |
| `sort` | no | `occurredAt_desc`, `occurredAt_asc`, `amount_desc`, `amount_asc` | Sort allowlist; выполняется только на видимом наборе. |

Ошибки общего query:

- `UNAUTHENTICATED` для отсутствующей/истекшей session.
- `INVALID_ENUM_VALUE` для неизвестного `reportMode`, `transactionTypes`, `bucket` или `status`.
- `INVALID_DATE_RANGE` для некорректных дат, timezone или слишком широкого периода, если backend вводит лимит.
- `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` или neutral `MEMBERSHIP_NOT_ACTIVE` для отсутствующего/недоступного `householdId`.
- `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` для любого supplied `accountIds` или `categoryIds`, который не входит в видимый набор выбранного mode.

## 3. Endpoints

| Method | Route | Response DTO | Назначение |
| --- | --- | --- | --- |
| `GET` | `/api/v1/reports/summary` | `ReportSummaryDto` | Totals по видимым transactions периода. |
| `GET` | `/api/v1/reports/category-breakdown` | `ReportCategoryBreakdownDto` | Breakdown по видимым categories/uncategorized bucket. |
| `GET` | `/api/v1/reports/account-balances` | `ReportAccountBalancesDto` | Балансы только видимых accounts. |
| `GET` | `/api/v1/reports/cash-flow` | `ReportCashFlowDto` | Trend income/expense/net по bucket. |
| `GET` | `/api/v1/reports/transactions` | `ReportTransactionDrillDownDto` | Drill-down list по тем же predicates, что `/transactions`. |

Все endpoints являются вычисляемыми read endpoints. Они не создают user-visible `Report` resource id в MVP и не имеют detail route `/reports/{reportId}`.

## 4. Mode inputs и visibleAccountIds

### 4.1 `shared_family_report`

Required inputs:

- `reportMode = shared_family_report`;
- `householdId`;
- `startDate`, `endDate`, `timezone`;
- optional narrowing filters: `accountIds`, `categoryIds`, `transactionTypes`, `currency`, `bucket`.

Preconditions:

1. `currentUserId` authenticated.
2. `hasActiveMembership(currentUserId, householdId)` is true.
3. `Household` is readable by current user and not in a state that blocks reports.

`visibleAccountIds` resolution:

```text
visibleAccountIds =
  SELECT Account.id
  FROM Account
  WHERE Account.ownershipType = 'shared'
    AND Account.householdId = :householdId
    AND Account.status IN allowedReportStatuses
    AND hasActiveMembership(:currentUserId, Account.householdId)
```

If `accountIds` is supplied:

```text
effectiveAccountIds = suppliedAccountIds INTERSECT visibleAccountIds
require size(effectiveAccountIds) == size(unique(suppliedAccountIds))
```

If the size check fails, return `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`. Do not return which id failed and do not return hidden/filtered count.

Visibility proof:

- personal accounts have `ownershipType = personal`, therefore fail `Account.ownershipType = shared`;
- personal transactions inherit account scope, therefore no personal transaction can enter the report;
- shared accounts from other households fail `Account.householdId = householdId` and active membership check.

### 4.2 `combined_viewer_overview`

Required inputs:

- `reportMode = combined_viewer_overview`;
- `householdId`;
- `startDate`, `endDate`, `timezone`;
- optional narrowing filters: `accountIds`, `categoryIds`, `transactionTypes`, `currency`, `bucket`.

Preconditions:

1. `currentUserId` authenticated.
2. `viewerUserId = currentUserId`.
3. `hasActiveMembership(currentUserId, householdId)` is true for the shared part.

`visibleAccountIds` resolution:

```text
viewerPersonalAccountIds =
  SELECT Account.id
  FROM Account
  WHERE Account.ownershipType = 'personal'
    AND Account.ownerUserId = :currentUserId
    AND Account.status IN allowedReportStatuses

householdSharedAccountIds =
  SELECT Account.id
  FROM Account
  WHERE Account.ownershipType = 'shared'
    AND Account.householdId = :householdId
    AND Account.status IN allowedReportStatuses
    AND hasActiveMembership(:currentUserId, Account.householdId)

visibleAccountIds = viewerPersonalAccountIds UNION householdSharedAccountIds
```

If `accountIds` is supplied, every supplied id must be in `visibleAccountIds`; otherwise return `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`.

Visibility proof:

- personal accounts of another member have `ownerUserId != currentUserId`, therefore fail `viewerPersonalAccountIds`;
- only shared accounts of selected household enter `householdSharedAccountIds`;
- no join to `Membership.userId` of other active members is used to add personal accounts;
- aggregates, balances, category usage, trends and drill-down all read only rows whose `accountId` is in `visibleAccountIds`.

## 5. Aggregation pipeline proof

All report endpoints must follow the same ordered pipeline. Reordering is a release blocker.

1. Authenticate and resolve `currentUserId`.
2. Validate primitive query shape: enums, date formats, timezone, pagination shape. This step does not read hidden resources.
3. Validate `householdId` by active membership for the requested mode.
4. Resolve `visibleAccountIds` for the mode.
5. Validate supplied `accountIds` by set inclusion in `visibleAccountIds`; only then narrow to `effectiveAccountIds`.
6. Build `visibleTransactions` with `Transaction.accountId IN effectiveAccountIds`.
7. Apply record-state, date, transaction type, currency, amount and text filters to `visibleTransactions`.
8. Resolve category filters only against categories visible for the mode and against category ids used by `visibleTransactions`.
9. Aggregate, group, bucket, sort and paginate only the filtered visible rows.
10. Shape DTOs with allowed fields only.
11. Write sanitized audit/metrics event without amounts, balances, names, descriptions or raw query payload.

Formal invariant:

```text
aggregateInputRows = filterUserQuery(
  filterCategories(
    filterDateAndStatus(
      Transactions WHERE accountId IN visibleAccountIds
    )
  )
)

Report DTO fields = aggregate(aggregateInputRows)
```

There is no valid implementation path where `COUNT`, `SUM`, `GROUP BY`, `BALANCE`, `FACET`, `TREND`, `PERCENTAGE`, pagination metadata or cache materialization runs before `accountId IN visibleAccountIds`.

## 6. DTOs

Money values are decimal strings. `currency` is ISO 4217. MVP does not perform FX conversion; multi-currency reports return per-currency buckets.

### 6.1 Common DTOs

```json
{
  "ReportPeriodDto": {
    "startDate": "2026-05-01",
    "endDate": "2026-05-31",
    "timezone": "Europe/Moscow"
  },
  "ReportScopeDto": {
    "viewerUserId": "usr_123",
    "householdId": "hsh_123",
    "reportMode": "combined_viewer_overview",
    "includedAccountIds": ["acc_own", "acc_shared"],
    "generatedAt": "2026-05-17T10:00:00Z"
  },
  "MoneyTotalDto": {
    "currency": "RUB",
    "incomeTotal": "100000.00",
    "expenseTotal": "65000.00",
    "netTotal": "35000.00"
  }
}
```

`includedAccountIds` contains only visible account ids after filter resolution. It must not include ids rejected by filters, inaccessible ids, hidden ids or hidden count metadata.

### 6.2 `ReportSummaryDto`

```json
{
  "scope": {
    "viewerUserId": "usr_123",
    "householdId": "hsh_123",
    "reportMode": "combined_viewer_overview",
    "includedAccountIds": ["acc_own", "acc_shared"],
    "generatedAt": "2026-05-17T10:00:00Z"
  },
  "period": {
    "startDate": "2026-05-01",
    "endDate": "2026-05-31",
    "timezone": "Europe/Moscow"
  },
  "totalsByCurrency": [
    {
      "currency": "RUB",
      "incomeTotal": "100000.00",
      "expenseTotal": "65000.00",
      "netTotal": "35000.00"
    }
  ]
}
```

No `hiddenCount`, `filteredOutCount`, pre-filter `totalCount`, household member count or personal/shared split by owner is allowed.

### 6.3 `ReportCategoryBreakdownDto`

```json
{
  "scope": {},
  "period": {},
  "items": [
    {
      "categoryId": "cat_food",
      "categoryName": "Food",
      "categoryType": "expense",
      "categoryScope": "household",
      "currency": "RUB",
      "amount": "25000.00",
      "transactionCount": 12,
      "shareOfVisibleTotal": "0.3846"
    },
    {
      "categoryId": null,
      "categoryName": null,
      "categoryType": "expense",
      "categoryScope": null,
      "currency": "RUB",
      "amount": "1200.00",
      "transactionCount": 2,
      "shareOfVisibleTotal": "0.0185"
    }
  ]
}
```

Rules:

- `transactionCount` is allowed only for visible transactions in the bucket.
- `shareOfVisibleTotal` denominator is the visible filtered total for the same currency and category type.
- Personal category of another user is never returned. If another user's personal transaction used any category, that transaction is outside `visibleTransactions`, so category usage is also invisible.
- `categoryName` is returned only for categories readable by the viewer. Uncategorized visible rows use `categoryId = null` and do not imply hidden categories.

### 6.4 `ReportAccountBalancesDto`

```json
{
  "scope": {},
  "asOfDate": "2026-05-31",
  "timezone": "Europe/Moscow",
  "items": [
    {
      "accountId": "acc_shared",
      "accountName": "Shared cash",
      "accountType": "cash",
      "ownershipType": "shared",
      "householdId": "hsh_123",
      "ownerUserId": null,
      "currency": "RUB",
      "currentBalance": "50000.00",
      "balanceAsOf": "2026-05-31T20:59:59Z"
    },
    {
      "accountId": "acc_own",
      "accountName": "Personal cash",
      "accountType": "cash",
      "ownershipType": "personal",
      "householdId": null,
      "ownerUserId": "usr_123",
      "currency": "RUB",
      "currentBalance": "25000.00",
      "balanceAsOf": "2026-05-31T20:59:59Z"
    }
  ]
}
```

Rules:

- In `shared_family_report`, all items must have `ownershipType = shared` and `ownerUserId = null`.
- In `combined_viewer_overview`, personal items must have `ownerUserId = viewerUserId`; shared items have `householdId = requested householdId`.
- Balances for personal accounts of another member are never used for totals, chart points, account counts or sorting.

### 6.5 `ReportCashFlowDto`

```json
{
  "scope": {},
  "period": {},
  "bucket": "month",
  "points": [
    {
      "periodStartDate": "2026-05-01",
      "periodEndDate": "2026-05-31",
      "totalsByCurrency": [
        {
          "currency": "RUB",
          "incomeTotal": "100000.00",
          "expenseTotal": "65000.00",
          "netTotal": "35000.00"
        }
      ]
    }
  ]
}
```

Rules:

- Empty visible buckets may be returned with zero totals for chart continuity.
- Empty buckets must not encode hidden activity; zero means zero visible rows after filters.
- Trend calculations cannot use hidden rows for moving averages, percentages, deltas or baseline normalization.

### 6.6 `ReportTransactionDrillDownDto`

```json
{
  "scope": {},
  "period": {},
  "items": [
    {
      "id": "trn_123",
      "transactionType": "expense",
      "accountId": "acc_shared",
      "counterpartyAccountId": null,
      "categoryId": "cat_food",
      "amount": "250.00",
      "currency": "RUB",
      "occurredAt": "2026-05-17T09:30:00Z",
      "description": "Manual note",
      "sourceType": "manual",
      "createdByUserId": "usr_123",
      "lastEditedByUserId": "usr_123",
      "createdAt": "2026-05-17T10:00:00Z",
      "updatedAt": "2026-05-17T10:00:00Z",
      "version": 1
    }
  ],
  "page": {
    "limit": 50,
    "nextCursor": "cur_...",
    "hasMore": false
  }
}
```

Rules:

- `items` are regular `TransactionDto` rows after the same predicates as `/api/v1/transactions`.
- Detail access equivalence: every transaction returned by drill-down must pass `canReadTransaction(currentUserId, transactionId)`.
- A direct `/transactions/{transactionId}` that would be denied must never appear in report drill-down.
- Pagination metadata is computed only over visible filtered rows and has no `totalCount`.

## 7. Filters and neutral errors

### 7.1 Account filters

`accountIds` are resolved after `visibleAccountIds`. Supplied inaccessible, missing, archived-out-of-mode or wrong-mode accounts all return the same:

```json
{
  "error": {
    "code": "REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
    "message": "Ресурс не найден или недоступен.",
    "requestId": "req_..."
  }
}
```

Response must not identify which id failed, whether the id exists, account owner, account name, balance, ownership type or household.

### 7.2 Category filters

Category filter validation uses `resolveVisibleCategoryScope` plus transaction/account compatibility:

- `shared_family_report`: allowed categories are household categories of `householdId` that are readable by active members, plus `null` uncategorized visible transactions if supported by query.
- `combined_viewer_overview`: allowed categories are viewer personal categories, household categories of `householdId`, and categories actually used by visible transactions.
- Personal category of another user always fails neutral reference validation.

If `categoryIds` includes a hidden id, wrong-scope id, missing id or category incompatible with the effective visible account set, return `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` or `CATEGORY_SCOPE_MISMATCH` only after visibility is established. The response must not disclose category name, owner, usage count or whether hidden rows matched.

### 7.3 Transaction filters

`transactionTypes`, date range, `currency`, amount/search filters and drill-down sort are applied after `Transaction.accountId IN visibleAccountIds`.

Rules:

- Text search never runs over hidden descriptions.
- Amount filters never expose hidden min/max or hidden matches.
- Transfer transactions appear only if their readable representation passes `canReadTransaction`; personal/shared transfers are out of MVP and must not exist as report input.
- Filtered empty result returns an empty visible report, not "N hidden rows removed".

## 8. No hidden counts, facets and inference policy

Report API must not return:

- `hiddenCount`, `filteredOutCount`, `preFilterCount`, global `totalCount`;
- "found N, visible M" or equivalent text;
- facets/counts for hidden account, category, owner, member, currency, type or date buckets;
- category/account suggestions based on hidden rows;
- percentages whose denominator includes hidden rows;
- chart axis scaling, min/max, empty-state wording or timing intentionally derived from hidden rows;
- different error shape for missing id vs existing-but-inaccessible id.

Allowed counts:

- `transactionCount` inside category/cash-flow/account breakdown only after visible filtering;
- `hasMore` for drill-down pagination only after visible filtering;
- number of `items` actually returned to the viewer.

## 9. Caching and materialization constraints

Report cache is allowed only if cache keys encode the full visibility context:

```text
cacheKey = hash(
  reportEndpoint,
  reportMode,
  viewerUserId,
  householdId,
  membershipVersion,
  accountVisibilityVersion,
  categoryVisibilityVersion,
  transactionVersionWatermark,
  queryFilters,
  timezone
)
```

Constraints:

- Do not materialize cross-user personal aggregates.
- Do not share `combined_viewer_overview` cache between two viewers in the same household.
- `shared_family_report` cache may be shared only among active members of the same household if the cache key includes household membership/version and contains no viewer-personal rows.
- Cached rows must already be filtered to the mode's visible account set; raw pre-filter aggregate cache is forbidden for user-facing reports.
- Materialized report tables must store `scopeType` and `scopeId` such as `household:{householdId}` or `personal:{viewerUserId}`. Mixed scope materialization is forbidden unless split into separate scoped records and re-filtered before response.
- Membership changes (`active`, `left`, `revoked`), invite acceptance/revocation, account ownership/status changes, account archive/delete/restore, category archive/delete/restore and transaction create/update/delete/restore invalidate affected report caches.
- Former members must not retain shared report access through stale cache, offline snapshot or cursor.
- Drill-down cursors are scoped to `viewerUserId`, `reportMode`, `householdId`, filter hash and membership/access version.

Audit/metrics for cache hits and report generation may contain endpoint, mode, actor id, scope id, result allow/deny and request id. They must not contain amounts, balances, report totals, account/category names, transaction descriptions or raw query payload.

## 10. QA proof obligations

QA must provide evidence for each obligation before release:

| Obligation | Required evidence |
| --- | --- |
| Mode input validation | Golden tests for both modes with required `householdId`, date range, timezone and enum errors. |
| `shared_family_report` visible accounts | Tests with Owner A, Member B, Other C, Invited and Former users proving only shared account AB enters `includedAccountIds`, totals, balances, breakdown, cash flow and drill-down. |
| `combined_viewer_overview` visible accounts | Tests proving A sees shared AB + personal A, B sees shared AB + personal B, and neither sees the other's personal rows in any aggregate or drill-down. |
| Filter before aggregate | Query/integration evidence or code review checklist showing `accountId IN visibleAccountIds` before `SUM`, `COUNT`, `GROUP BY`, balance projection, trend buckets and pagination. |
| Hidden id neutral errors | Missing id and inaccessible id produce same user-facing response for `accountIds`, `categoryIds`, `householdId` and drill-down cursor scope. |
| No hidden counts/facets | Snapshot tests proving no `hiddenCount`, `filteredOutCount`, pre-filter `totalCount`, hidden facets or "partially hidden" messages. |
| Drill-down predicate equivalence | For every drill-down row, `/transactions/{transactionId}` is readable by the same user; hidden personal transactions never appear. |
| Category leak prevention | Personal category of another member is absent from breakdown, filters, names, counts and usage; household category usage from personal hidden transactions is not exposed. |
| Account balance leak prevention | Account balances endpoint never includes personal account B when viewer is A, including sorting, empty states and cache hits. |
| Cache invalidation | Membership `left`/`revoked`, invite accept/revoke, account/category/transaction mutation invalidate report caches and old cursors. |
| Log/audit boundaries | Log inspection for allow, deny, cache hit and cache miss shows no amounts, balances, descriptions, account/category names, tokens or raw payload. |
| Release gate closure | RG-01..RG-12 from `access-security-scenarios.md` pass, with explicit RG-06 evidence for both report modes. |

Minimum report fixture:

- Owner A and Family Member B active in Household AB;
- Other User C outside Household AB;
- Invited Member before acceptance;
- Former Member after `left` or `revoked`;
- personal accounts/categories/transactions for A and B;
- shared account/category/transactions for AB;
- foreign shared account/category/transactions for Household C;
- at least two currencies or explicit evidence that reports group by currency without FX conversion;
- transfers allowed only same-owner personal or same-household shared.

## 11. Release gates for Report API

Report API cannot ship unless:

- both canonical `ReportMode` values are implemented or explicitly feature-gated together with client behavior;
- all report endpoints use the same `visibleAccountIds` resolver for the selected mode;
- aggregation pipeline proof is reviewed and test-covered;
- drill-down is predicate-equivalent to transaction list/detail;
- neutral errors are golden-tested for missing vs inaccessible ids;
- no hidden counts/facets policy is verified in response schemas and snapshots;
- report cache keys include viewer/scope/membership/access versions;
- membership leave/revoke invalidates shared report access immediately;
- logs/audit are inspected for sensitive financial values;
- RG-06, RG-08, RG-10 and RG-12 from access-security scenarios are green.

Any P0/P1 defect in report visibility, aggregation order, neutral errors, cache invalidation or log redaction blocks release.

## 12. Risks and escalation triggers

Risks:

- A shared report implementation that joins household members before account visibility could accidentally include personal rows of another member.
- Category breakdowns can leak personal activity if they count category usage before filtering visible transactions.
- Account balance sorting/min/max can leak hidden personal balances if computed over pre-filter rows.
- Report caches can leak data across viewers if `combined_viewer_overview` is keyed only by `householdId`.
- Drill-down can bypass safety if it has a separate simplified predicate instead of using transaction list/detail predicates.

Escalate to Product/Security/Privacy before implementation if:

- a requested report mode needs personal data of another participant;
- a requested aggregate, count, comparison, household total, member contribution, facet or trend includes hidden personal data;
- former members need historical shared report access;
- support/admin/debug tooling needs report financial values;
- materialized reports cannot be scoped and invalidated by viewer/household/membership version;
- bank imports, SMS/push, external credentials or FX/revaluation enter the report surface.

Safe default: deny, filter before aggregation, return only visible rows, and omit any count or facet that would require hidden data.
