# Backend API contracts MVP

## 1. Статус и границы

Документ фиксирует контракт backend API для Wave 1 MVP. Он не заменяет `access-model.md`, `security-baseline.md` и `privacy-baseline.md`: здесь описаны routes, DTO, ошибки и authz-предикаты, а детальная реализация проверок остается задачей W1-03.

MVP поддерживает ручной ввод: `sourceType = manual`. Импорт файлов, банковские API, полноценные SMS/push-интеграции, банковские и брокерские credentials, внешние платежи и автоматическая синхронизация не входят в API surface MVP. Post-MVP safe auto-capture является отдельной draft-only surface: Android opt-in, no raw SMS/notification body server-side, structured draft with `idempotencyKey`/`evidenceHash`, transaction только после user confirm/edit.

Канонические правила wire contract:

- base path: `/api/v1`;
- routes: plural lowercase kebab-case;
- path params в документации: camelCase, например `{householdId}`;
- DTO fields: camelCase;
- enum values: lower_snake_case;
- error codes: UPPER_SNAKE_CASE;
- canonical API terms: `Household`, `Transaction`, `Membership`, `Invite`, `Account`, `Category`, `Report`;
- report modes: `shared_family_report`, `combined_viewer_overview`;
- personal данные всегда приватны и видны только владельцу.

## 2. API design principles

1. **Deny by default.** Каждый endpoint требует явного разрешения по `currentUserId`, `ownerUserId`, active `Membership` или verified invite/reset context.
2. **Authz на сервере.** UI-фильтры, UUID, route nesting и скрытые поля клиента не считаются контролем доступа.
3. **Один scope на финансовый объект.** `Account.ownershipType` равен `personal` или `shared`; `Category.scope` равен `personal` или `household`; `Transaction` наследует видимость от счета.
4. **Фильтрация до агрегации.** Reports, export, search, autocomplete и list сначала применяют access predicate, затем сортировку, пагинацию, group by, sum и balance calculations.
5. **Нейтральные ошибки доступа.** API не подтверждает существование недоступного объекта, чужого email, invite token, reset token, account, category, transaction или household.
6. **No hidden counts.** Ответы не возвращают `hiddenCount`, `filteredOutCount`, global `totalCount` до access filter или сообщения вида "найдено N, доступно M".
7. **Sensitive data minimization.** Errors, logs, audit и telemetry не содержат суммы, остатки, описания операций, названия счетов/категорий, email, invite/reset/session tokens.
8. **Manual or confirmed draft only.** Создание `Transaction` в MVP принимает `sourceType = manual`; post-MVP capture draft не создает transaction напрямую и становится manual-equivalent transaction только после user confirm/edit.

## 3. Общие DTO и ошибки

