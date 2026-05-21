# Production Smoke Evidence

Date: 2026-05-22 MSK
Verdict: PASS.

## Public Targets

- PWA `http://<production-host>/finance/`: HTTP 200, evidence `android-emulator/data/pwa-health-sanitized.json`.
- API `http://<production-host>/finance-api/health`: HTTP 200, evidence `android-emulator/data/api-health-sanitized.json`.

## Android Smoke

- APK built from `d9ffc75454c57007b465f51b7782c12c52935823` with production API base URL.
- APK installed successfully on `emulator-5554`.
- Unit tests and connected Android instrumentation tests passed before manual production retest.
- Login, dashboard, assets, categories, expense, income, transfer, analytics, validation, session restore, logout, and relaunch-after-logout were exercised against production.
- Session persistence after `am force-stop` passed: relaunch showed authenticated dashboard without manual relogin.

## Runtime / Safety

Server production runtime remains `808f7278` per release context. No server deploy, DB write outside the app UI, cleanup, commit, push, tag, or evidence staging was performed. Credential values are not printed in this evidence file.
