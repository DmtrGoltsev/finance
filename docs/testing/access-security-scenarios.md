# Access and Security Test Scenarios

## 1. Цель и область

Цель документа - зафиксировать минимальный набор QA/security сценариев для MVP финансового приложения, чтобы проверить корректность доступа, приватности и базовой безопасности до релиза.

Область MVP:
- ручной ввод счетов и операций;
- без импорта файлов, банковских API, SMS/push-интеграций и перехвата SMS/push/notifications;
- capture drafts допускаются только как user-initiated OCR из выбранного пользователем скриншота: локально/on-device до structured draft review, без server-side хранения raw SMS/push/notification body;
- personal и shared счета;
- операции, категории и отчеты с теми же правилами доступа, что и связанные с ними счета;
- `shared family report` только по shared данным Household;
- `combined viewer overview` по shared данным Household и personal данным текущего viewer;
- запрет переводов personal<->shared;
- отсутствие хранения банковских токенов, паролей и API credentials;
- логи и audit без сумм, описаний операций, названий счетов, токенов и секретов.

Вне области MVP:
- банковские интеграции;
- автоматический импорт транзакций;
- автосоздание операций из SMS/push или notifications;
- server-side хранение raw SMS/push/notification body;
- внешние платежи;
- хранение платежных или банковских секретов.

## 2. Тестовые акторы и фикстуры

Акторы:
- Owner A - владелец Household AB, active member.
- Family Member B - участник Household AB, active member.
- Other User C - пользователь вне Household AB.
- Invited Member - пользователь с приглашением в Household AB, но без active membership.
- Former Member - пользователь, ранее состоявший в Household AB, но покинувший или удаленный из семьи.

Фикстуры:
- personal account A - personal счет Owner A.
- personal account B - personal счет Family Member B.
- shared account AB - shared счет Household AB.
- foreign shared account C - shared счет Household C, недоступный A и B.
- personal category A - personal категория Owner A.
- personal category B - personal категория Family Member B.
- shared category AB - shared категория Household AB.
- operations A - операции personal account A.
- operations B - операции personal account B.
- operations AB - операции shared account AB.
- report A - отчет по personal данным Owner A.
- shared family report AB - отчет только по shared данным Household AB.
- combined viewer overview A - обзор shared данных Household AB и personal данных Owner A.
- combined viewer overview B - обзор shared данных Household AB и personal данных Family Member B.

## 3. Acceptance Scenarios

### 3.1 Регистрация и вход

AS-REG-01: Новый пользователь регистрируется и получает собственную область данных.
- Given Other User C не имеет Household AB membership.
- When C входит в приложение.
- Then C не видит счета, операции, категории и отчеты Owner A или Member B.

AS-REG-02: Пользователь после входа видит только свои personal данные и доступные shared данные.
- Given Owner A вошел в систему.
- When A открывает dashboard.
- Then A видит personal account A и shared account AB.
- And A не видит personal account B и foreign shared account C.

### 3.2 Семья и membership

AS-FAM-01: Active member видит shared данные своей семьи.
- Given Owner A и Family Member B являются active members Household AB.
- When B открывает список shared счетов.
- Then B видит shared account AB.

AS-FAM-02: Invited Member не видит shared данные до активации membership.
- Given Invited Member имеет pending invite в Household AB.
- When Invited Member открывает список счетов.
- Then shared account AB отсутствует в списке.

AS-FAM-03: Former Member теряет доступ к shared данным.
- Given Former Member был удален из Household AB.
- When Former Member открывает список счетов, операций, категорий или отчетов Household AB.
- Then shared account AB, operations AB, shared category AB и `shared family report` AB недоступны.

### 3.3 Personal и shared счета

AS-ACC-01: Владелец видит свой personal счет.
- Given Owner A имеет personal account A.
- When A открывает список счетов.
- Then personal account A присутствует.

AS-ACC-02: Другой active member не видит чужой personal счет.
- Given Family Member B является active member Household AB.
- When B открывает список счетов.
- Then personal account A отсутствует.

AS-ACC-03: Active member видит shared счет Household.
- Given A и B являются active members Household AB.
- When A или B открывает detail shared account AB.
- Then detail доступен.

AS-ACC-04: Пользователь вне Household не видит shared счет.
- Given Other User C не является member Household AB.
- When C открывает list или detail shared account AB.
- Then данные не раскрываются.

### 3.4 Операции

