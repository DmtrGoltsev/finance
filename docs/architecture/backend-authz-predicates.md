# Предикаты авторизации backend MVP

## Статус и область

Документ фиксирует deny-by-default архитектуру авторизации backend access layer для MVP. Он уточняет, какие переиспользуемые predicates должны применяться к `Household`, `Membership`, `Invite`, `Account`, `Transaction`, `Category`, `Report`, export/debug поверхностям и связанным спискам.

Канон для MVP:

- `personal` всегда приватен и виден только владельцу `ownerUserId`;
- `shared` виден только active members того же `Household`;
- `Transaction` наследует доступ от счета или от пары счетов для `transactionType = transfer`;
- list/detail/search/autocomplete/report/export/debug используют одни и те же access predicates;
- фильтрация выполняется до агрегации, сортировки по чувствительным полям, count, totals, report breakdown, export и debug output;
- personal<->shared transfers запрещены;
- invited/former members не получают shared financial access;
- ошибки доступа нейтральны и не раскрывают существование недоступных объектов.

## Deny-by-default архитектура

Backend access layer является обязательной границей между API/service layer и чтением/записью финансовых данных. Любой endpoint, job, export, report, autocomplete, debug или internal tool получает доступ к объектам только через authz predicate или через уже построенный visible scope.

Архитектурные правила:

1. Сначала аутентификация. Без `currentUserId` доступны только auth/register/reset flows; все финансовые, household, invite-management и report/export/debug endpoints отвечают `UNAUTHENTICATED`.
2. Затем resolution scope. Backend определяет owner/scope объекта из БД, а не из route/body. Вложенный route вроде `/households/{householdId}/invites` является только hint и должен сверяться с фактическим `Invite.householdId`.
3. Затем predicate. Default decision - deny. Allow возникает только при явном совпадении `currentUserId = ownerUserId` для personal или active `Membership` для shared/household.
4. Затем state validation. После access allow проверяются business-state ограничения: archived/deleted mutability, immutable ownership, transfer scope, category type, invite status, member limit.
5. Затем data operation. Чтение, запись, агрегация, export и debug output выполняются только поверх visible rows или конкретного объекта, прошедшего predicate.
6. Затем audit. Access-sensitive actions и denies пишутся как audit event без финансовых значений, названий счетов/категорий, описаний, email, tokens и request/response body.

Access layer должен иметь два режима использования:

- object predicate для detail/mutation по конкретному id;
- scope filter для collection/report/export/search/autocomplete, возвращающий концептуальный фильтр видимых строк.

Запрещено иметь отдельные "упрощенные" проверки для autocomplete, report, export, debug, background recalculation или admin-support paths, если они возвращают пользовательские данные.

## Контракт predicate

Каждый predicate принимает:

- `actor`: authenticated `currentUserId`, session id/version, request id, optional client/app context;
- `action`: read, create, update, archive, delete, export, report, invite, leave, debug;
- `target`: resource id или draft payload, включая `accountId`, `transactionId`, `categoryId`, `householdId`, `inviteId`, `membershipId`, `reportMode`;
- `routeScope`: optional ids из URL/query; используется только для consistency check;
- `asOf`: время запроса для проверки expiry/status, но не для восстановления доступа former members;
- `includeArchived`: явный backend flag для history/admin-safe flows; не расширяет visibility.

Каждый predicate возвращает:

- decision: allow или deny;
- resolved scope: `personal:{ownerUserId}`, `household:{householdId}`, `system`, или none;
- safe error class: unauthenticated, neutral not found/not accessible, forbidden known context, validation/state;
- audit classification: no audit, audit allow, audit deny, audit state-deny;
- internal reason для logs/metrics без чувствительных payload values.

Internal reason не возвращается пользователю и не должен содержать финансовые значения, названия объектов, free text, email или tokens.

## Правила разрешения scope

### Account

`Account.ownershipType` является источником истины:

- `personal`: scope = `personal:{ownerUserId}`; `ownerUserId` обязателен; `householdId` не дает доступа.
- `shared`: scope = `household:{householdId}`; `householdId` обязателен; доступ только через active `Membership`.

`ownershipType` не меняется в MVP. Любая попытка изменить personal/shared должна отклоняться после проверки, что caller имеет доступ к самому account, с `ACCOUNT_OWNERSHIP_IMMUTABLE`.

### Transaction

`Transaction` наследует scope от `accountId`.

Для `transactionType = income`, `expense` или `brokerage`:

