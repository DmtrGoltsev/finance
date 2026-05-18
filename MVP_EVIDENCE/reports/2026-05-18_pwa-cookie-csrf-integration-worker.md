# PWA cookie/CSRF integration worker

Дата: 2026-05-18  
Worker: `MVP-PWA-COOKIE-CSRF-INTEGRATION`

## Итог

PWA переведена с bearer token в `localStorage` на cookie/CSRF transport:

- `POST /api/v1/sessions` отправляет `{ email, password, transport: "pwa_cookie" }`;
- все PWA API calls идут с `credentials: "include"`;
- bearer/access token не читается и не сохраняется в `localStorage`;
- CSRF token берется из `csrfToken` login response или cookie `finance_csrf`;
- unsafe `POST/PUT/PATCH/DELETE` добавляют `X-CSRF-Token`, кроме самого login request;
- dev CORS для `http://127.0.0.1:5174` и `http://127.0.0.1:5173` разрешает credentials и `X-CSRF-Token` без wildcard origin.

## Измененные файлы

- `apps/web-pwa/src/api/client.ts`
- `apps/web-pwa/src/api/client.test.ts`
- `apps/web-pwa/dist/index.html`
- `apps/web-pwa/dist/assets/index-BJ0_b3E1.js`
- `apps/backend/src/app/main.py`
- `apps/backend/tests/test_dev_surface.py`
- `MVP_EVIDENCE/test-runs/2026-05-18_pwa-cookie-csrf-*.txt`
- `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-cookie-csrf-desktop.png`
- `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-cookie-csrf-ios.png`

## Проверки

- `npm.cmd test` в `apps/web-pwa`: `2 passed`, `5 tests passed`.
- `npm.cmd run build` в `apps/web-pwa`: `tsc -b && vite build` успешно.
- `.\.venv\Scripts\python.exe -m pytest tests/test_dev_surface.py tests/auth/test_session_flow.py` в `apps/backend`: `14 passed`, `1 warning`.
- Source/dist scan: в production PWA source/dist нет `localStorage`, `finance-mvp-pwa-token`, `accessToken`, `Bearer`, `Authorization`.

## Live smoke

Seeded backend был перезапущен с актуальным CORS-кодом:

- URL: `http://127.0.0.1:8000`
- PID после рестарта: `18528`
- stderr log: `MVP_EVIDENCE/test-runs/2026-05-18_pwa-cookie-csrf-uvicorn.err.log`
- stdout log: `MVP_EVIDENCE/test-runs/2026-05-18_pwa-cookie-csrf-uvicorn.out.log`

Live smoke:

- preflight `Origin: http://127.0.0.1:5174`, `Access-Control-Request-Headers: content-type,x-csrf-token`: `200`, credentials `true`;
- preflight `Origin: http://127.0.0.1:5173`, `Access-Control-Request-Headers: content-type,x-csrf-token`: `200`, credentials `true`;
- `POST /api/v1/sessions` with `transport=pwa_cookie`: `201`, `csrfToken` present, `accessToken` absent;
- `GET /api/v1/sessions/current` with cookie session: `200`;
- `DELETE /api/v1/sessions/current` with `X-CSRF-Token`: `204`.

Evidence:

- `MVP_EVIDENCE/test-runs/2026-05-18_pwa-cookie-csrf-live-smoke.txt`
- `MVP_EVIDENCE/test-runs/2026-05-18_pwa-cookie-csrf-desktop-dom.txt`
- `MVP_EVIDENCE/test-runs/2026-05-18_pwa-cookie-csrf-ios-dom.txt`

## Screenshots

- Desktop: `MVP_EVIDENCE/screenshots/pwa-desktop/2026-05-18_pwa-cookie-csrf-desktop.png`
- iOS-like: `MVP_EVIDENCE/screenshots/ios-pwa/2026-05-18_pwa-cookie-csrf-ios.png`

Chrome headless DOM smoke подтвердил наличие live seed data (`Dev Personal Cash`) на desktop и iOS-like viewport.

## Статус блокера

PWA localStorage bearer blocker закрыт.

## Оставшиеся ограничения

- В PWA пока нет пользовательского logout action; CSRF на unsafe flow доказан unit-тестом клиента и live `DELETE /api/v1/sessions/current`.
- `git status` недоступен в рабочей папке: `fatal: not a git repository`.
