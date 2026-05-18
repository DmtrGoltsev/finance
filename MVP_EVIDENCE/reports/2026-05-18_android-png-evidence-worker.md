# Android PNG evidence worker

Дата: 2026-05-18

## Результат

Перегенерированы Android live API screenshots через `adb -s emulator-5554 exec-out screencap -p` с бинарно-безопасным чтением stdout в файл.

Файлы:
- `MVP_EVIDENCE/screenshots/android/2026-05-18_android-live-api-smoke.png`
- `MVP_EVIDENCE/screenshots/android/2026-05-18_android-live-api-after-login.png`
- `MVP_EVIDENCE/screenshots/android/2026-05-18_android-live-api-final.png`

## Проверка

Лог проверки: `MVP_EVIDENCE/test-runs/2026-05-18_android-png-validation.txt`

Подтверждено:
- эмулятор `emulator-5554` доступен через `adb devices -l`;
- foreground activity: `com.finance.mvp/.MainActivity`;
- у всех трех PNG magic bytes: `89 50 4E 47 0D 0A 1A 0A`;
- все три файла успешно декодируются через `System.Drawing.Image`;
- размер изображений: `1440x3120`.

## Android resources

В `apps/android/app/src/main/res` не найдено `*.png` файлов, поэтому resource PNG correction не требовался.

`assembleDebug` не запускался, потому что Android resource PNG не исправлялись.

## Блокеры

Блокеров нет.
