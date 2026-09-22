# Контракт установки инвестиционных рекомендаций Finance

**Статус: производство заблокировано.** После preflight PR #11 Docker-путь
выведен из эксплуатации. `production-package-gate` безусловно останавливает
любой release push до обращения к хосту с кодом
`DELIVERY_HOST_NATIVE_CAPACITY_UNVERIFIED`. Ни approval variables, ни ручной
dispatch не снимают блокировку. Host-native код подготовлен локально, но его
вместимость и восстановление на VPS не доказаны.

## Host-native контракт (локальная реализация)

`native_contract.py preflight` выполняет только чтение. Он требует approval
`host-native-v1` не старше 24 часов с SHA-256 файлов доказательств, точными
Ubuntu 26.04 x86_64, Node 24 и npm 10/11 с контрольными суммами,
PostgreSQL 18 с правами администратора, ревизией Finance `20260822_0019`,
здоровым backend на loopback `8081`, свободными или уже принадлежащими Finance
портами `5680/8080/8091`. Доступные память и место должны покрывать
**измеренные** пики n8n/gateway/worker, установку, рост БД, резервные копии,
пробное восстановление и запас минимум 512 МиБ/1 ГиБ. Примерные числа из
локальных тестов не являются измерением VPS. Поля контракта заданы в
`native_contract.py`; синтетическую проверку выполняют командой `dry-run
--approval <файл> --facts <файл>`. Режим `preflight` не принимает `--facts`.

До любой записи `native_release.py stage` повторяет живой preflight, проверяет
источник по lockfile SHA-256 и n8n `2.39.8`, root-owned файлы `0600`, реальные
значения семи раздельных секретов, DeepSeek, FCM service account от `finance`,
токен и UUID тестового снимка, а также доказательства backup/restore и
недеструктивного rollback. Источник секретов только
`/etc/finance/delivery/production.env`, не Git и не workflow inputs:

```text
FINANCE_N8N_POSTGRES_PASSWORD
FINANCE_GATEWAY_DB_PASSWORD
N8N_ENCRYPTION_KEY
FINANCE_GATEWAY_QUEUE_KEY
FINANCE_GATEWAY_TOKEN
FINANCE_INGRESS_HMAC_SECRET
FINANCE_CALLBACK_HMAC_SECRET
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
FINANCE_BACKEND_FCM_ENABLED
FINANCE_BACKEND_FCM_PROJECT_ID
FINANCE_BACKEND_FCM_CREDENTIALS_FILE
FINANCE_E2E_BEARER_TOKEN_FILE
FINANCE_E2E_SNAPSHOT_ID
```

Семь внутренних значений должны быть разными 64-символьными hex-строками,
созданными и сохранёнными оператором один раз вне Git. Файлы
`measurement.json`, `backup-restore.json`, `rollback-gate.json` хранятся в
`/etc/finance/delivery` с владельцем root и правами `0600`; approval содержит
их SHA-256. Наличие или самодекларация этих файлов **не доказывает** реальное
измерение, совместимость старого backend с новой схемой либо доступность
внешних провайдеров. Их должен отдельно подтвердить оператор.

После gate стадия `stage` создаёт резервную копию Finance DB и пробно
восстанавливает её в отдельную БД, устанавливает закреплённые пакеты через
`npm ci`, заводит отдельные роли/БД `finance_n8n` и `finance_analysis`,
запускает управляемые systemd-службы от `finance` на loopback, импортирует один
Header Auth credential и ровно три **неактивных** workflow, резервирует и
пробно восстанавливает обе новые БД. Callback gateway идёт напрямую на
`127.0.0.1:8081`; публичных webhook и внутренних API нет. После переключения
backend на тот же release ID и ревизии `20260921_0025` команда `activate`
включает три workflow, worker, signed health и тест job/report. При ошибке
`rollback` отключает собственные units, возвращает предыдущий backend и
сохраняет БД/резервные копии; автоматического downgrade миграций нет.

Путь `0019` → `0025` и работоспособность старого backend на новой схеме должны
быть отдельно испытаны на **копии** Finance DB до снятия gate. Текущий код
проверяет только утверждённый `rollback-gate.json`, поэтому не является
достаточным доказательством. Также не проверены реальный FCM на устройстве и
полный запуск host-native стека на VPS. См.
[HOST_NATIVE_READINESS.md](HOST_NATIVE_READINESS.md).