- основной `accountId` должен быть доступен через `canReadAccount`/`canMutateAccount`;
- `categoryId`, если задан, должен пройти `canUseCategory` для resolved account scope;
- `sourceType` в MVP должен быть `manual`.

Для `transactionType = transfer`:

- `accountId` и `counterpartyAccountId` обязательны;
- обе стороны должны быть доступны actor;
- разрешены только `personal_same_owner` и `household_same_household`;
- `personal<->shared`, cross-user personal и cross-household shared запрещены с `TRANSFER_SCOPE_NOT_SUPPORTED`;
- response и logs не раскрывают, какая сторона недоступна.

### Category

`Category.scope` является источником истины:

- `personal`: scope = `personal:{ownerUserId}`; видит и меняет только владелец.
- `household`: scope = `household:{householdId}`; видят и меняют active members household.

`shared` не является category scope value. Household category может быть видимой семье, но факт ее использования в personal transaction другого участника не должен раскрываться через category usage, counts, reports или autocomplete.

### Household, Membership, Invite

`Household` виден только active members. Invited user видит только минимальный verified invite context, достаточный для accept/decline, но не shared financial data и не полный состав семьи.

`Membership.status`:

- `active`: дает shared access к household scope;
- `invited`: не дает shared financial access;
- `left` и `revoked`: не дают shared financial access и не дают historical read через API;
- legacy `removed` трактуется как `revoked` при миграции/compatibility.

`Invite` является одноразовым token-bound flow. Resource id и token не взаимозаменяемы: token проверяется по hash, expiry и intended recipient; после accept/decline/revoke/expire повторное использование запрещено.

### Report, export, debug

`Report` не является источником прав. Он строится из visible rows:

- `shared_family_report`: только shared accounts/transactions/categories выбранного household, если actor active member;
- `combined_viewer_overview`: shared rows выбранного household для active member плюс personal rows самого viewer;
- personal rows другого участника исключаются до count, sum, balance, category breakdown, trend, drill-down, export и cache materialization.

Export возвращает только данные, которые actor видит в момент export. Former member export не включает former shared data, если нет нового Product/Security/Privacy решения.

Debug/support output не имеет привилегии обхода authz: он использует тот же visible scope и дополнительно редактирует чувствительные поля.

## Reusable predicates

### Base predicates

| Predicate | Назначение | Концептуальные joins/filters |
| --- | --- | --- |
| `isAuthenticated` | Подтвердить валидную session/token и `currentUserId`. | Хранилище session/token; статус user; revocation/session version. |
| `isSelf` | Разрешить доступ к собственному профилю/настройкам. | `User.id = currentUserId`. |
| `hasActiveMembership` | Подтвердить active участие в household. | `Membership` по `userId = currentUserId`, `householdId`, `status = active`, без active `endedAt`. |
| `hasVisibleHouseholdScope` | Построить набор household scopes actor. | Active memberships actor; household status, если учитывается archive. |
| `resolveVisibleAccountScope` | Построить видимый account filter для collections. | Accounts плюс active memberships; personal owner filter или shared household active membership filter. |
| `resolveVisibleCategoryScope` | Построить видимый category filter для collections. | Categories плюс active memberships; personal owner filter или household active membership filter. |

### User and profile predicates

| Predicate | Входы | Логика allow | Примечания |
| --- | --- | --- | --- |
| `canReadUserProfile` | `currentUserId`, `targetUserId`, optional `householdId` | Полный профиль только через `isSelf`. Minimal profile другого user только если оба являются active members одного household и endpoint явно возвращает minimal profile. | Email, auth settings и security fields не раскрываются другому member. |
| `canMutateUserProfile` | `currentUserId`, `targetUserId` | Только `isSelf`. | Deactivate/delete account требует отдельного privacy/account deletion flow и session revocation. |

### Household and membership predicates

