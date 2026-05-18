# W3 TTR privacy and safety matrix

Дата: 2026-05-17

Scope: transactions, transfers and reports backend evidence matrix for W3. This is a test/evidence planning artifact, not runtime implementation.

## Canonical actors and scopes

| Actor | State | Personal visibility | Shared AB visibility | Foreign C visibility | Notes |
| --- | --- | --- | --- | --- | --- |
| Owner A | active member of AB | own A personal only | AB shared | none unless also member of C | baseline owner/member proof |
| Member B | active member of AB | own B personal only | AB shared | none unless also member of C | mirror proof; must not see A personal |
| Other C | not member of AB, active in C | own C personal | none for AB | C shared | cross-household denial |
| Invited | pending invite to AB | own personal only | none | none unless separately active elsewhere | token/invite is not financial access |
| Former | left/revoked from AB | own personal only | none, including historical old ids | none unless separately active elsewhere | stale cache/session/cursor denial |

Invariant: active household membership grants access only to household/shared rows. It never grants access to another member's personal rows.

## Transaction visibility matrix

| Resource | Owner A | Member B | Other C | Invited AB | Former AB | Required evidence |
| --- | --- | --- | --- | --- | --- | --- |
| A personal transaction | allow read/mutate if owner | deny neutral | deny neutral | deny neutral | deny neutral | detail/list/search/autocomplete; missing vs inaccessible same shape |
| B personal transaction | deny neutral | allow read/mutate if owner | deny neutral | deny neutral | deny neutral | cross-personal leakage proof |
| AB shared transaction | allow as active member | allow as active member | deny neutral | deny neutral | deny neutral after leave/revoke | active member only; stale old id denial |
| C shared transaction | deny neutral unless A member of C | deny neutral unless B member of C | allow if active C member | deny neutral | deny neutral | cross-household denial |
| Missing transaction id | neutral not found/not accessible | neutral not found/not accessible | neutral not found/not accessible | neutral not found/not accessible | neutral not found/not accessible | identical public envelope vs inaccessible |

Rules:

- List/search/autocomplete must build visible account ids before query text/date/amount/sort/pagination.
- Detail must be equivalent to list membership: if detail allows, row would appear in visible list under matching filters.
- No list envelope may include hidden `totalCount`, `hiddenCount`, `filteredOutCount`, hidden facets or "partially hidden" copy.
- Error body must not contain amount, description, account/category names, owner, household, SQL or stack traces.

## Category/account reference matrix for transaction writes

| Request reference | Visible compatible | Missing | Inaccessible personal | Inaccessible household | Wrong scope/type |
| --- | --- | --- | --- | --- | --- |
| `accountId` for income/expense | allow after state checks | `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` | same public shape | same public shape | same public shape or safe validation only after visible |
| `categoryId` for income/expense | allow if visible and compatible with account/type | `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` | same public shape | same public shape | `CATEGORY_SCOPE_MISMATCH` only after category visibility is established |
| `counterpartyAccountId` for transfer | proceed to same-scope validation | neutral/safe transfer denial | safe transfer denial | safe transfer denial | `TRANSFER_SCOPE_NOT_SUPPORTED` without side details |

Evidence must compare missing and inaccessible responses for each direct/referenced id family.

## Transfer safety matrix

| Scenario | Expected result | Public error/details | Persistence proof | Report proof |
| --- | --- | --- | --- | --- |
| A personal -> A personal | allow, `personal_same_owner` | n/a | one logical transfer, both balance effects atomic | appears only in A `combined_viewer_overview` if transfer presentation included |
| B personal -> B personal | allow, `personal_same_owner` | n/a | mirror proof | appears only in B combined overview |
| AB shared -> AB shared by A | allow, `household_same_household` | n/a | actor A recorded safely | visible to A/B shared reports |
| AB shared -> AB shared by B | allow, `household_same_household` | n/a | actor B recorded safely | visible to A/B shared reports |
| personal -> shared | deny | `TRANSFER_SCOPE_NOT_SUPPORTED`; no account side details | no row, no one-sided balance, no allow audit | no trace in reports |
| shared -> personal | deny | same safe public shape | no row/effect | no trace |
| A personal -> B personal | deny | no B owner/name/balance/membership details | no row/effect | no trace |
| AB shared -> C shared | deny | no C household/account details | no row/effect | no trace |
| Invited AB shared transfer | deny | neutral; invite is not membership | no row/effect | no trace |
| Former restore/read AB transfer | deny | neutral with old id/session/cache | no restore/effect | no old shared report access |
| missing counterparty | deny | indistinguishable from hidden counterparty where policy requires | no row/effect | no trace |
| visible cross-currency own transfer | deny | `INVALID_CURRENCY` only when both accounts are visible | no row/effect | no trace |

Required denial checks:

- public response does not say source/counterparty failed;
- no account names, owner ids, household ids, balances, amounts or descriptions in details;
- logs/audit do not contain raw request/response body or hidden-side metadata;
- timing differences are not intentionally introduced as an existence signal.

## Report privacy matrix

### Mode: `shared_family_report`

