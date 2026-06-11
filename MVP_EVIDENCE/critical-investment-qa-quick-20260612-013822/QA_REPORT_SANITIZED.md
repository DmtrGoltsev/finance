# Critical Investment QA Quick Run

Status: PASS
Run root: MVP_EVIDENCE/critical-investment-qa-quick-20260612-013822
Live serial: emulator-5556
AVD/model: OpenCode / sdk_gphone16k_x86_64
APK install: Performing Streamed Install
Success
APK SHA256: B6960DB5D13198405984C027746343432CB95B0C08BB24F54D6A7FCD5061DCC7 (matched expected)
Secrets: raw auth/token not stored in new evidence; PASS: no raw QA email/password/accessToken/Bearer/Authorization hits in text evidence

## Steps Completed

1. adb devices -l selected only emulator-5556.
2. Installed debug APK on emulator-5556.
3. Logged in to synthetic QA seed without writing raw auth to evidence.
4. Captured API before save.
5. Opened Assets -> Broker -> checked Investment -> Save.
6. Captured UI around dialog/save and after result.
7. Captured API immediately after save.
8. Force-stopped/relaunched app, dismissed notification permission dialog, captured Assets/Analytics after restart.
9. Captured API after restart/analytics.

## Key Values

Before: brokerage account 2c308a5c-7914-4eea-8e4d-21830d4f15ad, assetCategoryId=null, investmentCategories=[], investmentsTotal=0.0000 RUB.
After save: assetCategoryId=8a0b7218-6077-4e0a-a637-6ff5ab893b21, linkedAssetCategory.id=8a0b7218-6077-4e0a-a637-6ff5ab893b21, linkedAssetCategory.isInvestment=True, investmentCategories.count=1, investmentsByCurrency[0].investmentsTotal=150000.0000 RUB, summary investmentsTotal=150000.0000 RUB.
After restart: assetCategoryId=8a0b7218-6077-4e0a-a637-6ff5ab893b21, linkedAssetCategory.id=8a0b7218-6077-4e0a-a637-6ff5ab893b21, investmentCategories.count=1, summary investmentsTotal=150000.0000 RUB.
UI analytics after restart: Инвестиции 150 000,00 RUB, RUB 150 000,00 RUB in 18_analytics_after_restart_retry.xml/png.

## Evidence Highlights

- 00_adb_devices_initial.txt, 20_adb_devices_final.txt
- 01_apk_checksum.txt, 02_apk_install.txt
- 06_before_api_verification_summary.json
- 10_broker_group_dialog_before.xml/png, 11_broker_investment_checked.xml/png, 12_assets_after_save.xml/png
- 13_after_api_verification_summary.json
- 17_assets_after_restart_retry.xml/png, 18_analytics_after_restart_retry.xml/png
- 19_restart_api_verification_summary.json
- 22_secret_scan_summary.json