### 3.1 Error response

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
    "message": "Ресурс не найден или недоступен.",
    "requestId": "req_01h..."
  }
}
```

`details` допустим только для собственных невалидных полей запроса, например `field`, `reason`, `allowedValues`. `details` не содержит скрытые object names, суммы, owner email, tokens, stack traces или SQL text.

Основные общие ошибки:

| Code | HTTP | Когда используется |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Нет валидной session/token. |
| `SESSION_EXPIRED` | 401 | Session/token истек или отозван. |
| `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` | 404 | Detail/read/update/delete по id вне access scope или несуществующий id. |
| `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` | 404 | Чужой или несуществующий referenced id в create/update. |
| `ACTION_NOT_ALLOWED` | 403 | Объект уже безопасно раскрыт caller, но действие запрещено состоянием/ролью MVP. |
| `VALIDATION_FAILED` | 400 | Невалидная форма запроса. |
| `INVALID_ENUM_VALUE` | 400 | Значение enum не входит в canonical set. |
| `INVALID_DATE_RANGE` | 400 | Невалидный период или range. |
| `CONFLICTING_UPDATE` | 409 | Optimistic concurrency/version conflict. |
| `RATE_LIMITED` | 429 | Общий rate limit. |

### 3.2 Pagination and list envelope

Все list/search/autocomplete endpoints возвращают только видимые caller объекты.

```json
{
  "items": [],
  "page": {
    "limit": 50,
    "nextCursor": "cur_...",
    "hasMore": false
  }
}
```

Правила:

- `limit`: default 50, max 100 для list/search, max 20 для autocomplete;
- `cursor`: opaque string, не содержит открытых ids или query text;
- `sort`: allowlist на endpoint; default обычно `createdAt desc` или `occurredAt desc`;
- `totalCount` не возвращается в MVP;
- `hasMore` и `nextCursor` считаются только по уже отфильтрованному видимому набору.

### 3.3 Common filters

Общие query params:

- `status`: `active`, `archived`, `deleted` только если endpoint явно поддерживает историю;
- `ownershipType`: `personal`, `shared` для accounts;
- `scope`: `personal`, `household` для categories;
- `householdId`: допускается только как scope narrowing; не расширяет доступ;
- `accountId`, `categoryId`: перед применением проверяются на видимость;
- `startDate`, `endDate`, `timezone`: date-only `YYYY-MM-DD`, timezone IANA string;
- `q`: строка поиска, server-side normalized, не логируется как raw payload.

Autocomplete возвращает минимальные DTO без counters и без упоминания скрытых совпадений.

## 4. Endpoint groups

### 4.1 Auth, sessions, password resets

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `POST` | `/api/v1/users` | Регистрация пользователя. |
| `POST` | `/api/v1/sessions` | Login и выпуск session/refresh token или cookie session. |
| `GET` | `/api/v1/sessions/current` | Проверка текущей сессии. |
| `DELETE` | `/api/v1/sessions/current` | Logout текущей сессии. |
| `DELETE` | `/api/v1/sessions` | Logout all sessions текущего пользователя. |
| `POST` | `/api/v1/password-resets` | Запрос reset email/link с нейтральным ответом. |
| `POST` | `/api/v1/password-resets/confirmations` | Подтверждение reset token и установка нового пароля. |

Request DTO summary:

- `UserCreateRequest`: `email`, `password`, `displayName`.
- `SessionCreateRequest`: `email`, `password`, optional `deviceName`.
- `PasswordResetCreateRequest`: `email`.
- `PasswordResetConfirmRequest`: `resetToken`, `newPassword`.

Response DTO summary:

- `UserDto`: `id`, `displayName`, `email` только для self, `createdAt`, `updatedAt`.
- `SessionDto`: `user`, `sessionId`, `expiresAt`; refresh token transport зависит от auth stack и не логируется.
- Password reset request always returns `PasswordResetAcceptedDto`: `accepted: true`.

Authz note:

- `POST /users`, `POST /sessions`, `POST /password-resets`, `POST /password-resets/confirmations` доступны anonymous, но rate limited и account-neutral.
- `GET/DELETE /sessions/current` и `DELETE /sessions` требуют authenticated session.
- После password reset старые sessions/refresh tokens отзываются.

Main errors:

- `VALIDATION_FAILED`, `PASSWORD_POLICY_FAILED`, `LOGIN_RATE_LIMITED`, `RESET_RATE_LIMITED`, `RESET_TOKEN_NOT_FOUND_OR_EXPIRED`, `RESET_TOKEN_ALREADY_USED`, `UNAUTHENTICATED`, `SESSION_EXPIRED`.
- Login/reset/register не раскрывают наличие email.

### 4.2 Users/me

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/users/me` | Полный профиль текущего пользователя. |
| `PATCH` | `/api/v1/users/me` | Обновление `displayName` и безопасных настроек профиля. |
| `GET` | `/api/v1/users/me/memberships` | Memberships текущего пользователя, без hidden household counts. |

Request DTO summary:

- `UserUpdateRequest`: optional `displayName`, optional profile preferences.

Response DTO summary:

- `UserDto`: `id`, `displayName`, `email`, `createdAt`, `updatedAt`, optional `deactivatedAt`.
- `MembershipDto[]`: видимые memberships текущего пользователя.

Authz note:

- Только `Self`. Другие пользователи не получают полный профиль; в household/member lists возвращается только `MinimalUserDto`.

Main errors:

- `UNAUTHENTICATED`, `SESSION_EXPIRED`, `VALIDATION_FAILED`, `CONFLICTING_UPDATE`.

### 4.3 Households

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/households` | Список households, где caller active member. |
| `POST` | `/api/v1/households` | Создание household; creator получает active `Membership`. |
| `GET` | `/api/v1/households/{householdId}` | Detail household для active member. |
| `PATCH` | `/api/v1/households/{householdId}` | Обновление минимальных настроек household. |
| `POST` | `/api/v1/households/{householdId}/archive` | Архивация household, если MVP policy допускает. |

Request DTO summary:

- `HouseholdCreateRequest`: `name`.
- `HouseholdUpdateRequest`: optional `name`, optional `version`.

Response DTO summary:

- `HouseholdDto`: `id`, `name`, `createdByUserId`, `status`, `createdAt`, `updatedAt`, optional `archivedAt`.

Authz note:

- List возвращает только households с active `Membership`.
- Detail/update/archive требуют `isActiveHouseholdMember(currentUserId, householdId)`.
- Former/invited member не получает shared data.

Main errors:

- `UNAUTHENTICATED`, `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `MEMBERSHIP_NOT_ACTIVE`, `VALIDATION_FAILED`, `ACTION_NOT_ALLOWED`, `CONFLICTING_UPDATE`.

### 4.4 Invites

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/households/{householdId}/invites` | Pending/known invites household для active member. |
| `POST` | `/api/v1/households/{householdId}/invites` | Создать invite второго участника в лимите MVP. |
| `GET` | `/api/v1/invites/{inviteId}` | Detail invite для active member или verified invited user. |
| `POST` | `/api/v1/invites/{inviteId}/accept` | Принять invite. |
| `POST` | `/api/v1/invites/{inviteId}/decline` | Отклонить invite. |
| `POST` | `/api/v1/invites/{inviteId}/revoke` | Отозвать pending invite active member. |
| `POST` | `/api/v1/invites/{inviteId}/resend` | Повторная отправка invite notice без раскрытия токена. |

Request DTO summary:

- `InviteCreateRequest`: `email`, optional `displayNameHint`.
- `InviteAcceptRequest`: `inviteToken`.
- `InviteDeclineRequest`: `inviteToken`.

Response DTO summary:

- `InviteDto`: `id`, `householdId`, `status`, `invitedByUserId`, `invitedAt`, `expiresAt`, optional `acceptedAt`, `declinedAt`, `revokedAt`.
- Invite token никогда не возвращается после первичной доставки.

Authz note:

- Create/list/revoke/resend требуют active `Membership` в `householdId`.
- Accept/decline требуют verified invite token и текущего пользователя; до accept shared accounts/reports недоступны.
- Invite token одноразовый, хранится как hash, не является resource id.

Main errors:

- `INVITE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `INVITE_EXPIRED`, `INVITE_ALREADY_USED`, `INVITE_REVOKED`, `HOUSEHOLD_MEMBER_LIMIT_REACHED`, `INVITE_RATE_LIMITED`, `MEMBERSHIP_NOT_ACTIVE`.

### 4.5 Memberships

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/households/{householdId}/memberships` | Минимальный состав household для active member. |
| `GET` | `/api/v1/memberships/{membershipId}` | Detail membership, если caller имеет право видеть context. |
| `POST` | `/api/v1/memberships/{membershipId}/revoke` | Отозвать active/pending membership по MVP policy. |
| `POST` | `/api/v1/memberships/{membershipId}/leave` | Caller покидает household; status становится `left`. |

Request DTO summary:

- `MembershipRevokeRequest`: optional `reasonCode`.
- `MembershipLeaveRequest`: optional `confirm: true`.

Response DTO summary:

- `MembershipDto`: `id`, `householdId`, `userId`, `status`, `invitedByUserId`, `invitedAt`, `joinedAt`, `endedAt`, `user: MinimalUserDto`.
- `MinimalUserDto`: `id`, `displayName`; email не включается.

Authz note:

- Active members видят минимальный состав household.
- Caller может leave только свою active membership.
- Revoke другого active member остается policy-sensitive; если не утверждено, возвращать `ACTION_NOT_ALLOWED`.
- После `left`/`revoked` access caches и sessions должны перестать давать shared access.

Main errors:

- `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `MEMBERSHIP_NOT_ACTIVE`, `ACTION_NOT_ALLOWED`, `CONFLICTING_UPDATE`.

