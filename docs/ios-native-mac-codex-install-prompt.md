# Промпт для Codex на новом Mac: сборка и установка Finance на iPhone

Скопируйте весь блок ниже в новую задачу Codex на Mac.

```text
Ты работаешь на новом Mac и должен полностью подготовить, проверить, подписать,
установить и запустить native iOS Finance на моём физическом iPhone. Доведи
задачу до результата. Рутинные команды выполняй сам; обращайся ко мне только
для неизбежных системных подтверждений macOS, GitHub, Apple и физического
взаимодействия с iPhone.

Исходные данные:
REPOSITORY="DmtrGoltsev/finance"
BRANCH="prod/release-finance-ios-current-parity-20260823-db7ebdd"
EXPECTED_SHA="db7ebdd41a35018ae59e1fc4f5c5e38f0ed37de6"
NATIVE_DIR="apps/ios"
PROJECT="FinanceApp.xcodeproj"
SCHEME="FinanceAppPersonalHTTP"
TARGET="FinanceAppPersonalHTTP"
CONFIGURATION="PersonalSideloadHTTP"
API_BASE_URL="http://45.10.110.42/finance-api"
HEALTH_URL="http://45.10.110.42/finance-api/health"
MINIMUM_IOS="17.0"
FINAL_IOS_CI_RUN="32603535573"
PRODUCTION_DEPLOY_RUN="32604838031"

Критические правила:
- Используй только immutable release branch и точный EXPECTED_SHA выше.
- Целевой native client находится только в `apps/ios`. Не используй legacy
  Capacitor wrapper `apps/web-pwa/ios`.
- Сначала прочитай `AGENTS.md`, `Ru_OrchestratorRules.md` и
  `Ru_SubagentFirstFinishNew.md`; соблюдай их, включая реальную оркестрацию.
- Не меняй tracked source/config/docs, не создавай commit и не делай push.
  Допустимы локально сгенерированный Xcode project, DerivedData, signing и
  provisioning metadata, а также локальные evidence-файлы вне репозитория.
- Не выполняй deploy, миграции, seed, регистрацию production-пользователя или
  изменение production financial data. Backend уже задеплоен run 32604838031.
- Не проси токены, пароли, Apple ID password, 2FA-коды, signing keys или
  production credentials в чате и не выводи их в логи/evidence.
- Production login/password пользователь вводит только непосредственно на
  iPhone. Не извлекай bearer/refresh tokens из Keychain или network traffic.
- Это owner/family personal sideload. Не создавай Archive/IPA, не используй
  App Store/TestFlight/ad hoc/public distribution и сторонние signing-сервисы.
- HTTP разрешён только target/scheme `FinanceAppPersonalHTTP`, configuration
  `PersonalSideloadHTTP` и точному URL выше. Не ослабляй обычные Debug/Release,
  не добавляй broad ATS exception и не меняй allowlist.
- Plaintext HTTP несёт принятый owner-waived риск перехвата/подмены credentials,
  tokens и financial data. Waiver подлежит пересмотру до 2026-11-22 и сразу
  теряет силу при изменении host/path/auth/device/distribution или появлении
  подходящего HTTPS.

1. Подготовка Mac

Сам проверь и сохрани в локальный sanitized evidence:
`sw_vers`, `uname -m`, `xcode-select -p`, `xcodebuild -version`,
`swift --version`, `git --version`, `brew --version`, `gh --version`,
`xcodegen --version`.

Нужен полный Xcode с iOS 17+ SDK, а не только Command Line Tools. Перед
установкой отсутствующего компонента коротко сообщи, что и зачем установишь,
какую команду запустишь и какое системное окно/пароль/перезапуск возможны.
После моего подтверждения системного действия выполняй установку сам:
- CLT: `xcode-select --install`;
- CLI tools: `brew install gh xcodegen`;
- полный Xcode: открой официальный Mac App Store и попроси только подтвердить
  Apple ID/установку;
- при необходимости выбери `/Applications/Xcode.app/Contents/Developer`,
  прими license и выполни first-launch setup.
Пароль администратора вводится только в системный prompt, не в чат.

2. GitHub без передачи токена

- Выполни `gh auth status`.
- Если входа нет, запусти
  `gh auth login --hostname github.com --git-protocol https --web`.
- Я только подтверждаю browser/device authorization. Токен не показывай.
- Выполни `gh auth setup-git` и повторно проверь статус.

3. Чистый clone и immutable revision

- Используй `~/Developer/finance`. Если каталог уже существует, не удаляй и не
  перезаписывай его; проверь remote/status или создай новый чистый каталог.
- Клонируй `gh repo clone DmtrGoltsev/finance`.
- Выполни `git fetch --prune origin` и checkout release branch в detached HEAD.
- Проверь, что локальный HEAD и `origin/$BRANCH` строго равны EXPECTED_SHA.
- Проверь, что worktree чистый и SHA является потомком:
  `4e1ef36724f804d648f2ea385da5259688915325`,
  `6d3f4e3cdb1ed7b333879603789d1ca9a1bb080c`,
  `744a422c5d012149f6c0051dcaf291623fd9a19c`.
- При любом несовпадении остановись и назови точный blocker. Не тестируй и не
  подписывай другой commit.

4. Источники истины

До генерации проекта прочитай как минимум:
- `README.md`;
- `docs/current-status.md`;
- `docs/ios-native-mac-handoff.md`;
- `docs/ios-native-mac-codex-install-prompt.md`;
- `docs/testing/ios-native-parity-qa-test-model.md`;
- `docs/security/ios-personal-http-waiver-2026-08-22.md`;
- `MVP_EVIDENCE/native-ios-current-parity-20260822/SUMMARY_SANITIZED.md`;
- `apps/ios/project.yml`;
- `.github/workflows/ios-build.yml`;
- normal и personal Info.plist;
- transport/environment implementation и tests.

5. Локальное evidence

Создай каталог вне Git, например
`~/Desktop/finance-ios-evidence-YYYYMMDD-HHMMSS`. Сохраняй туда версии,
branch/SHA, build/test logs, `.xcresult`, sanitized signing/install status и
`SUMMARY_SANITIZED.md`. Не сохраняй credentials, cookies, tokens, provisioning
profile целиком, Team ID, UDID, financial payloads или production screenshots.
Ничего не загружай и не коммить.

6. XcodeGen и воспроизводимые gates

Из `apps/ios`:
- `xcodegen generate`;
- `xcodebuild -list -project FinanceApp.xcodeproj -json`;
- выбери доступный iPhone Simulator через `xcrun simctl list devices available`;
- используй отдельные DerivedData и `set -o pipefail`.

Повтори gates `.github/workflows/ios-build.yml`:
- unsigned Debug build схемы `FinanceApp`;
- unsigned ordinary Release build схемы `FinanceApp` с compile-only
  `FINANCE_RELEASE_API_BASE_URL=https://finance.invalid/finance-api`;
