# Architecture Wave 0 Review

## Executive summary

Статус: **Go for next wave** после alignment P1-01/P1-02 для перехода к проектированию backend API/client contracts.

P0-конфликтов не найдено: базовые security/privacy инварианты про ручной ввод, отсутствие импорта/API/SMS/push, запрет хранения банковских секретов, server-side authz, personal/shared visibility и фильтрацию до агрегации в целом согласованы.

P1-блокеры уровня архитектурного контракта закрыты после продуктового решения:

1. P1-01 closed: personal-счета, personal-операции, personal-категории и personal-агрегаты другого участника семьи не раскрываются в MVP.
2. P1-02 closed: report modes разведены как `shared family report` только по shared-данным household и `combined viewer overview` по shared-счетам + personal-счетам текущего viewer.

Пакет можно переводить в следующую волну проектирования API/backend/клиентов.

## Reviewed documents

- `docs/product-mvp.md`
- `docs/current-status.md`
- `docs/architecture/domain-model.md`
- `docs/architecture/access-model.md`
- `docs/security/security-baseline.md`
- `docs/compliance/privacy-baseline.md`
- `docs/testing/access-security-scenarios.md`

## Consistency findings

- MVP scope согласован: MVP строится на ручном вводе счетов, операций, категорий и отчетов. Импорт Excel/CSV/файлов, банковские API, SMS/push-интеграции, банковские/брокерские credentials, налоговая аналитика, рекомендации и массовая поддержка источников вынесены за пределы MVP.
- Доменные сущности в целом согласованы: `User`, `Household`/`FamilySpace`, `Membership`, `Account`, `Operation`/`Transaction`, `Category`, `AnalyticsView`, audit/security/supporting concepts. Термины `Household` и `FamilySpace`, `Operation` и `Transaction` используются как близкие синонимы, но API-дизайну нужен один канонический словарь.
- Ownership согласован: personal account/category принадлежат `User`, shared/household account/category принадлежат `Household`, operation наследует видимость от account.
- Access model согласован на ключевых инвариантах: deny by default, server-side authz, одинаковые predicates для detail/list/search/autocomplete/report/export, нейтральные ошибки, отсутствие hidden counts, инвалидация доступа после изменения membership.
- Personal/shared visibility согласована на уровне security/privacy/testing: personal-данные другого участника не видны прямо, через списки, search, категории, переводы, отчеты, агрегаты, ошибки, логи и audit; shared-данные видны только active members того же household.
- Правило аналитики "фильтрация до агрегации" явно зафиксировано в access/security/testing и поддержано privacy baseline.
- Переводы personal<->shared в MVP фактически запрещены в access-model и testing. Security/privacy допускают формулу "split visibility или запрет"; выбранный безопасный вариант для MVP - запрет. Same-scope transfers остаются разрешенными: personal->personal одного владельца и shared->shared внутри одного household.
- Security/privacy release gates покрыты QA-документом: AS/NEG/SEC/PRIV/RG сценарии закрывают cross-user, cross-family, personal-vs-shared, invite/former member, neutral errors, logs/audit, secrets, backup, export/delete/leave family.

## Conflicts or drift

### P1-A: Product/status drift по personal-only видимости - closed

Product/current-status теперь фиксируют, что модель доступа и видимости личных счетов между участниками семьи закрыта для MVP: personal видит только владелец, shared видят active members.

Product явно подтвердил, что "общий семейный бюджет" в MVP не означает раскрытие personal-счетов, операций, категорий или агрегатов второго участника.

### P1-B: Drift по семантике семейной аналитики - closed

Domain/access/testing теперь разделяют два режима: `shared family report` включает только shared-счета household, а `combined viewer overview` включает shared-счета household и personal-счета самого viewer.

QA должен проверять оба report modes; ни один режим не включает personal-счета, операции, категории или агрегаты второго участника.

### Non-blocking terminology drift

- `Household` и `FamilySpace` используются параллельно.
- `Operation` и `Transaction` используются параллельно.
- Membership statuses частично различаются: `left`, `revoked`, `removed`. Следующей волне нужно выбрать канонический enum и маппинг.

## Blocking issues P0/P1

- P0: не найдено.
- P1-01: closed - personal-only видимость подтверждена как финальное MVP-правило.
- P1-02: closed - API/QA контракт для `shared family report` и `combined viewer overview` зафиксирован на уровне Wave 0 docs.

## Non-blocking risks