AS-OPS-01: Owner A создает операцию на personal account A.
- Given A владеет personal account A.
- When A вручную создает операцию на personal account A.
- Then операция сохраняется и видна только A.

AS-OPS-02: Member B не видит операции personal account A.
- Given operations A существуют.
- When B открывает список, detail или search операций.
- Then operations A отсутствуют.

AS-OPS-03: Active members видят операции shared account AB.
- Given operations AB существуют.
- When A или B открывает list, detail или search операций shared account AB.
- Then operations AB доступны.

AS-OPS-04: Other User C не видит операции Household AB.
- Given operations AB существуют.
- When C открывает list, detail или search по ID или фильтрам Household AB.
- Then операции не раскрываются.

### 3.5 Категории

AS-CAT-01: Personal категория видна только владельцу.
- Given personal category A существует.
- When A открывает категории.
- Then personal category A доступна.
- When B или C открывает категории или detail personal category A.
- Then personal category A не раскрывается.

AS-CAT-02: Shared категория видна active members Household.
- Given shared category AB существует.
- When A или B открывает list/detail категорий Household AB.
- Then shared category AB доступна.
- When C, Invited Member или Former Member открывает list/detail shared category AB.
- Then shared category AB не раскрывается.

AS-CAT-03: Операция не может быть привязана к недоступной категории.
- Given B не имеет доступа к personal category A.
- When B создает или редактирует операцию с category_id personal category A.
- Then запрос отклоняется нейтральной ошибкой.

### 3.6 Аналитика и отчеты

AS-REP-01: Personal отчет Owner A включает только personal данные A.
- Given у A и B есть personal операции.
- When A строит personal report A.
- Then отчет включает operations A.
- And отчет не включает operations B.

AS-REP-02: `shared family report` фильтрует данные до агрегации.
- Given Household AB имеет operations AB, а A и B имеют personal операции.
- When A или B строит `shared family report` AB.
- Then агрегаты считаются только по shared данным Household AB.
- And personal данные другого участника не попадают в сумму, count, breakdown, trend или drill-down.

AS-REP-03: Other User C не получает отчеты Household AB.
- Given `shared family report` AB существует.
- When C запрашивает list/detail/export `shared family report` AB.
- Then отчет не раскрывается.

AS-REP-04: `combined viewer overview` включает shared данные и personal данные только текущего viewer.
- Given Household AB имеет operations AB, A имеет operations A, а B имеет operations B.
- When A строит `combined viewer overview` A.
- Then обзор включает operations AB и operations A.
- And обзор не включает operations B ни в totals, count, breakdown, trend, balances, drill-down или export.
- When B строит `combined viewer overview` B.
- Then обзор включает operations AB и operations B.
- And обзор не включает operations A ни в totals, count, breakdown, trend, balances, drill-down или export.

## 4. Negative and Abuse Scenarios

### 4.1 IDOR/BOLA: list/detail/search

NEG-IDOR-01: Detail personal account другого пользователя.
- Given B знает или угадывает account_id personal account A.
- When B запрашивает detail personal account A.
- Then ответ нейтрален и не раскрывает существование счета.

NEG-IDOR-02: Detail shared account чужой семьи.
- Given A знает или угадывает account_id foreign shared account C.
- When A запрашивает detail foreign shared account C.
- Then ответ нейтрален и не раскрывает данные.

NEG-IDOR-03: List с подменой owner_id или household_id.
- Given C подставляет owner_id A или household_id AB в параметры list.
- When C открывает accounts/operations/categories/reports list.
- Then ответ содержит только данные, доступные C.

NEG-IDOR-04: Search не обходит доступ.
- Given B ищет по тексту, дате, сумме или ID operations A.
- When B выполняет search.
- Then results не содержат operations A и не раскрывают совпадения.

### 4.2 Report/category/transfer abuse

NEG-REP-01: Report filters не расширяют доступ.
- Given C подставляет household_id AB, account_id shared account AB или user_id A в report filters.
- When C строит отчет.
- Then отчет пуст или отклонен нейтральной ошибкой без раскрытия данных.

NEG-CAT-01: Category assignment через чужой category_id.
- Given A создает операцию на personal account A.
- When A указывает personal category B или foreign shared category.
- Then запрос отклоняется.

NEG-TRN-01: Запрет personal->shared.
- Given A владеет personal account A и имеет доступ к shared account AB.
- When A создает перевод personal account A -> shared account AB.
- Then перевод отклоняется как недопустимый для MVP.

