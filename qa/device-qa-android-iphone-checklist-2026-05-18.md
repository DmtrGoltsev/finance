# Device QA checklist: Android `2_Pixel 6 Pro` and iPhone browser

Дата: 2026-05-18

Цель: не начинать full device QA как "GO", пока тестовая модель не закрывает privacy, transfer, import placeholder и device UX.

## Preconditions

- Backend seeded dev API доступен с Android emulator через `http://10.0.2.2:8000`.
- PWA доступна для iPhone browser через reachable host/port, не только `127.0.0.1`.
- Тестовый пользователь: `demo.owner@example.test`.
- Evidence folder создается до прогона; screenshots и logs имеют timestamp.

## Сценарии

| ID | Платформа | Сценарий | Обязательные проверки |
| --- | --- | --- | --- |
| DEV-001 | Android, iPhone | Login/session | Успешный вход, нет bearer/localStorage leakage в PWA, Android token не виден plaintext. |
| DEV-002 | Android, iPhone | Деньги / Личное | Видны только personal счета/операции; shared rows отсутствуют; нет hidden counts/placeholders. |
| DEV-003 | Android, iPhone | Деньги / Общее | Видны только shared счета/операции active household; чужое personal отсутствует. |
| DEV-004 | Android, iPhone | Деньги / Обзор | Personal текущего пользователя + shared; personal другого участника отсутствует. |
| DEV-005 | Android, iPhone | Quick Add expense/income | Создается manual transaction с категорией нужного направления; список и summary обновляются. |
| DEV-006 | Android, iPhone | Quick Add transfer | Создается `transactionType=transfer`; расходы месяца не увеличиваются на сумму перевода. |
| DEV-007 | Android, iPhone | Quick Add asset | Card/deposit/brokerage/metal видны в капитале; shared visibility сохраняется, если выбрана. |
| DEV-008 | Android, iPhone | Активы | Card, bank/cash, deposit, brokerage, metal отображаются как отдельные группы без обрезки текста. |
| DEV-009 | Android, iPhone | Категории | Income/expense категории различимы; shared/personal scope не смешивается. |
| DEV-010 | Android, iPhone | Аналитика | Report switcher: Личное/Общее/Обзор; transferTotal отдельно от expense. |
| DEV-011 | Android, iPhone | Import placeholder | Передаются только metadata: reportType/sourceType/targetScope/householdId/fileName/fileSizeBytes/mimeType; нет confirm/apply. |
| DEV-012 | Android, iPhone | Import privacy | Shared preview требует active household; personal preview не отправляет householdId. |
| DEV-013 | Android, iPhone | Logout/back-stack | После logout/back/home/reopen не видны финансовые данные предыдущей сессии. |
| DEV-014 | Android, iPhone | Offline/background | При потере сети нет offline mutation; stale data явно не выдается за fresh save. |

## Evidence format

- Screenshot: `platform-id-scenario-result.png`.
- API/server log excerpt: request path, status, request id, no tokens/file content.
- Test output: command, exit code, summary.
- Defect entry: scenario id, expected, actual, reproduction steps, evidence path, owner role.

## Stop-the-line defects

- Transfer учитывается как расход.
- Shared/personal visibility нарушена или hidden resource подтверждается ошибкой/счетчиком.
- Import placeholder принимает file body, parsed rows, amounts, account/category names или показывает active confirm/apply.
- PWA маскирует authz/validation error import preview локальным success-placeholder.
- Android shared Quick Add сохраняет personal без явного предупреждения.
