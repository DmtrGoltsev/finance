# Client state contracts MVP для Android и PWA

## 1. Статус и границы

Документ фиксирует клиентские контракты навигации, состояний экранов и правил видимости для Android и PWA в Wave 1 MVP. Он не задает визуальный дизайн, компоненты дизайн-системы или реализацию клиентского кэша. Цель - сделать так, чтобы оба клиента одинаково следовали `access-model.md`, `privacy-baseline.md`, `backend-api-contracts.md`, `report-api-contracts.md` и `transfer-api-contract.md`.

Базовый инвариант клиента: UI показывает только данные, уже разрешенные backend API для текущего пользователя. Клиентские фильтры, скрытые элементы, локальный кэш и route guards не являются контролем доступа и не могут расширять видимость.

Клиент не должен раскрывать personal-счета, personal-операции, personal-категории, personal-агрегаты, placeholders или counts другого участника семьи ни в обычных экранах, ни в пустых состояниях, ни в ошибках, ни в offline/cache состояниях.

## 2. Общие принципы состояния

- Android и PWA используют одинаковую state model: `unauthenticated`, `authenticating`, `authenticated`, `refreshingSession`, `sessionExpired`, `offlineReadonly`, `forbiddenOrNotFound`, `errorRetryable`.
- Любой экран с финансовыми данными имеет явный `viewerUserId`, текущую session/access version и выбранный scope: `personal`, `household` или report mode.
- Списки, search, autocomplete, drill-down и selector options отображают только `items`, полученные от API после access filtering.
- UI не показывает `hiddenCount`, `filteredOutCount`, "еще N скрыто", "часть данных недоступна", "у другого участника есть личные счета" или аналогичные сообщения.
- Пустое состояние означает только "нет видимых данных для текущего фильтра", а не "нет данных вообще".
- Нейтральные ошибки API отображаются нейтрально: "Ресурс не найден или недоступен" без уточнения, существует ли объект, кому он принадлежит и какой scope был нарушен.
- В shared-формах UI предупреждает, что создаваемая или изменяемая запись будет видна активным участникам household.
- После logout, истечения session, смены membership на `left`/`revoked`, accept/revoke invite или delete/deactivate account клиент обязан сбросить финансовые экраны, локальные снимки и navigation back stack, которые могли содержать shared данные.

## 3. Навигационные состояния

### Auth

Состояния:

- `Auth.Start`: splash/boot, проверка локальной session без показа финансовых данных.
- `Auth.SignedOut`: login/register/reset entry.
- `Auth.LoginSubmitting`, `Auth.RegisterSubmitting`, `Auth.ResetSubmitting`: отправка формы без раскрытия, существует ли email.
- `Auth.SessionRestoring`: silent refresh или проверка `/sessions/current`.
- `Auth.SessionExpired`: сессия истекла; показать повторный вход и очистить защищенные route state.
- `Auth.SignedIn`: пользователь подтвержден, можно загрузить `users/me` и memberships.

Правила:

- Ошибки login/register/reset должны быть account-neutral: не подтверждать наличие email или invite/reset token.
- PWA history и Android back stack не должны возвращать пользователя на финансовый экран после logout/session expiration.
- Если session restore не завершен, финансовые экраны показывают только skeleton без сумм, названий счетов и counts.

### Dashboard

Состояния:

- `Dashboard.Loading`: загрузка видимых summary данных.
- `Dashboard.PersonalOnly`: есть только personal scope или нет active household.
- `Dashboard.HouseholdActive`: есть active membership и видимые shared данные.
- `Dashboard.EmptyVisible`: нет видимых счетов/операций для текущего пользователя.
- `Dashboard.PartialOffline`: показывается только валидный локальный снимок, помеченный как offline.
- `Dashboard.ErrorRetryable`: сетевой или временный сбой.
- `Dashboard.ForbiddenOrNotFound`: membership/resource больше недоступен.

Правила:

