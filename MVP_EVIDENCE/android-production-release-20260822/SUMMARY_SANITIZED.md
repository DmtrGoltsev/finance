# Android Production Release - Sanitized Evidence

Date: `2026-08-22`

## Source

- Branch: `prod/finance-personal-android-backend-20260822`
- Session/account isolation: `af22cce6417012e2adedb2fe0689c0670e322cf1`
- Android functional fixes: `12a1b91f20c2ce3f48bcae6919b76eb976b12c3f`
- Final analytics selector/source: `43f4b1780e3bdcf6891b877fe03ee53971f74500`

## Android Artifact

- File: `C:\Users\style\Documents\Codex\Финансы\artifacts\apk\finance-android-prod-20260822-035412-personal-FINAL-manual-install.apk`
- SHA-256: `b7244a339eb71bcb91dc8a02066e93bc219707691a350488315255a57f5cb1c4`
- Size: `8119142` bytes
- Package/version: `com.finance.mvp`, `0.1.0`, code `1`
- Certificate SHA-256: `b5675864b9cb8a046d889f54e58f5b0256d6937ecd448e69d7faa955e587aca0`
- Production API: `http://45.10.110.42/finance-api`

Binary gates passed: non-debuggable manifest/package, production URL present,
local development URLs absent, ZIP/EOCD/central-directory integrity, zero
trailing bytes, zero abnormal entry gaps, zipalign, v2/v3 signatures and prior
manual-install certificate continuity.

## Verification

- Android unit tests: `167/167` PASS.
- Android lint: `0` errors.
- Install/upgrade on `emulator-5554`: PASS.
- Production login: PASS.
- Targeted E2E: persisted session, selected-month investment transfer,
  newest-first operations including transfer, payment-account refresh, vertical
  searchable category dialog and manual dated expense: PASS.
- Raw screenshots/UI XML remain local under `C:\Temp\finance-absolute-final-*`
  and `C:\Temp\finance-final-e2e-*`; they are intentionally excluded here.

## Backend Production Deployment

- GitHub Actions: https://github.com/DmtrGoltsev/finance/actions/runs/32540824773
- Source: `12a1b91f20c2ce3f48bcae6919b76eb976b12c3f`
- Release: `/opt/finance/releases/finance-personal-backend-20260822-12a1b91f`
- Backend deploy PASS; frontend deploy skipped.
- Health, OpenAPI, production QA login and refresh rotation PASS.
- Migrations disabled; backup skipped; DB unchanged.
- Last confirmed revision: `20260618_0017`.
- Rollback candidate: `/opt/finance/releases/20260726T220603Z-55f4ac53`.

## Residual Risk

- Full UI offline create/reconnect/sync was not rerun on the final APK.
- OCR was not tested with a real image and remains online-only.
- Android 17 Espresso is incompatible with the framework image before test
  assertions, although instrumentation compilation passes.
- Production API still uses plain HTTP; TLS remains unresolved.

No credentials, tokens, raw financial data, raw screenshots or authenticated UI
dumps are stored in this evidence file.
