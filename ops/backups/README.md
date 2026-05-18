# Backup Runbook Skeleton

Status: documentation skeleton only. Do not add scripts, cloud resources, credentials, backup object URLs, or production infrastructure code here.

## Purpose

This directory holds the closed-MVP backup runbook. The release requirement is to prove that PostgreSQL backups are encrypted, run at least daily, meet RPO <= 24 hours, and are protected from deletion by runtime application credentials.

## Baseline Controls

- Backup target: PostgreSQL 16 database for the closed MVP.
- Frequency: at least daily automated backup.
- Encryption: backup storage encryption enabled; transport encryption used by the platform where applicable.
- RPO: latest usable backup age <= 24 hours by default.
- RTO: restore drill completes within <= 24 hours by default.
- Isolation: backup storage and backup administration are separate from app runtime credentials.
- Delete boundary: app runtime identity cannot delete backups.
- Storage hygiene: no local development copies, public buckets, issue attachments, chat uploads, or unprotected file shares.

## Roles

| Role | Allowed | Not allowed |
| --- | --- | --- |
| App runtime | Normal application database access only. | Backup storage delete, backup administration, restore operation. |
| Backup job identity | Create/write encrypted backups and emit safe job metadata. | Use app runtime credentials as proof, publish backup objects, write secrets to logs. |
| Restore operator | Read selected backup and restore to isolated environment. | Restore into production for a drill, expose restored data to normal users. |
| Operations reviewer | Review backup policy, encryption, access, audit, and evidence. | Accept missing tenant-boundary proof for release. |

## Evidence to Collect

Future execution workers should write evidence under `artifacts/evidence/backups/`:

- `encrypted-backup-proof.md`: encryption settings and safe platform evidence.
- `backup-job-inventory.md`: schedule, last successful backup timestamp, backup id redacted as needed.
- `backup-access-control-proof.md`: least-privilege backup storage access.
- `runtime-cannot-delete-proof.md`: explicit proof app runtime has no backup delete permission.
- `rpo-rto-measurement.md`: latest backup freshness and latest restore duration.
- `backup-audit-log-proof.md`: audit event or platform log proving backup/restore operations are auditable.
- `p0-p1-backup-risk-register.md`: open risks, blockers, and accepted exceptions.

Evidence must be sanitized. It may include fixture labels, timestamps, policy summaries, and redacted ids. It must not include secrets, tokens, raw backup files, raw financial payloads, or credential-bearing URLs.

## Backup Acceptance Checklist

- [ ] PostgreSQL automated backup exists and runs at least daily.
- [ ] Latest successful backup is within the RPO window.
- [ ] Backup encryption is enabled.
- [ ] Backup storage is private and access-controlled.
- [ ] App runtime identity cannot delete backups.
- [ ] Backup job and backup access are audited.
- [ ] Backups are not copied to forbidden locations.
- [ ] Restore drill evidence exists in `artifacts/evidence/backups/restore-drill-report.md`.
- [ ] Tenant-boundary verification exists in `artifacts/evidence/backups/tenant-boundary-verification.md`.
- [ ] P1-B03 legal/retention/backup deletion/public launch policy remains explicitly open or has formal signoff.

## Non-Goals

- No backup scripts in this directory for W2-18.
- No cloud/IaC configuration.
- No production credentials.
- No live backup execution.
- No formal public retention/deletion SLA.

## Blockers

Release remains blocked if backup encryption, backup access isolation, runtime no-delete proof, separate-environment restore, RPO/RTO measurement, or tenant-boundary verification is missing.
