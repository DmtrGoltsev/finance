# Диагностика схемы production Finance

Workflow `.github/workflows/finance-prod-readonly-inventory.yml` не развёртывает
сервисы и не меняет хост. Прямой SSH/SCP с рабочей станции запрещён. После
слияния этого PR в `main` владелец вручную запускает `workflow_dispatch` **на
`main`** с `phase=bootstrap` и подтверждением `finance-readonly-inventory`.
До слияния новый workflow недоступен для ручного запуска.

## Две фазы

1. `bootstrap` проверяет владельца, `main`, точное подтверждение и отсутствие
   внешнего `bootstrap_run_id`. Только этот job получает `contents: write` и
   `actions: write`. Он создаёт `prod/release-inventory-<run-id>` из точного
   SHA `main` через GitHub API, используя **только** `GITHUB_TOKEN` запуска.
   Ветка не создаётся с рабочей станции и не получает новых коммитов.
2. Тем же `GITHUB_TOKEN` bootstrap вызывает `workflow_dispatch` с
   `phase=inventory` на созданном ref. GitHub не запускает push-workflow от
   событий, созданных `GITHUB_TOKEN`, но делает исключение для
   `workflow_dispatch`. См. [правило GitHub](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
   Production deploy workflow отдельно отвергает `prod/release-inventory-*`
   до подготовки релиза и обращения к окружению, даже при ручном запуске.
   Ответ [API версии 2026-03-10](https://docs.github.com/en/rest/actions/workflows?apiVersion=2026-03-10#create-a-workflow-dispatch-event)
   должен содержать точный `workflow_run_id`: поиск по ветке/SHA запрещён.
   Пустой ответ или несовпадение метаданных останавливают bootstrap без
   автоматического удаления ref.
3. Отдельный `validate-inventory` без production secrets проверяет строгий
   формат ref, SHA, actor `github-actions[bot]` текущего запуска, первую
   попытку, точные ID, имя и фазу обоих запусков, а также происхождение
   активного owner-started bootstrap-run на `main`. Чужой ручной dispatch не
   проходит. Только после его успеха job `inventory` получает существующие SSH
   secrets окружения `production`. Политика `prod/release-*` пропускает этот
   временный ref; `deployment: false` не создаёт запись о развёртывании.
4. Inventory обращается к хосту только из Actions с закреплённым host key и
   `StrictHostKeyChecking=yes`. Скрипт читает метаданные и фиксированные
   loopback health endpoints; не читает `.env`, `docker inspect .Config.Env`,
   секретные файлы, БД или содержимое финансовых данных. Проверка
   `validate_output.py` требует полный список полей, типизированные значения,
   отсутствие повторов и неизвестных полей **до** показа или загрузки вывода.
5. Bootstrap ждёт завершения inventory. Затем он удаляет только собственный
   ref, повторно проверив, что его SHA всё ещё равен исходному SHA `main`.
   Если запуск не найден, ожидание истекло или SHA изменился, автоматическое
   удаление не выполняется.

## Если временный ref остался

Не отправлять в него коммиты и не запускать deploy workflow. Записать ID и SHA
bootstrap-run, по ним найти inventory-run и дождаться завершения всех его
jobs. Сверить, что ref имеет точное имя
`prod/release-inventory-<bootstrap-run-id>` и всё ещё указывает на исходный
SHA `main`. Только после этих трёх проверок владелец может удалить именно этот
ref через GitHub API. При изменившемся SHA или активном run остановиться и
разобрать ситуацию; не применять массовую очистку `prod/release-*`.

## Границы доказательства

Артефакт содержит только значения `yes`, `no`, `unknown` и перечисления для
области двух symlink. `*_writable=yes` означает права SSH-пользователя на
существующий каталог, а не разрешение устанавливать там сервис. Отсутствие
доступа к Docker daemon не доказывает отсутствия Docker на хосте. Сетевую
достижимость из контейнера в host backend этот read-only скрипт не проверяет.

Наличие имён provider credentials на хосте остаётся `unknown`: узнать их из
`.env` или Docker configuration без чтения строк с секретами нельзя в рамках
этого режима. Имена environment secrets GitHub можно проверить отдельно через
`gh secret list --env production`; значения не извлекать.

Если GitHub ограничивает `GITHUB_TOKEN` в создании веток или dispatch,
bootstrap завершится с ошибкой. Не использовать PAT, GitHub App token,
локальный push в `prod/release-*` или изменение branch policy как обход.
GitHub документирует действие `GITHUB_TOKEN` от имени Actions, но не обещает
в справке конкретное значение actor для дочернего `workflow_dispatch`.
Поэтому проверка `github-actions[bot]` намеренно закрыта при несовпадении.
Проверить фактический actor можно только при разрешённом запуске после слияния;
если он иной, остановиться и выбрать другой диагностический маршрут, например
ограниченную read-only инвентаризацию на `main` без production environment
secrets, либо согласовать безопасное изменение политики окружения.