- unsigned `PersonalSideloadHTTP` build схемы `FinanceAppPersonalHTTP`;
- normal XCTest и launch UI test на simulator;
- dedicated personal transport XCTest для personal scheme/configuration.

Проверь фактически собранные Info.plist fail-closed:
- Personal `FINANCE_API_BASE_URL` строго равен API_BASE_URL;
- `NSAllowsArbitraryLoads=false` и `NSAllowsLocalNetworking=false`;
- единственный HTTP exception host `45.10.110.42`;
- insecure HTTP разрешён только ему, subdomains=false;
- bundle id `com.codex.FinanceApp.PersonalSideload`;
- product/display name относятся к personal target;
- manual Apple Development signing;
- target не поддерживает archive/export;
- normal Debug/Release не содержат production IP, personal URL/ATS exception
  или personal bundle identity;
- redirect policy отклоняет 3xx и final response URL повторно валидируется.

Через `gh` проверь, что run 32603535573 завершён success и его head SHA равен
EXPECTED_SHA. Базовое доказательство: Debug/Release/Personal PASS, normal
87/0, personal 10/0, artifact 9483613408, digest
sha256:52d98838dd947420e0093c308c58286ab3f5db831017030c4f64be61f6c7bc43.

7. Apple signing и физический iPhone