### 4.6 Accounts

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/accounts` | List/search видимых accounts. |
| `POST` | `/api/v1/accounts` | Создать personal или shared account. |
| `GET` | `/api/v1/accounts/{accountId}` | Detail visible account. |
| `PATCH` | `/api/v1/accounts/{accountId}` | Обновить mutable fields без изменения ownership. |
| `POST` | `/api/v1/accounts/{accountId}/archive` | Архивировать account. |
| `POST` | `/api/v1/accounts/{accountId}/restore` | Восстановить archived account, если policy допускает. |
| `DELETE` | `/api/v1/accounts/{accountId}` | Soft delete только если допустимо policy и history. |
| `GET` | `/api/v1/accounts/autocomplete` | Минимальные видимые accounts для выбора. |

Request DTO summary:

- `AccountCreateRequest`: `name`, `accountType`, `ownershipType`, optional `householdId` for `shared`, `currency`, `initialBalance`.
- `AccountUpdateRequest`: optional `name`, optional `accountType`, optional `status`, optional `version`; `ownershipType`, `ownerUserId`, `householdId` immutable.
- Filters: `ownershipType`, `householdId`, `status`, `q`, `currency`, `accountType`, `limit`, `cursor`, `sort`.

Response DTO summary:

- `AccountDto`: `id`, `name`, `accountType`, `ownershipType`, `ownerUserId` for personal visible to owner, `householdId` for shared, `currency`, `initialBalance`, `currentBalance`, `status`, `createdByUserId`, `createdAt`, `updatedAt`, optional `archivedAt`, optional `deletedAt`, `version`.
- `AccountAutocompleteDto`: `id`, `name`, `accountType`, `ownershipType`, `currency`, optional `householdId`.

Authz note:

- Personal account predicate: `ownerUserId == currentUserId`.
- Shared account predicate: active `Membership` in `householdId`.
- List/search/autocomplete use same predicate as detail.
- Creating shared account requires active membership in supplied `householdId`; creating personal ignores any client-supplied `ownerUserId` and uses `currentUserId`.

Main errors:

- `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `ACCOUNT_OWNERSHIP_IMMUTABLE`, `INVALID_CURRENCY`, `ARCHIVED_RECORD_NOT_MUTABLE`, `CONFLICTING_UPDATE`.

