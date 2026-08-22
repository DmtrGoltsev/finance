# Native iOS current parity: final approved QA evidence

Run date: 2026-08-22 (Europe/Moscow)

Branch: `codex/ios-native-current-parity-20260822`

Integrated deliverable: fetched remote head of
`origin/codex/ios-native-current-parity-20260822`.

Required ancestors:

- governance: `4e1ef36724f804d648f2ea385da5259688915325`;
- production pipeline: `6d3f4e3cdb1ed7b333879603789d1ca9a1bb080c`;
- iOS personal transport security: `744a422c5d012149f6c0051dcaf291623fd9a19c`.

Resolve the exact deliverable SHA with
`git fetch origin && git rev-parse origin/codex/ios-native-current-parity-20260822`
and require all three `git merge-base --is-ancestor <sha> <head>` checks. This
identity rule deliberately avoids recording a false self-referential SHA in the
same commit that contains this report.

Result: **CODE/CI APPROVE with external production and device blockers**

This report is sanitized. It contains no passwords, access/refresh tokens,
cookies, session identifiers, Apple signing data, private keys, production
financial payloads, raw OCR text or screenshots.

## Final CI

Worker GitHub Actions:

- pipeline: `https://github.com/DmtrGoltsev/finance/actions/runs/32576848852`;
- iOS security: `https://github.com/DmtrGoltsev/finance/actions/runs/32601960992`;
- repeated iOS security proof:
  `https://github.com/DmtrGoltsev/finance/actions/runs/32602392746`.

Final acceptance additionally requires a successful `iOS Build` run and a
CI-only `Finance HexCore Production CI/CD` dispatch on the exact fetched target
head. Their run IDs and artifact digests are recorded in the external delivery
report; adding them here would create a new untested commit.

| Gate | Result |
| --- | --- |
| Exact branch/ancestry | PASS when fetched target head contains all required ancestors above |
| Pipeline worker CI-only | PASS: both packages and common gate; host/deploy skipped |
| CI backend auth/migration tests | PASS: 63 |
| Backend Ruff | PASS |
| Alembic heads | PASS: one head, `20260822_0019` |
| XcodeGen | PASS |
| iOS Debug build | PASS |
| iOS Release build | PASS; ordinary Release remains HTTPS-only |
| PersonalSideloadHTTP build and plist policy | PASS; separate identity/manual development signing/no archive/export |
| XCTest | PASS: normal suite plus 10/10 dedicated personal transport tests |
| Launch UI test | PASS: 1/1 |
| Physical signing/install | NOT RUN |

Latest repeated security worker artifact: `ios-build-test-evidence-32602392746`,
id `9483356517`, digest
`sha256:088b7f69e2702cecb729e7e4931356943d87c315d37ec88f1366f43fbacb0181`.
The artifact is retained by GitHub Actions and was not copied into the repository.

## Closed review findings

Cycle 1 closed the real-path 72-hour offline restore cap, session refresh
lifetime rotation, offline edit/delete analytics overlay, and the
refresh-versus-logout revocation race.

Cycle 2 separated the 15-minute access-token expiry from the 30-day sliding
refresh/session lifetime, rebased partial edit -> delete sync analytics on the
applied edit, and fixed uncategorized expense edit/delete analytics using the
canonical `uncategorized` key.

The personal target is isolated under bundle id
`com.codex.FinanceApp.PersonalSideload`, manual Apple Development signing and a
no-archive/no-export gate. The owner HTTP waiver is explicit, expires unless
reviewed by 2026-11-22, and does not reduce the accepted plaintext risk.

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
- The integrated workflow requires frontend package plus backend package, then
  a common gate, then a read-only host preflight before backend and frontend
  deployment. Backend precedes frontend.
- A CI-only dispatch with all production actions false does not request the
  production environment, host access or deployment.
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
