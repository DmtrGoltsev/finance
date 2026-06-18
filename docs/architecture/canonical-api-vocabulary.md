# Канонический словарь API MVP

## Статус и область

Этот документ фиксирует канонический словарь API/backend/client contracts для Wave 1. Он не меняет бизнес-границы Wave 0: MVP строится на ручном вводе счетов, транзакций, категорий и отчетов; импорт файлов, банковские API, SMS, push и банковские/брокерские credentials остаются post-MVP.

Базовые инварианты:

- personal-данные всегда приватны и видны только владельцу;
- shared/household-данные видны только active members того же household;
- отчеты фильтруют видимые данные до агрегации;
- personal<->shared transfers запрещены в MVP;
- ошибки доступа нейтральны и не подтверждают существование недоступного объекта.

## Канонические термины домена

| API-термин | Статус | Значение | Маппинг старых терминов Wave 0 |
| --- | --- | --- | --- |
| `User` | canonical | Учетная запись пользователя. | Без изменений. |
| `Household` | canonical | Семейное пространство для shared-счетов, shared-категорий, shared-транзакций и отчетов. | `FamilySpace`, `family space`, "семейное пространство", "семья" в API-контрактах маппятся в `Household`. `FamilySpace` допустим только как UI/product wording. |
| `Membership` | canonical | Связь `User` и `Household`, определяющая участие и доступ. | Без изменений. `FormerMember` является actor label, не отдельным ресурсом. |
| `Invite` | canonical | Одноразовое приглашение в `Household`. | "Invitation", "pending membership" маппятся в `Invite`; после принятия создается/активируется `Membership`. |
| `Account` | canonical | Счет или место учета денег/активов. | Без изменений. |
| `Transaction` | canonical | Финансовое событие ручного учета: доход, расход, перевод или базовая брокерская запись. | `Operation`, `operation`, "операция" в Wave 0 маппятся в `Transaction`. Поле `operationType` становится `transactionType`. В русском тексте "операция" можно использовать описательно, но API names используют `Transaction`. |
| `Category` | canonical | Категория дохода или расхода. | Без изменений. |
| `Report` | canonical | Вычисляемое представление аналитики за период. | `AnalyticsView`, "analytics view", "отчет/аналитика" маппятся в `Report`. |
| `Transfer` | canonical concept | Тип `Transaction`, который связывает два счета в одном разрешенном scope. | Не отдельный MVP resource, если backend не вводит отдельную агрегирующую запись. |

Решение по конфликтным парам:

- API выбирает `Household`, а `FamilySpace` остается продуктовым/UI-синонимом.
- API выбирает `Transaction`, а `Operation` остается старым доменным синонимом в документах Wave 0.

## Ресурсы и стиль именования routes

API routes используют стабильный REST-like стиль:

- базовый prefix: `/api/v1`;
- route segments: lowercase kebab-case, plural resource names;
- path params: camelCase в фигурных скобках в документации, например `{householdId}`;
- JSON DTO fields: camelCase;
- enum values: lower_snake_case;
- error codes: UPPER_SNAKE_CASE;
- resource names в OpenAPI/DTO types: PascalCase singular, например `HouseholdDto`, `TransactionCreateRequest`.

Канонические resource route names:

| Resource | Collection route | Detail route / примечания |
| --- | --- | --- |
| `User` | `/users` | `/users/{userId}`; текущий пользователь может иметь алиас `/me`, но DTO fields остаются `userId`/`viewerUserId`. |
| `Session` | `/sessions` | Auth/session endpoints не раскрывают наличие email/account. |
| `PasswordReset` | `/password-resets` | Tokens не передаются в URL после первичной доставки; в API не логируются. |
| `Household` | `/households` | `/households/{householdId}`. Не использовать `/families` или `/family-spaces`. |
| `Membership` | `/households/{householdId}/memberships` | `/memberships/{membershipId}` допустим для detail, если authz не зависит от вложенного route. |
| `Invite` | `/households/{householdId}/invites` | `/invites/{inviteId}` для accept/decline/revoke; token не является resource id. |
| `Account` | `/accounts` | `/accounts/{accountId}`; list всегда возвращает только видимые счета. |
| `Transaction` | `/transactions` | `/transactions/{transactionId}`; не использовать `/operations`. |
| `Category` | `/categories` | `/categories/{categoryId}`; list фильтруется по видимому scope. |
| `Report` | `/reports` | Вычисляемый endpoint, например `/reports/summary?reportMode=shared_family_report`. |