### 4.7 Transactions

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/transactions` | List/search видимых transactions. |
| `POST` | `/api/v1/transactions` | Создать manual transaction. |
| `GET` | `/api/v1/transactions/{transactionId}` | Detail visible transaction. |
| `PATCH` | `/api/v1/transactions/{transactionId}` | Обновить mutable fields. |
| `DELETE` | `/api/v1/transactions/{transactionId}` | Soft delete transaction. |
| `POST` | `/api/v1/transactions/{transactionId}/restore` | Восстановить soft-deleted transaction, если policy допускает. |
| `GET` | `/api/v1/transactions/autocomplete` | Минимальные видимые transactions для быстрого поиска. |

Request DTO summary:

- `TransactionCreateRequest`: `transactionType`, `accountId`, optional `counterpartyAccountId`, optional `categoryId`, `amount`, `currency`, `occurredAt`, optional `description`, `sourceType`.
- `TransactionUpdateRequest`: mutable financial fields above, optional `version`.
- Filters: `accountId`, `categoryId`, `transactionType`, `householdId`, `ownershipType`, `startDate`, `endDate`, `q`, `minAmount`, `maxAmount`, `status`, `limit`, `cursor`, `sort`.

Response DTO summary:

- `TransactionDto`: `id`, `transactionType`, `accountId`, optional `counterpartyAccountId`, optional `categoryId`, `amount`, `currency`, `occurredAt`, optional `description`, `sourceType`, optional `transferScope`, optional `transferStatus`, `createdByUserId`, `lastEditedByUserId`, `createdAt`, `updatedAt`, optional `deletedAt`, `version`.

Authz note:

- Transaction visibility inherits from `accountId`.
- Income/expense require a visible compatible category: personal account uses personal category of owner; shared account uses household category of same `householdId` or approved system category.
- Transfer allowed only same-scope:
  - `personal_same_owner`: both accounts personal and `ownerUserId == currentUserId`;
  - `household_same_household`: both accounts shared in same `householdId` and caller active member.
- `personal <-> shared`, cross-user personal and cross-household shared transfers are rejected.

Main errors:

- `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `TRANSACTION_ACCOUNT_MISMATCH`, `CATEGORY_SCOPE_MISMATCH`, `TRANSFER_COUNTERPARTY_REQUIRED`, `TRANSFER_COUNTERPARTY_NOT_ACCESSIBLE`, `TRANSFER_SCOPE_NOT_SUPPORTED`, `INVALID_CURRENCY`, `ARCHIVED_RECORD_NOT_MUTABLE`, `CONFLICTING_UPDATE`.

### 4.8 Categories

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/categories` | List/search видимых categories. |
| `POST` | `/api/v1/categories` | Создать personal или household category. |
| `GET` | `/api/v1/categories/{categoryId}` | Detail visible category. |
| `PATCH` | `/api/v1/categories/{categoryId}` | Обновить mutable category fields. |
| `POST` | `/api/v1/categories/{categoryId}/archive` | Архивировать category. |
| `POST` | `/api/v1/categories/{categoryId}/restore` | Восстановить archived category. |
| `DELETE` | `/api/v1/categories/{categoryId}` | Soft delete, если не ломает history. |
| `GET` | `/api/v1/categories/autocomplete` | Минимальные видимые categories для выбора. |

Request DTO summary:

- `CategoryCreateRequest`: `name`, `type`, `scope`, optional `householdId`, optional `iconKey`, optional `color`.
- `CategoryUpdateRequest`: optional `name`, optional `iconKey`, optional `color`, optional `status`, optional `version`; `scope`, `ownerUserId`, `householdId` immutable.
- Filters: `scope`, `householdId`, `type`, `status`, `q`, `limit`, `cursor`, `sort`.

Response DTO summary:

- `CategoryDto`: `id`, `name`, `type`, `scope`, optional `ownerUserId`, optional `householdId`, optional `iconKey`, optional `color`, `status`, `createdByUserId`, `createdAt`, `updatedAt`, optional `archivedAt`, optional `deletedAt`, `version`.
- `CategoryAutocompleteDto`: `id`, `name`, `type`, `scope`, optional `householdId`, optional `iconKey`, optional `color`.

Authz note:

- Personal category predicate: `ownerUserId == currentUserId`.
- Household category predicate: active `Membership` in `householdId`.
- Category list/search/autocomplete never returns personal categories of another user.

Main errors:

- `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `CATEGORY_SCOPE_MISMATCH`, `ARCHIVED_RECORD_NOT_MUTABLE`, `CONFLICTING_UPDATE`.

