# RocketFlow: миграция с `/` и `/api/` после выноса Finance

Этот handoff предназначен для отдельного RocketFlow-чата. Работать нужно только с RocketFlow и серверной маршрутизацией RocketFlow. Finance уже занимает свои префиксы и считается чужой зоной ответственности.

## 1. Current State

- RocketFlow сейчас публично доступен как:
  - frontend: `/`
  - backend API: `/api/`
  - backend upstream: `http://127.0.0.1:8080`
- Finance уже будет или уже есть рядом с RocketFlow как:
  - frontend: `/finance/`
  - backend API: `/finance-api/`
  - backend upstream: `http://127.0.0.1:8081`
- Текущий контракт RocketFlow временно использует корень сайта и `/api/`. Цель этой работы - освободить эти публичные пути для более чистого разделения приложений.

## 2. Target State

Итоговая публичная схема должна быть такой:

- `/` -> redirect на `/rocket/`
- `/rocket/` -> RocketFlow frontend
- `/rocket-api/` -> RocketFlow backend на `http://127.0.0.1:8080`
- `/finance/` -> Finance frontend, не трогать
- `/finance-api/` -> Finance backend на `http://127.0.0.1:8081`, не трогать

После миграции RocketFlow не должен требовать `/api/` в production-клиентах. Все production-запросы RocketFlow должны идти через `/rocket-api/`.

## 3. Strict No-Touch Rules For Finance

Нельзя менять, переименовывать, отключать, перезапускать или перепроксировать Finance:

- не менять nginx `location /finance/`;
- не менять nginx `location /finance-api/`;
- не менять upstream `127.0.0.1:8081`;
- не менять Finance systemd service, env-файлы, директории деплоя, backend/frontend artifacts;
- не править Finance runtime-код;
- не использовать Finance routes как тестовый полигон для RocketFlow;
- не добавлять общие Service Worker scope, rewrite или fallback, которые могут захватить `/finance/`.

Любое требование, которое предполагает изменение Finance, является эскалацией к владельцу Finance, а не частью этой задачи.

## 4. Required RocketFlow Web Frontend Changes

RocketFlow web должен быть собран и проверен как приложение под path-prefix `/rocket/`.

Обязательные изменения/проверки:

- Base path / public path:
  - production build должен генерировать assets с базой `/rocket/`;
  - все script/link/img/font URLs должны корректно резолвиться из `/rocket/`, а не из `/`.
- Router basename:
  - SPA router должен иметь basename `/rocket`;
  - nested routes должны открываться напрямую по URL, например `/rocket/projects/123`, без 404.
- Static assets:
  - не должно быть абсолютных ссылок вида `/assets/...`, если они ломают размещение под `/rocket/`;
  - favicon, icons, fonts, chunks, lazy-loaded bundles должны грузиться из правильного префикса.
- Service Worker:
  - scope должен быть ограничен `/rocket/`;
  - SW не должен контролировать `/finance/`, `/finance-api/`, `/rocket-api/` или корень шире, чем нужно;
  - старый SW со scope `/` должен быть удален/мигрирован, иначе он может перехватывать чужие routes.
- Web manifest:
  - `start_url` должен указывать на `/rocket/`;
  - `scope` должен быть `/rocket/`;
  - icons должны быть доступны из `/rocket/`.
- API base:
  - production API base должен быть `/rocket-api/`;
  - проверить trailing slash и конкатенацию путей, чтобы не появлялись `/rocket-apiusers` или `//users`;
  - auth refresh, session check, upload/download, WebSocket/SSE endpoints, если есть, должны использовать новый base.

## 5. Required RocketFlow Android Changes

Android production-клиент должен перейти с `/api/` на `/rocket-api/`.

Обязательные изменения/проверки:

- production API base URL должен завершаться на `/rocket-api/`;
- trailing slash должен быть стабильным в HTTP-клиенте и endpoint builders;
- login/logout/session refresh должны работать через `/rocket-api/`;
- auth token/cookie/session persistence не должны зависеть от старого `/api/`;
- upload endpoints должны отправлять файлы через `/rocket-api/`;
- download endpoints должны получать файлы через `/rocket-api/`;
- deep links или embedded web views, если они открывают web frontend, должны вести на `/rocket/`;
- проверить, что debug/staging конфиги не были случайно сломаны при production-переключении.