| Predicate | Входы | Логика allow | Концептуальные joins/filters |
| --- | --- | --- | --- |
| `canCreateHousehold` | `currentUserId` | Authenticated user; MVP limit по числу active households применяется отдельной state validation. | User, active memberships count если MVP ограничивает один household. |
| `canReadHousehold` | `currentUserId`, `householdId` | Только active member. Invited user получает не household detail, а verified invite context. Former member получает deny. | Household join Membership по household/user/status. |
| `canMutateHousehold` | `currentUserId`, `householdId`, action | Active member может менять минимальные настройки, не расширяющие доступ и не меняющие финансовую историю. | Household, active Membership. Archive требует блокировки будущих shared mutations. |
| `canReadMembership` | `currentUserId`, `membershipId` или `householdId` | Active members видят минимальный состав household. Invited/former user видит только собственную invite/former metadata, если endpoint предназначен для профиля/audit. | Membership target плюс actor active Membership в том же household или `target.userId = currentUserId` для limited self metadata. |
| `canManageMembership` | `currentUserId`, `householdId`, target membership/action | Active member может create/revoke pending invite. Удаление active member другим member не разрешено без product/security решения. | Actor active Membership; target Membership/Invite; active member count. |
| `canLeaveHousehold` | `currentUserId`, `householdId` | Только собственная active membership может перейти в `left`. | Membership by actor/household/status active; transition audit. |

### Invite predicates

| Predicate | Входы | Логика allow | Концептуальные joins/filters |
| --- | --- | --- | --- |
| `canManageInvite` | `currentUserId`, `householdId`, optional `inviteId`, action create/revoke/resend | Active member household; pending invite belongs to same household; MVP member limit соблюден; rate limit применен. | Actor active Membership; Invite by household/status; active membership count; invite target uniqueness. |
| `canReadInvite` | invite token or `inviteId`, `currentUserId` optional | Verified intended recipient sees minimal invite context. Active member can see pending invites for own household without token secret. Others denied neutral. | Invite hash/status/expiresAt; intended email/user binding; actor active Membership for management views. |
| `canAcceptInvite` | `currentUserId`, invite token | Token hash valid, status `pending`, not expired, intended recipient matches authenticated user or verified email/identifier; member limit not exceeded. | Invite by token hash; recipient binding; Household; active membership count; existing Membership for user/household. |
| `canDeclineInvite` | `currentUserId`, invite token | Same verified recipient rules as accept; status `pending`; no shared financial access is granted. | Invite by token hash/status/expiresAt/recipient. |

### Account predicates

| Predicate | Входы | Логика allow | Концептуальные joins/filters |
| --- | --- | --- | --- |
| `canCreateAccount` | `currentUserId`, draft `ownershipType`, `ownerUserId`, `householdId` | Personal: `ownerUserId` absent or equal `currentUserId`. Shared: actor has active membership in `householdId`. | For shared: Membership by actor/household/status active. |
| `canReadAccount` | `currentUserId`, `accountId` or account row | Personal: `account.ownerUserId = currentUserId`. Shared: active membership in `account.householdId`. Invited/former denied. | Account; for shared join active Membership on `account.householdId`. |
| `canMutateAccount` | `currentUserId`, `accountId`, mutation | Same scope as `canReadAccount`; plus record not deleted; mutation cannot change `ownershipType`; archive/delete follows history rules. | Account; active Membership for shared; transaction existence for archive vs soft delete; version for concurrency. |
| `filterReadableAccounts` | `currentUserId`, optional filters | Возвращает только personal accounts actor плюс shared accounts из active memberships. Конфликтующие `ownerUserId`/`householdId` filters вне visible scope игнорируются или дают neutral deny. | Accounts left/semi-join active Memberships; record status filter; no hidden counts. |

### Transaction predicates

| Predicate | Входы | Логика allow | Концептуальные joins/filters |
| --- | --- | --- | --- |
| `canCreateTransaction` | `currentUserId`, draft transaction | `accountId` passes `canMutateAccount`; category passes `canUseCategory`; transfer counterparty passes same-scope transfer rules; `sourceType = manual` or user-confirmed capture draft resolved to manual-equivalent transaction. | Account primary; optional counterparty Account; Category; active Memberships for any shared side. |
| `canReadTransaction` | `currentUserId`, `transactionId` or transaction row | Primary account transaction проходит `canReadAccount`. Transfer detail не должен раскрывать недоступную counterparty; в MVP valid transfer требует один resolved scope, поэтому обе стороны читаемы. | Transaction join Account; optional counterparty Account for transfer; active Membership for shared accounts. |
| `canMutateTransaction` | `currentUserId`, `transactionId`, mutation | Existing transaction primary account passes `canMutateAccount`; new account/category/counterparty also pass create rules; deleted transaction not mutable except approved restore flow. | Transaction; current Account; proposed Account; Category; counterparty Account; active Memberships. |
| `filterReadableTransactions` | `currentUserId`, optional filters | Сначала строится `visibleAccountIds`, затем возвращаются transactions, где `accountId` входит в этот набор. Дополнительные filters не могут добавить accounts вне этого набора. | Transactions join visible Accounts; category/date/type filters применяются после authz filter. |
| `canUseTransferScope` | `currentUserId`, source account, counterparty account | Allow only same owner personal-personal or same household shared-shared with active membership. Deny personal/shared, cross-user personal, cross-household shared. | Both Account rows; active Membership for shared household. |