### 4.9 Reports

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/reports/summary` | Вычисляемый summary report. |
| `GET` | `/api/v1/reports/category-breakdown` | Breakdown по видимым categories. |
| `GET` | `/api/v1/reports/account-balances` | Balances по видимым accounts. |
| `GET` | `/api/v1/reports/cash-flow` | Income/expense trend по периоду. |
| `GET` | `/api/v1/reports/transactions` | Drill-down list видимых transactions для report filters. |

Request/query DTO summary:

- `ReportQuery`: `reportMode`, `startDate`, `endDate`, `timezone`, optional `householdId`, optional `accountIds`, optional `categoryIds`, optional `transactionTypes`.
- Для drill-down дополнительно `limit`, `cursor`, `sort`.

Response DTO summary:

- `ReportSummaryDto`: `viewerUserId`, optional `householdId`, `reportMode`, `period`, `includedAccountIds`, `incomeTotal`, `expenseTotal`, `netTotal`, `generatedAt`.
- `CategoryBreakdownItemDto`: `categoryId`, `categoryName`, `categoryType`, `amount`, `currency`.
- `AccountBalanceDto`: `accountId`, `accountName`, `ownershipType`, `currency`, `currentBalance`.
- `CashFlowPointDto`: `periodStartDate`, `periodEndDate`, `incomeTotal`, `expenseTotal`, `netTotal`.
- Report transaction drill-down uses regular `TransactionDto` list envelope after access filtering.

Authz note:

- `shared_family_report` requires `householdId` and active membership; includes only shared accounts, shared transactions and household categories of that household.
- `combined_viewer_overview` may include selected household shared data plus personal data of `viewerUserId == currentUserId`; never includes personal data of another member.
- All supplied `accountIds`/`categoryIds` are intersected with visible set before aggregation; inaccessible direct ids are rejected neutrally or ignored only if this does not reveal hidden counts. Preferred default: reject with `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`.

Main errors:

- `INVALID_DATE_RANGE`, `INVALID_ENUM_VALUE`, `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `MEMBERSHIP_NOT_ACTIVE`, `VALIDATION_FAILED`.

### 4.10 Export, delete account/data, leave family

Routes:

| Method | Route | Назначение |
| --- | --- | --- |
| `POST` | `/api/v1/exports` | Создать export job для данных, видимых текущему пользователю. |
| `GET` | `/api/v1/exports` | List своих export jobs. |
| `GET` | `/api/v1/exports/{exportId}` | Status/detail своего export job. |
| `GET` | `/api/v1/exports/{exportId}/files` | Получить файл экспорта, если ready и owned by caller. |
| `POST` | `/api/v1/users/me/deletion-requests` | Запросить delete/deactivation account flow. |
| `GET` | `/api/v1/users/me/deletion-requests/{deletionRequestId}` | Status своего deletion request. |
| `POST` | `/api/v1/households/{householdId}/leave-requests` | Запрос/подтверждение выхода из household. |

Request DTO summary:

- `ExportCreateRequest`: `format` (`json` or `csv_zip`), optional `householdId`, optional `includeSharedData`.
- `DeletionRequestCreateRequest`: `confirm: true`, optional `reasonCode`.
- `LeaveRequestCreateRequest`: `confirm: true`.

Response DTO summary:

- `ExportJobDto`: `id`, `status` (`pending`, `processing`, `ready`, `failed`, `expired`), `format`, `requestedByUserId`, `createdAt`, optional `readyAt`, optional `expiresAt`.
- `DeletionRequestDto`: `id`, `status`, `requestedByUserId`, `createdAt`, optional `completedAt`.
- `LeaveRequestDto`: `id`, `householdId`, `membershipId`, `status`, `createdAt`, optional `completedAt`.

Authz note:

- Export includes only data visible to current user at export generation time: own personal data plus shared data where caller is active member. It never includes another member's personal accounts, transactions, categories or personal aggregates.
- Former member export does not include current shared data unless a future Product/Legal/Security decision changes the rule.
- Delete/deactivation affects self only; shared history handling follows privacy baseline and may anonymize author markers.
- Leave family sets current user's membership to `left`, revokes future shared access and requires session/access cache invalidation.

Main errors:

- `UNAUTHENTICATED`, `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`, `MEMBERSHIP_NOT_ACTIVE`, `ACTION_NOT_ALLOWED`, `VALIDATION_FAILED`, `CONFLICTING_UPDATE`.

## 5. DTO schemas for W1-03/W1-04/W1-09

Ниже не OpenAPI, а минимальная contract schema. W1-03 может превратить ее в строгие backend types/OpenAPI.