- Dashboard может показывать own personal агрегаты и shared агрегаты active household, но не personal агрегаты другого участника.
- Если household есть, но shared-счетов нет, текст должен говорить о видимых shared данных, без предположений о personal данных второго участника.
- Любые счетчики на Dashboard считаются только по видимым объектам. Запрещены "всего в семье", "скрыто", "у партнера" и owner-based counts.

### Accounts

Состояния:

- `Accounts.ListLoading`, `Accounts.ListReady`, `Accounts.ListEmptyVisible`, `Accounts.ListError`.
- `Accounts.DetailLoading`, `Accounts.DetailReady`, `Accounts.DetailForbiddenOrNotFound`.
- `Accounts.CreatePersonal`, `Accounts.CreateShared`, `Accounts.EditVisible`.
- `Accounts.ArchiveConfirm`, `Accounts.DeleteConfirm`, `Accounts.MutationSubmitting`, `Accounts.MutationConflict`.

Правила:

- Account list содержит только own personal accounts и shared accounts households, где пользователь active member.
- Personal-счета другого участника не показываются как карточки, placeholders, серые строки, "скрытые счета" или counts.
- `ownershipType` выбирается при создании и не меняется через edit UI в MVP.
- Для shared account create/edit UI показывает предупреждение: название, баланс, тип счета и связанные операции будут видны активным участникам household.
- Archive/delete confirm должен описывать последствия только для видимого счета и не упоминать скрытые связанные данные.

### Transactions

Состояния:

- `Transactions.ListLoading`, `Transactions.ListReady`, `Transactions.ListEmptyVisible`, `Transactions.ListError`.
- `Transactions.DetailLoading`, `Transactions.DetailReady`, `Transactions.DetailForbiddenOrNotFound`.
- `Transactions.CreateIncomeExpense`, `Transactions.CreateTransfer`, `Transactions.EditVisible`.
- `Transactions.Filtering`, `Transactions.SearchEmptyVisible`.
- `Transactions.MutationSubmitting`, `Transactions.MutationConflict`, `Transactions.MutationDenied`.

Правила:

- Transaction list строится только по видимым счетам; прямой route на скрытую операцию дает нейтральный `DetailForbiddenOrNotFound`.
- Search empty state говорит "По видимым операциям ничего не найдено" или эквивалентно, без hidden match hints.
- Для операции на shared account UI предупреждает: сумма, дата, категория и описание будут видны активным участникам household.
- Поле description в shared-операции должно сопровождаться нейтральной подсказкой не вводить секреты, номера карт, документы и личные детали.
- Категории в форме операции выбираются только из совместимых видимых категорий: personal для own personal account, household для shared account.

### Categories

Состояния:

- `Categories.ListLoading`, `Categories.ListReady`, `Categories.ListEmptyVisible`, `Categories.ListError`.
- `Categories.CreatePersonal`, `Categories.CreateHousehold`, `Categories.EditVisible`.
- `Categories.ArchiveConfirm`, `Categories.DeleteConfirm`, `Categories.MutationSubmitting`.

Правила:

- Category list/search/autocomplete возвращают только own personal categories и household categories active household.
- Personal категории другого участника не показываются и не учитываются в счетчиках usage.
- Usage count допустим только по видимым операциям текущего пользователя/scope. Если безопасный видимый count не доступен, UI должен опустить count.
- Для household category create/edit UI предупреждает, что название, иконка и цвет категории будут видны активным участникам household.

### Reports

Состояния:

- `Reports.ModeSelect`: выбор только из `shared_family_report` и `combined_viewer_overview`.
- `Reports.FiltersEditing`: период, timezone, household, visible account/category filters.
- `Reports.Loading`, `Reports.Ready`, `Reports.EmptyVisible`, `Reports.ErrorRetryable`.
- `Reports.ForbiddenOrNotFound`: household/filter больше недоступен.
- `Reports.DrillDownLoading`, `Reports.DrillDownReady`, `Reports.DrillDownEmptyVisible`.

Правила:

- `shared_family_report` доступен только при active household и строится по shared-счетам, shared-операциям и household-категориям выбранного household.
- `combined_viewer_overview` строится по shared-счетам выбранного household плюс own personal-счетам текущего viewer.
- UI не должен предлагать режим, сравнение или breakdown "по участникам", "личное партнера", "вклад участника", если для этого нужны personal данные другого участника.
- `includedAccountIds`, account filters и category filters отображаются только для видимых объектов выбранного режима.
- Пустой отчет означает "нет видимых данных за период/фильтры"; он не должен намекать, что данные другого участника существуют или скрыты.
- Drill-down использует те же predicates, что transaction list/detail; каждая строка drill-down должна быть открываема тем же пользователем через detail.

### Household

Состояния:

- `Household.None`: у пользователя нет active household.
- `Household.Loading`, `Household.Active`, `Household.EmptySharedVisible`.
- `Household.InvitedContext`: пользователь видит только собственное приглашение до accept.
- `Household.LeftOrRevoked`: shared access отозван, локальные shared snapshots сброшены.
- `Household.ErrorRetryable`, `Household.ForbiddenOrNotFound`.

Правила:

- Active members видят минимальный состав household: `userId`, `displayName`, membership status, без email и без personal финансовых counts.
- Invited user до accept не видит shared accounts, operations, categories, reports и detailed household composition.
- Former member после leave/revoke не видит shared screens; deep links в shared resources переводятся в нейтральное недоступно/не найдено.

### Invites

Состояния:

- `Invites.ListLoading`, `Invites.ListReady`, `Invites.ListEmpty`.
- `Invites.CreateForm`, `Invites.Submitting`, `Invites.Created`.
- `Invites.AcceptPreview`, `Invites.AcceptSubmitting`, `Invites.Accepted`.
- `Invites.DeclineSubmitting`, `Invites.RevokeSubmitting`, `Invites.ExpiredOrInvalid`.

Правила:

- До accept preview показывает только минимальный invitation context, достаточный для решения принять/отклонить.
- Invite errors нейтральны: истекший, отозванный, использованный или недоступный token не должен раскрывать лишние household/member детали.
- После accept клиент перезагружает memberships и financial scopes с сервера, а не раскрывает shared данные из invite payload.

### Export, delete account/data, leave family

Состояния export:

- `Export.Form`: выбор формата и видимого scope.
- `Export.RequestSubmitting`, `Export.Pending`, `Export.Processing`, `Export.Ready`, `Export.Failed`, `Export.Expired`.

Правила export:

- UI явно говорит, что export включает только данные, видимые текущему пользователю на момент генерации.
- Export не обещает personal данные другого участника и не показывает hidden counts.
- Ссылки на export file не кэшируются дольше срока действия job/file.

Состояния delete account/data:

- `DeleteAccount.Confirm`, `DeleteAccount.Submitting`, `DeleteAccount.PendingOrCompleted`, `DeleteAccount.Error`.

Правила delete:

- Delete/deactivation flow относится только к текущему пользователю.
- UI должен предупреждать, что сессии будут отозваны, personal данные будут удалены/обезличены по принятой процедуре, а shared history может сохраняться в household с обезличенным автором согласно privacy baseline.
- После успешного запроса клиент очищает локальные финансовые снимки и переводит пользователя в signed-out или restricted state по ответу API.

Состояния leave family:

- `LeaveFamily.Confirm`, `LeaveFamily.Submitting`, `LeaveFamily.Completed`, `LeaveFamily.Error`.

Правила leave:

- UI предупреждает: после выхода будущий доступ к shared-счетам, shared-операциям, household-категориям и shared-отчетам прекратится.
- UI также предупреждает: shared-данные, уже видимые другим active member, нельзя технически забрать обратно.
- После completed клиент инвалидирует household navigation, shared report caches, shared selectors, cursors и offline snapshots.

## 4. UI visibility rules для personal/shared