### Category and icon predicates

| Predicate | Входы | Логика allow | Концептуальные joins/filters |
| --- | --- | --- | --- |
| `canReadCategory` | `currentUserId`, `categoryId` or row | Personal: owner only. Household: active member only. | Category; active Membership for household category. |
| `canMutateCategory` | `currentUserId`, `categoryId`, mutation | Same scope as read; record not deleted; archive rules preserve historical transactions. | Category; active Membership; transaction usage for archive/soft delete. |
| `canUseCategory` | `currentUserId`, `categoryId`, resolved account scope, `transactionType` | Category must be readable by actor, have compatible type for income/expense, and match account scope: personal owner with personal account, or same household for shared account. Household category on personal transaction is allowed only if it does not expose usage to household reports/counters. | Category; Account resolved scope; active Membership; category type. |
| `filterReadableCategories` | `currentUserId`, optional filters | Personal categories owned by actor plus household categories in active memberships. No personal categories of other members. | Categories plus active Memberships; status filter. |
| `canUseIcon` | `currentUserId`, `iconId`, target category scope | Global icons: allow. Personal icons: owner only. Household icons: active member same household. | Icon row; active Membership if household icon. |

### Report, search, autocomplete and export predicates

| Predicate | Входы | Логика allow | Концептуальные joins/filters |
| --- | --- | --- | --- |
| `canReadReport` | `currentUserId`, `reportMode`, optional `householdId`, period/filters | `shared_family_report`: actor active member of selected household; data set only shared rows. `combined_viewer_overview`: actor active member for selected household shared part плюс own personal rows. Backend не должен подбирать другой household или расширять scope неявно. | Active Membership; visible Accounts; Transactions joined after account filter; Categories filtered by visible usage. |
| `canExportData` | `currentUserId`, export type/scope | Export only rows visible to actor at request time using the same filters as list/report. Former member export excludes former shared data by default. | Visible Accounts, Transactions, Categories, Membership self metadata; active Memberships; audit event. |
| `canSearch` | `currentUserId`, resource type, query/filters | Search executes only inside visible account/category/household scopes. Query text, ids, dates, sums and facets cannot reveal hidden matches. | Visible scope filters before text/date/amount filters; no hidden count/facet leak. |
| `canAutocomplete` | `currentUserId`, resource type, prefix/filters | Same as search, with stricter output minimization. Returns only visible labels/ids and no hidden counts. | Visible scope filters first; no cross-scope suggestions. |
| `canAccessDebugData` | `currentUserId`, requested scope/tool | Default deny. MVP product user debug endpoints may return only actor-visible sanitized rows. Support/admin debug needs separate product/security decision and audit. | Same visible scope filters plus field redaction; no raw request/response bodies. |

### Audit and system predicates

| Predicate | Входы | Логика allow | Концептуальные joins/filters |
| --- | --- | --- | --- |
| `canWriteAuditEvent` | system service context, sanitized event | Backend system may append audit events for auth, access, membership, account, transaction, category, report/export/security actions. | Service identity; schema validation excluding sensitive fields. |
| `canRunSystemRecalculation` | system service context, scope | System jobs may recalculate derived balances/reports only within explicit owner/household scope and must not materialize cross-scope aggregates. | Explicit job scope; accounts/transactions filtered by scope; audit/ops log. |
| `canReadAuditEvent` | actor/admin context, scope | Not a user-facing MVP capability except limited self/security history if defined. Operational access requires separate least-privilege/admin decision. | Separate operational authz; redaction; audit of audit access. |

## Консистентность collection, detail и aggregate

Для каждого resource должны выполняться equivalence rules:

- Detail по id возвращает объект только если тот же объект появился бы в соответствующем list для actor.
- List/search/autocomplete возвращают подмножество объектов, которые прошли бы detail predicate.
- Report/export строятся из тех же readable account/transaction/category rows, что list/detail.
- Facets, totals, count, pagination metadata и empty states считаются после access filter.
- Unknown id и known-but-inaccessible id дают одинаковую user-facing форму ответа.
- Route/query/body ids не могут расширить visible scope; они только сужают уже видимый набор или приводят к нейтральному deny.