```json
{
  "HouseholdDto": {
    "id": "hsh_123",
    "name": "Дом",
    "createdByUserId": "usr_123",
    "status": "active",
    "createdAt": "2026-05-17T10:00:00Z",
    "updatedAt": "2026-05-17T10:00:00Z"
  },
  "MembershipDto": {
    "id": "mem_123",
    "householdId": "hsh_123",
    "userId": "usr_123",
    "status": "active",
    "invitedByUserId": "usr_001",
    "invitedAt": "2026-05-17T10:00:00Z",
    "joinedAt": "2026-05-17T10:05:00Z",
    "endedAt": null,
    "user": {
      "id": "usr_123",
      "displayName": "User"
    }
  },
  "AccountDto": {
    "id": "acc_123",
    "name": "Cash",
    "accountType": "cash",
    "ownershipType": "personal",
    "ownerUserId": "usr_123",
    "householdId": null,
    "currency": "RUB",
    "initialBalance": "1000.00",
    "currentBalance": "1250.00",
    "status": "active",
    "createdByUserId": "usr_123",
    "createdAt": "2026-05-17T10:00:00Z",
    "updatedAt": "2026-05-17T10:00:00Z",
    "version": 1
  },
  "TransactionDto": {
    "id": "trn_123",
    "transactionType": "expense",
    "accountId": "acc_123",
    "counterpartyAccountId": null,
    "categoryId": "cat_123",
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
  },
  "CategoryDto": {
    "id": "cat_123",
    "name": "Food",
    "type": "expense",
    "scope": "personal",
    "ownerUserId": "usr_123",
    "householdId": null,
    "iconKey": "utensils",
    "color": "#3366CC",
    "status": "active",
    "createdByUserId": "usr_123",
    "createdAt": "2026-05-17T10:00:00Z",
    "updatedAt": "2026-05-17T10:00:00Z",
    "version": 1
  }
}
```

Transfer create example:

```json
{
  "transactionType": "transfer",
  "accountId": "acc_from",
  "counterpartyAccountId": "acc_to",
  "amount": "500.00",
  "currency": "RUB",
  "occurredAt": "2026-05-17T09:30:00Z",
  "description": "Between own accounts",
  "sourceType": "manual"
}
```

Report query example:

```json
{
  "reportMode": "combined_viewer_overview",
  "householdId": "hsh_123",
  "startDate": "2026-05-01",
  "endDate": "2026-05-31",
  "timezone": "Europe/Moscow"
}
```

Canonical enum sets:

- `AccountType`: `cash`, `bank`, `deposit`, `brokerage`;
- `OwnershipType`: `personal`, `shared`;
- `MembershipStatus`: `invited`, `active`, `left`, `revoked`;
- `InviteStatus`: `pending`, `accepted`, `declined`, `revoked`, `expired`;
- `TransactionType`: `income`, `expense`, `transfer`, `brokerage`;
- `CategoryScope`: `personal`, `household`;
- `CategoryType`: `income`, `expense`;
- `ReportMode`: `shared_family_report`, `combined_viewer_overview`;
- `TransferScope`: `personal_same_owner`, `household_same_household`, `unsupported_cross_scope`;
- `TransferStatus`: `posted`, `voided`;
- `RecordStatus`: `active`, `archived`, `deleted`;
- `SourceType` MVP accepted value: `manual`.

## 6. Search, filtering and pagination rules

- `GET /accounts`, `/transactions`, `/categories`, `/reports/transactions` are cursor-paginated and access-filtered.
- Search `q` matches only visible records. No endpoint returns "matches exist but hidden".
- Autocomplete returns only minimal visible objects and never returns balances for accounts unless a concrete W1-03 decision approves it for visible accounts.
- Direct filters by hidden ids return neutral `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` for mutations and reports. For list/search, the safe default is empty visible result if the filter is optional, or neutral 404 if the filter is required to define scope.
- Sorting is allowlisted. Free-form sort expressions are invalid.
- Date filters use `occurredAt` for transactions and report periods; report dates are inclusive date-only boundaries interpreted in `timezone`.
- Amount filters apply only after authz filtering and do not reveal hidden min/max.

