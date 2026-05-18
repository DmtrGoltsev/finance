# Restore Drill Runbook Skeleton

Status: documentation skeleton only. This directory does not contain restore scripts, infrastructure code, production credentials, or live restore output.

## Purpose

Restore drills prove that a closed-MVP PostgreSQL backup can be restored on a separate environment within RTO <= 24 hours and that restored data still preserves personal ownership and `Household` boundaries.

## Preconditions

- A candidate encrypted PostgreSQL backup exists and is within RPO <= 24 hours.
- Restore target is separate from production and normal closed-MVP user traffic.
- Restore target uses separate credentials and cannot send production notifications, export links, or user-visible side effects.
- Operators have approved access to read the selected backup.
- Evidence directory exists: `artifacts/evidence/backups/`.
- Fixture or test data includes Owner A, Member B, Other C, Invited, and Former labels, or an equivalent approved boundary dataset.

## Drill Steps

1. Record drill metadata: date, operator, environment, backup timestamp, redacted backup id, expected RPO/RTO.
2. Confirm backup encryption and private storage before restore begins.
3. Confirm app runtime identity has no delete permission on backup storage.
4. Start restore timer.
5. Restore the selected backup into the separate PostgreSQL environment.
6. Stop restore timer when the database is queryable and app/API test surface can run against the restored environment.
7. Record actual restore duration and compare with RTO <= 24 hours.
8. Verify schema/migration version and required scoped tables: users, households, memberships, accounts, categories, transactions, sessions, export jobs, deletion requests, audit events, and outbox/invalidation tables when present.
9. Run tenant-boundary verification.
10. Record pass/fail/blocker status and evidence links.
11. Tear down or lock down the restore environment.

## Tenant-Boundary Verification Matrix

| Actor | Must be true after restore | Gates |
| --- | --- | --- |
| Owner A | Sees own personal A rows and shared Household AB rows only. Does not see Member B personal rows or Household C rows. | `RG-07`, `RG-12`, `SEC-BACKUP-01` |
| Member B | Sees own personal B rows and shared Household AB rows only. Does not see Owner A personal rows or Household C rows. | `RG-07`, `RG-12`, `SEC-BACKUP-01` |
| Other C | Sees own personal/Household C data only. Cannot read Household AB shared or personal data. | `RG-12`, `SEC-BACKUP-01` |
| Invited | Has no shared AB financial access before active membership. Minimal invite context only, if invite verification is in scope. | `RG-07`, `RG-12`, `SEC-BACKUP-01` |
| Former | Has own personal data only and cannot regain current or historical AB shared financial access through old ids, sessions, exports, cursors, search/autocomplete, reports, or cache artifacts. | `RG-07`, `RG-12`, `PF-RG-11`, `PF-RG-12`, `SEC-BACKUP-01` |

## Required Boundary Checks

- Personal account/category/transaction rows keep `ownerUserId` binding after restore.
- Shared account/category/transaction rows keep `householdId` binding after restore.
- Active membership remains the only state that grants shared financial access.
- Invited, left, and revoked memberships grant no shared financial access.
- `shared_family_report` includes only shared rows for the requested household.
- `combined_viewer_overview` includes shared household rows plus only the current viewer's personal rows.
- Exports after restore include only visible rows at generation time.
- Old export files/jobs containing shared data are revoked or inaccessible after leave/revoke where the implementation has those artifacts.
- Missing and inaccessible ids still use neutral response shapes.
- Audit/log evidence for the drill uses safe metadata only and does not include amounts, descriptions, account/category names, passwords, reset/invite/session/refresh tokens, secrets, or raw financial payloads.

## Evidence Outputs

Future execution workers should produce:

- `artifacts/evidence/backups/restore-drill-report.md`
- `artifacts/evidence/backups/tenant-boundary-verification.md`
- `artifacts/evidence/backups/rpo-rto-measurement.md`
- `artifacts/evidence/backups/backup-audit-log-proof.md`
- `artifacts/evidence/backups/p0-p1-backup-risk-register.md`

The restore report should include:

- backup timestamp and redacted backup id;
- restore start/end timestamps;
- calculated RPO and RTO;
- environment isolation statement;
- schema/migration version;
- verification matrix result;
- failed/retried run references if applicable;
- blocker and escalation status.

## Failure Handling

Classify as release-blocking until resolved if:

- restore fails or exceeds accepted RTO;
- selected backup exceeds accepted RPO;
- restored schema is incomplete;
- any actor sees another user's personal data;
- Other C, Invited, or Former can access Household AB shared financial data;
- reports aggregate hidden rows before visible filtering;
- export/delete/leave behavior differs from pre-restore boundary requirements;
- evidence cannot be captured without exposing secrets or sensitive financial content.

## Open Policy Note

P1-B03 remains open. Restore drills must not imply a public/legal backup deletion promise, formal retention period, deletion SLA, public launch readiness, or selective backup deletion guarantee. Those decisions require Legal/Product/Security/Operations signoff before `PF-RG-12` can close for public launch.
