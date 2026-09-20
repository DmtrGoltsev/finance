# Эксплуатация Finance n8n

## Порядок запуска

1. PostgreSQL Finance n8n.
2. n8n Finance.
3. Импорт и назначение credential.
4. Подписанная прикладная проверка готовности.
5. Worker outbox Finance.

Один Docker health недостаточен. После каждого перезапуска выполнить `scripts/health.ps1`; ожидаемый результат — HTTP `200` и `status=ok` от подписанного внутреннего процесса.

## Ежедневная проверка

- контейнеры healthy, без циклических рестартов и превышения лимитов;
- PostgreSQL отвечает `pg_isready`;
- подписанный health возвращает `PASS`;
- публичные `/webhook/internal/finance/*` и `/webhook-test/internal/finance/*` возвращают `404`;
- счётчики `queued/collecting/analyzing/failed` проверяются без payload;
- старые `ready` удалены после 7 дней, `failed` после 30 дней;
- свободное место томов и backup destination достаточно;
- новости по-прежнему выключены;
- внешний audit не показывает включённых опасных узлов или новых credentials.

Нельзя выводить `.env`, HMAC headers, portfolio payload, DeepSeek response, номера счетов и screenshots.

## Backup

`scripts/backup.ps1` создаёт PostgreSQL custom dump, workflow, policy и SHA-256. `.env`, credential values и encryption key не копируются. Backup необходимо перенести в отдельное неизменяемое хранилище. Runtime-роль не должна иметь право его удалить.

## Restore drill

`scripts/restore-drill.ps1` проверяет hashes и восстанавливает dump только в новую временную БД. Он не переключает production. После восстановления проверяется наличие технической таблицы; затем временная БД удаляется.

## Rollback

1. Остановить только Finance n8n; Finance backend и его outbox сохранить.
2. Зафиксировать pending/leased счётчики без payload.
3. Запустить предыдущий точный image tag.
4. Импортировать предыдущий workflow без автоматической активации.
5. Выполнить Docker health, подписанный health и безопасный повтор одного event ID.
6. Активировать процесс только после подтверждения отсутствия дублей.

Скрипт `rollback.ps1` не активирует workflow сам. PostgreSQL и очередь не удаляются.

## Сбой источника или DeepSeek

После трёх попыток n8n отправляет Finance безопасный код ошибки. При `attempt < 3` backend создаёт новый outbox attempt. При недоступности критичного источника готовая рекомендация не формируется. Нельзя заменять официальный источник поисковым сниппетом, Telegram, блогом или данными модели.

## Сбой callback

Не писать результат напрямую в БД Finance. Сохранить технический event, восстановить внутреннюю сеть и повторить тот же подписанный callback. Один nonce повторно не используется. Если Finance уже принял terminal status, ручной повтор должен быть остановлен и расследован как идемпотентный replay.
