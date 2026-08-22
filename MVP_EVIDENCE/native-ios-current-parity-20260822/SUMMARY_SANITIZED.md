# Native iOS current parity: final approved QA evidence

Run date: 2026-08-22 (Europe/Moscow)

Branch: `codex/ios-native-current-parity-20260822`

Current verified code commit: `cd69581375be2f40e42771fa6be79d129b32873c`

Result: **CODE/CI APPROVE with external production and device blockers**

This report is sanitized. It contains no passwords, access/refresh tokens,
cookies, session identifiers, Apple signing data, private keys, production
financial payloads, raw OCR text or screenshots.

## Final CI

GitHub Actions:
`https://github.com/DmtrGoltsev/finance/actions/runs/32574558652`

| Gate | Result |
| --- | --- |
| Exact branch/SHA | PASS: `codex/ios-native-current-parity-20260822` / `cd69581...` |
| Full local backend suite | PASS: 313 passed, 6 skipped |
| CI backend auth/migration tests | PASS: 63 |
| Backend Ruff | PASS |
| Alembic heads | PASS: one head, `20260822_0019` |
| XcodeGen | PASS |
| iOS Debug build | PASS |
| iOS Release build | PASS; ordinary Release remains HTTPS-only |
| PersonalSideloadHTTP build and plist policy | PASS |
| XCTest | PASS: 85/85 |
| Launch UI test | PASS: 1/1 |
| Final independent review | APPROVE |

CI artifact: `ios-build-test-evidence-32574558652`, digest
`sha256:3ce42ad490ac6559f8e4bcc15a6d381704f9beb48e4d2d8ecc24d303857763c4`.
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

- GitHub environment `production`: no Required reviewer under the solo-owner
  waiver; custom deployment branch policy permits only `prod/release-*`.
- No release branch was pushed for this evidence update.
- Production database revision: last documented as `20260618_0017`; no fresh
  host preflight was claimed by this evidence update.
- Public health: HTTP 200.
- Trusted HTTPS/FQDN: absent.
- Alembic head `20260822_0019` is not applied to production.

No direct SSH/SCP deploy was performed and production data was not mutated.

## Explicit non-results and blockers

- **Physical iPhone/signing: NOT RUN/BLOCKED.** No signed IPA was produced and
  no installation on a real iPhone was performed. Mac/Xcode, Apple
  Team/provisioning and a connected device are required.
- **Production HTTPS/ATS:** ordinary Release still requires a publicly trusted
  HTTPS endpoint. The personal sideload configuration is separately restricted
  to the exact HTTP production IP/path and has no physical-device proof. No
  broad ATS exception may be added.
- **Physical OCR and complete offline reconnect flow: NOT RUN.** Automated
  boundaries passed; device evidence is still required.

No production QA credentials were copied into this repository.
