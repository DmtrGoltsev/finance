# Finance personal/native iOS final regression

Run date: 2026-08-21 (Europe/Moscow)
Branch: `codex/ios-native-personal-parity-20260820`
Commit: `96aa58226ad8f80834ea333192ebace7885d69c2`
Worktree at start: clean and synchronized with `origin`
Result: **PASS with an external HTTPS release blocker**

This report is sanitized. It contains no passwords, tokens, cookies, CSRF values,
signing identities, private keys, production financial payloads, raw OCR text or
raw screenshots.

## Regression results

| Area | Command/evidence | Result |
| --- | --- | --- |
| Backend | `pytest -q` | PASS: 296 passed, 6 skipped, 13 deprecation warnings |
| Backend lint | `ruff check .` | PASS: all checks passed |
| Android unit | `:app:testDebugUnitTest` | PASS: 143 tests, 0 failures/errors/skipped |
| Android debug | `:app:assembleDebug` | PASS; debug-signed APK generated |
| Android release | `:app:assembleRelease` | PASS; `app-release-unsigned.apk` generated and independently confirmed unsigned |
| PWA dependencies | `npm ci` | PASS; clean lockfile install |
| PWA tests | `npm test` | PASS: 4 files, 69 tests |
| PWA build | `npm run build` | PASS: TypeScript and Vite production build |
| PWA runtime audit | `npm audit --omit=dev` | PASS: 0 runtime vulnerabilities |
| PWA service worker | targeted Vitest | PASS: 5 tests; plain HTTP IP registration is skipped and API/OCR requests are not cached |
| Legacy Capacitor HTTP guard | negative build probe | PASS: cleartext API URL rejected |
| iOS GitHub Actions | run `32523201106` | PASS: completed/success on this exact branch and commit |
| Native iOS Debug/Release | downloaded CI evidence | PASS: both logs contain `BUILD SUCCEEDED` |
| Native iOS XCTest | downloaded CI evidence | PASS: 47/47 |
| Native iOS UI test | downloaded CI evidence | PASS: 1/1 |

GitHub Actions run:
`https://github.com/DmtrGoltsev/finance/actions/runs/32523201106`

Artifact: `ios-build-test-evidence-32523201106`, artifact id `9461389241`,
size 464997 bytes, digest
`sha256:df99fa5b33d6292f84adf010f5e6ad5fa170cca5d4431100a80734cb129fff6b`.
The downloaded artifact was inspected from a temporary directory; the bulky
`.xcresult` bundle was not copied into repository evidence.

## Personal-only contract scan

- Runtime source contains no exact user-facing labels `Общее`, `Мой обзор` or
  `Личное` as a selectable finance mode.
- Android is pinned to `FinanceMode.Personal`; writable mode enumeration returns
  only personal mode.
- Android, PWA and native iOS request personal account/category/asset scopes and
  use `reportMode=personal` for reachable report flows.
- Category management is titled `Категории расходов`; active and archived lists
  are filtered to expense categories; create requests are expense/personal.
- Legacy shared/household enum, DTO and decode branches remain internally for
  backend/wire compatibility. They are not exposed as product mode selectors.

## APK metadata

| APK | Size | SHA-256 | Signature state |
| --- | ---: | --- | --- |
| `apps/android/app/build/outputs/apk/debug/app-debug.apk` | 11772404 | `451BF296FC76A1626ED76C432D810302B9DF20B2BFE739CA7609B17F0E3D720F` | Android debug V2 signature |
| `apps/android/app/build/outputs/apk/release/app-release-unsigned.apk` | 8076546 | `9A4798066A6E2B8591879173AB068040FB3A7F755BA687638DEFF159215AD879` | Unsigned, expected for this gate |

The APK binaries are build outputs and are not stored in this evidence folder.

## Release blocker and limitations

- Native iOS source and CI are ready, but **actual production login on a physical
  iPhone is blocked until a trusted HTTPS Finance API endpoint is selected**.
- Do not add an arbitrary ATS cleartext exception. Supported paths are a normal
  owned domain with a trusted certificate, or a trusted short-lived Let's Encrypt
  IP-address certificate when its operational renewal constraints are accepted.
- The current plain HTTP production IP is not a valid native iOS Release endpoint.
- Physical iPhone signing, install, login, Keychain/session restore, offline/online
  convergence and online-only OCR still require the Mac/device run.
- `apps/web-pwa/ios` legacy Capacitor output is not the native application target.
  The target is `apps/ios`.
- No production deploy and no production account login were performed in this run.

## Local text evidence

The same evidence directory contains local generated text logs for backend,
Android, PWA, iOS run metadata and the personal-only scan. They are intentionally
ignored by git; only this curated sanitized summary is trackable.
