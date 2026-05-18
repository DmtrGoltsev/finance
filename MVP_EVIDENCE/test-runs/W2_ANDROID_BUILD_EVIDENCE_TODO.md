# W2 Android Build Evidence TODO

Статус: `BLOCKED`
Владелец: W2 Android Gradle/build worker
Дата создания placeholder: `2026-05-17`

## Цель

Заполнить этот файл реальными W2 результатами Android build/test после устранения Gradle blocker.

## Текущий blocker

First wave зафиксировала:

- `apps/android/gradlew.bat`: absent.
- `apps/android/gradle/wrapper/gradle-wrapper.jar`: absent.
- local `gradle`: unavailable.

Из-за этого Android assemble/unit tests не были runnable, а Android screenshots не были получены.

## Что нужно приложить после разблокировки

- Команда сборки/test.
- Полный или краткий Gradle output.
- Версия Gradle/Android plugin/JDK.
- Результаты unit tests.
- Если будут emulator/device checks: device/emulator info и ссылки на screenshots в `MVP_EVIDENCE/screenshots/android/`.

## Нельзя заполнять

- Нельзя ставить `PASS`, пока Gradle build/test реально не выполнены.
- Нельзя добавлять screenshots, если они не были получены с устройства или эмулятора.
