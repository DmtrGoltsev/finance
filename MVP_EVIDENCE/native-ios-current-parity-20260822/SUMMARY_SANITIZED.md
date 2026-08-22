# Native iOS current parity: final approved QA evidence

Run date: 2026-08-22 (Europe/Moscow)

Branch: `codex/ios-native-current-parity-20260822`

Final code commit: `a5a332093587fc2467383686cca089877d03f90e`

Result: **CODE/CI APPROVE with external production and device blockers**

This report is sanitized. It contains no passwords, access/refresh tokens,
cookies, session identifiers, Apple signing data, private keys, production
financial payloads, raw OCR text or screenshots.

## Final CI

GitHub Actions:
`https://github.com/DmtrGoltsev/finance/actions/runs/32563222674`

| Gate | Result |
| --- | --- |
| Exact branch/SHA | PASS: `codex/ios-native-current-parity-20260822` / `a5a3320...` |
| Full local backend suite | PASS: 313 passed, 6 skipped |
| CI backend auth/migration tests | PASS: 63 |
| Backend Ruff | PASS |
| Alembic heads | PASS: one head, `20260822_0019` |
| XcodeGen | PASS |
| iOS Debug build | PASS |
| iOS Release build | PASS |
| XCTest | PASS: 77/77 |
| Launch UI test | PASS: 1/1 |
| Final independent review | APPROVE |

CI artifact: `ios-build-test-evidence-32563222674`, artifact id
`9473425949`, size `571076` bytes, digest
`sha256:028cd3b931aec26c119ca649eb4f392eda1d1d60182c1295fd57e3302d22e801`.
The artifact is retained by GitHub Actions and was not copied into the repository.

## Closed review findings

Cycle 1 closed the real-path 72-hour offline restore cap, session refresh
lifetime rotation, offline edit/delete analytics overlay, and the
refresh-versus-logout revocation race.

Cycle 2 separated the 15-minute access-token expiry from the 30-day sliding
refresh/session lifetime, rebased partial edit -> delete sync analytics on the
applied edit, and fixed uncategorized expense edit/delete analytics using the
canonical `uncategorized` key.

No P0/P1 code finding remains open in the final reviewed scope.

## Covered automated behavior

- secure persistent `ios_bearer` session with no password persistence;
- single-flight refresh, one retry, safe `403`, 72-hour offline cap, stable
  logout revocation and stale refresh rejection;
- separate access/refresh expiry with replay protection;
- A -> B account isolation and session-bound sync lease;
- SwiftData JSON migration/recovery, atomic writes and rollback;
- stale and partial push response handling;
- category partial-text search in a modal vertical list;
- newest-first operation ordering and operation editing;
- selected-month pending investment and edit/delete analytics overlays;
- personal-only UI/API contracts and OCR online-only boundary;
- payment-account filtering and compact month switching.

## Production deploy preflight

Result: **BLOCKED / NOT DEPLOYED**.

- GitHub environment `production`: `protection_rules=[]`.
- Release branch `prod/release-finance-ios-backend-20260822`: local only and
  not pushed.
- Production database revision: `20260618_0017`.
- Public health: HTTP 200.
- Trusted HTTPS/FQDN: absent.
- Alembic head `20260822_0019` is not applied to production.

No direct SSH/SCP deploy was performed and production data was not mutated.

## Explicit non-results and blockers

- **Physical iPhone/signing: NOT RUN/BLOCKED.** No signed IPA was produced and
  no installation on a real iPhone was performed. Mac/Xcode, Apple
  Team/provisioning and a connected device are required.
- **Production HTTPS/ATS: NOT RUN/BLOCKED.** Native iOS Release requires a
  publicly trusted HTTPS endpoint. No broad ATS exception may be added.
- **Physical OCR and complete offline reconnect flow: NOT RUN.** Automated
  boundaries passed; device evidence is still required.

No production QA credentials were copied into this repository.
