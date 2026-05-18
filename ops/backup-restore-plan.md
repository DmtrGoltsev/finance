# Backup/Restore Evidence Plan for Closed MVP

Status: W2-18 planning artifact. This file defines runbook and evidence requirements only. It does not create backup scripts, infrastructure code, production credentials, or run a backup.

Source inputs:

- `docs/architecture/decision-records/adr-0001-stack-repo-layout.md`
- `docs/planning/wave-2-backlog.md`
- `docs/security/security-release-checklist.md`
- `docs/security/security-baseline.md`
- `docs/compliance/privacy-flows-mvp.md`
- `docs/testing/qa-endpoint-traceability.md`
- `docs/testing/wave-2-fixture-evidence-matrix.md`
- `docs/architecture/data-model-implementation-plan.md`

## Closed-MVP Baseline

The closed MVP backup baseline is:

- PostgreSQL automated encrypted backups at least daily.
- Default RPO <= 24 hours.
- Default RTO <= 24 hours.
- Backup storage is isolated from runtime application credentials.
- Runtime application credentials cannot delete backups.
- Backups are not copied to local development, public buckets, issue trackers, chat attachments, or unprotected file shares.
- Restore is tested on a separate environment before release.
- Restore evidence proves personal ownership and `Household` boundaries are preserved.

The baseline applies to PostgreSQL data, including security/audit tables stored in PostgreSQL. If audit logs are later stored outside PostgreSQL, that storage needs its own encrypted backup and restore evidence before release.

## Gate Mapping

| Gate | W2-18 obligation | Required evidence path |
| --- | --- | --- |
| `SEC-BACKUP-01` | Prove encrypted backup, isolated access, successful separate-environment restore, and tenant-boundary checks. | `artifacts/evidence/backups/` |
| `RG-07` | Support security release evidence for auth/session/security operations by proving recoverability does not weaken access boundaries. | `artifacts/evidence/backups/restore-drill-report.md`, `artifacts/evidence/backups/tenant-boundary-verification.md` |
| `RG-12` | Feed P0/P1 closure with backup/restore status, blocker state, and residual risks. | `artifacts/evidence/backups/p0-p1-backup-risk-register.md` |
| `PF-RG-11` | Document closed-MVP backup/restore evidence and backup deletion uncertainty. | `artifacts/evidence/backups/retention-backup-risk-note.md` |
| `PF-RG-12` | Keep public launch, formal retention/deletion SLA, backup deletion promises, support/admin access, and shared-history ownership out of scope unless signed off. | `artifacts/evidence/backups/legal-product-security-signoff.md` |

## Planned Evidence Inventory

No evidence files are created by this planning task. Future execution workers should place proof under:

- `artifacts/evidence/backups/encrypted-backup-proof.md`
- `artifacts/evidence/backups/backup-job-inventory.md`
- `artifacts/evidence/backups/backup-access-control-proof.md`
- `artifacts/evidence/backups/runtime-cannot-delete-proof.md`
- `artifacts/evidence/backups/rpo-rto-measurement.md`
- `artifacts/evidence/backups/restore-drill-report.md`
- `artifacts/evidence/backups/tenant-boundary-verification.md`
- `artifacts/evidence/backups/migration-restore-precheck.md`
- `artifacts/evidence/backups/backup-audit-log-proof.md`
- `artifacts/evidence/backups/retention-backup-risk-note.md`
- `artifacts/evidence/backups/p0-p1-backup-risk-register.md`
- `artifacts/evidence/backups/legal-product-security-signoff.md`

Evidence must use synthetic fixture labels where possible and must not include production secrets, plaintext tokens, raw financial request/response bodies, backup object URLs with credentials, or unnecessary financial values.

## Backup Access Boundary

Minimum access model for closed MVP:

- Application runtime role: may connect to its database with least privilege; must not hold backup storage delete permissions.
- Backup job role: may create backups and write to protected backup storage; delete permission is not granted unless Operations approves a separate retention mechanism outside app runtime.
- Restore operator role: may read a selected backup and restore into an isolated environment; cannot use app runtime credentials as proof of backup control.
- Operations reviewer: verifies encryption, access policy, audit trail, RPO/RTO measurement, and restore evidence.

