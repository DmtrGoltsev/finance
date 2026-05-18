# Privacy-потоки MVP

## Статус и границы

Документ фиксирует безопасные MVP-потоки для export, delete/deactivate account и leave household. Это инженерный privacy baseline для закрытого MVP, а не публичная privacy policy и не юридически утвержденная retention/deletion SLA.

Опорные документы:

- `docs/compliance/privacy-baseline.md`
- `docs/architecture/backend-api-contracts.md`
- `docs/architecture/backend-authz-predicates.md`
- `docs/architecture/access-model.md`
- `docs/security/security-baseline.md`

Безопасные значения по умолчанию:

- `personal` данные всегда видит только владелец.
- `shared` данные видят только active members соответствующего `Household`.
- Former/invited members не получают shared financial access и не получают historical read через API.
- Export, reports, search, autocomplete, debug и support output используют те же authz predicates, что detail/list.
- Фильтрация выполняется до агрегации, подсчета, export generation, file generation и cache materialization.
- Ошибки доступа нейтральны: API не подтверждает существование чужого account, transaction, category, household, membership, invite или export job.
- Logs, telemetry, audit и errors не содержат финансовые суммы, остатки, названия счетов, описания операций, пользовательский free text, email в plaintext, токены, пароли и request/response bodies.
- Backup deletion, formal retention periods, deletion SLA, публичный запуск, SaaS/self-hosted модель и ownership shared family data остаются post-MVP/legal escalation.

## Поток экспорта

### Цель

Дать пользователю копию данных, которые он вправе видеть в продукте на момент генерации export, без раскрытия personal данных другого участника и без восстановления доступа бывшего участника к shared history.

### Безопасная область данных

Export включает только:

- профиль текущего пользователя: `userId`, self email/login, `displayName`, timestamps и безопасные настройки профиля;
- personal accounts, transactions, categories и вычислимые personal reports текущего пользователя;
- минимальную self membership history пользователя;
- shared accounts, shared transactions, household categories и shared report data только для households, где пользователь является active member на момент генерации export;
- metadata самого export job: `id`, `status`, `format`, `createdAt`, `readyAt`, `expiresAt`.

Export не включает:

- personal accounts, transactions, categories, reports, aggregates, balances или free text другого участника;
- email/security settings другого участника;
- hidden counts, filtered-out counts или сообщения о скрытых данных;
- raw audit logs, application logs, telemetry, debug dumps, database dumps, backups;
- invite/reset/session/refresh tokens, token hashes, password hashes, production secrets;
- current shared data для former member после `left`/`revoked`.

### Поток

1. Пользователь запрашивает export через authenticated session; для закрытого MVP допустимо требовать fresh authentication перед созданием job.
2. Backend валидирует `format`, `householdId`, `includeSharedData` без чтения скрытых объектов.
3. Backend строит visible scope через `canExportData` и те же readable predicates, что lists/reports.
4. Data set фиксируется на момент генерации: own personal rows плюс active shared rows, если requested scope это допускает.
5. Export job создает файл в short-lived protected storage. Файл доступен только владельцу job, без публичного URL и без bearer token в логах.
6. Download требует authenticated session и ownership check по `exportId`.
7. Export file автоматически истекает; безопасный closed-MVP default: short TTL, например не больше 7 дней, с обязательной настройкой удаления/expiration до релиза.
8. Любой export job и download пишут audit event без финансовых значений и без содержимого файла.

### Поведение для бывшего участника

После `left`/`revoked` бывший участник может экспортировать только own personal data и минимальную self membership history, если такой self endpoint утвержден. Export бывшего участника не включает бывшие shared accounts, transactions, categories, reports, search/autocomplete data или debug output.

Если продукт требует export shared history за период бывшего участия, это Product/Legal/Security escalation и новая authz-модель, а не MVP-допущение.

## Поток удаления или деактивации аккаунта

### Цель

Позволить пользователю закрыть собственную учетную запись без раскрытия personal данных другим участникам, без разрушения shared history и без ложного обещания физического удаления из backup до юридического решения.

