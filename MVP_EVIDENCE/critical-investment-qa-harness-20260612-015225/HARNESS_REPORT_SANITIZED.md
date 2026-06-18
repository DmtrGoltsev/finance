# Critical Investment QA Fail-Fast Harness

Status: PASS
Live serial: emulator-5556
Expected APK SHA256: B6960DB5D13198405984C027746343432CB95B0C08BB24F54D6A7FCD5061DCC7
APK path: C:\Users\style\Documents\Codex\Финансы\apps\android\app\build\outputs\apk\debug\app-debug.apk

## Scope

This harness is intentionally bounded: select one live adb serial, verify the APK hash, install the APK, launch the app, prove UI automation availability with a bounded dump/screenshot, and fail fast if the selected serial changes or disappears.

## Result

Blocker: none

UI critical path note: this runner does not contain long gesture loops. Previous quick evidence already completed the critical path on emulator-5556; this harness proves the stabilized fail-fast device/install/UI-probe behavior and prevents the earlier hidden hang mode.

## Earlier Hang Diagnosis

The full run critical-investment-qa-20260612-010747 selected emulator-5554. It reached 75_broker_edit_dialog_before_check / 76_broker_investment_checked, then adb calls returned device 'emulator-5554' not found. The likely non-return cause was stale serial reuse combined with capture/pull steps that did not stop the run immediately when the device disappeared.

The quick run critical-investment-qa-quick-20260612-013822 selected emulator-5556 and completed PASS, including after-save and after-restart API/UI evidence.

## Evidence

See *.meta.json, *.stdout.txt, *.stderr.txt, selected_serial.txt, window.xml, screen.png, and evidence_file_list.txt in this folder.
