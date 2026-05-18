# Модель доступа и видимости MVP

## Контекст

Документ фиксирует минимальную модель доступа для MVP личных и общих семейных финансов. Базовое безопасное правило:

- `personal`-счета, операции, категории и аналитика видны только владельцу.
- `shared`-счета, операции, категории и аналитика видны только активным участникам того же `Household`.
- Личные счета другого участника не раскрываются в списках, поиске, отчетах, агрегатах, категориях, переводах, ошибках API, логах и audit-событиях.

MVP не вводит сложные роли внутри семьи. Активный участник семейного пространства может работать с общими семейными данными, но это не дает ему доступа к личным данным другого участника.

## Принципы доступа

1. **Deny by default.** Любой endpoint и backend-сервис сначала запрещает доступ, затем явно разрешает его по `ownerUserId` или active `Membership`.
2. **Серверная авторизация обязательна.** UI-фильтры, скрытые поля, UUID и клиентские проверки не являются контролем доступа.
3. **Scope у объекта один.** Финансовая запись относится либо к личной области пользователя, либо к общей области семьи. Смешанный scope в одной записи запрещен.
4. **Видимость наследуется от владельца области.** `Operation` наследует доступ от счета, `AnalyticsView` строится только из уже отфильтрованных видимых счетов и операций.
5. **Фильтрация до агрегации.** Отчеты, остатки, category breakdown, search и autocomplete сначала применяют access filter, затем считают суммы и возвращают результаты.
6. **Нейтральность отказов.** Ответ API для объекта вне области доступа не подтверждает, существует ли объект.
7. **Минимальное раскрытие профиля.** Участникам семьи виден только минимальный профиль другого участника, необходимый для совместного учета.
8. **Выход из семьи немедленно отзывает будущий доступ.** Бывший участник теряет доступ к shared-данным после смены статуса membership и инвалидирования кэшей/сессий.
9. **История не удаляется физически по умолчанию.** Удаление финансовых объектов в MVP предпочтительно делать через archive/soft delete, чтобы не ломать аудит и расчеты.

## Акторы

| Актор | Описание |
| --- | --- |
| `Anonymous` | Неаутентифицированный пользователь. |
| `AuthenticatedUser` | Пользователь с валидной сессией. |
| `Self` | Пользователь, обращающийся к своему профилю и личным данным. |
| `AccountOwner` | Владелец `personal`-счета или категории. |
| `ActiveHouseholdMember` | Пользователь с active `Membership` в `Household`. |
| `InvitedMember` | Пользователь с приглашением, но без active membership. |
| `FormerMember` | Пользователь со статусом `left`, `removed` или `revoked`. |
| `OtherUser` | Пользователь вне нужного personal scope или household. |
| `System` | Backend-процессы, выполняющие проверенные операции, аудит и пересчет. |

## Ресурсы

| Ресурс | Scope | Владелец доступа |
| --- | --- | --- |
| `User` | personal | Сам пользователь; семье доступен только минимальный профиль. |
| `Household` | shared | Активные участники через `Membership`. |
| `Membership` | shared | `Household`; доступ зависит от статуса участия. |
| `Account` | personal/shared | `ownerUserId` для personal, `householdId` для shared. |
| `Operation` | inherited | Наследует scope от `accountId`; переводы в MVP ограничены одинаковым scope. |
| `Category` | personal/household | `ownerUserId` для personal, `householdId` для household. |
| `AnalyticsView` | computed | Текущий пользователь; строится только по видимым данным. |

## Матрица доступа actor x resource x action

Обозначения: `Y` - разрешено, `N` - запрещено, `Limited` - только минимальные поля или ограниченный сценарий, `Own` - только свои personal-данные, `Shared` - только shared-данные active household.