### Безопасная область действия

Delete/deactivate действует только на self account. Один пользователь не может запросить удаление аккаунта, personal data или sessions другого пользователя.

Безопасное поведение закрытого MVP:

- сначала `deactivated` state и немедленный отзыв sessions/refresh tokens;
- прекращение active memberships через `left`/ended state или эквивалентный self-only transition;
- personal financial data пользователя удаляются, soft-delete или необратимо обезличиваются через контролируемый maintenance-процесс после короткого operational grace period;
- shared history сохраняется как shared household history, если она нужна оставшемуся active member, отчетам, audit или целостности записей;
- author/editor markers в shared history после удаления аккаунта заменяются на нейтральный deleted-user marker или необратимо обезличенный идентификатор, если это не ломает audit integrity;
- audit/security records сохраняются в минимальном sanitized виде по утвержденной retention policy; до публичного запуска срок и исключения являются escalation.

### Поток

1. Пользователь создает deletion request с `confirm: true`; безопасный default - fresh authentication или повторное подтверждение session.
2. Backend проверяет `isSelf` и создает `DeletionRequestDto`.
3. Система переводит account в `deactivation_pending` или `deactivated` по выбранной state model; новые logins и новые shared mutations блокируются.
4. Все server-side sessions, refresh tokens, reset tokens и access-decision caches пользователя отзываются или сужаются.
5. Active memberships пользователя закрываются как self leave; former access к shared data прекращается.
6. Personal accounts, transactions, categories, export files/jobs и локальные snapshots получают deletion/anonymization task. Если объект нужен для восстановления в коротком grace period, он остается soft-deleted и невидимым.
7. Shared transactions/categories/accounts не удаляются физически только из-за удаления одного участника. Они остаются в household scope для remaining active members, но без раскрытия deleted user's personal profile, email или security metadata.
8. Завершение deletion request фиксируется в status endpoint и audit event. Ответ не раскрывает данные других участников и не сообщает hidden counts.

### Что не обещает MVP

- Мгновенное физическое удаление из backups.
- Юридически обязательный deletion SLA.
- Право одного участника удалить shared history для другого участника.
- Удаление audit/security records без отдельной legal/security retention policy.
- Support/admin ручную правку production данных без отдельной policy, least privilege и audit.

## Поток выхода из household

### Цель

Дать пользователю безопасный self-service выход из household, немедленно отозвать будущий shared access и сохранить целостность shared history без расширения прав бывшего участника.

### Безопасное поведение

- Leave разрешен только для собственной active membership.
- Revoke другого active member другим участником не разрешен без отдельного Product/Security решения; pending invite revoke остается отдельным invite flow.
- После `left` пользователь не видит shared accounts, transactions, categories, reports, exports, search, autocomplete или debug data этого household.
- Старые direct ids, cached report/export/search results и offline/PWA snapshots не дают доступ после смены membership.
- Исторические shared operations остаются в household для active members и audit, но бывший участник не получает historical API read.

### Поток

1. Пользователь запрашивает leave с `confirm: true`.
2. Backend применяет `canLeaveHousehold`: authenticated actor, target household, own active membership.
3. Membership меняется на `left`, заполняются `endedAt`/`completedAt` и безопасная reason metadata, если она не содержит free text.
4. Access-decision cache, report/export/search/autocomplete caches, server-side sessions/refresh tokens и PWA/offline snapshots для affected `userId`/`householdId` инвалидируются или сужаются.
5. Готовые export files, созданные до leave и содержащие shared data, истекают немедленно или становятся недоступными, если они еще не скачаны; новые exports после leave не включают former shared data.
6. Shared mutations от бывшего участника блокируются. Новые запросы к shared endpoints получают neutral deny или `MEMBERSHIP_NOT_ACTIVE` по единой политике.
7. Audit event фиксирует membership left, cache/session invalidation и результат.

Если после выхода в household не остается active members, безопасный default - архивировать household, заблокировать shared mutations и не расширять read access до отдельного Product/Legal/Security решения.

## Доступ бывшего участника по умолчанию

