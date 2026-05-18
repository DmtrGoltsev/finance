# Критический аудит тестовой модели, 2026-05-18

Роль: QA Lead / Test Architect subagent.

Область: backend tests, PWA tests, Android unit/instrumentation tests, QA/evidence docs. Продуктовый код не менялся.

## Вывод

Тестовая модель стала лучше закрывать import placeholder, OpenAPI-контракт, PWA Quick Add и Android mode filtering, но full device QA на Android emulator `2_Pixel 6 Pro` и iPhone browser нельзя считать готовым к запуску без фиксов ниже.

## Покрыто исполняемыми тестами

| Область | Уровень | Доказательство |
| --- | --- | --- |
| Backend privacy для accounts/categories/transactions/reports | Сильное | Матрицы owner/member/other/invited/former, нейтральные 404, отсутствие hidden counts/facets/placeholders. |
| Backend transfers | Сильное | Same-scope create/update/delete/restore, атомарность балансов, cross-scope/cross-user/cross-household denial. |
| Backend import placeholder | Усилено | Metadata-only, no mutation, reject content-like fields, reserved sourceType, shared membership, file basename sanitization. |
| Static OpenAPI contract | Усилено | Import preview добавлен в canonical OpenAPI; asset account/transaction enum coverage добавлен. |
| PWA client transport | Среднее | Cookie transport, CSRF for unsafe requests, no localStorage bearer. |
| PWA UX smoke | Среднее | Dashboard, modes, transfer not expense, import placeholder, Quick Add expense/transfer/shared asset. |
| Android JVM model | Среднее | Sections, copy guardrails, transfer not expense, asset kinds, mode filtering. |

## Тонкие места и фиктивные PASS

| Риск | Почему это важно | Что нужно до full device QA |
| --- | --- | --- |
| Android instrumentation test `FinanceAppUiTest` помечен `@Ignore` | Android emulator evidence может опираться на ручные screenshots, а не на исполняемый UI gate. | Implementation/QA worker должен починить или заменить instrumented сценарий под `2_Pixel 6 Pro`. |
| Android `LiveFinanceApiClient.createDemoAccount` и `createDemoCategory` игнорируют shared scope | Quick Add "Общее" для asset/category может сохранять personal, а UI будет давать ложное ощущение shared действия. | Implementation worker: передавать `ownershipType=shared`/`householdId` для accounts и `scope=household`/`householdId` для categories. |
| PWA `previewImportReport` fallback ловит любые ошибки backend | 401/403/422/404 privacy denial может превратиться в локальный placeholder и скрыть authz/contract defect. | Implementation worker: fallback разрешить только для "endpoint отсутствует" на dev/stub, а authz/validation/server errors показывать как ошибку. |
| iPhone evidence является iOS-like browser viewport, не физическим Safari/iPhone | PWA installability, file picker, viewport safe areas и input behavior не доказаны настоящим устройством. | Full QA worker: реальный iPhone/Safari или явно утвержденный waiver. |
| Android device privacy/offline/back-stack не покрыты | Финансовые данные могут остаться после logout/session revoke или в back stack/cache. | Добавить device сценарии logout, повторный вход другим пользователем, rotate/background/restore. |
| Import placeholder device UX не доказан на Android connected test | Есть unit/build и screenshots, но нет исполняемого device assertion по file metadata only. | Добавить instrumented smoke: открыть import, выбрать тип/scope/file metadata stub, проверить no confirm/no mutation copy. |

## Definition of Done для device QA gate

- Backend/PWA/Android unit suites проходят на текущем workspace.
- Android connected test не `@Ignore` и проходит на `2_Pixel 6 Pro`.
- iPhone browser evidence содержит дату, устройство/browser, viewport, сценарий и PNG/screenshot proof.
- Для каждого сценария есть "действие -> ожидаемый результат -> evidence path".
- Любой `PASS WITH LIMITATIONS` содержит owner и следующий шаг; для P0/P1 нельзя маскировать как release GO.
