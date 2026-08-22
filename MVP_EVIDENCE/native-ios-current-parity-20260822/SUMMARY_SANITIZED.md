# Native iOS current parity: integrated QA evidence

Run date: 2026-08-22 (Europe/Moscow)

Branch: `codex/ios-native-current-parity-20260822`

Integrated commit: `33df6710a7ee3fb6386634563a0e8c5a33b80d20`

Result: **AUTOMATED PASS with external release blockers**

This report is sanitized. It contains no passwords, access/refresh tokens,
cookies, session identifiers, Apple signing data, private keys, production
financial payloads, raw OCR text or screenshots.

## Integrated CI

GitHub Actions:
`https://github.com/DmtrGoltsev/finance/actions/runs/32556492248`

| Gate | Result |
| --- | --- |
| Exact branch/SHA | PASS: `codex/ios-native-current-parity-20260822` / `33df6710...` |
| Backend auth/migration tests | PASS: 29 |
| Backend Ruff | PASS |
| Alembic heads | PASS: one head, `20260822_0018` |
| XcodeGen | PASS |
| iOS Debug build | PASS |
| iOS Release build | PASS |
| XCTest | PASS: 69/69 |
| Launch UI test | PASS: 1/1 |

CI artifact: `ios-build-test-evidence-32556492248`, artifact id
`9471631068`, size `542519` bytes, digest
`sha256:40641f8822e91a36737fd7c9c448e43a12edd689aaecb38878729fad13aadc3a`.
The artifact is retained by GitHub Actions and was not copied into the repository.

## Worker evidence

| Stream | Evidence | Result |
| --- | --- | --- |
| Backend `ios_bearer` | commit `407e5628112f7d819b5f898f87d2f6a3f666689b` | Local backend 304 passed/6 skipped; targeted 61 and 29; Ruff PASS; one Alembic head |
| Secure session | run `32554005096`, commit `13bff57b8c1961ce67aa0bd35ec25a31dc132a4f` | Debug/Release, XCTest 57/57, UI 1/1 PASS |
| SwiftData/sync | run `32554343934`, commit `640f93e254d34f56025c2c5366d9251e44cfc407` | Debug/Release, XCTest 52/52, UI 1/1 PASS |
| UX parity | run `32552813248`, commit `ba195e2d0d1590b492d71b5bb972a54f822149de` | PASS |

Worker evidence is supporting evidence only. The integrated release claim is
based on run `32556492248` at the exact integrated SHA.

## Covered automated behavior

- secure persistent `ios_bearer` session with no password persistence;
- single-flight refresh, one retry, safe `403`, offline logout and stale refresh rejection;
- A -> B account isolation and session-bound sync lease;
- SwiftData JSON migration/recovery, atomic writes and rollback;
- stale push response rejection;
- category partial-text search in a modal vertical list;
- newest-first operation ordering with stable tie-breakers;
- operation edit wiring for amount/date/category/account;
- selected-month pending investment overlay;
- personal-only UI/API contracts;
- OCR online-only boundary;
- payment-account filtering;
- compact month switcher and current-month shortcut.

## Explicit non-results and blockers

- **Physical iPhone/signing: NOT RUN/BLOCKED.** No signed IPA was produced and no
  installation on a real iPhone was performed. Mac/Xcode, Apple Team/provisioning
  and a connected device are required.
- **Production HTTPS/ATS: NOT RUN/BLOCKED.** The current production Finance API
  endpoint is plain HTTP. Native iOS Release requires a publicly trusted HTTPS
  endpoint. No broad ATS exception may be added.
- **Production backend deploy: NOT PERFORMED.** Migration `20260822_0018` passed
  CI contract checks but was not applied to the live production database in this
  QA wave.
- **Physical OCR and complete offline reconnect flow: NOT RUN.** Automated
  boundaries passed; device evidence is still required.

No production QA credentials were copied into this repository.
