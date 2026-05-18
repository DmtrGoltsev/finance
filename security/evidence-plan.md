# Wave 2 security evidence plan

## Status and scope

Status: W2-17 planning artifact for Wave 2/MVP release gates.

This document defines required security evidence, recommended tools, artifact paths, blockers, and escalation triggers. It does not run scanners, install tools, create CI, or change production code.

Inputs reviewed:

- `docs/architecture/decision-records/adr-0001-stack-repo-layout.md`
- `docs/planning/wave-2-backlog.md`
- `docs/security/security-release-checklist.md`
- `docs/security/security-baseline.md`
- `docs/testing/qa-endpoint-traceability.md`
- `docs/testing/wave-2-fixture-evidence-matrix.md`
- `docs/architecture/backend-api-contracts.md`

Stack assumptions from ADR-0001:

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x, PostgreSQL 16, Alembic, Pydantic DTOs aligned to OpenAPI.
- Web/PWA: TypeScript, React, Vite, TanStack Query, generated OpenAPI client.
- Android: Kotlin, Jetpack Compose, Retrofit/OkHttp or generated OpenAPI client, platform secure storage.
- API source of truth: `api/openapi/openapi.yaml`.
- Auth transport: PWA HttpOnly Secure SameSite cookies plus CSRF protection; Android opaque bearer access token plus rotating refresh token in secure storage.
- Evidence root: `artifacts/evidence/**`.

## Release gates covered

| Gate | W2-17 evidence focus | Blocking meaning |
| --- | --- | --- |
| RG-07 | Auth, sessions, reset, invite, rate limits, CSRF/CORS, backup security handoff | P0/P1 if auth/session security evidence is absent or failing. |
| RG-08 | Logs/audit minimization for all auth, financial, report, transfer, export and denial paths | P0 if logs/audit contain sensitive financial values, tokens, secrets or raw bodies. |
| RG-10 | Neutral responses for auth/reset/invite/rate limit/direct-id/reference failures | P1 or P0 if response shape leaks account, token, object, owner, household or hidden data existence. |
| RG-11 | Out-of-scope absence and no credential surfaces for imports, bank API, SMS/push, broker credentials and raw statements | P0 if out-of-scope routes, config, secrets, schema fields, source types or storage appear. |
| RG-12 | P0/P1 closure, dependency/SBOM triage, route/debug inventory, accepted residual risk list | Release hold until all P0/P1 findings are fixed or formally accepted as release-blocker exceptions. |

## Evidence inventory