Минимальный Android smoke после деплоя: запуск, login, session restore после перезапуска, открыть основной список/экран данных, upload/download или ближайший production-критичный файловый сценарий.

## 6. Required RocketFlow iOS Browser/PWA Changes

iOS Safari/PWA должен считать RocketFlow приложением в scope `/rocket/`.

Обязательные изменения/проверки:

- manifest `start_url`: `/rocket/`;
- manifest `scope`: `/rocket/`;
- Service Worker registration должен происходить только под `/rocket/`;
- history fallback должен возвращать RocketFlow `index.html` только для `/rocket/...`;
- hard reload nested route в Safari должен открывать приложение, а не nginx 404;
- PWA install/open from home screen должен стартовать на `/rocket/`;
- старый SW/cache со scope `/` должен быть очищен или обновлен так, чтобы не контролировать `/finance/`.

Критический запрет: RocketFlow SW не должен обслуживать, кэшировать или перехватывать `/finance/` и `/finance-api/`.

## 7. Nginx Target Config Skeleton

Ниже skeleton, а не готовый drop-in. Перед применением сверить реальные server blocks, TLS, include-файлы, root/alias paths и текущие заголовки.

Важен порядок `location`: более специфичные префиксы должны быть выше корневого redirect/fallback.

```nginx
server {
    listen 80;
    server_name example.com;

    # Finance: DO NOT TOUCH.
    location /finance-api/ {
        proxy_pass http://127.0.0.1:8081/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Finance: DO NOT TOUCH.
    location /finance/ {
        alias /var/www/finance/current/;
        try_files $uri $uri/ /finance/index.html;
    }

    # RocketFlow API after migration.
    location /rocket-api/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Add Upgrade/Connection headers here if RocketFlow uses WebSocket.
    }

    # RocketFlow frontend after migration.
    location /rocket/ {
        alias /var/www/rocketflow/current/;
        try_files $uri $uri/ /rocket/index.html;
    }

    # Root no longer serves RocketFlow directly.
    location = / {
        return 302 /rocket/;
    }

    # Optional: avoid accidental old API usage after clients are migrated.
    # Keep temporary compatibility only if release coordination requires it.
    # location /api/ {
    #     return 410;
    # }
}
```

Предупреждение про `alias` + `try_files`:

- при `location /rocket/ { alias /var/www/rocketflow/current/; }` fallback `/rocket/index.html` должен реально попадать в RocketFlow `index.html`;
- не заменять без проверки на `root`, потому что path resolution изменится;
- не ставить общий `try_files ... /index.html` на уровне `/`, иначе можно случайно начать отдавать RocketFlow или Finance не тем routes;
- не добавлять catch-all `location /` до специфичных `/finance/`, `/finance-api/`, `/rocket/`, `/rocket-api/`.

Рекомендуемая процедура на сервере:

```bash
sudo cp /etc/nginx/sites-available/<site> /etc/nginx/sites-available/<site>.bak.$(date +%Y%m%d-%H%M%S)
sudo nginx -t
sudo systemctl reload nginx
```

Если конфигурация хранится в `sites-enabled`, `conf.d` или другом include, backup делать для фактического файла, который меняется. Reload выполнять только после успешного `nginx -t`.

## 8. Verification Checklist

Проверки после деплоя должны доказать одновременно две вещи: RocketFlow переехал, Finance не поврежден.

Server/curl:

```bash
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/rocket/
curl -I http://127.0.0.1/rocket-api/
curl -I http://127.0.0.1/finance/
curl -I http://127.0.0.1/finance-api/
```

Ожидания:

- `/` возвращает redirect на `/rocket/`;
- `/rocket/` отдает RocketFlow frontend;
- `/rocket-api/` проксирует RocketFlow backend `127.0.0.1:8080`;
- `/finance/` продолжает отдавать Finance frontend;
- `/finance-api/` продолжает проксировать Finance backend `127.0.0.1:8081`.

Browser:

- hard reload `/rocket/`;
- hard reload нескольких nested routes, например `/rocket/<known-route>`;
- проверить Network: static chunks/assets грузятся из `/rocket/`;
- проверить Network: API-запросы идут в `/rocket-api/`;
- убедиться, что нет запросов RocketFlow к `/api/`;
- открыть `/finance/` и Finance nested routes, если известны, без RocketFlow fallback.

Android smoke:

- production build/config использует `/rocket-api/`;
- login успешен;
- session restore после перезапуска успешен;
- основной production-критичный экран загружается;
- upload/download сценарии используют `/rocket-api/`.

iOS Safari/PWA smoke:

- Safari открывает `/rocket/`;
- hard reload nested route под `/rocket/` успешен;
- install/open PWA стартует на `/rocket/`;
- SW scope в devtools/remote debug ограничен `/rocket/`;
- `/finance/` не контролируется RocketFlow SW.

Finance regression:

- `/finance/` открывается;
- `/finance-api/` отвечает как до миграции;
- нет изменений в Finance service status, env, artifacts или логике routes;
- Finance browser/API smoke проходит не хуже, чем до RocketFlow миграции.

## 9. Rollback Plan

Rollback должен возвращать только RocketFlow-пути и не трогать Finance.

Шаги rollback:

1. Восстановить nginx backup для RocketFlow routes.
2. Вернуть RocketFlow frontend на `/`.
3. Вернуть RocketFlow API proxy на `/api/` -> `http://127.0.0.1:8080`.
4. Убрать redirect `/` -> `/rocket/`.
5. Оставить `/finance/` и `/finance-api/` без изменений.
6. Выполнить `sudo nginx -t`.
7. Выполнить `sudo systemctl reload nginx` только после успешного config test.
8. Проверить:
   - `curl -I http://127.0.0.1/`
   - `curl -I http://127.0.0.1/api/`
   - `curl -I http://127.0.0.1/finance/`
   - `curl -I http://127.0.0.1/finance-api/`

Если rollback нужен из-за клиентских production-сборок, также вернуть RocketFlow web/Android/iOS production API base и frontend base path к прежнему контракту только в RocketFlow-коде.

## 10. Common Failure Modes And Escalation Triggers

Common failure modes:

- RocketFlow открывается на `/rocket/`, но nested routes дают 404: не настроен router basename или nginx history fallback.
- HTML грузится, но JS/CSS 404: неверный public path/base path для assets.
- API-запросы уходят в `/api/`: production API base не обновлен в web/Android/iOS.
- API-запросы уходят в `/rocket-apiusers`: сломана trailing slash конкатенация.
- Upload/download ломаются: отдельные file endpoints не переведены на `/rocket-api/`.
- PWA открывается на `/`: manifest `start_url` или установленный старый PWA cache не обновлены.
- Finance внезапно показывает RocketFlow: общий fallback или SW захватил `/finance/`.
- `/finance-api/` проксирует не туда: поврежден location ordering или proxy_pass.
- Старый Service Worker со scope `/` продолжает перехватывать traffic после деплоя.
- Корневой redirect поставлен как catch-all и ломает `/finance/` или `/rocket-api/`.

Escalation triggers:

- любое требование изменить Finance routes, Finance backend, Finance frontend или Finance service;
- неясность, где находится реальный nginx server block или какой файл reload реально использует;
- production Android/iOS клиенты уже выпущены и требуют совместимости со старым `/api/`;
- backend RocketFlow генерирует absolute URLs с `/api/` или `/`;
- auth/session зависит от cookie path, который конфликтует с новым `/rocket-api/`;
- WebSocket/SSE endpoints требуют отдельных nginx headers или route exceptions;
- повторный провал `nginx -t`;
- после rollback Finance не возвращается к исходному поведению;
- обнаружен Service Worker со scope `/`, который нельзя безопасно удалить без отдельного release plan.

## Definition Of Done

Задача считается завершенной только если:

- RocketFlow frontend доступен под `/rocket/`;
- RocketFlow production API идет через `/rocket-api/`;
- `/` редиректит на `/rocket/`;
- Finance routes `/finance/` и `/finance-api/` не менялись и прошли smoke;
- web nested routes, Android smoke и iOS Safari/PWA smoke пройдены;
- есть сохраненный nginx backup;
- `nginx -t` успешен перед reload;
- rollback path документирован и не требует изменения Finance.
