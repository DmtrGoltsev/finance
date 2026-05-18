# Placeholder импорта отчета: контракт и тексты

Дата: 2026-05-18

Статус: продуктовый контракт для preview stub. Реальный импорт, парсинг файлов, сохранение содержимого файла и изменение финансовых данных не входят в этот этап.

## 1. Цель и границы

Placeholder нужен, чтобы UI мог показать будущую точку входа импорта отчета и короткую безопасную сводку без обещания готового импорта.

Инварианты:

- backend не принимает и не сохраняет содержимое файла;
- backend не парсит файл и не извлекает операции, счета, категории или активы;
- preview не создает и не изменяет счета, операции, категории, переводы, брокерские записи, вклады или металлы;
- `personal` данные остаются приватными и видны только владельцу;
- shared-сценарий требует активного доступа к `householdId`;
- UI не должен говорить "импорт выполнен", "данные распознаны" или "операции добавлены";
- любое будущее подтверждение импорта должно быть отдельным endpoint и отдельным privacy/security review.

## 2. Минимальный backend contract

### Endpoint

`POST /api/v1/imports/report-preview`

Назначение: вернуть безопасный placeholder preview по метаданным выбранного отчета. Endpoint не является импортом.

Content-Type: `application/json`. Multipart/form-data и бинарное тело файла для этого stub запрещены.

### Request DTO: `ImportReportPreviewRequest`

```json
{
  "reportType": "generic_finance_report",
  "sourceType": "file_metadata_only",
  "targetScope": "personal",
  "householdId": null,
  "fileName": "report.pdf",
  "fileSizeBytes": 245760,
  "mimeType": "application/pdf"
}
```

Поля:

| Поле | Required | Значения / формат | Правило |
| --- | --- | --- | --- |
| `reportType` | yes | см. allowlist ниже | Тип отчета, выбранный UI или определенный по user intent, не по парсингу файла. |
| `sourceType` | yes | `file_metadata_only` | Только метаданные файла. Не использовать transaction `sourceType = file_import` для этого stub. |
| `targetScope` | yes | `personal`, `shared` | Куда пользователь хотел бы импортировать данные в будущем. Сейчас данные не меняются. |
| `householdId` | условно | resource id или `null` | Required только при `targetScope = shared`; backend проверяет active membership. |
| `fileName` | no | string, max 255 | Только отображаемое имя файла. Не использовать для доверенного определения типа. |
| `fileSizeBytes` | no | integer >= 0 | Только для UI-сводки. |
| `mimeType` | no | string | Только заявленный тип, без обработки содержимого. |

Не передавать: `fileContent`, `base64`, `text`, `rows`, `parsedData`, `accountIds`, `transactionIds`, суммы, описания операций, реквизиты, брокерские идентификаторы, банковские credentials.

### Allowed values

`reportType`:

| Value | UI-смысл |
| --- | --- |
| `generic_finance_report` | Общий финансовый отчет или выписка. |
| `bank_statement` | Банковская выписка или отчет по счету. |
| `brokerage_report` | Брокерский отчет. |
| `deposit_report` | Отчет по вкладу. |
| `metals_report` | Отчет по металлам. |

`sourceType` для этого endpoint:

| Value | Статус | Правило |
| --- | --- | --- |
| `file_metadata_only` | allowed now | Разрешены только имя, размер и mime type. |
| `file_import` | reserved | Не принимать в stub; это будущий реальный импорт. |
| `bank_api` | reserved | Не принимать в stub; требует отдельного review. |
| `sms` | reserved | Не принимать в stub; требует отдельного review. |
| `push` | reserved | Не принимать в stub; требует отдельного review. |

### Response DTO: `ImportReportPreviewResponse`

```json
{
  "status": "preview_placeholder",
  "canConfirm": false,
  "willChangeData": false,
  "message": "Файл не импортирован. Сейчас показана только предварительная сводка.",
  "scope": {
    "targetScope": "personal",
    "householdId": null
  },
  "file": {
    "fileName": "report.pdf",
    "fileSizeBytes": 245760,
    "mimeType": "application/pdf"
  },
  "summary": {
    "title": "Предварительный просмотр импорта",
    "statusText": "Импорт пока не выполняется",
    "sections": [
      {
        "key": "accounts_assets",
        "title": "Счета и активы",
        "status": "not_recognized_yet",
        "text": "Будущий импорт сможет показать найденные счета и активы."
      },
      {
        "key": "transactions",
        "title": "Операции",
        "status": "not_recognized_yet",
        "text": "Операции не распознаны и не добавлены."
      },
      {
        "key": "categories",
        "title": "Категории",
        "status": "not_recognized_yet",
        "text": "Категории не распознаны и не созданы."
      },
      {
        "key": "transfers",
        "title": "Переводы",
        "status": "not_recognized_yet",
        "text": "Переводы не распознаны и не созданы."
      },
      {
        "key": "brokerage_deposits_metals",
        "title": "Брокеры, вклады и металлы",
        "status": "not_recognized_yet",
        "text": "Специальные активы пока не обрабатываются."
      }
    ]
  },
  "warnings": [
    {
      "code": "NO_DATA_CHANGES_WITHOUT_CONFIRMATION",
      "text": "Данные не изменятся без подтверждения."
    },
    {
      "code": "PLACEHOLDER_ONLY",
      "text": "Сейчас файл не сохраняется и не разбирается."
    }
  ]
}
```

