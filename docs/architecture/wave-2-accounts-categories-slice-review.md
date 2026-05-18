# Ревью среза Wave 2 по accounts/categories

## Краткий вывод

Рекомендация: Go для следующей worker-волны, ограниченной последующим укреплением accounts/categories; Hold для MVP-релиза.

Срез Wave 2 accounts/categories подключает ожидаемую узкую backend-поверхность: `/health` плюс 16 утвержденных операций `/api/v1/accounts*` и `/api/v1/categories*`. Runtime-доказательства по маршрутам и route-contract тесты показывают, что исключенные семейства маршрутов остаются неподключенными: auth/session/password reset placeholders, households/invites/memberships, transactions/transfers/reports, exports/privacy lifecycle, imports, bank/SMS/push/broker, debug и support routes.

Реализованный прототип соблюдает ключевые продуктовые правила приватности для ручного среза accounts/categories: personal-записи доступны только владельцу, shared/household-записи требуют активного членства в household, а invited/former/other actors получают отказ. Для отсутствующих и недоступных прямых ID в покрытых тестах используется нейтральная публичная форма отказа. Lists, search, autocomplete и pagination metadata фильтруются после проверки видимости и не раскрывают скрытые counts, facets или placeholders.

P0/P1 blockers для принятия этого среза как prototype service-route increment не найдено. MVP release остается в статусе Hold, пока не завершены production auth/session, DB-backed persistence, trigger-level DB hardening, transactions/reports/transfers и privacy/security release gates.

## Проверенные артефакты

- `docs/planning/accounts-categories-route-subset.md`
- `docs/planning/wave-2-service-slice-plan.md`
- `api/openapi/openapi.yaml`
- `apps/backend/src/app/main.py`
- `apps/backend/src/app/api/router.py`
- `apps/backend/src/app/api/auth_context.py`
- `apps/backend/src/app/accounts/*`
- `apps/backend/src/app/categories/*`
- `apps/backend/src/app/authz/predicates.py`
- `apps/backend/src/app/db/models.py`
- `db/migrations/versions/20260517_0001_accounts_categories_slice.py`
- `apps/backend/tests/accounts/*`
- `apps/backend/tests/categories/*`
- `apps/backend/tests/api/test_accounts_categories_route_contract.py`
- `apps/backend/tests/api/test_accounts_categories_privacy.py`
- `apps/backend/tests/db/test_accounts_categories_migration_slice.py`
- `artifacts/evidence/api/backend-pytest.md`
- `artifacts/evidence/api/backend-route-inventory.md`
- `artifacts/evidence/security/route-inventory/backend-route-inventory.md`
- `artifacts/evidence/api/accounts-categories-route-contract.md`
- `artifacts/evidence/authz/accounts-categories-privacy.md`
- `artifacts/evidence/api/accounts-categories-migration-slice.md`
- `artifacts/evidence/api/openapi-redocly-lint.md`

## Доказательства валидации

Статус evidence для обязательных gates среза: pass.

- Full backend pytest: `58 passed, 1 warning`.
- Focused accounts/categories router tests: `14 passed, 1 warning`.
- Route contract QA: `4 passed, 1 warning`.
- Privacy/authz QA: `6 passed, 0 skipped, 1 warning`.
- Migration slice QA: `6 passed, 1 warning`.
- Redocly OpenAPI lint: pass.
- Runtime route inventory: pass, с `/health` и ровно 16 schema-included accounts/categories routes.
- Security route inventory: pass, исключенные financial, credential, lifecycle, diagnostic и placeholder auth route families отсутствуют.

Повторяющееся предупреждение - Python 3.14 `pytest_asyncio` deprecation warning; оно не влияет на валидацию среза.

## Функциональные выводы

Смонтированное приложение включает `/health` в `apps/backend/src/app/main.py` и монтирует `api_router` под `/api/v1`. `apps/backend/src/app/api/router.py` включает только accounts и categories routers.

Accounts предоставляют утвержденные операции list, create, autocomplete, detail, update, delete, archive и restore. Service выводит personal ownership из текущего actor, требует active membership для создания shared account, фильтрует list/search/autocomplete через `canReadAccount` и использует soft lifecycle transitions для archive/delete/restore.

Categories предоставляют утвержденные операции list, create, autocomplete, detail, update, delete, archive и restore. Service выводит personal category ownership из текущего actor, требует active membership для создания household category, фильтрует list/search/autocomplete через `canReadCategory` и удерживает lifecycle mutations в рамках видимых records.

Текущие repositories являются process-local in-memory repositories. Это приемлемо только как prototype/non-release slice implementation. Для production release нужны DB-backed repository integration, transaction semantics, migration-backed persistence и concurrency behavior, сохраняющееся после process restart.

## Выводы по privacy/security

Personal privacy соблюдена в покрытой implementation и tests: personal accounts/categories видны только владельцу. Shared accounts и household categories видны только active members соответствующего household. Invited, former/left и other-household actors получают отказ в route tests и privacy matrix.

Direct ID probing нейтрален в покрытых тестах. Missing и inaccessible account IDs возвращают одинаковую публичную форму отказа для account; missing и inaccessible category IDs возвращают одинаковую публичную форму отказа для category. Hidden names и IDs не повторяются в этих denial responses.

Lists, search, autocomplete и pagination metadata фильтруются после visibility. Evidence и tests проверяют отсутствие hidden count/facet/placeholder markers, отсутствие `totalCount` и subset behavior для autocomplete.