Бывший участник со статусом `left`, `removed` или `revoked`:

- сохраняет доступ только к own personal data;
- может видеть только минимальную self membership metadata, если endpoint нужен для профиля/audit;
- не видит former shared accounts, transactions, categories, reports, exports, search, autocomplete, debug data или member list;
- не получает подсказки "вы раньше имели доступ", hidden counts, названия объектов, balances, descriptions или состав household;
- не может использовать старые IDs, старые export links, старые cached reports или старые refresh/session tokens для shared access;
- получает одинаковую user-facing ошибку для missing и inaccessible shared resources.

Любой запрос на сохранение historical shared access after leaving является escalation и требует новой predicate design, UX notice, retention/legal review и QA proof obligations.

## Обработка shared history

Shared history принадлежит household scope в технической модели MVP, но правовая модель shared family data не утверждена. Поэтому безопасное MVP-поведение такое:

- shared accounts, transactions, categories и reports остаются доступными active members household;
- бывший участник не получает API read к historical shared data;
- leaving не удаляет shared history физически;
- account deletion/deactivation пользователя не раскрывает его personal data remaining member;
- deleted/deactivated user отображается в shared history только как минимальный нейтральный marker, без email, текущего профиля, security settings и personal financial data;
- personal records не мигрируются в shared records автоматически;
- personal/shared transfers в MVP запрещены; если нужен вклад в общий бюджет, пользователь создает отдельную fully shared transaction без ссылки на personal account;
- archive/soft delete предпочтительнее физического удаления финансовых объектов, если physical delete ломает audit/history/report integrity;
- shared history ownership, право одного участника удалить shared history, конфликт участников и доступ после выхода являются post-MVP/legal escalation.

## Ограничения audit, privacy и logging

Audit обязателен для:

- export requested, processing started, ready, downloaded, expired, failed;
- deletion request created, account deactivated, personal data anonymization/deletion task started/completed/failed;
- leave requested/completed, membership `left`/`revoked`, cache/session invalidation;
- denied access к direct ids, suspicious cross-scope attempts, former-member shared access attempts;
- backup/restore/admin/support access, если такие operational tools существуют.

Audit event может содержать:

- timestamp;
- actor user id или system actor id;
- action;
- target type и target id, если id был предоставлен caller или создан системой;
- scope type/id: `personal:{userId}` или `household:{householdId}`;
- result: allow, deny, state-deny, failed;
- request id;
- coarse IP/user-agent, если это разрешено privacy baseline.

Audit/log/telemetry не должны содержать:

- amounts, balances, report totals;
- transaction descriptions, account/category names, custom labels, raw search query;
- email в plaintext, кроме строго утвержденных operational/security случаев;
- passwords, password hashes, invite/reset/session/refresh tokens, token hashes без необходимости;
- raw request/response bodies for financial/export/delete/leave endpoints;
- export file content, database dumps, backup paths с секретами;
- stack traces/SQL errors в user-facing responses.

Доступ к audit/logs/telemetry/backup сам должен быть least-privilege и аудируемым. Support/admin access к финансовым значениям не входит в MVP без отдельной policy и escalation.

## Безопасные retention defaults

Это не юридическая retention policy. Для closed MVP действуют только безопасные инженерные defaults:

| Данные или процесс | Safe default для MVP | Что остается escalation |
| --- | --- | --- |
| Export jobs/files | Short-lived protected storage, owner-only download, automatic expiration; recommended default не больше 7 дней для файлов. | Formal export SLA, юридические сроки ответа, формат публичного self-service process. |
| Deactivated account | Немедленная блокировка login и sessions; короткий operational grace period только для восстановления ошибки. | Точный deletion SLA, основания хранения, user notices. |
| Personal financial data after deletion | Soft delete, physical delete или irreversible anonymization через controlled maintenance task. | Формальный срок, исключения, доказательство удаления, legal hold. |
| Shared financial history | Archive/retain в household scope, если нужно для active member history, reports или audit. | Кто владеет shared history и кто может требовать ее удаления/экспорта. |
| Membership history | Сохранять минимально для access/audit; бывший участник видит только self metadata, если endpoint утвержден. | Формальный срок retention и правовая модель former access. |
| Audit logs | Минимальный sanitized retention для безопасности; security baseline задает closed-pilot ориентир 90 дней. | Публичный срок, исключения, legal/security retention policy. |
| Application logs | Короткое operational окно, автоматическая ротация, без sensitive payload. | Конкретные сроки для production/SaaS. |
| Telemetry | Только coarse/minimal events; raw events удаляются по короткому окну; без user content. | Third-party analytics, cookies/mobile telemetry policy. |
| Backups | Encrypted daily backup, RPO/RTO до 24 часов для closed MVP, restore проверен до релиза; app не имеет права удалять backups. | Backup retention, selective deletion из backup, deletion after request, legal hold. |

Backup/retention uncertainty: до публичного запуска/SaaS нужно Legal/Product/Security/Operations решение по formal retention periods, deletion SLA, backup deletion approach и исключениям для audit/security. До этого нельзя обещать пользователю физическое удаление из backups быстрее истечения backup retention.

## Маппинг endpoint

| Поток | Endpoint | Predicate / правило | Безопасное поведение ответа |
| --- | --- | --- | --- |
| Создать export | `POST /api/v1/exports` | `canExportData`; только visible rows на момент генерации. | `ExportJobDto`; без hidden counts; скрытый/чужой `householdId` дает neutral deny. |
| Список export jobs | `GET /api/v1/exports` | Владелец: `requestedByUserId == currentUserId`. | Только свои jobs; без содержимого файлов. |
| Статус export | `GET /api/v1/exports/{exportId}` | Только own export job. | Missing/inaccessible `exportId` -> `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`. |
| Скачать export | `GET /api/v1/exports/{exportId}/files` | Own ready non-expired job; повторная проверка доступа перед скачиванием, если файл содержит shared data. | Без публичных ссылок; expired возвращает безопасный статус или neutral error. |
| Запросить deletion/deactivation | `POST /api/v1/users/me/deletion-requests` | `isSelf`; optional fresh auth; `confirm: true`. | Действует только на self; без данных другого участника в ответе. |
| Статус deletion request | `GET /api/v1/users/me/deletion-requests/{deletionRequestId}` | Только own deletion request. | Только status; без hidden counts и cross-user details. |
| Запросить leave household | `POST /api/v1/households/{householdId}/leave-requests` | `canLeaveHousehold`; только own active membership. | Создает/завершает `LeaveRequestDto`; neutral deny для недоступного household. |
| Membership leave transition | `POST /api/v1/memberships/{membershipId}/leave` | Тот же `canLeaveHousehold`; если endpoint открыт, он должен быть эквивалентен leave request flow. | Caller может выйти только из own active membership. |
| Logout current session | `DELETE /api/v1/sessions/current` | Authenticated session. | Используется при deactivation/leave cleanup. |
| Logout all sessions | `DELETE /api/v1/sessions` | Authenticated self. | Требуется после deletion/deactivation; может запускаться системой при смене account state. |
| Текущий профиль | `GET /api/v1/users/me` | `isSelf`. | Deactivated users получают blocked/session-expired behavior по выбранному auth stack. |
| Список memberships | `GET /api/v1/users/me/memberships` | Только self memberships; active shared access все равно требует active status. | Минимальная former membership metadata. |

Новые export/delete/leave endpoints не добавляются в MVP без Privacy/Security review. Любой support/admin/backoffice endpoint для этих потоков обязан использовать те же predicates, более строгую redaction и audit.

## Release gates и требуемые доказательства