Access proof must show:

- backup encryption is enabled at storage and transport layers appropriate to the selected platform;
- backup storage is private and not public-readable;
- app runtime identity is absent from backup delete policy;
- delete-capable backup administration, if any, is limited to Operations-controlled identities and audited;
- backup paths, object names, and logs do not expose secrets or user-entered financial content.

## Restore Drill Baseline

Restore drills must run in a separate environment that is isolated from production and closed-MVP users. The environment must use separate credentials, no public app traffic, and no production notification/export delivery side effects.

High-level drill sequence:

1. Select a backup whose timestamp is within the accepted RPO window.
2. Record backup metadata without exposing secrets: backup id or redacted object name, backup timestamp, encryption status, retention class, and operator.
3. Provision or select a separate restore environment with an empty PostgreSQL target.
4. Restore the backup into that environment using Operations-controlled credentials.
5. Record restore start/end timestamps and calculate RTO.
6. Verify schema/migration version and core table availability.
7. Run tenant-boundary verification against the restored data.
8. Record pass/fail/blocker results and link them under `artifacts/evidence/backups/`.
9. Destroy or lock down the restore environment after evidence capture.

## Tenant-Boundary Proof After Restore

The restore drill must prove restored data preserves the same boundaries as the live system:

- `personal` rows remain bound to `ownerUserId` and are visible only to that owner.
- `shared` rows remain bound to the correct `Household` and are visible only to active members of that `Household`.
- Invited members do not gain shared financial access before activation.
- Former members do not regain shared financial access after `left` or `revoked`, including through stale ids, sessions, report cursors, export jobs/files, search/autocomplete, or offline/cache artifacts if those exist in the fixture set.
- `shared_family_report` includes only shared household rows.
- `combined_viewer_overview` includes shared household rows plus only the current viewer's personal rows.
- Missing and inaccessible restored resources keep neutral response behavior.

Preferred fixture labels for proof are Owner A, Member B, Other C, Invited, and Former from the Wave 2 fixture matrix.

## Migration Safety Hook

Before production-like migrations touching auth, sessions, membership, accounts, categories, transactions, transfers, exports, deletion, audit, or outbox tables:

- capture an encrypted PostgreSQL backup;
- record fresh backup metadata under `artifacts/evidence/backups/migration-restore-precheck.md`;
- confirm rollback/forward-fix notes exist for the migration;
- run or schedule a restore drill if the migration changes ownership, household, transfer, export, deletion, audit, or cache invalidation semantics.

## Open P1-B03 Policy Blocker

P1-B03 remains open. Legal/Product/Security/Operations still need to decide public launch policy, formal retention/deletion SLA, backup deletion promises, selective backup deletion behavior after account deletion, legal hold handling, shared-history ownership, and jurisdiction/compliance commitments.

Until P1-B03 is closed:

- closed MVP must not promise physical deletion from backups before backup retention expiry;
- backup retention duration is an operational default, not a public/legal SLA;
- public launch, SaaS/self-hosted commitment, support/admin production data access, and formal deletion language require escalation and signoff;
- `PF-RG-11` can be satisfied by documented closed-MVP evidence plus explicit uncertainty;
- `PF-RG-12` remains a release signoff gate for anything beyond closed MVP.

## Escalation Triggers

Escalate to the parent orchestrator and Operations/Security/Privacy/Legal if:

- backup storage is public or too broadly accessible;
- runtime app credentials can delete backups;
- encryption cannot be proven;
- restore cannot complete within the accepted RTO;
- backup freshness cannot satisfy RPO;
- restored data loses ownership, `Household`, membership, session, export, audit, or cache invalidation boundaries;
- restore evidence requires exposing secrets, tokens, raw financial payloads, or production backup artifacts in unsafe locations;
- product or legal language requires a backup deletion promise before P1-B03 is closed.