NEG-TRN-02: Запрет shared->personal.
- Given A имеет доступ к shared account AB и personal account A.
- When A создает перевод shared account AB -> personal account A.
- Then перевод отклоняется как недопустимый для MVP.

NEG-TRN-03: Разрешен personal->personal только одного владельца.
- Given A владеет двумя personal счетами.
- When A создает перевод между своими personal счетами.
- Then перевод разрешен.
- When A пытается перевести personal account A -> personal account B.
- Then перевод отклоняется.

NEG-TRN-04: Разрешен shared->shared только внутри одного Household.
- Given Household AB имеет два shared счета.
- When A или B создает перевод между ними.
- Then перевод разрешен.
- When A пытается перевести shared account AB -> foreign shared account C.
- Then перевод отклоняется.

### 4.3 Invited/Former member

NEG-MEM-01: Invited Member не получает доступ через прямой URL.
- Given Invited Member имеет pending invite.
- When Invited Member открывает detail/list/search/report/category/transfer endpoints Household AB.
- Then данные Household AB не раскрываются.

NEG-MEM-02: Former Member не получает доступ через cached IDs.
- Given Former Member ранее видел shared account AB и operations AB.
- When Former Member использует старые IDs для detail/search/report/category/transfer.
- Then доступ отклонен нейтральной ошибкой.

### 4.4 Neutral errors

NEG-ERR-01: Ошибка доступа не подтверждает существование объекта.
- Given пользователь запрашивает недоступный account/operation/category/report.
- When объект существует или не существует.
- Then форма ответа одинаково нейтральна для unauthorized пользователя.

NEG-ERR-02: Validation errors не раскрывают приватные поля.
- Given пользователь отправляет чужой account_id или category_id.
- When запрос отклоняется.
- Then сообщение не содержит сумму, описание операции, название счета, название категории или владельца.

## 5. Security Scenarios

SEC-AUTH-01: Неаутентифицированный пользователь не получает данные.
- When anonymous пользователь открывает list/detail/search/report/category/transfer.
- Then требуется аутентификация.

SEC-AUTH-02: Session invalidation после logout.
- Given A вошел в систему.
- When A выходит.
- Then старый session token не дает доступ к данным.

SEC-AUTH-03: Session не смешивает пользователей.
- Given A и B используют разные сессии.
- When B выполняет запросы после действий A.
- Then B не получает cached данные A.

SEC-RESET-01: Password reset не раскрывает существование email.
- When пользователь запрашивает reset для существующего и несуществующего email.
- Then ответ одинаково нейтрален.

SEC-RESET-02: Reset token одноразовый и ограничен по времени.
- Given reset token использован или истек.
- When пользователь повторяет reset.
- Then запрос отклоняется.

SEC-INV-01: Invite token не дает доступ до принятия и активации.
- Given Invited Member имеет invite token.
- When Invited Member использует приложение до acceptance.
- Then shared данные Household AB недоступны.

SEC-INV-02: Invite token одноразовый и отзываемый.
- Given invite принят, истек или отозван.
- When тот же token используется повторно.
- Then membership не создается повторно и данные не раскрываются.

SEC-RATE-01: Rate limit на login/password reset/invite.
- When один источник многократно вызывает login, reset или invite endpoints.
- Then применяется rate limit без раскрытия учетных данных или membership.

SEC-LOG-01: Логи не содержат финансовые значения.
- Given создаются, редактируются и отклоняются операции, счета, категории, отчеты и переводы.
- When проверяются application logs и audit events.
- Then в логах нет сумм, описаний операций, названий счетов, названий категорий, токенов и секретов.
- And допустимы только технические IDs, тип события, статус, actor_id и timestamp, если это разрешено privacy baseline.

SEC-LOG-02: Ошибки transfer/report/search не логируют payload с финансовыми данными.
- Given пользователь отправляет недопустимый transfer/report/search запрос.
- When запрос отклоняется.
- Then raw payload не сохраняется в логах/audit.

SEC-SECRET-01: MVP не хранит банковские credentials.
- When проверяются настройки, база данных, секреты окружения, audit и backups.
- Then отсутствуют банковские токены, банковские пароли и API credentials.