- Открой сгенерированный `FinanceApp.xcodeproj` в Xcode.
- Если Apple account/Team не настроены, попроси меня только войти в Xcode
  Settings > Accounts, пройти Apple ID/2FA и выбрать Personal Team или paid
  Development Team. Не проси credentials в чат.
- Обнаружь iPhone через `xcrun devicectl list devices`.
- Попроси меня только подключить/разблокировать iPhone, подтвердить Trust This
  Computer, включить Developer Mode, перезагрузить устройство и подтвердить
  device/profile registration, когда это запросит система.
- Используй target/scheme `FinanceAppPersonalHTTP`, configuration
  `PersonalSideloadHTTP`, automatic provisioning update для development install,
  но сохрани Apple Development identity, отдельный bundle id и no-archive.
- Если bundle id недоступен Team, используй только локальный generated-project
  build override с уникальным owner-controlled suffix. Не меняй tracked
  `project.yml` или source.
- Не выводи Team ID, UDID, certificate details или profile целиком.

Собери device `.app` командой `xcodebuild` с project, scheme, configuration,
destination физического iPhone, отдельным DerivedData,
`-allowProvisioningUpdates` и `-allowProvisioningDeviceRegistration`. Перед
установкой повторно проверь подпись и built Info.plist. Не выполняй Archive.

8. Установка и запуск

- Уточни актуальный синтаксис через `xcrun devicectl help`.
- Установи `.app` командой `xcrun devicectl device install app`.
- Запусти через `xcrun devicectl device process launch`, при необходимости с
  terminate-existing.
- Xcode Product > Run используй только как fallback.
- Если iPhone просит доверять developer identity, попроси меня подтвердить это
  в Settings.
- Подтверди, что приложение запускается и остаётся установленным.

9. Production smoke без изменения данных

- Read-only health:
  `curl -fsS --max-time 10 http://45.10.110.42/finance-api/health`;
  ожидается `{"status":"ok"}`. Health не является доказательством login.
- Я ввожу production login/password непосредственно на iPhone.
- Подтверди login и загрузку главного экрана.
- Read-only открой операции, активы, категории расходов и аналитику; проверь
  поиск категории и переключение месяца без сохранения изменений.
- Выполни terminate/relaunch и проверь сохранение сессии.
- Не создавай, не редактируй, не архивируй и не удаляй финансовые сущности.
- Не запускай OCR с production screenshot.
- В evidence записывай только endpoint, HTTP status/error class, этап и
  sanitized message, без финансовых значений или response bodies.

10. Финальный отчёт

Верни на русском:
- exact branch и SHA;
- версии macOS/Xcode/CLT/XcodeGen;
- matching CI status;
- результаты XcodeGen, трёх builds, normal/personal XCTest и UI test;
- exact API/ATS/bundle/signing/no-archive policy;
- signing/build/install/launch status;
- health/login/read-only/relaunch smoke status;
- путь к локальному evidence;
- `git status --short` и подтверждение отсутствия source edits/commit/push/deploy;
- только реальные blockers с одной точной следующей ручной операцией.

Для free Personal Team не обещай фиксированный срок. Проверь фактическую дату
expiration в созданном provisioning profile/Xcode и сообщи её без Team ID/UDID.
Предупреди, что free provisioning часто требует повторной подписи примерно
через 7 дней, но фактический срок берётся только из текущего profile. Для paid
Developer Team также сообщай срок только по фактическому profile.

Неизбежные действия пользователя ограничены:
1. Подтвердить GitHub browser/device authorization.
2. Подтвердить системную установку и при необходимости ввести пароль macOS
   только в системный prompt.
3. Войти в Apple ID в Xcode, пройти 2FA и выбрать Team.
4. Разблокировать iPhone, подтвердить Trust, Developer Mode, reboot и device
   registration.
5. Ввести production login/password прямо на iPhone и визуально подтвердить
   read-only smoke.
```

Проектный release evidence, скачанный после production workflow, хранится вне
Git по пути
`C:\Users\style\Documents\Codex\Finance-release-evidence\32604838031`.
Этот Windows-путь приведён для traceability; на Mac создаётся отдельный локальный
sanitized evidence-каталог по инструкции выше.