Поля ответа:

| Поле | Правило |
| --- | --- |
| `status` | Всегда `preview_placeholder` в текущем stub. |
| `canConfirm` | Всегда `false`; кнопка подтверждения реального импорта не должна быть активной. |
| `willChangeData` | Всегда `false`; preview не меняет данные. |
| `message` | Короткий статус для UI. |
| `scope` | Повторяет безопасный target scope; не раскрывает чужие personal данные. |
| `file` | Только метаданные из request после безопасной нормализации. |
| `summary.sections` | Фиксированный список ожидаемых секций распознавания. |
| `warnings` | Минимум два предупреждения: нет изменений без подтверждения, файл не сохраняется/не разбирается. |

Ошибки:

- `UNAUTHENTICATED` для отсутствующей/истекшей session.
- `VALIDATION_FAILED` для неверной формы request.
- `INVALID_ENUM_VALUE` для неподдержанных `reportType`, `sourceType`, `targetScope`.
- `RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE` или neutral `MEMBERSHIP_NOT_ACTIVE` для недоступного `householdId`.

Логи и telemetry могут содержать только coarse event: endpoint, `reportType`, `sourceType`, `targetScope`, result, request id. Не логировать `fileName`, содержимое файла, суммы, описания, account/category names, emails, tokens.

## 3. Русские UI-тексты

### Заголовки

| Ключ | Текст |
| --- | --- |
| `import.entry.title` | Импорт отчета |
| `import.preview.title` | Предварительный просмотр импорта |
| `import.summary.title` | Что сможет распознать импорт |
| `import.warnings.title` | Перед импортом |

### Status

| Ключ | Текст |
| --- | --- |
| `import.status.placeholder` | Импорт пока не выполняется |
| `import.status.fileSelected` | Файл выбран |
| `import.status.previewOnly` | Показана только предварительная сводка |
| `import.status.notParsed` | Файл не разобран |
| `import.status.noChanges` | Данные не изменены |

### Summary

| Ключ | Текст |
| --- | --- |
| `import.summary.short` | Сейчас мы показываем, какие разделы сможет проверить будущий импорт. Файл не сохраняется и не разбирается. |
| `import.summary.personal` | Личный импорт будет виден только вам. |
| `import.summary.shared` | Общий импорт будет доступен только активным участникам семьи после отдельного подтверждения. |
| `import.summary.empty` | Распознанных данных пока нет. |

### Warning и guardrails

| Ключ | Текст |
| --- | --- |
| `import.warning.noChangesWithoutConfirm` | Данные не изменятся без подтверждения. |
| `import.warning.placeholderOnly` | Сейчас это предварительный экран: файл не импортируется. |
| `import.warning.noFileStorage` | Содержимое файла не сохраняется и не разбирается. |
| `import.warning.personalPrivate` | Личные данные видны только владельцу. |
| `import.warning.futureParsing` | Распознавание отчета появится позже. |

### Действия

| Ключ | Текст |
| --- | --- |
| `import.action.chooseFile` | Выбрать файл |
| `import.action.preview` | Показать сводку |
| `import.action.cancel` | Отмена |
| `import.action.confirmDisabled` | Подтверждение пока недоступно |

Запрещенные формулировки для текущего stub:

- "Импортировать";
- "Импорт выполнен";
- "Мы распознали операции";
- "Операции будут добавлены";
- "Счета будут созданы";
- "Категории будут назначены автоматически";
- "Подключить банк/брокера";
- "Загрузить и обработать файл".

## 4. Expected recognition sections

Фиксированный порядок секций:

1. Счета и активы (`accounts_assets`).
2. Операции (`transactions`).
3. Категории (`categories`).
4. Переводы (`transfers`).
5. Брокеры, вклады и металлы (`brokerage_deposits_metals`).

Для текущего stub все секции имеют `status = not_recognized_yet`. Не возвращать counts, суммы, балансы, названия счетов, названия категорий или описания операций, потому что файл не парсится.

Будущий реальный импорт должен пройти отдельное проектирование контракта, включая:

- upload и storage policy;
- parser trust boundaries;
- preview diff;
- подтверждение изменений;
- audit;
- deletion/retention;
- privacy review для personal/shared;
- QA evidence на отсутствие скрытых counts и утечек personal данных.

## 5. Definition of done для текущего placeholder

- Есть единый endpoint contract для preview stub.
- Request принимает только метаданные, не содержимое файла.
- Response явно сообщает `canConfirm = false` и `willChangeData = false`.
- UI-тексты короткие, на русском и не обещают готовый импорт.
- Expected recognition sections зафиксированы.
- Personal/private guardrail явно указан.
- Реальный импорт, парсинг, сохранение файла и изменение данных вынесены за рамки текущего этапа.