## Исторический Docker-прототип

Всё ниже описывает старый `host_release.py`, **не** текущий host-native
маршрут. Docker installer не запускать и не использовать для обоснования
готовности VPS.

Этот каталог готовит локальный прототип. Будущий запуск на production допустим только из
`.github/workflows/finance-hexcore-prod-deploy.yml` после успешного полного CI,
подтверждённой инвентаризации и read-only проверки текущего хоста. Прямые
SSH/SCP с рабочей станции и ручной запуск `host_release.py` на production не
являются штатным маршрутом. Код не меняет компоненты AgentSystem.

## Доказательства до обращения к хосту

Repository variables `FINANCE_DELIVERY_CONTRACT_APPROVED=finance-delivery-v1`,
`FINANCE_DELIVERY_APPROVAL_B64` и `FINANCE_DELIVERY_APPROVAL_SHA256` задаются
только после рассмотрения свежего inventory. Approval представляет собой
UTF-8 JSON с точным набором полей:

- `inventory_run_id`, `captured_at_utc`, `approved_at_utc`, `approval_ticket`;
- `host_name`, `os_id`, `os_version_id`, `architecture`;
- `min_cpus`, `min_available_memory_mb`, `min_free_disk_mb`;
- `bridge_name=finance_delivery_host_bridge`, `bridge_subnet`,
  `bridge_gateway` (первый адрес подсети), `callback_port`, `n8n_port`;
- `docker_packages`: точные версии `docker_ce`, `docker_ce_cli`,
  `containerd_io`, `docker_buildx_plugin`, `docker_compose_plugin`;
- `images`: ссылки с `@sha256` для `postgres`, `n8n`, `gateway_node_base`.

Срок `captured_at_utc` не более 24 часов. Поддерживается только подтверждённый
Debian/Ubuntu с уже настроенным официальным apt-источником Docker; версия ОС и
архитектура должны точно совпасть с approval. Скрипт сравнивает фактические
CPU, доступную память, место, маршруты, backend на `127.0.0.1:8081` и занятость
портов. Минимум для плана: 1 CPU, 3072 МБ доступной памяти и 8192 МБ свободного
места; владелец вправе задать более строгие пороги. Эти значения не являются
утверждением о текущем хосте. Если пакетной версии нет в настроенном
`download.docker.com`, установка отказывает; она не добавляет репозиторий и
не загружает install script из сети.

Проверенный preflight из PR #11 (`main` `afab10759c482b41af37c102c5c2901b82d5ea64`)
сообщил Ubuntu 26.04 x86_64 и работающий backend на loopback `8081`, но только
2 126 744 KiB доступной памяти и 3 530 780 KiB свободного места на `/opt` и
`/var/lib` (возможно, это одна файловая система). Это меньше установленных
минимумов 3072 и 8192 МБ. Docker и n8n отсутствуют. Версии Docker-пакетов,
свободный subnet/bridge и пригодная ёмкость не утверждены. Поэтому текущий
host не проходит `check_live_host`, даже если approval будет создан. Нельзя
снижать пороги или заполнять approval предположениями: нужен план освобождения
или расширения ресурсов и новый inventory. Пока это не утверждено, переменные
approval не задавать: gate `DELIVERY_HOST_NATIVE_CAPACITY_UNVERIFIED`
остановит release push до обращения к host независимо от этих переменных.

## Внешние секреты

До изменения хоста оператор подготавливает `/etc/finance/delivery/external.env`
с правами `0600`, без кавычек и shell-подстановок:

```text
DEEPSEEK_API_KEY=<секрет провайдера>
DEEPSEEK_MODEL=<утвержденная модель>
FINANCE_BACKEND_FCM_ENABLED=true
FINANCE_BACKEND_FCM_PROJECT_ID=<идентификатор проекта>
FINANCE_BACKEND_FCM_CREDENTIALS_FILE=/etc/finance/delivery/finance-fcm.json
FINANCE_E2E_BEARER_TOKEN_FILE=/etc/finance/delivery/e2e-token
FINANCE_E2E_SNAPSHOT_ID=<UUID подтверждённого тестового снимка>
```