| Evidence area | Scenarios and gates | Required evidence | Recommended tools, not installed here | Planned artifact path |
| --- | --- | --- | --- | --- |
| Auth registration/login | `SEC-AUTH-01..03`, `SEC-RATE-01`, `RG-07`, `RG-10`, `RG-12` | Password hash review, neutral registration/login response golden tests, anonymous/protected endpoint tests, session fixation defense, logout/logout-all revocation, PWA cookie and Android token storage config evidence. | `pytest`, Schemathesis for contract probes where routes are in OpenAPI. | `artifacts/evidence/security/auth-session-reset/` |
| Sessions and revocation | `SEC-AUTH-02..03`, `PRIV-LEAVE-01`, `RG-07`, `RG-10` | Current-session checks, revoked/expired session rejection, password reset/session version revocation, membership leave/revoke access invalidation, no cross-viewer cache/session mixing. | `pytest`, client cache suites from later workers, Schemathesis for auth-required routes. | `artifacts/evidence/security/auth-session-reset/` and client evidence handoff. |
| Password reset | `SEC-RESET-01..02`, `SEC-RATE-01`, `RG-07`, `RG-08`, `RG-10` | Neutral reset request response, one-time short-lived hashed token, replay/expiry/revoked token tests, old session/refresh rejection after reset, log scan proving reset token is absent. | `pytest`, log scan grep/script later. | `artifacts/evidence/security/auth-session-reset/`, `artifacts/evidence/security/logs-audit/` |
| Invites | `SEC-INV-01..02`, `SEC-RATE-01`, `NEG-MEM-01`, `RG-07`, `RG-08`, `RG-10` | Token-bound accept/decline, hashed one-time token, expiry/revoke/replay tests, no shared financial access before active membership, resend response/logs do not include token, former/invited denial. | `pytest`, Schemathesis, W2-15 fixture set. | `artifacts/evidence/security/auth-session-reset/`, `artifacts/evidence/security/logs-audit/` |
| Rate limits | `SEC-RATE-01`, `RG-07`, `RG-10`, `RG-12` | Config dump and tests for login, registration, password reset, reset confirmation, invite create/resend/accept/decline attempts; proof of `429` or approved progressive denial without account/member enumeration. | `pytest`; load/abuse harness later if approved. | `artifacts/evidence/security/rate-limit/` |
| CSRF, CORS and cache headers | `SEC-AUTH-*`, `RG-07`, `RG-10`, `RG-12` | PWA state-changing cookie-auth routes require CSRF token or approved SameSite strategy; CSRF negative tests; CORS explicit allowlist; no wildcard origin with credentials; sensitive responses use private/no-store. Android native traffic is outside browser CORS but must use HTTPS and the same API auth rules. | `pytest`, Schemathesis, browser/client tests later. | `artifacts/evidence/security/csrf-cors/` |
| Logs and audit | `SEC-LOG-01..02`, `RG-08`, `RG-10`, `RG-12` | Production-like sanitized log/audit samples plus scan output for allow, deny, validation, transfer denial, report/export/cache, auth/reset/invite/session flows. Audit schema review proves safe metadata only. | Structured log sample checks, grep/script later, `pytest` fixtures for emitted audit events. | `artifacts/evidence/security/logs-audit/` |
| Secret scan and config review | `SEC-SECRET-01`, `RG-11`, `RG-12` | Repo/config/bundle/image scan output, deployment secret-source review, no production secrets in markdown, code, bundles, Docker layers, logs or issue artifacts; required secrets fail closed. | `gitleaks`; bundle/image scan tool later if frontend/mobile/container outputs exist. | `artifacts/evidence/security/secret-scan/` |
| Dependency scan and SBOM | `RG-12` and security release dependency gate | Python, web and Android dependency scans plus SBOMs; no unaccepted critical/high CVEs in auth, crypto, session, parser, ORM or web framework components. | `pip-audit`, `npm audit` or OSV, Gradle dependency audit; SBOM tool later, for example CycloneDX family if approved. | `artifacts/evidence/dependencies/` |
| Route inventory and out-of-scope scan | `SEC-SECRET-01`, `RG-11`, `RG-12` | OpenAPI and implemented route inventory proving no import, bank API, SMS/push, broker credential, external credential or raw bank statement endpoint; schema/config scan; `sourceType = manual` create/update rejection evidence. | Route inventory script later, Schemathesis/OpenAPI lint from W2-02, source/config scan later. | `artifacts/evidence/security/route-inventory/` and `artifacts/evidence/api/` handoff. |
| Debug/support/internal bypass inventory | `SEC-LOG-*`, `SEC-SECRET-01`, `RG-08`, `RG-10`, `RG-11`, `RG-12` | Prove absent in MVP or prove same predicates, redaction, no raw bodies, safe audit and least privilege. | Route inventory script later, code review checklist, `pytest` if any route exists. | `artifacts/evidence/security/route-inventory/` |

## Log and audit redaction invariant

Logs, audit, telemetry, crash reports, debug output and scan artifacts must not contain:

- amounts, balances, report totals or derived financial totals;
- transaction descriptions, raw search strings, raw filters or raw financial request/response bodies;
- account names, category names, hidden owner names, hidden household names or hidden membership diagnostics;
- plaintext passwords, reset tokens, invite tokens, session tokens, refresh tokens, bearer tokens, token hashes unless explicitly approved for a narrow audit field, API keys or secrets;
- raw export file contents, raw database dumps, stack traces, SQL text or environment ids returned to users.

Allowed audit metadata is limited to timestamp, request id, actor/system id when safe, action, target type/id when safe, scope type/id when safe, result, reason code, and coarse client metadata where policy allows it. Denied access audit must not enrich caller-supplied hidden ids with hidden metadata.

## Evidence metadata contract

Every future evidence artifact should include or be linked from a manifest with:

- `artifactVersion`
- `generatedAt`
- `gitOrBuildRef`
- `runner`
- `toolName` and `toolVersion`
- command or task name, with secrets and tokens redacted
- target path or environment
- scenario ids, gate ids and endpoint surfaces
- actor labels from the W2-15 fixture set where applicable
- result: `pass`, `fail`, `blocked`, `not_run` or `not_applicable`
- blocking findings and owner/date for remediation or accepted exception

