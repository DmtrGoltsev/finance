# W2 DB Runtime Evidence TODO

Статус: `TODO`
Владелец: W2 backend DB/runtime worker
Дата создания placeholder: `2026-05-17`

## Цель

Заполнить этот файл реальными W2 результатами, которые доказывают, что backend runtime использует request-scoped DB-backed repositories/sessions, а не in-memory repositories.

## Что нужно приложить

- Команда запуска тестов.
- Полный или краткий test output.
- Подтверждение, что accounts/categories runtime routes используют DB-backed wiring.
- Privacy checks для owner/member/other/invited/former в runtime path.
- Информация о skipped tests, warnings и известных gaps.

## Текущий blocker

First wave зафиксировала P0 blocker: backend runtime остается in-memory для accounts/categories. Пока этот файл не заполнен реальными результатами, release gate остается `BLOCKED`.

## Нельзя заполнять

- Нельзя ставить `PASS` без фактического W2 test output.
- Нельзя переносить сюда contract/OpenAPI pass как доказательство runtime DB wiring.