Вложенные routes допустимы для читаемости scope (`/households/{householdId}/invites`), но не являются контролем доступа. Backend обязан проверять `currentUserId`, `ownerUserId`, active `Membership` и visibility predicates независимо от формы route.

## Канонические enum names/values

Все enum values являются wire contract и не переименовываются без versioned migration.

### `AccountType`

| Value | Значение |
| --- | --- |
| `cash` | Наличные. |
| `bank` | Банковский счет или карта как учетный счет без хранения реквизитов. |
| `deposit` | Вклад/депозит. |
| `brokerage` | Брокерский счет для базового учета без налоговой/портфельной логики. |

### `OwnershipType`

| Value | Значение |
| --- | --- |
| `personal` | Владелец - `ownerUserId`; видит только владелец. |
| `shared` | Владелец scope - `householdId`; видят active members этого `Household`. |

`Account.ownershipType` задается явно и не меняется в MVP.

### `MembershipStatus`

| Value | Значение |
| --- | --- |
| `invited` | Пользователь приглашен, но shared-доступ еще не активирован. |
| `active` | Пользователь является active member и имеет доступ к shared-данным household. |
| `left` | Пользователь сам вышел из household; будущий shared-доступ прекращен. |
| `revoked` | Доступ или приглашение отозваны active member/system; будущий shared-доступ прекращен. |

`removed` из Wave 0 маппится в `revoked`. Истечение приглашения фиксируется через `Invite.status = expired`; `MembershipStatus.expired` не вводится, чтобы не смешивать состояние membership и invite token.

### `InviteStatus`

| Value | Значение |
| --- | --- |
| `pending` | Приглашение создано и еще может быть принято до `expiresAt`. |
| `accepted` | Приглашение принято; token больше не действителен. |
| `declined` | Приглашенный отказался; token больше не действителен. |
| `revoked` | Приглашение отозвано; token больше не действителен. |
| `expired` | Срок действия истек; token больше не действителен. |

Invite expiry выражается полями `expiresAt` и `status = expired`.

### `TransactionType`

| Value | Значение |
| --- | --- |
| `income` | Доход. |
| `expense` | Расход. |
| `transfer` | Перевод между двумя счетами в разрешенном same-scope. |
| `brokerage` | Базовая брокерская запись без налоговой, портфельной и инвестиционной логики. |

Старое поле `operationType` маппится в `transactionType`.

### `CategoryScope`

| Value | Значение |
| --- | --- |
| `personal` | Категория принадлежит `ownerUserId` и видна только владельцу. |
| `household` | Категория принадлежит `householdId` и видна active members household. |

Не использовать `shared` как category scope value: для счетов canonical value `shared`, для категорий canonical value `household`.

### `CategoryType`

| Value | Значение |
| --- | --- |
| `income` | Категория дохода. |
| `expense` | Категория расхода. |

### `ReportMode`

| Value | Значение |
| --- | --- |
| `shared_family_report` | Отчет только по shared-счетам, shared-транзакциям и household-категориям выбранного `Household`. Не включает personal-счета ни одного участника. |
| `combined_viewer_overview` | Обзор по shared-данным выбранного `Household` плюс personal-данным текущего `viewerUserId`. Не включает personal-данные другого участника даже агрегированно. |

Legacy labels `shared family report` и `combined viewer overview` маппятся только в эти API values.

### `TransferScope`

