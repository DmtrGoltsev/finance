# Native iOS current parity: final approved QA evidence

Run date: 2026-08-22 (Europe/Moscow)

Branch: `codex/ios-native-current-parity-20260822`

Deployed code SHA: `db7ebdd41a35018ae59e1fc4f5c5e38f0ed37de6`.

Immutable release branch:
`prod/release-finance-ios-current-parity-20260823-db7ebdd`.

Required ancestors:

- governance: `4e1ef36724f804d648f2ea385da5259688915325`;
- production pipeline: `6d3f4e3cdb1ed7b333879603789d1ca9a1bb080c`;
- iOS personal transport security: `744a422c5d012149f6c0051dcaf291623fd9a19c`.

Resolve the immutable release branch and require it to equal the deployed code
SHA above, then require all three `git merge-base --is-ancestor <sha> <head>`
checks. Documentation-only commits may follow on the integration branch and do
not change the deployed code identity.

Result: **CODE/CI/PRODUCTION APPROVE; physical iPhone NOT RUN**

This report is sanitized. It contains no passwords, access/refresh tokens,
cookies, session identifiers, Apple signing data, private keys, production
financial payloads, raw OCR text or screenshots.

## Final CI

Worker GitHub Actions:

- pipeline: `https://github.com/DmtrGoltsev/finance/actions/runs/32576848852`;
- iOS security: `https://github.com/DmtrGoltsev/finance/actions/runs/32601960992`;
- repeated iOS security proof:
  `https://github.com/DmtrGoltsev/finance/actions/runs/32602392746`.

Final exact-SHA runs:

- iOS Build: `https://github.com/DmtrGoltsev/finance/actions/runs/32603535573`;
- CI-only package proof:
  `https://github.com/DmtrGoltsev/finance/actions/runs/32604090062`;
- production deploy:
  `https://github.com/DmtrGoltsev/finance/actions/runs/32604838031`.

| Gate | Result |
| --- | --- |
| Exact release branch/SHA/ancestry | PASS: immutable release branch resolves to `db7ebdd...` and contains all required ancestors |
| Pipeline worker CI-only | PASS: both packages and common gate; host/deploy skipped |
| CI backend auth/migration tests | PASS |
| Backend Ruff | PASS |
| Alembic heads | PASS: one head, `20260822_0019` |
| XcodeGen | PASS |
| iOS Debug build | PASS |
| iOS Release build | PASS; ordinary Release remains HTTPS-only |
| PersonalSideloadHTTP build and plist policy | PASS; separate identity/manual development signing/no archive/export |
| XCTest | PASS: normal model 87/0 plus 10/0 dedicated personal transport tests |
| Launch UI test | PASS: 1/1 |
| Physical signing/install | NOT RUN |

Final iOS artifact: `ios-build-test-evidence-32603535573`, id `9483613408`,
digest
`sha256:52d98838dd947420e0093c308c58286ab3f5db831017030c4f64be61f6c7bc43`.
CI-only artifacts: frontend `9483667044`, digest
`sha256:0e430fdb2cfca47dcac29d18cec1351b45e17807fb2524800337c78a1db28bed`;
backend `9483674722`, digest
`sha256:d38af135dab7b04ca1ce5c72c920f9e3f5b542eb73284964465d60fe3b522864`.
Artifacts are retained by GitHub Actions and were not committed.

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

## Production deploy

Result: **PASS**.

- GitHub environment `production`: no Required reviewer under the solo-owner
  waiver; custom deployment branch policy permits only `prod/release-*`.
- The integrated workflow requires frontend package plus backend package, then
  a common gate, then a read-only host preflight before backend and frontend
  deployment. Backend precedes frontend.
- A CI-only dispatch with all production actions false does not request the
  production environment, host access or deployment.
- Owner push to the immutable release branch triggered run `32604838031` once;
  no duplicate dispatch occurred.
- Old backend: `finance-personal-backend-20260822-12a1b91f`; old frontend:
  `20260726T220603Z-55f4ac53`.
- New backend and frontend release ID: `20260822T231803Z-db7ebdd4`.
- Backend path: `/opt/finance/releases/20260822T231803Z-db7ebdd4`;
  frontend path: `/var/www/finance/releases/20260822T231803Z-db7ebdd4`.
- `finance-backend.service` is active and wired through `/opt/finance/current`.
- Database migration PASS:
  `20260618_0017 -> 20260822_0018 -> 20260822_0019`.
- Backup before the first upgrade:
  `/opt/finance/backups/postgres/finance_prod-20260822T232027Z-20260822T231803Z-db7ebdd4-20260618_0017-to-20260822_0019.dump`;
  SHA-256
  `238d8d441b5bacca2a5f0ddba728cdf4066c34bd0e32a6c1a589f13cfcd57142`;
  sibling evidence file suffix `.dump.evidence.txt`.
- Smoke PASS: health `200`; OpenAPI `200`, 42 routes; frontend shell,
  manifest, JS, CSS, icon and service worker `200`; scope `/finance/`; hard
  reload current; login `201`; refresh `200` and rotated; logout `204`;
  post-logout `401`; personal read-only endpoints `200`.
- No rollback was required. Release branch is retained for the rollback window.
- Trusted HTTPS/FQDN: absent.

Deployment used GitHub Actions only. No direct manual SSH/SCP deploy was
performed. Sanitized downloaded workflow evidence is stored outside Git at
`C:\Users\style\Documents\Codex\Finance-release-evidence\32604838031`.

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