Auth boundary работает по default-deny. `provide_actor()` возвращает `None`, routes зависят от `CurrentActor`, а unauthenticated runtime execution возвращает 401, если tests явно не подменяют provider. Placeholder auth router все еще есть в codebase, но не импортируется и не монтируется `app.main`.

Report-mode invariants остаются только архитектурными в этом срезе. Принятые modes `shared_family_report` и `combined_viewer_overview` присутствуют в authz/OpenAPI vocabulary, но report routes не смонтированы. Transfer predicates и same-scope transfer vocabulary существуют вне смонтированного среза; transfer routes не смонтированы.

## Scope маршрутов и миграции

Route scope соответствует замороженному allowlist:

- 8 account routes смонтированы.
- 8 category routes смонтированы.
- `/health` смонтирован.
- FastAPI docs/OpenAPI helper routes существуют как non-schema framework routes.

Исключенные route families отсутствуют в runtime evidence: auth/users/sessions/password reset, households/invites/memberships, transactions/transfers/reports, exports/privacy lifecycle, imports/bank/SMS/push/broker/external credentials, debug/support и diagnostic bypass routes.

Migration revision `20260517_0001` создает только `users`, `households`, `memberships`, `accounts` и `categories`. Она включает UUID primary keys, timestamps, optimistic versions, active membership indexes, exactly-one-scope checks, account/category visibility indexes, currency shape и account money numeric columns. Она явно исключает invites, sessions, password reset tokens, transactions, export/privacy lifecycle, audit/outbox, reports и transfers.

DB immutability gap честно отражен. Account ownership fields и category scope fields обеспечиваются на уровне API/schema/service behavior для этого среза, но trigger-level protection остается pre-release DB hardening TODO и не заявлена как завершенная.

## P0/P1 blockers

P0 blockers: 0.

P1 blockers для принятия этого prototype slice в следующую worker-волну: 0.

Release blockers остаются открытыми и намеренно не решаются этим срезом:

- Production auth/session implementation с реальной credential verification, token/session storage, revocation, CSRF/cookie или mobile bearer behavior, rate limits и audit evidence.
- DB-backed persistence/repository integration вместо in-memory repositories.
- DB trigger hardening для immutable account ownership и category scope fields.
- Transactions, reports и mounted transfer behavior.
- Privacy/security release gates, включая более широкие endpoint-contract, log-safety, persistence и regression evidence.

## Пробелы в evidence

Route contract evidence проверяет mounted paths и operation IDs, но не полностью валидирует runtime response bodies по canonical OpenAPI schemas. В частности, category service errors сейчас используют FastAPI `HTTPException.detail` shape в tests, тогда как canonical OpenAPI error response - это `ErrorEnvelope` с top-level `error`. Нужно добавить response-envelope contract tests перед release hardening.

Privacy evidence покрывает list/detail/autocomplete и immutable update probes для accounts/categories. Оно не покрывает каждую lifecycle mutation для каждого actor по archive/restore/delete в cross-resource privacy matrix, хотя focused router tests покрывают representative lifecycle behavior.

Нет evidence, доказывающего DB-backed persistence, process restart durability, concurrent writes, optimistic locking enforcement для accounts или production transaction boundaries. Это ожидаемо для текущего in-memory prototype и остается non-release gap.

Нет evidence, заявляющего, что DB triggers обеспечивают immutable ownership/scope. Migration evidence корректно фиксирует это как known gap.

## Рекомендация Go/Hold

Go для следующей worker-волны, сфокусированной на hardening среза accounts/categories.

Hold для MVP-релиза.

Этот срез приемлем как узкий prototype increment, потому что passing evidence подтверждает mounted route surface, core privacy rules, neutral direct-ID behavior и migration scope. Он не готов к релизу, потому что production auth/session, DB persistence, DB trigger hardening, transaction/report/transfer behavior и release-grade privacy/security gates еще не завершены.

## Рекомендуемая следующая worker-волна

1. API contract hardening worker: добавить runtime response-shape tests для success и error envelopes по canonical OpenAPI accounts/categories schemas.
2. Persistence worker: заменить in-memory accounts/categories repositories на DB-backed repositories с использованием утвержденных migration tables.
3. DB hardening worker: реализовать и протестировать immutable ownership/scope triggers для account `ownership_type`/`owner_user_id`/`household_id` и category `category_scope`/`owner_user_id`/`household_id`.
4. Security/auth worker: реализовать production auth/session boundary до любого release candidate или real-user deployment.
5. Privacy QA worker: расширить lifecycle mutation privacy matrix по archive/restore/delete, stale IDs, archived/deleted states, logs и DB-backed persistence.
6. Transactions/reports/transfers planning worker: держать routes неподключенными, пока следующий scoped implementation plan явно не покроет same-scope transfers и report-mode privacy.

## Definition of done

Это integration review завершено, когда:

- Review file существует по пути `docs/architecture/wave-2-accounts-categories-slice-review.md`.
- Утвержденные 16 accounts/categories routes плюс `/health` сверены с route inventory evidence.
- Исключенные route families сверены с route inventory и security evidence.
- Personal/shared visibility rules сверены с implementation и privacy evidence.
- Invited/former/other actor denial сверен с tests и evidence.
- Neutral direct-ID behavior и отсутствие hidden-count/facet/placeholder сверены с tests и evidence.
- Ownership/scope immutability проверена на уровне API/service behavior, а DB trigger hardening отмечен как incomplete.
- Migration scope проверен как minimal и без overclaiming.
- Required evidence pass counts записаны.
- In-memory persistence отмечена как prototype/non-release limitation.
- Go/Hold recommendation и next worker wave записаны.