Концептуальный порядок для collections:

1. Resolve actor visible scopes.
2. Apply base access filter.
3. Apply record-state filter (`active`, optional history mode).
4. Apply user filters/search/sort.
5. Compute pagination/count/facets only over filtered visible rows.
6. Shape response with allowed fields only.

Концептуальный порядок для reports/exports:

1. Validate report/export mode without reading hidden objects.
2. Resolve visible account set for that mode.
3. Filter transactions by visible account set.
4. Filter categories by visible usage and scope.
5. Apply period/type/category filters.
6. Aggregate/export only filtered rows.
7. Redact or omit fields forbidden for logs/debug/export profile.

## Маппинг нейтральных ошибок

| Сценарий | User-facing response | Примечания |
| --- | --- | --- |
| No valid session/token | `401 UNAUTHENTICATED` или `SESSION_EXPIRED` | Без подтверждения существования target. |
| Detail object missing or inaccessible | `404 RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` | Canonical neutral response for direct id. |
| Referenced account/category/household/invite inaccessible during create/update | `404 REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` или resource-specific neutral code | Не уточнять, какой id чужой. |
| Invite token invalid/missing/inaccessible | `404 INVITE_NOT_FOUND_OR_NOT_ACCESSIBLE` | Expired/revoked/used details допустимы только после verified invite context. |
| Caller authenticated but action forbidden in already-known own context | `403 ACTION_NOT_ALLOWED` | Например unsupported transition собственного объекта. |
| Membership not active and household existence must stay hidden | `404 RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` или neutral `MEMBERSHIP_NOT_ACTIVE` policy | Invited/former/other users не получают состав семьи или счетчики. |
| Personal/shared transfer | `422 TRANSFER_SCOPE_NOT_SUPPORTED` | Не раскрывать скрытую сторону transfer. |
| Ownership mutation | `422 ACCOUNT_OWNERSHIP_IMMUTABLE` | Только после access к account; иначе neutral 404. |
| Archived/deleted record mutation | `409 ARCHIVED_RECORD_NOT_MUTABLE` | Только если record уже safely visible actor. |
| List/search/autocomplete no accessible rows | `200 OK` с пустым результатом | Без hidden counts, hidden facets, "часть результатов скрыта". |
| Report/export no accessible rows | Empty report/export или neutral deny, согласно mode | Не показывать hidden totals/counts. |

Error `details` может содержать имена невалидных полей собственного запроса, но не содержит названия скрытых объектов, суммы, описания, category/account names, emails, tokens, stack traces, SQL errors, internal environment ids.

## Membership changes, cache и session implications

Изменение membership или invite status является security-sensitive событием и должно немедленно влиять на authz.

Triggers:

- invite accepted, declined, revoked, expired;
- membership created, activated, left, revoked;
- household archived/deactivated;
- password reset, logout, suspected compromise;
- account deletion/deactivation.

Обязательные эффекты:

- invalidate access-decision cache for affected `userId` and `householdId`;
- invalidate or narrow server-side sessions/refresh tokens for user losing shared access;
- clear report/export/search/autocomplete caches keyed by affected household/user scope;
- invalidate PWA/offline snapshots and require refresh before showing shared data;
- ensure old invite/reset/session tokens cannot be replayed;
- audit the membership/session/cache event with safe metadata only.

Access decisions must not be cached longer than the session/access-token validity unless cache key includes membership version/session version. Former members must not retain shared access because of stale materialized report/export/debug cache.

## Audit and logging boundaries

Audit required for:

- auth login/logout/failed login/password reset;
- invite create/accept/decline/revoke/expire;
- membership create/activate/left/revoked;
- account create/update/archive/delete/restore;
- transaction create/update/delete/restore and transfer denials;
- category create/update/archive/delete/restore;
- report/export generation for financial data;
- access denied for direct object ids or suspicious cross-scope attempts;
- cache/session invalidation after membership/security changes;
- backup/restore/admin access if operational tooling exists.

Audit event may contain:

- timestamp;
- actor user id or system actor id;
- action;
- target type and target id;
- scope type and scope id;
- result allow/deny/state-deny;
- request id;
- coarse IP/user-agent if allowed by privacy baseline;
- internal reason code without sensitive values.

Audit/log/telemetry must not contain:

- amounts, balances, report totals;
- transaction descriptions and user-entered free text;
- account/category names;
- emails in plaintext when avoidable;
- invite/reset/session/refresh tokens or token hashes if not needed;
- passwords, secrets, production configuration values;
- raw request/response bodies for financial endpoints;
- stack traces/SQL errors returned to users.