| Gate | Требуемое доказательство |
| --- | --- |
| PF-RG-01 Export visible-scope equivalence | Тесты показывают, что export содержит ровно строки, видимые через list/report для owner A, active member B, other user C, invited user и former member. |
| PF-RG-02 No other-member personal export | Тесты показывают, что export active member исключает personal accounts, transactions, categories, reports, aggregates, balances и free text другого участника. |
| PF-RG-03 Former member export denied for shared | Тесты после `left`/`revoked` со старыми ids, старыми export jobs и обновленными sessions показывают отсутствие shared data и hidden hints. |
| PF-RG-04 Delete/deactivate self-only | Тесты показывают, что пользователь может создать deletion request только для self; cross-user попытки дают neutral errors и не создают partial writes. |
| PF-RG-05 Delete does not expose personal data | Review/tests показывают, что remaining active member видит shared history только с neutral deleted-user marker и без email, profile или personal financial data deleted user. |
| PF-RG-06 Leave revokes future access | Тесты показывают, что membership `left` инвалидирует sessions/access cache/report/export/search/autocomplete/offline snapshots и блокирует старые IDs. |
| PF-RG-07 Shared history integrity | Tests/review показывают, что leave/deactivation не ломает shared reports/history для active members и не дает former member historical API read. |
| PF-RG-08 Neutral errors/no hidden counts | Golden response tests сравнивают missing vs inaccessible IDs для export, deletion request, household, membership, account, transaction и category references. |
| PF-RG-09 Logs/audit privacy | Инспекция логов для export/delete/leave allow/deny/failure flows показывает отсутствие amounts, balances, names, descriptions, email plaintext, tokens, raw bodies и export contents. |
| PF-RG-10 Export file lifecycle | Есть доказательства, что export files encrypted/protected, owner-only, не имеют public links и expire/delete по настроенному TTL. |
| PF-RG-11 Retention/backups documented | Есть closed-MVP backup/restore evidence; backup deletion uncertainty задокументирована как post-MVP/legal escalation. |
| PF-RG-12 Legal/Product/Security signoff | Public launch, formal retention/deletion SLA, backup deletion, support/admin access и shared history ownership явно out of scope или подписаны до release. |

Release must block on any P0/P1 privacy/authz defect in these gates unless Product/Legal/Security formally accepts it as a release-blocker exception. For public beta/production, PF-RG-12 cannot be waived by engineering alone.

## Триггеры эскалации

Escalate to Product, Legal, Security Architect and Operations before implementation or release if:

- требуется публичный запуск, SaaS/self-hosted commitment, выбор юрисдикции или публичная privacy policy;
- нужно утвердить retention periods, deletion SLA, export SLA, legal hold или backup deletion approach;
- нужно решить, кто владеет shared family data и кто может удалить/экспортировать shared history;
- бывший участник должен получить historical shared access после `left`/`revoked`;
- требуется показать personal account, transaction, category, report, aggregate, balance или free text другому household member;
- требуется разрешить personal<->shared transfers без отдельной split-visibility модели;
- требуется support/admin access к production financial values или backoffice ручная обработка export/delete/leave;
- появляются bank APIs, broker APIs, SMS/push, imports, external financial identifiers или банковские/API secrets;
- family model расширяется сверх двух active members, появляются роли, дети/несовершеннолетние, delegated access;
- backup restore не проходит, backup неполный, selective restore раскрывает чужие данные или deletion из backup становится публичным обещанием;
- telemetry/crash reporting начинает собирать user content, screenshots, screen recording или granular financial events;
- обнаружена утечка financial/personal данных, ошибочное раскрытие personal/shared, повторная проблема с logs/backup/cache invalidation или repeated QA failure.

## Definition of Done

- Export flow описан с visible-at-generation scope, deny default для former member и запретом раскрытия personal данных другого участника.
- Delete/deactivate flow описан как self-only, с immediate deactivation/session revocation, personal deletion/anonymization task и safe shared history handling.
- Leave household flow описан с own active membership only, `left` transition, cache/session invalidation и no historical shared read для former member.
- Former member access по умолчанию не расширен.
- Personal данные другого участника не раскрываются через export, delete, leave, shared history, logs, audit, reports или errors.
- Backup/retention uncertainty явно вынесена как post-MVP/legal escalation.
- Endpoint mapping покрывает export, deletion request, leave request, membership leave и session cleanup.
- Release gates и требуемые доказательства зафиксированы.
