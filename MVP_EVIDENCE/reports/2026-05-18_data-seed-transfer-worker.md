# DATA-SEED-TRANSFER evidence

Дата: 2026-05-18  
Worker: `DATA-SEED-TRANSFER`

## Итог

Dev seed обновлен для воспроизводимого live transfer evidence. Transfer добавлен как обычная transaction-запись через существующую runtime-модель `/api/v1/transactions`, без отдельного `/api/v1/transfers` route и без реальных финансовых данных.

## Что изменено

- В `apps/backend/src/app/dev_seed.py` добавлен синтетический shared savings account `aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa`.
- В `apps/backend/src/app/dev_seed.py` добавлен deterministic transfer transaction `bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb`.
- Transfer shape:
  - `transaction_type="transfer"`
  - `account_id="44444444-4444-4444-8444-444444444444"`
  - `counterparty_account_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"`
  - `category_id=None`
  - `amount=25.00`
  - `currency="USD"`
  - `source_type="manual"`
  - `transfer_scope="household_same_household"`
  - `transfer_status="posted"`
- В `apps/backend/tests/test_dev_surface.py` dev surface smoke теперь проверяет transfer count и transfer fields.

## Проверки

Backend URL: `http://127.0.0.1:8000`  
Старый backend PID: `18528`, показывал `TRANSFER_COUNT=0`.  
Новый backend parent PID: `30888`, listener PID: `34464`, запущен через `app.dev_seed:app`.

Тесты:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dev_surface.py tests/transfers/test_transfer_runtime_safety.py
```

Результат: `7 passed, 3 warnings in 1.56s`.

Lint:

```powershell
.\.venv\Scripts\ruff.exe check src/app/dev_seed.py tests/test_dev_surface.py
```

Результат: `All checks passed!`.

Live smoke:

- `GET /api/v1/accounts`: `3`
- `GET /api/v1/categories`: `3`
- `GET /api/v1/transactions`: `3`
- `GET /api/v1/transactions?transactionType=transfer`: `1`
- transfer id: `bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb`
- transfer scope: `household_same_household`
- transfer status: `posted`
- `GET /api/v1/reports/summary?...currency=USD`: `200`
- `GET /api/v1/reports/transactions?...transactionTypes=transfer`: `200`

Подробный test-run: `MVP_EVIDENCE/test-runs/2026-05-18_data-seed-transfer-live-smoke.txt`.

## Риски и заметки следующему worker

- Aggregate release files в корне `MVP_EVIDENCE` не редактировались, потому что worker write-scope ограничен `MVP_EVIDENCE/reports/**` и `MVP_EVIDENCE/test-runs/**`.
- Следующим QA/PWA/Android worker нужно переиспользовать live backend `http://127.0.0.1:8000`, listener PID `34464`, и обновить пользовательские screenshots/evidence, где раньше был `TRANSFER_COUNT=0`.
- Android emulator может потребовать backend host `0.0.0.0` или URL `http://10.0.2.2:8000`; текущий backend слушает `127.0.0.1:8000`.