Denied access audit should record target type/id only when the id was supplied by caller and logging it is necessary for security investigation. It must not enrich the event with hidden object names, owners, balances or descriptions.

## Former и invited members

Invited member:

- may verify and accept/decline own invite through token-bound flow;
- may see only minimal invitation context after token/recipient verification;
- cannot read shared accounts, transactions, categories, reports, exports, search, autocomplete, debug data or member list beyond invitation minimum;
- after accept, shared access begins only after active membership is committed and caches/sessions reflect the new status.

Former member with `left` or `revoked`:

- keeps access only to own personal data and optional minimal self membership history;
- cannot read former shared accounts, transactions, categories, reports, exports, search, autocomplete or debug data;
- cannot use cached ids from prior participation;
- cannot receive hidden counts or "you used to have access" hints in financial endpoints;
- any historical shared read access requires Product/Security/Privacy escalation and a new predicate design.

## Proof obligations для QA и release gates

QA/release must provide evidence for each proof obligation:

| Obligation | Required evidence |
| --- | --- |
| `canReadAccount` blocks IDOR/BOLA | Tests for direct `accountId`, list, search, autocomplete across owner A, member B, other C, invited and former users. |
| `canMutateAccount` is scoped | Tests for create/update/archive personal owner only, shared active member only, immutable `ownershipType`, neutral errors for foreign ids. |
| `canReadTransaction` inherits account scope | Tests for direct `transactionId`, list, search and report drill-down for personal A/B, shared AB, foreign household. |
| `canMutateTransaction` validates all references | Tests for foreign `accountId`, foreign `categoryId`, hidden counterparty, archived records, no partial write on deny. |
| `canUseTransferScope` forbids mixed scope | Tests for personal->shared, shared->personal, cross-user personal, cross-household shared, plus allowed same-owner and same-household transfers. |
| `canUseCategory` prevents category leaks | Tests for personal category of another user, household category from another household, usage counters not revealing personal operations. |
| `canReadReport` filters before aggregation | Tests for totals, counts, balances, category breakdown, charts, trends, drill-down and export in both report modes. |
| `canExportData` matches visible data | Tests that active member export excludes other member personal data and former member export excludes former shared data. |
| Search/autocomplete consistency | Tests that query by hidden name/id/date/sum returns no hidden result, no hidden count/facet, no timing/error distinction accepted as release evidence. |
| Invited/former member denial | Tests before accept, after decline/revoke/expire, after `left`/`revoked`, with old ids and refreshed sessions. |
| Neutral errors | Golden response tests comparing missing id vs inaccessible id for account, transaction, category, report, invite and referenced ids. |
| Cache/session invalidation | Tests that membership `left`/`revoked` invalidates access cache, report/export cache and old refresh/session tokens. |
| Audit/log boundaries | Log inspection evidence for allow/deny/mutation/report/export flows showing no amounts, descriptions, names, tokens, secrets or raw bodies. |
| No debug bypass | Tests or review evidence that debug/support endpoints use same predicates and redaction, or are absent in MVP. |
| Release gate closure | RG-01..RG-12 from access-security scenarios pass; any P0/P1 authz/privacy defect blocks release unless formally accepted as release-blocker exception. |

Minimum scenario set must include:

- Owner A, Family Member B active in Household AB;
- Other User C outside Household AB;
- Invited Member before acceptance;
- Former Member after `left` or `revoked`;
- personal accounts/categories/transactions for A and B;
- shared account/category/transactions for AB;
- foreign shared account/category/transactions for Household C;
- both report modes and export.

## Risks and escalation triggers

Escalate before implementation or release if any of these occur:

- product asks to show personal accounts, transactions, categories or aggregates to another household member;
- product asks to allow personal<->shared transfers without a split-visibility model;
- former members must retain historical shared access after leaving;
- household model expands beyond two active members or adds roles/children/delegated access;
- support/admin tooling needs to read financial values;
- debug/export/report cache cannot be keyed and invalidated by user/household/membership version;
- bank APIs, imports, SMS/push or external financial credentials enter MVP;
- repeated QA failure in access predicates, neutral errors, logs, report aggregation or cache invalidation;
- legal/product decision changes export/delete/retention semantics for shared family data.

Until such decision is made, safe MVP default is deny, filter before aggregation, do not disclose hidden counts, and do not grant historical shared access to invited or former members.