| UI surface | Personal текущего viewer | Shared active household | Personal другого участника | Shared другого household |
| --- | --- | --- | --- | --- |
| Dashboard | Можно показывать | Можно показывать active member | Запрещено | Запрещено |
| Account list/detail | Можно показывать owner | Можно показывать active member | Запрещено | Запрещено |
| Transaction list/detail | Через видимый account | Через shared account | Запрещено | Запрещено |
| Category list/autocomplete | Own personal | Household categories | Запрещено | Запрещено |
| Reports | Только `combined_viewer_overview` | Оба report modes | Запрещено | Запрещено |
| Search/autocomplete | Только видимые объекты | Только видимые объекты | Запрещено | Запрещено |
| Export | Только видимые данные | Только видимые данные | Запрещено | Запрещено |
| Offline cache | Только текущий viewer и валидный access version | Только пока active member | Запрещено | Запрещено |

Дополнительные правила:

- Labels `personal` и `shared` допустимы только для видимых объектов.
- UI не должен показывать "личные счета участника B скрыты" или заглушки под чужие personal sections.
- Member profile в household UI не содержит financial counters: account count, transaction count, balance total, report total, category usage.
- Сортировка, группировка, axis scaling и filter chips не используют hidden rows.
- Любой badge/count в навигации считается только по видимым unread/pending/list items. Если безопасный видимый count не определен, badge не показывается.

## 5. Empty, error и loading states

Loading:

- Skeleton/placeholder не должен содержать реальные суммы, названия, counts, owner hints или предзаполненные examples из чужого scope.
- При переключении scope старые данные предыдущего scope скрываются до завершения загрузки нового видимого набора.
- Pull-to-refresh и background refresh не должны временно смешивать personal и shared данные разных режимов.

Empty:

- Для списков: "Нет видимых счетов", "Нет видимых операций", "Нет видимых категорий" или более продуктовый эквивалент.
- Для фильтров/search: "По видимым данным ничего не найдено".
- Для отчетов: "Нет видимых данных за выбранный период".
- Запрещено: "данные скрыты", "у другого участника нет/есть данных", "показано 0 из N", "нет семейных операций, кроме личных".

Errors:

- `UNAUTHENTICATED`/`SESSION_EXPIRED`: перевести в auth state и очистить защищенный UI state.
- `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` и `REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE`: показывать нейтральную недоступность без object details.
- `MEMBERSHIP_NOT_ACTIVE`: обновить memberships, очистить shared caches и показать нейтральное сообщение о недоступности shared-раздела.
- `TRANSFER_SCOPE_NOT_SUPPORTED`: показать общее сообщение "Перевод недоступен для выбранных счетов" без указания, какая сторона нарушила правило.
- `CONFLICTING_UPDATE`: предложить обновить видимую запись, не показывая скрытые diff/details.
- Retry UI не должен повторять raw request payload с суммами, описаниями или id.

## 6. Shared operation warnings

Shared warnings обязательны в Android и PWA перед созданием или изменением:

- shared account;
- shared income/expense/brokerage transaction;
- shared -> shared transfer;
- household category;
- household settings, invite, leave family;
- shared report export, если export включает shared data.

Минимальный смысл warning:

- запись относится к shared household;
- активные участники household смогут видеть соответствующие поля;
- описание и пользовательские названия не должны содержать секреты, номера карт, документы, пароли или информацию, которую пользователь не хочет раскрывать семье.

Warnings не должны раскрывать personal данные второго участника и не должны перечислять hidden последствия вроде "не затронет личные счета партнера", если это превращается в подсказку о наличии таких счетов. Допустимо общее утверждение privacy baseline: personal данные другого участника не входят в shared operation.

## 7. Report mode UX states

### `shared_family_report`

Состояния:

- `ReportMode.SharedFamily.UnavailableNoActiveHousehold`;
- `ReportMode.SharedFamily.FilterEditing`;
- `ReportMode.SharedFamily.Loading`;
- `ReportMode.SharedFamily.Ready`;
- `ReportMode.SharedFamily.EmptyVisible`;
- `ReportMode.SharedFamily.ForbiddenOrNotFound`;
- `ReportMode.SharedFamily.DrillDown`.

Контракт:

