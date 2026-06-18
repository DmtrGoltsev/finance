# iOS Capacitor handoff

## Что подготовлено

- iOS wrapper для `apps/web-pwa` на Capacitor.
- Bundle id: `com.codex.finance`.
- App name: `Finance`.
- Web assets bundled locally из `dist`.
- Mobile build reproducible из clean checkout: `npm run build:ios` задает `VITE_BASE_PATH=/` и `VITE_API_BASE_URL=http://45.10.110.42/finance-api` внутри tracked Node script `scripts/build-ios.mjs`.
- Mobile build использует base path `/`, чтобы WebView грузил ассеты от корня приложения.
- Mobile API base: `http://45.10.110.42/finance-api`.
- iOS permission: только `NSPhotoLibraryUsageDescription` для выбора скриншота из медиатеки.
- ATS: временное исключение только для `45.10.110.42`, потому что текущий API доступен по HTTP.
- Camera, SMS, push, background modes и document picker не добавлены.
- AppIcon сгенерирован из `public/pwa-icon.svg`.

## Сборка web assets

На Mac из папки `apps/web-pwa`:

```bash
npm ci
npm run build:ios
npx cap sync ios
```

Можно одной командой:

```bash
npm run cap:sync:ios
```

`build:ios` не зависит от `.env.capacitor`: файл `.env.capacitor` игнорируется общим `.gitignore` как `.env.*` и не должен быть нужен для iOS-сборки. Если локальный `.env.capacitor` существует у разработчика, считайте его optional scratch-файлом; canonical значения для iOS находятся в `scripts/build-ios.mjs`.

Обычная production PWA сборка остается отдельной:

```bash
npm run build
```

## Открыть в Xcode

Открыть workspace:

```bash
open ios/App/App.xcworkspace
```

Если Xcode предпочтет project напрямую для SwiftPM-проекта Capacitor 8:

```bash
open ios/App/App.xcodeproj
```

Точный workspace path в репозитории: `apps/web-pwa/ios/App/App.xcworkspace`.

## Signing и запуск на iPhone

1. В Xcode выбрать target `App`.
2. В `Signing & Capabilities` выбрать Apple Development Team.
3. Проверить bundle id `com.codex.finance`; если он занят в аккаунте, заменить на доступный id и синхронизировать с provisioning.
4. Подключить iPhone кабелем или выбрать устройство из сети.
5. Выбрать устройство в Xcode scheme/device picker.
6. Нажать Run.
7. Если iPhone попросит доверять разработчику: `Settings -> General -> VPN & Device Management`, выбрать developer profile и нажать Trust.

## Smoke checklist

- Приложение открывается без белого экрана.
- В WebView ассеты грузятся локально, без запросов к `/finance/`.
- Login/session flow доходит до API `http://45.10.110.42/finance-api`.
- Dashboard открывается после входа.
- Базовые операции UI работают: счета, категории, операции, переводы.
- Загрузка скрина расходов открывает выбор из Photo Library и не просит Camera permission.
- Screenshot OCR отправляет multipart upload на `/api/v1/capture-drafts/screenshot-ocr`.
- Не появляются системные запросы на push, SMS, background modes или document picker.

## Ограничения и риски

- Xcode build и запуск на iPhone не выполнялись на Windows.
- ATS exception для HTTP API временный. Для релиза нужно перевести API на HTTPS и удалить `NSAppTransportSecurity` exception из `ios/App/App/Info.plist`.
- API работает с cookie credentials. На устройстве нужно проверить, что backend CORS/cookie policy принимает origin Capacitor WebView (`capacitor://localhost`) и credentials. Backend в этой задаче не менялся.
- Если backend требует secure cookies, HTTP endpoint может не сохранить session cookie на iOS; это решается HTTPS на API.
