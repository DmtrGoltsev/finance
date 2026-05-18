# Transfer API contract MVP

## Статус и границы

Документ фиксирует контракт backend API для переводов в Wave 1 MVP. `Transfer` не является отдельным публичным ресурсом MVP: перевод моделируется как `Transaction` с `transactionType = transfer` и обслуживается через canonical routes `/api/v1/transactions`.

Контракт наследует правила из `canonical-api-vocabulary.md`, `backend-api-contracts.md`, `backend-authz-predicates.md`, `access-model.md`, `security-baseline.md` и `access-security-scenarios.md`.

Безопасный MVP-инвариант: разрешены только same-scope transfers:

- `personal_same_owner`: personal -> personal между счетами одного владельца, где `ownerUserId = currentUserId`;
- `household_same_household`: shared -> shared внутри одного `Household`, где caller является active member.

Запрещены:

- personal -> shared;
- shared -> personal;
- personal -> personal разных владельцев;
- shared -> shared разных `Household`;
- любой transfer, который требует split visibility, cross-user visibility или cross-household visibility.

Canonical public error для unsupported transfer scope: `TRANSFER_SCOPE_NOT_SUPPORTED`.

## Domain model

`TransactionType = transfer` означает одну логическую финансовую запись, связывающую два счета в одном разрешенном scope.

Семантика сторон:

- `accountId` - исходящий счет transfer, с которого уменьшается доступный баланс или расчетный остаток;
- `counterpartyAccountId` - входящий счет transfer, на который увеличивается доступный баланс или расчетный остаток;
- `amount` - положительная сумма transfer;
- `currency` - ISO 4217 currency transfer; в MVP должна совпадать с валютой обоих счетов;
- `categoryId` для `transactionType = transfer` не используется и должен быть `null` или отсутствовать;
- `sourceType` для MVP должен быть `manual`;
- `transferScope` вычисляется backend и не принимается от клиента как источник прав;
- `transferStatus` отражает участие transfer в текущих расчетах: `posted` или `voided`.

Transfer должен быть неделимой логической операцией: API не должен создавать только одну сторону перевода и не должен показывать caller частично созданный или частично измененный transfer.

## API surface

Переводы используют существующую transaction surface:

| Method | Route | Назначение |
| --- | --- | --- |
| `POST` | `/api/v1/transactions` | Создать `Transaction` с `transactionType = transfer`. |
| `GET` | `/api/v1/transactions/{transactionId}` | Прочитать видимый transfer. |
| `GET` | `/api/v1/transactions` | List/search видимых transactions, включая transfers. |
| `PATCH` | `/api/v1/transactions/{transactionId}` | Обновить mutable поля transfer с полной повторной проверкой scope. |
| `DELETE` | `/api/v1/transactions/{transactionId}` | Soft delete или void по принятой реализации, без физического удаления истории. |
| `POST` | `/api/v1/transactions/{transactionId}/restore` | Восстановить ранее удаленный/voided transfer, если восстановление поддержано W1 transaction API. |
| `POST` | `/api/v1/transactions/{transactionId}/void` | Рекомендуемый explicit endpoint, если API различает void и delete. |

Если W1 transaction API не вводит отдельный `/void`, то delete должен быть soft delete/void-equivalent для расчетов. Физическое удаление transfer через user-facing API не входит в MVP.

## Request DTO

`TransferCreateRequest` является специализацией `TransactionCreateRequest`.

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

Правила:

- `transactionType` обязателен и равен `transfer`;
- `accountId` и `counterpartyAccountId` обязательны;
- `accountId != counterpartyAccountId`;
- `amount` обязателен, положителен и передается как decimal string по canonical money contract;
- `currency` обязателен, uppercase ISO 4217 и совпадает с валютой обоих счетов;
- `occurredAt` обязателен, ISO 8601 UTC timestamp;
- `description` optional; если передан, виден всем, кто видит transfer, поэтому для shared transfers считается shared-visible текстом;
- `sourceType` обязателен или defaulted server-side в `manual`; другие source types rejected в MVP;
- `categoryId`, если передан для transfer, должен быть rejected с `VALIDATION_FAILED` или ignored только если OpenAPI явно фиксирует `null`; безопасный default - reject.

`TransferUpdateRequest` может менять только mutable поля, разрешенные transaction contract: `accountId`, `counterpartyAccountId`, `amount`, `currency`, `occurredAt`, `description`, optional `version`. Любое изменение счетов заново проходит same-scope validation. Клиент не может установить `transferScope`, `transferStatus`, `createdByUserId`, `lastEditedByUserId` или balance effects напрямую.

## Response DTO

`TransferDto` является `TransactionDto` с transfer fields.