- Требует `householdId`, `startDate`, `endDate`, `timezone`.
- Account selector содержит только shared accounts выбранного household.
- Category selector содержит только household categories выбранного household и безопасный uncategorized вариант, если поддержан API.
- Summary, balances, category breakdown, cash flow и drill-down строятся только по shared rows.
- UI не показывает own personal rows даже текущему viewer в этом режиме.
- UI не показывает personal rows второго участника ни напрямую, ни агрегированно, ни через "не включено" counts.

### `combined_viewer_overview`

Состояния:

- `ReportMode.CombinedViewer.UnavailableNoActiveHousehold`;
- `ReportMode.CombinedViewer.FilterEditing`;
- `ReportMode.CombinedViewer.Loading`;
- `ReportMode.CombinedViewer.Ready`;
- `ReportMode.CombinedViewer.EmptyVisible`;
- `ReportMode.CombinedViewer.ForbiddenOrNotFound`;
- `ReportMode.CombinedViewer.DrillDown`.

Контракт:

- Требует `householdId`, `startDate`, `endDate`, `timezone`.
- Account selector содержит own personal accounts текущего viewer и shared accounts выбранного household.
- Category selector содержит own personal categories текущего viewer, household categories выбранного household и безопасный uncategorized вариант, если поддержан API.
- UI может визуально отличать "мои личные" и "общие", но не создает секцию "личные другого участника".
- Report totals, balances, charts и drill-down не включают personal данные другого участника.
- Cache для этого режима всегда viewer-specific; Android/PWA не могут переиспользовать один cached overview между двумя пользователями одного household.

## 8. Transfer UI constraints

Transfer form states:

- `Transfer.SelectSourceAccount`;
- `Transfer.SelectCounterpartyAccount`;
- `Transfer.EditDetails`;
- `Transfer.Submitting`;
- `Transfer.ScopeDenied`;
- `Transfer.ConflictOrRetryableError`.

Правила выбора:

- Source account selector показывает только видимые счета текущего пользователя.
- После выбора source account counterparty selector сужается до same-scope accounts:
  - если source `ownershipType = personal`, доступны только personal accounts с `ownerUserId = currentUserId`;
  - если source `ownershipType = shared`, доступны только shared accounts с тем же `householdId`;
  - accounts другого household, personal accounts другого участника и любые personal<->shared пары не отображаются.
- UI не предлагает переключатель или shortcut для personal -> shared, shared -> personal, cross-user personal или cross-household shared.
- Если пользователь открыл deep link/edit существующего transfer и API вернул нейтральный deny, UI не пытается восстановить hidden side из локального кэша.
- `categoryId` не выбирается для transfer в MVP.
- Currency selector, если есть, не должен предлагать cross-currency transfer; безопасный default - currency выбранных счетов.

Сообщение при denied:

- Для `TRANSFER_SCOPE_NOT_SUPPORTED` показывать единый текст "Перевод недоступен для выбранных счетов".
- Не уточнять "личный счет нельзя перевести в общий", если такая формулировка основана на скрытой counterparty. Для локально выбранной видимой personal/shared пары UI может до отправки просто не дать выбрать такую пару.

## 9. Offline и cache constraints

Общие правила:

- Offline/cache является UX-оптимизацией, а не источником прав. Любая online mutation требует свежей server-side authorization.
- Локальные snapshots должны быть scoped минимум по `viewerUserId`, session/access version, `householdId`, report mode и membership/access version для shared данных.
- После logout, session expiration, password reset, delete/deactivation, leave/revoke membership, invite accept/revoke или household archive клиент очищает соответствующие protected snapshots.
- Former member не должен видеть shared данные через offline mode после потери membership. При следующем запуске или refresh shared cache должен быть заблокирован до проверки session/membership.
- PWA service worker не должен кэшировать authenticated API responses как общедоступные assets. Cache keys и storage должны быть user-scoped; shared browser/device сценарии требуют logout clear.
- Android local persistence должна хранить минимальный набор данных, необходимый для UX, и очищаться при смене account/session.
- Crash reports, frontend telemetry, breadcrumbs и analytics events не должны содержать суммы, балансы, названия счетов/категорий, descriptions, email, tokens, raw query payload или screenshots с финансовыми данными.