| Value | Значение |
| --- | --- |
| `personal_same_owner` | Разрешенный transfer между personal-счетами одного `ownerUserId`. |
| `household_same_household` | Разрешенный transfer между shared-счетами одного `householdId` для active member. |
| `unsupported_cross_scope` | Неразрешенный personal<->shared или иной mixed-scope transfer. Используется во внутренней validation/result модели; публичный API отклоняет запрос с `TRANSFER_SCOPE_NOT_SUPPORTED`. |

### `TransferStatus`

| Value | Значение |
| --- | --- |
| `posted` | Transfer принят и участвует в балансах/отчетах. |
| `voided` | Transfer мягко отменен/исключен из текущих расчетов, история сохранена. |

MVP не вводит банковские состояния `pending`, `processing`, `settled`, потому что внешних платежей и банковских API нет. Если UI нужна черновая форма, это client state, а не API enum.

### `RecordStatus`

Канонический enum для archive/soft delete статуса финансовых справочников и записей.

| Value | Значение |
| --- | --- |
| `active` | Запись активна и доступна по обычным visibility rules. |
| `archived` | Запись скрыта из выбора для новых операций, но история сохранена. |
| `deleted` | Запись мягко удалена и не участвует в текущих списках/аналитике, если endpoint явно не запрашивает историю. |

Для DTO timestamps используются `archivedAt` и `deletedAt`. Физическое удаление не является обычным API outcome MVP.

### `SourceType`

| Value | MVP | Значение |
| --- | --- | --- |
| `manual` | yes | Пользователь создал запись вручную. Единственный допустимый source type для MVP transactions. |
| `file_import` | post-MVP | Импорт из Excel/CSV/файлов. |
| `bank_api` | post-MVP | Прямое банковское/API подключение. |
| `sms` | post-MVP | SMS import. |
| `push` | post-MVP | Push import. |

Post-MVP values зарезервированы, но endpoints, credentials и processing flows для них не входят в MVP.

## Naming conventions для DTO fields

### IDs

- Primary id field: `id` внутри resource DTO.
- Foreign/reference ids: `{resourceName}Id`, например `userId`, `householdId`, `accountId`, `transactionId`, `categoryId`, `membershipId`, `inviteId`.
- Actor/current user fields: `viewerUserId`, `actorUserId`, `createdByUserId`, `lastEditedByUserId`, `invitedByUserId`.
- Owner fields: `ownerUserId` для personal scope; `householdId` для household/shared scope.
- Не использовать `familySpaceId`, `familyId`, `operationId` в новых API. Они допустимы только в migration notes или legacy adapters.

### Timestamps and dates

- Timestamps: ISO 8601 UTC string с suffix `At`: `createdAt`, `updatedAt`, `archivedAt`, `deletedAt`, `invitedAt`, `joinedAt`, `endedAt`, `expiresAt`, `generatedAt`.
- Business date/time of transaction: `occurredAt`.
- Period fields: `startDate`, `endDate`, `timezone`; date-only values используют ISO `YYYY-MM-DD`.
- Не использовать локальное время без `timezone` для отчетных периодов.

### Деньги и валюта

- Денежные поля используют decimal string или minor units по явному контракту; для MVP canonical DTO field names: `amount`, `initialBalance`, `currentBalance`, `incomeTotal`, `expenseTotal`.
- `currency` использует ISO 4217 uppercase alpha code, например `RUB`, `USD`, `EUR`.
- Валюта transaction должна совпадать с валютой account в MVP, пока следующая версия явно не определит exchange/revaluation.
- Logs, telemetry и error messages не должны включать денежные значения.

### Видимость и scope

- Видимость account выражается через `ownershipType`: `personal` или `shared`.
- Видимость category выражается через `scope`: `personal` или `household`.
- Видимость report выражается через `reportMode` плюс `viewerUserId` и опциональный `householdId`.
- Не вводить generic fields `visibility`, `access`, `privacy`, `familyVisible` или `isShared` в API DTOs, когда реальным контрактом является `ownershipType`, `scope` или `reportMode`.

### Actor fields