Failed or retried runs must not be overwritten. Link them to the final green run.

## P0 blockers

Release must stop if any of these appear:

- plaintext passwords, reset tokens, invite tokens, session/refresh tokens, bearer tokens, production secrets or bank/API/SMS/push/broker credentials are stored or logged;
- logs/audit/telemetry/debug output include amounts, balances, report totals, descriptions, account/category names, tokens, secrets or raw financial bodies;
- PWA cookie-auth state-changing endpoints work without CSRF protection, or CORS allows wildcard origin with credentials;
- logout, password reset, membership leave/revoke, account deletion/deactivation or suspected compromise does not revoke relevant server-side sessions/tokens/access caches;
- production/staging real-data traffic is available without HTTPS;
- out-of-scope routes, fields, config, storage or secrets for imports, bank API, SMS/push, broker credentials, external credentials or raw statements appear;
- route inventory finds a debug/support/internal route that bypasses predicates or redaction;
- dependency evidence finds an exploitable unaccepted critical auth, crypto, session, parser, ORM or web framework CVE with no mitigation before release.

## P1 blockers

Release must remain on hold until fixed or formally accepted as a release-blocker exception if:

- rate limit evidence is missing for login, registration, password reset, invite and resend flows;
- exact rate-limit values are not Product/Security approved and configured;
- neutral response evidence is missing or auth/reset/invite/rate-limit failures disclose email, token, account, household, membership or hidden object existence;
- audit events are missing for auth, failed login, logout, password reset, invite lifecycle, membership lifecycle, account/transaction/category changes, report/export generation, access denied and backup/restore handoff;
- dependency/SBOM evidence is missing for Python backend, React/Vite PWA or Android/Kotlin surfaces;
- secret scan evidence is missing for repo/config/bundle/image surfaces that exist by release time;
- route inventory and out-of-scope absence evidence is missing after W2-02/W2-04/W2-06 implementation surfaces exist.

## Escalation triggers

Escalate to the orchestrator and Security/Product/Privacy/Legal/Ops as applicable if:

- Product asks to expose another household member's personal accounts, transactions, categories, balances, reports, aggregates or exports;
- Product asks to allow personal/shared, cross-user personal or cross-household shared transfers;
- former members must retain historical shared access after `left` or `revoked`;
- support/admin/debug tooling needs financial values or hidden user data;
- report/export/debug/cache cannot be scoped and invalidated by viewer, household, membership and access versions;
- public launch, SaaS/self-hosted commitment, jurisdiction, formal retention/deletion SLA, backup deletion promise, 2FA/passkeys or production secret manager becomes MVP scope;
- repeated failures occur in auth/session/reset/invite/rate-limit, logs/audit redaction, route inventory, dependency scans or secret scans.

## Recommended execution order for later workers

1. W2-02 finishes OpenAPI skeleton so security route inventory and Schemathesis targets have a contract source.
2. W2-15 fixture outputs become the actor/scenario labels for `SEC-*`, `RG-*`, `TR-RG-*` and `PF-RG-*` metadata.
3. W2-04/W2-06/W2-12 produce auth/session/reset/invite/membership implementation and tests.
4. W2-17 security execution writes sanitized auth, rate-limit, CSRF/CORS, log/audit, secret and route inventory evidence.
5. Dependency evidence is generated once backend, web and Android dependency manifests exist.
6. W2-18 writes backup/restore evidence separately; W2-17 consumes only security checklist linkage for `SEC-BACKUP-01`.
7. W2-19 reviews all P0/P1 findings and residual risks before release recommendation.

## Definition of done for this planning artifact

- Security evidence requirements cover auth/session/reset/invite/rate limits, CSRF/CORS, logs/audit, secret scan, dependency/SBOM and route inventory/out-of-scope scan.
- Coverage is linked to `RG-07`, `RG-08`, `RG-10`, `RG-11`, `RG-12` and relevant `SEC-*` scenarios.
- Tool recommendations are named without installing or running them.
- Artifact paths under `artifacts/evidence/security/` and `artifacts/evidence/dependencies/` are defined.
- P0/P1 blockers and escalation triggers are explicit.
- No production code, CI, scanner execution or generated scan output is created by this task.