SEC-BACKUP-01: Backups защищены теми же правилами чувствительности.
- When создаются или проверяются backups.
- Then backups не содержат банковских секретов.
- And доступ к backup ограничен авторизованными операционными ролями.
- And восстановление backup не смешивает Household или personal ownership.

## 6. Privacy Scenarios

PRIV-VIS-01: Personal visibility.
- Given A и B состоят в одном Household.
- When B открывает list/detail/search/report по personal данным A.
- Then данные A не раскрываются.

PRIV-VIS-02: Shared visibility.
- Given A и B active members Household AB.
- When A или B открывает shared account AB, operations AB, shared category AB или `shared family report` AB.
- Then shared данные доступны.

PRIV-EXP-01: Export пользователя включает только доступные данные.
- Given A запрашивает export.
- When export формируется.
- Then `combined viewer overview` export включает personal данные A и shared данные Household AB, доступные A.
- And не включает personal данные B.

PRIV-EXP-02: Export Former Member не включает бывшие shared данные.
- Given Former Member покинул Household AB.
- When Former Member запрашивает export.
- Then export не включает текущие shared данные Household AB.

PRIV-DEL-01: Delete account удаляет или обезличивает personal данные пользователя по правилам privacy baseline.
- Given A запрашивает удаление аккаунта.
- When deletion completed.
- Then personal данные A недоступны другим пользователям.
- And shared данные обрабатываются по правилам ownership/retention без раскрытия personal данных A.

PRIV-LEAVE-01: Leave family немедленно прекращает shared access.
- Given B active member Household AB.
- When B покидает Household AB.
- Then B становится Former Member и теряет доступ к shared account AB, operations AB, shared category AB и `shared family report` AB.

PRIV-LEAVE-02: `shared family report` после ухода участника не раскрывает его personal данные.
- Given B покинул Household AB.
- When A строит `shared family report` AB.
- Then отчет не включает personal данные B и не раскрывает историю personal операций B.

## 7. Release Gates MVP

Перед MVP release должны быть выполнены все gates:
- RG-01: Все acceptance scenarios AS-* пройдены.
- RG-02: Все negative/abuse scenarios NEG-* пройдены для list/detail/search/report/category/transfer поверхностей.
- RG-03: Проверен запрет personal<->shared transfers.
- RG-04: Проверены разрешенные transfers: personal->personal одного владельца и shared->shared одного Household.
- RG-05: Invited Member и Former Member не имеют доступа к shared данным до/после membership.
- RG-06: `shared family report` и `combined viewer overview` фильтруют данные до агрегации и не включают personal данные другого участника.
- RG-07: Security scenarios SEC-* пройдены для auth/session/password reset/invite/rate limit/logs/secrets/backups.
- RG-08: Logs и audit не содержат суммы, описания операций, названия счетов, токены и секреты.
- RG-09: Privacy scenarios PRIV-* пройдены для export/delete/leave family и personal/shared visibility.
- RG-10: Все access-denied и validation ошибки нейтральны и не раскрывают существование недоступных объектов.
- RG-11: Нет хранения банковских токенов, банковских паролей или API credentials в MVP.
- RG-12: Все найденные P0/P1 security и privacy дефекты закрыты или формально приняты как release blocker exception.

## 8. Traceability

Ожидаемые источники требований:
- product-mvp - границы MVP, ручной ввод, запрет интеграций и переводов personal<->shared.
- domain-model - сущности account, operation, category, report, household, membership, transfer.
- access-model - правила видимости personal/shared данных и active membership.
- security-baseline - auth, session, password reset, invite, rate limit, logs, secrets, backups.
- privacy-baseline - export, delete, leave family, минимизация данных и нейтральные ошибки.

Матрица покрытия:

| Requirement source | Covered scenarios |
| --- | --- |
| product-mvp | AS-OPS-01, NEG-TRN-01..04, SEC-SECRET-01, RG-03, RG-04, RG-11 |
| domain-model | AS-ACC-*, AS-OPS-*, AS-CAT-*, AS-REP-*, NEG-CAT-*, NEG-TRN-* |
| access-model | AS-FAM-*, NEG-IDOR-*, NEG-MEM-*, PRIV-VIS-* |
| security-baseline | SEC-AUTH-*, SEC-RESET-*, SEC-INV-*, SEC-RATE-*, SEC-LOG-*, SEC-BACKUP-01 |
| privacy-baseline | PRIV-EXP-*, PRIV-DEL-01, PRIV-LEAVE-*, NEG-ERR-* |