- `createdByUserId`: пользователь, создавший запись.
- `lastEditedByUserId`: последний пользователь, изменивший mutable financial fields.
- `actorUserId`: actor audit/event, а не владелец ресурса.
- `viewerUserId`: пользователь, для которого строится вычисляемый view/report.
- Actor fields нельзя использовать как shortcut авторизации; backend authz использует текущего authenticated user плюс owner/membership predicates.

## Canonical error codes

Формат error response:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
    "message": "Ресурс не найден или недоступен.",
    "requestId": "req_..."
  }
}
```

`message` безопасен для пользователя и остается общим. `details` может содержать field names для собственного невалидного ввода, но не должен содержать названия скрытых объектов, суммы, описания, названия счетов, названия категорий, emails, tokens или stack traces.

### Access-neutral и auth errors

| Code | HTTP | Значение |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Нет валидной session/token. |
| `SESSION_EXPIRED` | 401 | Session/token истек или был отозван. |
| `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` | 404 | Объект не существует или недоступен caller; canonical neutral error для чтения по прямому id. |
| `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` | 404 | Переданный `accountId`, `categoryId`, `householdId` и т.п. невалиден или недоступен. |
| `ACTION_NOT_ALLOWED` | 403 | Authenticated user не может выполнить действие в сценарии, где существование объекта уже безопасно раскрыто, например transition собственного account. |
| `MEMBERSHIP_NOT_ACTIVE` | 404 or 403 | Caller не является active member; использовать neutral 404, если существование household нельзя подтверждать. |

### Validation и state errors

| Code | HTTP | Значение |
| --- | --- | --- |
| `VALIDATION_FAILED` | 400 | Request shape, required fields или field formats невалидны. |
| `INVALID_ENUM_VALUE` | 400 | Enum value отсутствует в canonical value set. |
| `INVALID_DATE_RANGE` | 400 | Report period или date range невалиден. |
| `INVALID_CURRENCY` | 400 | Currency format не поддержан или несовместим с MVP contract. |
| `ACCOUNT_OWNERSHIP_IMMUTABLE` | 422 | Попытка изменить `ownershipType` в MVP. |
| `CATEGORY_SCOPE_MISMATCH` | 422 | Category scope/type несовместим с transaction/account scope. |
| `TRANSACTION_ACCOUNT_MISMATCH` | 422 | Transaction ссылается на accounts, которые не могут образовать валидную transaction по MVP rules. |
| `ARCHIVED_RECORD_NOT_MUTABLE` | 409 | Archived/deleted record нельзя использовать для этой mutation. |
| `CONFLICTING_UPDATE` | 409 | Optimistic concurrency/version conflict. |

### Transfer errors

| Code | HTTP | Значение |
| --- | --- | --- |
| `TRANSFER_SCOPE_NOT_SUPPORTED` | 422 | personal<->shared, cross-user personal, cross-household shared или иной unsupported transfer scope. Response не раскрывает детали скрытой стороны. |
| `TRANSFER_COUNTERPARTY_REQUIRED` | 400 | `counterpartyAccountId` обязателен для `transactionType = transfer`. |
| `TRANSFER_COUNTERPARTY_NOT_ACCESSIBLE` | 404 | Counterparty account отсутствует или недоступен; neutral. |

### Rate limit errors

| Code | HTTP | Значение |
| --- | --- | --- |
| `RATE_LIMITED` | 429 | Generic rate limit. |
| `LOGIN_RATE_LIMITED` | 429 | Login attempts throttled; response остается account-neutral. |
| `RESET_RATE_LIMITED` | 429 | Password reset attempts throttled; response остается account-neutral. |
| `INVITE_RATE_LIMITED` | 429 | Invite creation/resend attempts throttled. |

### Invite, session and reset errors

| Code | HTTP | Значение |
| --- | --- | --- |
| `INVITE_NOT_FOUND_OR_NOT_ACCESSIBLE` | 404 | Invite отсутствует, недоступен или token невалиден; neutral. |
| `INVITE_EXPIRED` | 410 | Invite истек; безопасно только когда token ownership/context уже проверены. |
| `INVITE_ALREADY_USED` | 409 | Invite уже accepted/declined/revoked; безопасно только в verified invite flow. |
| `INVITE_REVOKED` | 410 | Invite отозван; безопасно только в verified invite flow. |
| `HOUSEHOLD_MEMBER_LIMIT_REACHED` | 409 | Будет превышен MVP limit: два active members. |
| `SESSION_REVOKED` | 401 | Session отозвана из-за logout, password reset, membership change или security event. |
| `RESET_TOKEN_NOT_FOUND_OR_EXPIRED` | 400 | Reset token невалиден, использован или истек; neutral. |
| `RESET_TOKEN_ALREADY_USED` | 409 | Reset token уже использован; безопасно только в verified reset flow. |
| `PASSWORD_POLICY_FAILED` | 400 | Новый пароль не соответствует policy; без раскрытия существования account. |

## Запрет ambiguous aliases в API

Новые API contracts, DTOs, OpenAPI schemas, backend service names и client state names не должны вводить эти aliases:

| Запрещенный alias | Canonical replacement |
| --- | --- |
| `FamilySpace`, `familySpaceId`, `/family-spaces` | `Household`, `householdId`, `/households` |
| `Family`, `familyId`, `/families` | `Household`, `householdId`, `/households` |
| `Operation`, `operationId`, `operationType`, `/operations` | `Transaction`, `transactionId`, `transactionType`, `/transactions` |
| `AnalyticsView`, `analyticsView` | `Report`, `report` |
| `removed` membership status | `revoked` |
| `shared` category scope | `household` |
| `isShared`, `familyVisible`, `visibility` for account scope | `ownershipType` |

Legacy terms могут появляться только в compatibility sections, migration notes, цитатах старых документов или adapter-layer comments. Они не должны быть wire-format fields или enum values в W1 API.

## Compatibility and migration note for Wave 0 docs

Wave 0 documents remain valid as product/security/privacy inputs, but API contracts normalize terms as follows:

- `FamilySpace` и "семейное пространство" становятся `Household`.
- `family_space_id`/`familySpaceId` становятся `householdId`.
- `Operation`/"операция" становятся `Transaction` в resource names и DTOs.
- `operationType` становится `transactionType`; values остаются `income`, `expense`, `transfer`, `brokerage`.
- `AnalyticsView` становится `Report`; `reportMode` values остаются `shared_family_report` и `combined_viewer_overview`.
- Membership `removed` становится `revoked`.
- Invite expiry выражается через `Invite.status = expired` и `expiresAt`, а не через `MembershipStatus.expired`.
- MVP transfer contract разрешает только same-scope. Любая personal<->shared формулировка в старом product text трактуется как unsupported by API и отклоняется с `TRANSFER_SCOPE_NOT_SUPPORTED`.
- `sourceType = manual` является единственным direct transaction source в MVP; `file_import`, `bank_api`, `sms`, `push` зарезервированы как post-MVP values и не подразумевают direct transaction endpoints. Capture drafts используют отдельный user-confirmed lifecycle с `pending`/`confirmed`/`discarded`: OCR запускается пользователем из выбранного скриншота, Android распознает on-device без upload, PWA/iOS browser использует temporary self-hosted backend OCR, SMS/push/notifications не перехватываются, transaction создается только после user confirm/edit.

This migration has no known blocker for W1-02/W1-03. Backend/client/API tasks should treat this document as the source of truth for wire names and enum values.

## Критичные риски и open questions

Бизнес-блокеров для W1-02/W1-03 нет.

Оставшиеся вопросы не блокируют canonical API vocabulary, если применяются безопасные defaults из Wave 0:

- Balance contract (`currentBalance` stored, computed or cached projection) должен быть выбран в отдельной API/report задаче.
- Minimal currency behavior остается single-currency per account/transaction в MVP, пока exchange/revaluation не спроектирован явно.
- Former member historical access по умолчанию denied после `left`/`revoked`; любой historical read access требует Product/Security/Privacy escalation.