| Actor | Household AB input | Included accounts | Excluded accounts | Expected result |
| --- | --- | --- | --- | --- |
| Owner A | active AB | AB shared only | A personal, B personal, C shared | allow |
| Member B | active AB | AB shared only | A personal, B personal, C shared | allow |
| Other C | not AB member | none | all AB | neutral deny or empty per endpoint contract; no AB existence leak |
| Invited AB | invited only | none | all AB | neutral deny; invite does not grant report |
| Former AB | left/revoked | none | all AB including historical | neutral deny; stale cursor/cache invalid |

### Mode: `combined_viewer_overview`

| Actor | Household AB input | Included accounts | Excluded accounts | Expected result |
| --- | --- | --- | --- | --- |
| Owner A | active AB | A personal + AB shared | B personal, C shared | allow |
| Member B | active AB | B personal + AB shared | A personal, C shared | allow |
| Other C | not AB member | none for AB | all AB | neutral deny or empty; no AB details |
| Invited AB | invited only | own personal is not combined with AB without active membership | all AB | neutral deny |
| Former AB | left/revoked | own personal only is not enough for AB combined mode | all AB historical/current | neutral deny |

Report endpoints must prove:

- `summary`: totals by visible currency only.
- `category-breakdown`: `transactionCount` counts visible transactions only.
- `account-balances`: balances only for visible accounts; owner id allowed only for current viewer personal rows.
- `cash-flow`: buckets and axis/baseline derive only from visible rows.
- `reports/transactions`: every row passes `canReadTransaction` and direct `/transactions/{id}` for same actor.

Forbidden report fields and signals:

- `hiddenCount`;
- `filteredOutCount`;
- `preFilterCount`;
- global `totalCount`;
- hidden owner/member contribution;
- household-wide personal totals;
- hidden facets/suggestions;
- chart min/max/axis based on hidden rows;
- "some rows hidden" or equivalent copy;
- `includedAccountIds` containing rejected, hidden or inaccessible ids.

Allowed counts:

- number of returned items;
- post-visible `transactionCount` inside visible buckets;
- post-visible `hasMore` for drill-down pagination.

## Missing vs inaccessible matrix

| Surface | Missing id | Existing but inaccessible id | Expected invariant |
| --- | --- | --- | --- |
| `/transactions/{transactionId}` | neutral 404 | same neutral 404 | same code/message/details shape |
| transaction `accountId` reference | neutral referenced-resource error | same public shape | no owner/account/household detail |
| transaction `categoryId` reference | neutral referenced-resource error | same public shape | no category name/usage detail |
| transfer `counterpartyAccountId` | safe transfer/reference denial | same public shape where policy requires | no hidden side identified |
| report `householdId` | neutral not found/not accessible | same public shape | no household/member detail |
| report `accountIds` filter | neutral referenced-resource error | same public shape | no failed id disclosed |
| report `categoryIds` filter | neutral referenced-resource error | same public shape | no name/owner/usage count |
| report/drill-down cursor | neutral invalid/inaccessible cursor | same public shape for stale foreign cursor | no scope or row count detail |

Snapshot requirements:

- normalize `requestId`, timestamps, generated ids and cursors;
- compare response body keys and safe details exactly;
- assert forbidden terms/fields are absent.

## Evidence matrix by worker

| Worker | Evidence buckets | Must prove |
| --- | --- | --- |
| W3-TTR-FIXTURES-CONTRACTS | `golden/neutral-errors`, `golden/no-hidden-counts`, `fixtures/ttr` | canonical actor graph, missing/inaccessible snapshots, schema fields |
| W3-TTR-TRANSACTIONS-DB-RUNTIME | `api/transactions`, `db/migrations`, `privacy/transactions` | route subset, DB constraints/indexes, list/detail/mutation privacy |
| W3-TTR-TRANSFER-SAFETY | `transfers/same-scope-allow`, `transfers/unsupported-deny`, `transfers/atomicity`, `security/logs-audit` | same-scope allow, unsupported deny, no partial write, sanitized logs |
| W3-TTR-REPORT-RUNTIME-SAFETY | `reports/visible-account-ids`, `reports/filter-before-aggregate`, `reports/drilldown-equivalence`, `reports/no-hidden-counts` | both report modes, visible-first aggregation, no hidden signals |

## Release gate mapping

| Gate | W3 evidence |
| --- | --- |
| RG-02 | hidden transaction/report/transfer direct-id and filter abuse |
| RG-03 | personal/shared transfer denial |
| RG-04 | allowed same-owner and same-household transfers |
| RG-05 | invited/former shared denial, stale ids/caches |
| RG-06 | report filter-before-aggregate |
| RG-08 | logs/audit minimization |
| RG-10 | neutral missing vs inaccessible errors |
| RG-12 | P0/P1 risk closure |
| TR-RG-01..10 | full transfer safety suite |

## Definition of done

This matrix is complete when:

- actors owner/member/other/invited/former are covered;
- personal/shared visibility is explicit for transactions, transfers and reports;
- missing vs inaccessible expectations are explicit for direct ids, referenced ids, filters and cursors;
- report aggregation forbids hidden counts/facets and hidden denominator use;
- transfer same-scope allow and unsupported denial are mapped to persistence/report/log evidence;
- worker evidence buckets and release gates are mapped.

Current status: planning complete, runtime evidence not run.