- Product doc неявно говорит "переводы" как MVP-сценарий, а архитектурные документы уточняют запрет personal<->shared. Риск снимается, если в следующей волне API явно поддерживает только same-scope transfers и возвращает общий `TRANSFER_SCOPE_NOT_SUPPORTED` для personal/shared.
- Одновременная поставка Android и PWA может увеличить объем первой реализации, но не меняет архитектурные инварианты.
- SaaS/self-hosted, юрисдикция, formal privacy policy, DPA, retention/deletion SLA, 2FA/passkeys, field-level encryption и production secret manager остаются post-MVP/escalation темами; перед публичным запуском они могут стать блокерами.
- Кастомные иконки могут затронуть хранение файлов и moderation/privacy; безопаснее начинать с системного каталога и пользовательского выбора.
- `currentBalance` как persisted state или computed value, валютная модель и исторический доступ former member к shared-данным остаются важными design decisions, но не ломают Wave 0 security/privacy инварианты при безопасных defaults.

## Required decisions before implementation

1. Backend/API must choose canonical names: `Household` или `FamilySpace`, `Operation` или `Transaction`.
2. Backend/API must choose canonical membership status enum and transitions: invited, active, left, revoked/removed, expired for invites if needed.
3. Product/API must confirm same-scope transfer contract and error code for personal<->shared prohibition.
4. Backend/API must decide balance calculation contract: stored `currentBalance`, computed balance, or cached computed projection.
5. Backend/API must define minimum currency behavior for MVP and explicitly defer complex exchange/revaluation.

## Go recommendation for next wave

Рекомендация: **Go for next wave** после закрытия P1-01 и P1-02.

После точечного решения по personal-only видимости и аналитическим report modes можно переходить к следующей волне с безопасными инвариантами:

- ручной ввод;
- no import/API/SMS/push;
- personal-only для личных данных;
- shared-only для household данных;
- report modes: `shared family report` и `combined viewer overview`;
- фильтрация до агрегации;
- запрет personal<->shared transfers;
- release gates из testing документа как обязательные для MVP.

## Required next-wave tasks

1. API Architect: зафиксировать canonical domain vocabulary и enum'ы ownership/membership/status.
2. Backend Architect: спроектировать authz predicates для account/operation/category/report/export/search/autocomplete с reuse между list/detail/report.
3. Backend Architect: спроектировать report API modes для `shared family report` и `combined viewer overview`.
4. Backend Architect: спроектировать transfer API с запретом personal<->shared и same-scope validation.
5. Security Engineer: превратить security baseline в backend release checklist: auth/session/reset/invite/rate limits/CSRF/CORS/log masking/secrets/backup/restore.
6. Privacy/Compliance Reviewer: уточнить export/delete/leave family flows и границы former member access для закрытого MVP.
7. QA Engineer: обновить traceability после решения report modes и добавить тесты для каждого endpoint surface.
8. Client Architect: спроектировать UI states так, чтобы shared operations явно предупреждали о видимости семье, а personal данные другого участника не имели client-side placeholders/counts.

## Evidence checklist

- Проверен `product-mvp.md`: ручной ввод входит в MVP; import/API/SMS/push, налоговая аналитика и инвестиционные рекомендации вынесены в post-MVP.
- Проверен `current-status.md`: Wave 0 product scope завершен; P1-01/P1-02 закрыты; следующий фокус - API/client contracts.
- Проверен `domain-model.md`: сущности, ownership, visibility, ручной `sourceType = manual`, report modes `shared family report`/`combined viewer overview`, фильтрация аналитики по видимости, запрет раскрытия чужих personal через аналитику/категории/переводы.
- Проверен `access-model.md`: deny by default, server-side authz, `visibleAccountIds` для обоих report modes, таблица visibility, neutral errors, фильтрация до агрегации, запрет personal<->shared transfers, acceptance checks.
- Проверен `security-baseline.md`: authn/authz/session/logging/audit/secrets/backup gates; отсутствие банковских секретов и интеграций; release requirements до MVP.
- Проверен `privacy-baseline.md`: data inventory, sensitivity, minimization, notice, export/delete/leave family, retention, logging/telemetry, backup privacy, escalation triggers.
- Проверен `access-security-scenarios.md`: AS/NEG/SEC/PRIV/RG сценарии покрывают access/security/privacy release gates, включая personal/shared, transfers, logs, secrets, backup, export/delete/leave family.
- P0/P1 перечислены явно; P1-01/P1-02 отмечены closed.
- Остаточные риски и required decisions вынесены отдельно.
- Рекомендация Go for next wave указана явно.