Offline UI:

- `offlineReadonly` может показывать только ранее видимые данные текущего viewer при валидном локальном access context.
- Mutations в offline MVP безопаснее запрещать или держать как локальный draft без отправки, пока сервер не подтвердит access. Draft для shared operation должен заново показать shared warning перед submit.
- Offline empty/error states не должны отличать "данных нет" от "данные могли измениться на сервере"; безопасный текст - "Не удалось обновить данные. Показаны последние доступные видимые данные" или "Данные недоступны без подключения".
- Report caches должны соблюдать правила report API: `shared_family_report` может быть household-scoped только без viewer-personal rows; `combined_viewer_overview` всегда viewer-scoped.
- Drill-down cursors и paginated list cursors нельзя переиспользовать после membership/access version change.

## 10. Handoff notes для future design

- Проектировать Android и PWA как два клиента одного privacy contract: одинаковые states, wording rules и deny behavior важнее визуального различия платформ.
- Для визуального дизайна нужны явные паттерны scope labels: "личное" для own personal и "общее" для household, без области для personal другого участника.
- Все shared create/edit forms должны иметь ненавязчивый, но обязательный warning. Текст warning лучше централизовать, чтобы Android/PWA не разошлись.
- Empty states должны быть заранее описаны в content guide, иначе есть риск случайно написать copy, раскрывающий hidden counts.
- Report UI не должен вводить новый report mode без Product/Security/Privacy escalation. Особенно опасны comparison by member, contribution, hidden totals, household-wide total including personal и "family net worth".
- Transfer UX должен строиться от same-scope selectors. Не делать универсальный account picker, который затем показывает ошибку для personal<->shared; это создает лишние inference paths.
- Для PWA отдельно проверить browser back/forward, service worker cache, shared device logout и deep links на hidden resource ids.
- Для Android отдельно проверить task stack, process death restore, biometric/session unlock, local DB migration и account switch.
- Перед реализацией QA должен получить snapshot tests на отсутствие `hiddenCount`, `filteredOutCount`, foreign personal placeholders и forbidden report/transfer options.

## 11. Definition of done coverage

- Client states не раскрывают чужие personal placeholders/counts: запрещены hidden placeholders, hidden counts, member financial badges и empty/error wording с намеком на чужие personal данные.
- Shared operation warnings есть: accounts, transactions, transfers, categories, invites/leave/export shared flows покрыты.
- Оба report modes отражены: `shared_family_report` и `combined_viewer_overview` имеют отдельные UX states, filters и visibility constraints.
- Transfer UI не предлагает personal<->shared: selectors сужаются до `personal_same_owner` или `household_same_household`.
- Android/PWA одинаково следуют privacy rules: документ задает общую state model, cache/offline constraints и одинаковую нейтральность ошибок для обеих платформ.

## 12. Риски и escalation triggers

Риски:

- Copy в empty/error states может случайно раскрыть, что данные скрыты, а не отсутствуют.
- Универсальные selectors account/category/report filters могут показать wrong-scope варианты до server deny.
- PWA service worker или Android local DB могут сохранить shared snapshots после leave/revoke.
- Report cache для `combined_viewer_overview` может быть ошибочно разделен между участниками household.
- Shared transaction description может содержать чувствительные личные детали, если UI не предупреждает пользователя.

Эскалировать к Product/Security/Privacy до реализации, если:

- нужен UX, который показывает personal placeholders, counts, aggregates или наличие personal данных другого участника;
- нужен новый report mode, comparison by member, contribution view или family total including personal второго участника;
- нужно разрешить personal<->shared transfer или split visibility;
- former member должен видеть исторические shared данные после leave/revoke;
- offline-first mutations должны работать без свежей server-side authorization;
- telemetry/crash reporting требует screenshots, raw payloads или granular financial events.