```json
{
  "id": "trn_123",
  "transactionType": "transfer",
  "accountId": "acc_from",
  "counterpartyAccountId": "acc_to",
  "categoryId": null,
  "amount": "500.00",
  "currency": "RUB",
  "occurredAt": "2026-05-17T09:30:00Z",
  "description": "Between own accounts",
  "sourceType": "manual",
  "transferScope": "personal_same_owner",
  "transferStatus": "posted",
  "createdByUserId": "usr_123",
  "lastEditedByUserId": "usr_123",
  "createdAt": "2026-05-17T10:00:00Z",
  "updatedAt": "2026-05-17T10:00:00Z",
  "deletedAt": null,
  "version": 1
}
```

Response не включает account names, balances, owner display names, emails или hidden-side diagnostics. Если UI нуждается в названиях счетов, он должен получать их из уже видимого account list/detail, прошедшего те же access predicates.

## Validation sequence

Backend должен выполнять проверки в порядке, который предотвращает частичную запись и утечку hidden side:

1. **Authenticate.** Без валидного `currentUserId` вернуть `UNAUTHENTICATED` или `SESSION_EXPIRED`.
2. **Validate request shape.** Проверить обязательные поля, enum values, формат `amount`, `currency`, `occurredAt`, отсутствие `categoryId` для transfer. Ошибки формы возвращают `VALIDATION_FAILED`, `INVALID_ENUM_VALUE`, `TRANSFER_COUNTERPARTY_REQUIRED` или `INVALID_CURRENCY`.
3. **Resolve source account through authz.** `accountId` должен быть видим и mutable для caller. Unknown или inaccessible source возвращает `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` без деталей.
4. **Resolve counterparty account in safe mode.** Backend может читать минимальные scope fields counterparty для проверки transfer, но public response не должен раскрывать existence, name, owner, balance или household. Unknown, inaccessible или unsupported counterparty pair collapses to neutral transfer denial according to this contract.
5. **Check record state.** Оба счета должны быть usable для новой mutation: не `deleted`, не state, который запрещает новые transactions. State-specific error допустим только для уже видимого source; для hidden counterparty не раскрывать state.
6. **Check currency compatibility.** `currency` transfer должна совпадать с currency обоих счетов. Cross-currency transfers out of scope MVP.
7. **Compute transfer scope.** Разрешены только `personal_same_owner` и `household_same_household`.
8. **Apply atomic write.** Создать или обновить transfer и оба balance effects в одной transaction boundary. На deny не должно быть ни одной финансовой записи, projection update или audit allow event.
9. **Emit sanitized audit.** Записать allow/deny/state-deny event без сумм, описаний, названий счетов, balances, emails, tokens или raw request body.
10. **Return DTO.** Вернуть только поля `TransferDto`, безопасные для resolved same-scope visibility.

Для update/restore/void/delete существующий `transactionId` сначала проходит `canReadTransaction`/`canMutateTransaction`; затем все proposed fields проходят тот же create-like validation. Existing visible transfer может давать state-specific ошибки, но недоступный `transactionId` всегда отвечает нейтрально.

## Same-scope rules

### `personal_same_owner`

Allow только если:

- `sourceAccount.ownershipType = personal`;
- `counterpartyAccount.ownershipType = personal`;
- `sourceAccount.ownerUserId = currentUserId`;
- `counterpartyAccount.ownerUserId = currentUserId`;
- оба счета не archived/deleted для новых transfers;
- `currency` совпадает с валютой обоих счетов.

Запретить с `TRANSFER_SCOPE_NOT_SUPPORTED`:

- personal account другого пользователя как source или counterparty;
- personal -> shared;
- shared -> personal;
- попытку использовать active household membership как основание доступа к personal account другого member.

### `household_same_household`

Allow только если:

- `sourceAccount.ownershipType = shared`;
- `counterpartyAccount.ownershipType = shared`;
- `sourceAccount.householdId = counterpartyAccount.householdId`;
- caller имеет active `Membership` в этом `householdId`;
- оба счета не archived/deleted для новых transfers;
- `currency` совпадает с валютой обоих счетов.

Запретить с `TRANSFER_SCOPE_NOT_SUPPORTED`:

- shared -> shared разных households;
- shared transfer для invited/former member;
- shared transfer, где caller не active member target household;
- любой transfer, который требует показать или использовать shared account чужого household.

## Error contract and hidden side protection

Public errors follow canonical envelope:

```json
{
  "error": {
    "code": "TRANSFER_SCOPE_NOT_SUPPORTED",
    "message": "Перевод недоступен для выбранных счетов.",
    "requestId": "req_..."
  }
}
```

Transfer-specific errors:

| Code | HTTP | Когда использовать |
| --- | --- | --- |
| `TRANSFER_COUNTERPARTY_REQUIRED` | 400 | `counterpartyAccountId` отсутствует при `transactionType = transfer`. |
| `TRANSFER_SCOPE_NOT_SUPPORTED` | 422 | personal<->shared, cross-user personal, cross-household shared, hidden/inaccessible counterparty in transfer-scope validation или любой transfer scope вне MVP. |
| `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` | 404 | `accountId` source не существует или недоступен caller до transfer-scope validation. |
| `INVALID_CURRENCY` | 400 | Currency format invalid или currency не совпадает с видимыми account currencies по MVP contract. |
| `ARCHIVED_RECORD_NOT_MUTABLE` | 409 | Visible account/transfer state запрещает mutation; применять только когда объект уже безопасно видим caller. |
| `CONFLICTING_UPDATE` | 409 | Optimistic concurrency/version conflict. |

Hidden side protection:

- не возвращать, какая сторона transfer нарушила правило;
- не различать user-facing message для personal<->shared, cross-user personal и cross-household shared;
- не включать в `details` account names, owner ids, household names, balances, amount, description, membership status или "source/counterparty belongs to...";
- не возвращать `hiddenCount`, `filteredOutCount`, suggestions или alternative account ids;
- не логировать raw request/response body для failed transfer;
- timing не должен быть намеренно разным для existing-hidden и non-existing counterparty cases;
- direct list/search/report не должен показывать факт rejected hidden-side transfer.

Если команда реализации не может обеспечить neutral handling для hidden counterparty при `TRANSFER_SCOPE_NOT_SUPPORTED`, это release blocker: нужно либо сузить public error до полностью нейтрального referenced-resource ответа, либо эскалировать Product/Security до реализации.

## Balance and update implications

Контракт не выбирает, хранится ли `currentBalance` как persisted state, cached projection или вычисляется на чтении. Но любая реализация обязана соблюдать эффекты:

- `posted` transfer уменьшает balance/projection исходящего `accountId` на `amount`;
- `posted` transfer увеличивает balance/projection входящего `counterpartyAccountId` на `amount`;
- оба эффекта применяются атомарно и в одном logical commit;
- reports, account balances, cash-flow и transaction drill-down должны видеть либо старое состояние, либо новое состояние, но не половину transfer;
- update amount/date/accounts/currency должен пересчитать или переиграть оба эффекта как единое изменение;
- failed validation, denied authz или concurrency conflict не меняют balances/projections;
- transfer не должен считаться income/expense в category breakdown, если report contract явно не вводит отдельную transfer presentation;
- shared family report включает только shared->shared transfers того же household;
- combined viewer overview включает own personal->personal transfers viewer и shared->shared transfers selected household, но не personal transfers другого member.

Для same-currency MVP transfer между счетами одной currency не создается exchange/revaluation entry. Cross-currency transfer требует отдельного contract и не входит в W1-05.

## Void, delete and restore

MVP должен сохранять финансовую историю через soft delete, `voided` status или equivalent record-state mechanism. Hard delete user-facing API для transfers запрещен.

Правила:

- `voided` transfer исключается из текущих balances, reports и cash-flow, но остается в истории/audit, если endpoint явно запрашивает историю;
- soft-deleted transfer не отображается в обычных lists/reports и не участвует в текущих расчетах;
- restore re-applies both sides atomically after повторной authz и state validation;
- restore должен заново проверить, что оба accounts все еще находятся в разрешенном same-scope и доступны caller;
- если один из счетов стал archived/deleted или membership потерян, restore запрещается нейтрально или state-specific только для уже видимого context;
- void/delete/restore пишут audit event без amount/description/account names;
- бывший member не может читать или restore old shared transfer после `left`/`revoked`, даже если он был `createdByUserId`.

Если implementation хранит transfer как две физические rows, contract-level invariant остается тем же: public API видит один logical transfer, void/delete/restore/update не могут примениться только к одной стороне.

## Audit and logging boundaries

Audit required for:

- transfer create allow/deny;
- transfer update allow/deny;
- transfer void/delete/restore;
- transfer denied due to unsupported scope;
- suspicious repeated cross-scope attempts;
- balance/projection repair jobs, если они затрагивают transfers.

Audit event may contain:

- timestamp;
- actor user id или system actor id;
- action;
- target type `Transaction`;
- target id, если он уже создан или был supplied by caller and safe for security investigation;
- scope type `personal` или `household`;
- scope id for allowed same-scope result;
- result `allow`, `deny`, `state-deny`;
- request id;
- internal reason code без sensitive values.

Audit/log/telemetry must not contain:

- amount, balances, report totals;
- transfer description;
- account/category names;
- emails, invite/reset/session tokens;
- raw request/response body;
- hidden-side owner, household, membership status или account existence diagnostics;
- stack traces, SQL text, environment secrets.

Denied transfer audit must not enrich a caller-supplied hidden id with hidden account metadata. If the target was hidden/inaccessible, store only coarse reason such as `transfer_scope_denied` and request id, unless separate security investigation tooling with stricter controls exists.

## QA proof obligations

QA/release evidence must prove:

- allowed `personal_same_owner`: user A transfers between two own personal accounts and sees expected `transferScope`;
- denied cross-user personal: A cannot transfer from/to personal account B; response uses `TRANSFER_SCOPE_NOT_SUPPORTED` and reveals no B details;
- allowed `household_same_household`: active A/B transfers between two shared accounts in Household AB;
- denied cross-household shared: A cannot transfer shared AB -> shared C;
- denied personal -> shared with `TRANSFER_SCOPE_NOT_SUPPORTED`;
- denied shared -> personal with `TRANSFER_SCOPE_NOT_SUPPORTED`;
- invited member cannot create/read shared transfer before accept;
- former member cannot read/create/restore shared transfer after `left`/`revoked`, including with cached ids;
- missing, hidden and unsupported counterparty responses are neutral in message/details and do not expose hidden side;
- no partial write occurs when any authz, validation, currency, state or concurrency check fails;
- balances/projections apply both sides atomically for create/update/void/delete/restore;
- reports filter visible transfers before aggregation and do not include personal transfers of another member;
- logs/audit for successful and denied transfers contain no amounts, descriptions, account names, balances, tokens or raw bodies;
- golden error tests compare personal<->shared, cross-user personal and cross-household shared for identical public message and safe details;
- concurrency tests prove stale `version` cannot double-apply or half-apply balance effects.

Minimum traceability to release gates:

- RG-02 covers transfer abuse in list/detail/search/report/category surfaces;
- RG-03 covers personal<->shared denial;
- RG-04 covers allowed same-owner and same-household transfers;
- RG-05 covers invited/former member denial;
- RG-06 covers report filtering before aggregation;
- RG-08 covers log/audit minimization;
- RG-10 covers neutral access-denied and validation errors;
- RG-12 blocks release on unresolved P0/P1 authz/privacy defects.

## Release gates for transfer API

Transfer API is not releasable until all gates are closed:

| Gate | Required evidence |
| --- | --- |
| TR-RG-01 Same-scope allow | Automated API tests for `personal_same_owner` and `household_same_household` pass. |
| TR-RG-02 Unsupported scope deny | Automated API tests for personal<->shared, cross-user personal and cross-household shared pass with safe canonical error behavior. |
| TR-RG-03 Hidden side neutrality | Golden responses show no hidden-side details in code/message/details/logs for transfer denials. |
| TR-RG-04 Atomicity | Integration tests show no partial transfer row or one-sided balance/projection change after denied or failed requests. |
| TR-RG-05 Balance consistency | Create/update/void/delete/restore tests prove both accounts' balances/projections change consistently without selecting storage strategy. |
| TR-RG-06 Report safety | Report tests prove transfers are filtered by visible accounts before totals, balances, trend, drill-down and export. |
| TR-RG-07 Membership safety | Invited/former member tests pass, including stale sessions/cached ids after membership changes. |
| TR-RG-08 Audit/log safety | Log inspection evidence confirms no amounts, descriptions, account names, balances, tokens or raw payloads. |
| TR-RG-09 Concurrency | Version/concurrent update tests prevent double-apply, lost update and half-apply. |
| TR-RG-10 Escalation closure | Any request for personal<->shared, cross-user or cross-household transfer is either rejected by this contract or formally escalated before implementation. |

## Risks and escalation triggers

Primary risks:

- a personal account can leak through counterparty fields, error differences, logs, reports or shared UI labels;
- balance projection can become inconsistent if transfer sides are applied separately;
- former member can retain access through stale session, cache, export or report materialization;
- report aggregation can double-count transfers or treat transfer as income/expense without an explicit report decision;
- cross-currency transfer can accidentally introduce exchange semantics outside MVP.

Escalate to Product/Security/Privacy before implementation or release if:

- product asks to allow personal<->shared transfer;
- product asks to allow transfer involving personal account of another user;
- product asks to allow shared transfer across households;
- implementation needs split visibility, different descriptions per side, or masked counterparty presentation;
- support/admin/debug tooling needs to read hidden transfer values;
- transfer QA repeatedly fails hidden-side neutrality, atomicity, report filtering or audit/log minimization.

Safe default remains: deny unsupported scope, filter before aggregation, no hidden counts, no hidden-side diagnostics, no partial writes.