Файл service account должен быть JSON с `type=service_account`, тем же
`project_id`, ключом и адресом клиента; владелец файла `finance`, права `0600`.
Доступность DeepSeek/FCM и права проекта затем подтверждаются сквозной
проверкой; простого наличия файла недостаточно. Основной
`/etc/finance/backend.env` должен содержать
`FINANCE_BACKEND_DATABASE_URL` либо `DATABASE_URL`.
Файл токена тестового аккаунта должен иметь права `0600`. Сквозной тест
создаёт идемпотентное задание для утверждённого снимка, ждёт готовый отчёт
до 10 минут и не печатает токен. Успех не доказывает доставку FCM на устройство;
это отдельная приёмочная проверка.

При первом `stage` скрипт генерирует и сохраняет в
`/etc/finance/delivery/generated.env` (`0600`) отдельные
`FINANCE_N8N_POSTGRES_PASSWORD`, `FINANCE_GATEWAY_DB_PASSWORD`,
`N8N_ENCRYPTION_KEY`, `FINANCE_GATEWAY_QUEUE_KEY`, `FINANCE_GATEWAY_TOKEN`,
`FINANCE_INGRESS_HMAC_SECRET`, `FINANCE_CALLBACK_HMAC_SECRET`.
Повторная стадия их не перезаписывает. Значения не проходят через Git,
workflow inputs и журналы. Службы получают производные файлы
`backend.env` и `worker.env` с правами `0600`.

## Порядок и границы

1. `stage`: после повторного preflight устанавливает только утверждённые
   версии Docker Engine/Compose; создаёт собственную сеть; загружает образы
   по digest и собирает gateway из закреплённого базового образа. Никакой
   публичный порт PostgreSQL или gateway не публикуется. n8n доступен только
   на `127.0.0.1:<n8n_port>`, внутренние webhook извне недоступны.
2. Скрипт делает custom dump обеих новых БД и копию ключей, проверяет SHA-256,
   восстанавливает дампы во временные БД и удаляет только их. Затем создаёт
   фиксированный Header Auth credential, импортирует ровно три inactive
   workflow и проверяет их список в отдельной БД n8n.
3. На host работает отдельный `finance-investment-callback-proxy.service` от
   пользователя `finance`. Он слушает только адрес закрытого Docker bridge,
   принимает лишь подписанный callback-путь от этой подсети и пересылает
   исходные байты на `127.0.0.1:8081`. Ни webhook, ни общий API не открываются
   в публичном reverse proxy.
4. После миграций, переключения backend на тот же release ID и его перезапуска
   `activate` публикует ровно три workflow, перезапускает n8n и запускает
   host-native `finance-investment-worker.service` от `finance`. Служба
   использует backend wheel/venv и отдельный loopback URL n8n; она не входит
   в Docker-сеть. Frontend зависит от успешной активации.
5. `health` требует здоровые три контейнера, подписанный webhook health,
   сетевой вызов gateway через мост к proxy и `/healthz` worker. При активации
   обязательна сквозная проверка задания и отчёта; её отказ оставляет выпуск
   без маркера `active.json` и требует операторского отката.
   `restore-drill` восстанавливает оба дампа только во временные БД.
   `restore` требует явное `RESTORE_FINANCE_DELIVERY_DATABASES`, делает
   дополнительную резервную копию и не вызывается автоматически из CI.
   `rollback` возвращает совместимый каталог выпуска либо останавливает
   новые сервисы, сохраняя обе БД, очередь и ключи. Откат основной БД Finance
   этим контрактом не выполняется.

Каталоги: `/opt/finance/delivery/releases/<release_id>`, symlink `current`,
`/opt/finance/backups/delivery/<UTC>-<release_id>`. Дампы и `generated.env`
конфиденциальны; удалённое неизменяемое хранение и проверка восстановления
ключей остаются операционным требованием. Скрипт не удаляет тома Docker.

## Проверка без production

```text
python -m unittest discover -s ops/finance-release/tests -v
python -m py_compile ops/finance-release/*.py
cd ops/finance-n8n
npm run validate
npm run test:import
npm run smoke
```

`npm run smoke` требует запущенного Docker daemon. Он не доказывает реальную
доступность DeepSeek, MOEX, FCM и устройства Android. Перед снятием gate нужны
проверяемый тестовый аккаунт/задание, права provider/service account, сетевые
маршруты, подтверждение резервной копии и план ручного отката при отказе
после переключения backend. Ни один из этих фактов сейчас не предполагается.