## 7. Neutral error policy and no hidden counts

Neutral policy applies to:

- direct read/update/delete by `accountId`, `transactionId`, `categoryId`, `householdId`, `membershipId`, `inviteId`, `exportId`;
- create/update references to inaccessible `accountId`, `counterpartyAccountId`, `categoryId`, `householdId`;
- report filters and drill-down;
- search/autocomplete/list where a caller tries to infer another user's personal data;
- login, registration, password reset and invite token flows.

API must not return:

- hidden counts or global totals before access filter;
- object names, owner names, email, balances or descriptions in errors;
- different error shape/timing intentionally tied to whether inaccessible object exists;
- raw request/response bodies in logs for financial endpoints;
- personal aggregates of another household member in any report mode.

Allowed observable behavior:

- authenticated vs unauthenticated can differ with `401`;
- visible object state can produce specific state errors after visibility is established;
- field validation can name invalid fields supplied by caller, without revealing hidden resource facts.

## 8. Out of scope MVP endpoints

These routes must not be added in MVP without Product/Security/Privacy escalation:

- `/api/v1/imports`, `/api/v1/import-jobs`, `/api/v1/files/imports`;
- `/api/v1/bank-connections`, `/api/v1/bank-accounts`, `/api/v1/bank-api/*`;
- `/api/v1/sms-imports`, `/api/v1/push-imports`, `/api/v1/notifications/push-tokens`;
- `/api/v1/broker-connections`, `/api/v1/external-credentials`;
- any endpoint accepting bank passwords, API keys, SMS codes, push secrets, card numbers, IBAN/account requisites or raw bank statements.

Post-MVP enum values such as `file_import`, `bank_api`, `sms`, `push` may exist only as reserved vocabulary; MVP create/update endpoints reject them for `sourceType`.

## 9. Open questions, risks and escalation triggers

Open questions that do not block this contract:

- финальное решение, хранится ли `currentBalance` как состояние или вычисляется как projection;
- exact auth stack: cookie session для PWA, bearer tokens для Android или гибрид;
- точные rate limit значения для login/reset/invite;
- точная policy удаления account/data, anonymization author markers и backup deletion SLA;
- кто, кроме self, может revoke active membership в MVP;
- нужен ли self-service export file или закрытому MVP достаточно job/backoffice процесса с audit.

Risks:

- Ошибка в shared report или combined overview может раскрыть personal агрегаты второго участника.
- Transfers personal/shared требуют split visibility; в MVP выбран запрет, иначе нужна эскалация.
- Former member historical access пока denied by default; любое сохранение shared history access после выхода требует Product/Legal/Security решения.
- Export/delete затрагивают privacy и retention; реализация должна пройти отдельный review.
- Любое появление imports, bank API, SMS/push или external credentials меняет threat model и не совместимо с этим MVP contract без пересмотра.

Escalation triggers:

- требуется показать personal account/transaction/category/report другому участнику Household;
- требуется разрешить personal<->shared transfer без отдельной split-visibility модели;
- требуется больше двух active members или детальные household roles;
- требуется публичный запуск, SaaS commitment, formal retention/deletion SLA или выбор юрисдикции;
- требуется хранить банковские/API/broker/SMS/push secrets или импортировать файлы;
- обнаружена repeated failure access/security scenario или утечка financial/personal данных.

## 10. Definition of done coverage

- Все MVP resources имеют route/method outline: auth/session/password reset, users/me, households, invites, memberships, accounts, transactions, categories, reports, export/delete/leave family.
- DTO summaries используют canonical names/enums: `Household`, `Transaction`, `reportMode`, `ownershipType`, `scope`, `sourceType = manual`.
- Authz notes указывают predicate для каждой surface, не заменяя W1-03 implementation.
- Neutral errors и no hidden counts покрыты для detail/list/search/autocomplete/report/export flows.
- Reports и transfers оставлены совместимыми с детализацией W1-04/W1-05: report modes фиксированы, same-scope transfer rules явные, personal/shared transfer запрещен в MVP.
