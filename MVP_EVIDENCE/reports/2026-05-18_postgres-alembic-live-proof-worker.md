# PostgreSQL Alembic live proof

Дата: 2026-05-18  
Worker: `MVP-POSTGRES-ALEMBIC-LIVE-PROOF`  
Статус: `PASS` для real PostgreSQL proof

## Итог

`alembic upgrade head` успешно выполнен против реального PostgreSQL 18.3. Docker/Podman в среде не найдены, локальный сервис PostgreSQL на `127.0.0.1:5432` требует пароль и не использовался для создания временной БД/роли. Вместо этого был поднят отдельный одноразовый PostgreSQL-кластер из локально установленных `postgres.exe/initdb.exe` в `%TEMP%`, на loopback-порту `51023`, с generated local-only паролями.

Production DB не трогалась. Реальные секреты не использовались. Сгенерированные пароли не записывались в репозиторий, не выводились в команды/results и были удалены вместе с temp-каталогом.

## Детекция среды

- `docker`: not found.
- `docker-compose`: not found.
- `docker compose`: `The term 'docker' is not recognized...`
- `podman`: not found.
- `podman compose`: `The term 'podman' is not recognized...`
- `psql`: `C:\Program Files\PostgreSQL\18\bin\psql.exe`, PostgreSQL `18.3`.
- `pg_isready`: PostgreSQL `18.3`.
- `postgres.exe`, `initdb.exe`, `pg_ctl.exe`: найдены в `C:\Program Files\PostgreSQL\18\bin`.
- Service `postgresql-x64-18`: `Running`, `Automatic`.

Локальный service на `5432` проверялся только passwordless-safe способом:

```powershell
$env:PGPASSFILE = "<temp-nonexistent-pgpass>"
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
psql -w -h 127.0.0.1 -p 5432 -U postgres -d postgres -Atc "select ..."
```

Результат: `fe_sendauth: no password supplied`, exit `2`. Аналогичные passwordless-попытки для `style/postgres`, `finance_local/finance_dev`, `finance_local/postgres`, `style/style` завершились exit `2`. Поэтому локальный service не использовался для temp DB/user.

## Выполненный proof

Disposable PostgreSQL:

- temp base: `C:\Users\style\AppData\Local\Temp\codex-pg-live-proof-527ae1f158`
- temp DB: `codex_db_527ae1f158`
- temp app role: `codex_app_527ae1f158`
- port: `51023`
- startup: `initdb` + hidden `postgres.exe -D <temp-data-dir> -p 51023 -h 127.0.0.1`

Alembic:

```powershell
$env:FINANCE_BACKEND_DATABASE_URL = "postgresql+asyncpg://<temp-app-user>:<generated-password-redacted>@127.0.0.1:51023/<temp-db>"
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Результат:

```text
Running upgrade  -> 20260517_0001
Running upgrade 20260517_0001 -> 20260518_0002
Running upgrade 20260518_0002 -> 20260518_0003
Running upgrade 20260518_0003 -> 20260518_0004
Running upgrade 20260518_0004 -> 20260518_0005
ALEMBIC_EXIT=0
```

Backend smoke против этой БД:

```powershell
$env:FINANCE_BACKEND_DATABASE_URL = "postgresql+asyncpg://<temp-app-user>:<generated-password-redacted>@127.0.0.1:51023/<temp-db>"
.\.venv\Scripts\python.exe - <backend async DB + FastAPI health smoke>
```

Результат:

```json
{"alembic_version":"20260518_0005","health_body":{"status":"ok"},"health_status":200,"postgres_server_version":"18.3","public_table_count":8}
```

Дополнительная проверка app role:

```powershell
psql -w -h 127.0.0.1 -p <temp-port> -U <temp-app-user> -d <temp-db> -Atc "select version_num from alembic_version;"
```

Результат: `20260518_0005`, exit `0`.

## Cleanup

```text
pg_ctl -D <temp-data-dir> -m fast -w stop
PG_CTL_STOP_EXIT=0
TEMP_POSTGRES_RUNNING=0
CLEANUP_REMOVED=C:\Users\style\AppData\Local\Temp\codex-pg-live-proof-527ae1f158
TEMP_CLUSTER_DIRS_REMAINING=0
TEMP_POSTGRES_PROCESSES_REMAINING=0
```

Отдельная финальная проверка показала, что `PGPASSWORD` и `FINANCE_BACKEND_DATABASE_URL` не присутствуют в текущем окружении shell-проверки.

## Ограничения и заметки

- Docker/Podman path остается недоступным в этой среде.
- Локальный service PostgreSQL на `5432` password-protected; без секретов его нельзя использовать для safe temp DB/user.
- В `apps/backend/.venv` есть `alembic`, `asyncpg`, `fastapi`, `sqlalchemy`, `httpx`, `uvicorn`, `pytest`; `psycopg/psycopg2` отсутствуют. Поэтому smoke был выполнен как backend async DB connection + FastAPI `/health`, а не как DB-backed sync route smoke.