| Actor / Resource / Action | User R | User C/U/D | Household R | Household C/U/D | Membership R | Membership C/U/D | Account R | Account C/U/D | Operation R | Operation C/U/D | Category R | Category C/U/D | AnalyticsView R | AnalyticsView C/U/D |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Anonymous` | N | Register only | N | N | N | N | N | N | N | N | N | N | N | N |
| `Self` | Y | Own profile only | Shared | Create own household | Shared | Own/Shared limited | Own + Shared | Own + Shared | Own + Shared | Own + Shared | Own + Shared | Own + Shared | Own + Shared | Read-only computed |
| `AccountOwner` | Y | Own profile only | Shared if member | Shared if member | Shared if member | Limited | Own + Shared | Own personal + Shared | Own + Shared | Own personal + Shared | Own + Shared | Own personal + Shared | Own + Shared | Read-only computed |
| `ActiveHouseholdMember` | Limited | N | Shared | Limited | Shared | Invite/leave/revoke limited | Shared only for other member data | Shared only | Shared only for other member data | Shared only | Household categories + own personal | Household categories + own personal | Shared + own personal | Read-only computed |
| `InvitedMember` | Own | Own profile only | Limited invitation context | N | Own invitation only | Accept/decline only | N | N | N | N | N | N | N | N |
| `FormerMember` | Own | Own profile only | N | N | Own ended membership metadata only | N | Own personal only | Own personal only | Own personal only | Own personal only | Own personal categories only | Own personal categories only | Own personal only | Read-only computed |
| `OtherUser` | Own only | Own only | N | N | N | N | Own only | Own only | Own only | Own only | Own only | Own only | Own only | Read-only computed |
| `System` | Limited | Service action only | Limited | Service action only | Limited | Service action only | Limited | Service action only | Limited | Service action only | Limited | Service action only | Limited | Generate only |

## CRUD-правила по ресурсам

### User

| Action | Правило |
| --- | --- |
| Create | `Anonymous` может создать только собственную учетную запись через регистрацию. Создание пользователя от имени другого пользователя запрещено. |
| Read | Пользователь читает свой полный профиль. Активный участник семьи видит только минимальный профиль другого участника: `userId`, `displayName`, статус участия. Email и security-настройки не раскрываются без отдельного решения. |
| Update | Пользователь обновляет только свой профиль и настройки. Другой участник семьи не может менять профиль пользователя. |
| Delete | Физическое удаление вне MVP. Допустимы deactivate/soft delete по отдельной процедуре без раскрытия финансовых данных другим участникам. |

### Household

| Action | Правило |
| --- | --- |
| Create | Аутентифицированный пользователь может создать семейное пространство, если MVP допускает одно active household на пользователя. Создатель получает active `Membership`. |
| Read | Только active members. Invited member видит только данные приглашения, достаточные для принятия. |
| Update | Active member может менять минимальные настройки household, если это не расширяет доступ и не меняет финансовую историю. Сложные роли вне MVP. |
| Delete | Физическое удаление вне MVP. Архивация допустима только если не нарушает доступ к audit/history; требует блокировки shared-операций после архивации. |

### Membership

| Action | Правило |
| --- | --- |
| Create | Active member может создать приглашение второго участника в пределах лимита MVP: максимум 2 active members. Invite token одноразовый, короткоживущий, хранится как hash. |
| Read | Active members видят состав семьи на минимальном уровне. Invited user видит только собственное приглашение. Former member видит только факт своего бывшего участия, если это нужно для профиля/audit. |
| Update | Invited user может accept/decline свое приглашение. Active member может отозвать pending invite. Выход пользователя меняет его membership на `left`; отзыв - на `revoked` или `removed`. |
| Delete | Физическое удаление membership запрещено в MVP; используется статус и `endedAt` для аудита. |

### Account

| Action | Personal account | Shared account |
| --- | --- | --- |
| Create | Пользователь создает только для себя с `ownerUserId = currentUserId`. | Active member создает счет в своем `householdId`. |
| Read | Только `ownerUserId`. Не виден второму участнику семьи ни прямо, ни через списки/search. | Только active members того же household. |
| Update | Только владелец. Изменение `ownershipType` personal/shared запрещено в MVP без отдельного product/security решения. | Active members могут обновлять название и параметры, не меняющие историю. |
| Delete | Если нет операций, возможно soft delete владельцем; если есть операции - archive. | Если нет операций, возможно soft delete active member; если есть операции - archive. |

### Operation

| Action | Правило |
| --- | --- |
| Create | Пользователь может создать операцию только на видимом ему счете. `accountId` обязан пройти authz до записи. Для income/expense категория должна быть видимой и совместимой со scope счета. |
| Read | Видимость наследуется от `accountId`. Операции personal-счета другого участника не видны ни через прямой id, ни через списки, отчеты, поиск, категории или переводы. |
| Update | Только пользователь с доступом к счету операции. Нельзя переносить операцию на счет или категорию вне видимого scope. |
| Delete | Soft delete/archive только пользователем с доступом к счету. История и audit сохраняют ссылки без чувствительных значений в логах. |

### Category

| Action | Personal category | Household category |
| --- | --- | --- |
| Create | Пользователь создает только для себя с `ownerUserId = currentUserId`. | Active member создает категорию в своем `householdId`. |
| Read | Только владелец. | Только active members household. |
| Update | Только владелец. | Active members household. |
| Delete | Archive вместо физического удаления, если есть операции. | Archive вместо физического удаления, если есть операции. |

### AnalyticsView

| Action | Правило |
| --- | --- |
| Create | Не является пользовательской записью в MVP; backend вычисляет представление на запрос. |
| Read | Текущий пользователь получает только агрегаты по видимым ему счетам и операциям. |
| Update | Не применяется; изменение периода/фильтров создает новый вычисляемый view. |
| Delete | Не применяется; кэш аналитики, если появится, очищается по scope пользователя/household и не является источником правды. |

## Таблица visibility

| Область | Account | Operation | Category | Analytics |
| --- | --- | --- | --- | --- |
| `personal` текущего пользователя | Видит и изменяет владелец. | Видит и изменяет владелец через доступ к счету. | Видит и изменяет владелец. | Включается в `combined viewer overview`, но не в `shared family report`. |
| `personal` другого участника семьи | Не возвращается. | Не возвращается. | Не возвращается, кроме случая family category, которая сама по себе не раскрывает личную операцию. | Не включается даже агрегированно. |
| `shared` household active member | Видят active members. | Видят active members. | Видят active members. | Включается в `shared family report` и `combined viewer overview`. |
| `shared` чужого household | Не возвращается. | Не возвращается. | Не возвращается. | Не включается. |
| `invited` membership | Shared-данные не видны до accept. | Не видны. | Не видны. | Не строится. |
| `left/removed/revoked` membership | Shared-данные больше не видны. | Shared-операции больше не видны. | Household categories больше не видны. | Shared analytics больше не строится. |

## Visibility rules

### Personal/shared accounts

- Account list для пользователя состоит из его personal-счетов и shared-счетов household, где у него active membership.
- Account detail применяет то же правило, что list; прямой `accountId` не расширяет доступ.
- Search/autocomplete возвращают только счета из видимого набора.
- Балансы personal-счетов другого участника не возвращаются и не входят в totals.
- `ownershipType` создается явно и не меняется в MVP. Перенос personal account в shared или обратно требует отдельного решения и миграции видимости.

### Operations

- Operation list строится только по видимым счетам.
- Operation detail проверяет доступ к `accountId` до чтения тела операции.
- При создании или изменении операции backend проверяет доступ к счету, counterparty account, category и household до записи.
- Описание, сумма, дата, категория и автор операции personal-счета другого участника не раскрываются.
- Shared-операция видна всем active members, включая описание, категорию и историю изменений, поэтому UI должен помогать не вносить личные события в shared-счет.

### Categories

- Personal category видна только владельцу и может применяться к personal-операциям владельца.
- Household category видна active members и применяется к shared-операциям этого household.
- Для personal-операции допускается household category только если это не раскрывает саму операцию. Категория может быть видна семье, но факт ее использования в личной операции другого участника не виден.
- Category list/search не возвращают personal categories другого пользователя.
- Архивированная категория остается связанной с историческими операциями, но не выбирается для новых операций.

### Analytics

- AnalyticsView получает `viewerUserId`, `householdId` и явный `reportMode`, затем строит набор `visibleAccountIds`.
- Для `shared family report`: `visibleAccountIds = shared accounts active household`.
- Для `combined viewer overview`: `visibleAccountIds = shared accounts active household + viewer personal accounts`.
- Personal-счета другого участника исключаются до агрегации: из totals, category breakdown, account balances, charts, search facets и exports.
- `shared family report` включает только shared-счета, shared-операции и household-категории household.
- `combined viewer overview` включает shared-счета семьи и personal-счета самого viewer, но не personal-счета, операции, категории или агрегаты второго участника.

## Семейное приглашение и выход из семьи

### Приглашение

- Приглашение создает active member household.
- MVP допускает максимум двух active members в household.
- Invite token одноразовый, короткоживущий, хранится только как hash.
- До принятия приглашенный пользователь не получает доступ к shared-счетам, операциям, категориям, аналитике и составу семьи сверх минимального контекста приглашения.
- Принять приглашение может только пользователь, для которого оно предназначено, либо пользователь, подтвердивший тот же email/identifier, если приглашение создавалось по email.
- После accept membership становится `active`, старый invite token инвалидируется, shared-доступ появляется только с этого момента.
- После decline/revoke/expire token нельзя использовать повторно.

### Выход или отзыв участия

- Пользователь может выйти из household; active member может отозвать pending invite. Удаление active участника другим участником в MVP требует явного product/security решения, если оно не равно самостоятельному выходу.
- После `left`, `removed` или `revoked` пользователь немедленно теряет доступ к shared-счетам, операциям, категориям и отчетам.
- Backend должен инвалидировать или сузить server-side сессии, refresh tokens, кэши и offline/PWA snapshots бывшего участника.
- Исторические shared-операции остаются в household для оставшегося active member и аудита.
- Бывший участник не получает дальнейший read-доступ к историческим shared-операциям через API. Если продукт потребует исторический доступ за период участия, это escalation trigger.

## Переводы между personal и shared

Безопасный MVP-вариант: **запретить переводы между personal и shared счетами** до отдельного решения и реализации split visibility.

Разрешены только:

- `personal -> personal`, если оба счета принадлежат текущему пользователю;
- `shared -> shared`, если оба счета принадлежат одному household и пользователь является active member.

Запрещены:

- `personal -> shared`;
- `shared -> personal`;
- перевод между personal-счетами разных пользователей;
- перевод между shared-счетами разных household.

Обоснование: split visibility требует двух связанных записей с разными областями видимости, отдельными описаниями, безопасным отображением counterparty и защитой аналитики от утечки личного счета. Для MVP запрет проще проверить и безопаснее: второй участник семьи не увидит personal account id, название, баланс, описание или факт личной стороны перевода.

Если бизнесу нужен сценарий внесения денег в общий бюджет, MVP может разрешить пользователю вручную создать отдельную shared income/expense операцию без ссылки на personal-счет. Такая операция становится полностью shared-видимой и не должна содержать ссылку на личный счет.

## Ошибки доступа и нейтральные ответы

| Сценарий | Ответ API | Правило нейтральности |
| --- | --- | --- |
| Чтение объекта вне scope | `404 Not Found` или единый `403/404` policy | Ответ не подтверждает существование объекта. |
| List/search без доступа | `200 OK` с пустым списком | Не возвращать счетчики скрытых объектов. |
| Create/update со ссылкой на чужой id | `404 Not Found` для referenced object или нейтральный validation error | Не уточнять, какой именно id чужой. |
| Попытка personal/shared transfer | `422 Unprocessable Entity` или `400 Bad Request` с общим кодом `TRANSFER_SCOPE_NOT_SUPPORTED` | Не возвращать детали скрытой стороны. |
| Invited/former member читает shared data | `404 Not Found` или `403 Forbidden` по единой политике | Не раскрывать состав семьи и наличие счетов. |
| Неаутентифицированный доступ | `401 Unauthorized` | Без деталей о существовании ресурса. |

Тексты ошибок должны быть общими: "Ресурс не найден или недоступен", "Операция недоступна для выбранных счетов", "Недостаточно прав для выполнения действия". Stack traces, SQL errors, internal ids и финансовые значения не возвращаются.

## Инварианты для API/backend

- Любой запрос имеет `currentUserId`; без него доступны только auth/register flows.
- Каждый `Account` имеет ровно один `ownershipType`: `personal` или `shared`.
- `personal Account` обязан иметь `ownerUserId = User.id` и не должен требовать `householdId`.
- `shared Account` обязан иметь `householdId` и доступен только через active `Membership`.
- `Operation.accountId` обязателен и проверяется на доступ до чтения/записи операции.
- `Operation.counterpartyAccountId` в MVP разрешен только для переводов внутри того же разрешенного scope: personal owner или shared household.
- `Category.scope` один: `personal` или `household`; смешивать `ownerUserId` и `householdId` как равноправные scope запрещено.
- Operation на shared account использует household category того же household или явно разрешенный системный вариант.
- Operation на personal account не делает личные данные видимыми через household category, analytics, transfer, search или audit response.
- Все list/search/autocomplete/report/export endpoints используют тот же access predicate, что detail endpoint.
- Analytics фильтрует account/operation rows до group by, sum, count и balance calculation.
- Soft-deleted/archived объекты не становятся видимыми шире, чем active объекты.
- Audit logs пишут actor, target type/id, scope type/id, result и request id, но не пишут суммы, описания операций, названия счетов, invite/reset/session tokens.
- Любое изменение membership немедленно влияет на authz; кэш access decisions должен инвалидироваться.
- Любое расширение семейной модели за пределы двух active members или простого active/invited/left/revoked требует пересмотра access model.

## Acceptance checks для будущей QA-ветки

1. Пользователь A не может получить personal account пользователя B по прямому `accountId`.
2. Участник семьи A не видит personal account участника B в account list.
3. Участник семьи A не видит personal account участника B в search/autocomplete.
4. Участник семьи A не видит operation personal-счета участника B по прямому `operationId`.
5. Reports пользователя A не включают personal-счета участника B в totals, balances, category breakdown и charts.
6. Shared account household виден обоим active members.
7. Пользователь из другого household не видит shared account, shared operations, household categories и shared analytics чужой семьи.
8. Invited member до accept не видит shared accounts и shared reports.
9. Former/revoked member после выхода не видит shared accounts и shared reports без повторного входа и после обновления сессии.
10. Category endpoints не возвращают personal categories другого участника.
11. Personal operation с household category не раскрывается второму участнику через category usage, counters или reports.
12. Создание operation с чужим `accountId` возвращает нейтральную ошибку и не создает запись.
13. Создание operation с category вне разрешенного scope возвращает нейтральную ошибку и не создает запись.
14. `personal -> shared` transfer отклоняется с `TRANSFER_SCOPE_NOT_SUPPORTED` или аналогичным общим кодом.
15. `shared -> personal` transfer отклоняется тем же правилом.
16. `personal -> personal` transfer разрешен только между счетами одного владельца.
17. `shared -> shared` transfer разрешен только внутри одного household для active member.
18. Account list, operation list, category list и analytics используют одинаковые authz predicates.
19. API не возвращает hidden object counts для чужих personal/shared данных.
20. Audit/logs для denied access не содержат суммы, описания операций, названия счетов и токены.
21. Invite token нельзя использовать повторно после accept, revoke или expire.
22. После смены membership на `left` или `revoked` server-side access cache инвалидируется.
23. Попытка изменить `ownershipType` account в MVP отклоняется.
24. Архивирование account/category не раскрывает объект новому actor и не удаляет историю операций.

## Unresolved decisions и escalation triggers

- Personal-only видимость подтверждена для MVP: personal-счета, personal-операции, personal-категории и personal-агрегаты другого участника не раскрываются.
- Нужно отдельное post-MVP product/security/privacy решение, если когда-либо потребуется показывать personal-счета одного участника другому участнику семьи.
- Нужно отдельное решение, если бизнес требует разрешить personal/shared transfers через split visibility в MVP.
- Нужно отдельное решение, если бывший участник должен сохранять доступ к историческим shared-операциям за период участия.
- Нужно уточнить, кто может удалить active member из household помимо самостоятельного выхода.
- Нужно уточнить, допускается ли больше одного household на пользователя после MVP.
- Нужно уточнить финальную политику account deletion/deactivation и user account deletion.
- Требуется эскалация к Security/Product, если появляются роли внутри семьи, больше двух active members, public SaaS commitment, field-level encryption, банковские API/imports или повторная неудача QA access checks.

## Definition of Done для этой модели

- Описаны read/create/update/delete правила для `User`, `Household`, `Membership`, `Account`, `Operation`, `Category`, `AnalyticsView`.
- Зафиксировано, что personal-данные другого участника не раскрываются в списках, поиске, отчетах, агрегатах, категориях и переводах.
- Зафиксировано, что shared-счета и связанные данные видны только active members.
- Выбран безопасный MVP-вариант для переводов personal/shared: запрет до отдельной split-visibility модели.
- Добавлены матрица доступа и таблица visibility.
- Добавлены acceptance checks для будущей QA-ветки.
