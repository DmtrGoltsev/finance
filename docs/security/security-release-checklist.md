# Релизный чеклист безопасности MVP

## Статус и назначение

Этот чеклист является release gate для MVP приложения учета личных и семейных финансов. Релиз считается допустимым только если закрыты все P0/P1 gates, собраны доказательства из раздела "Обязательные доказательства перед MVP release" и нет открытых escalation triggers.

Документ покрывает auth, session, password reset, invite, rate limits, CSRF, CORS, log masking, secrets, backups, restore, а также связанные API surfaces: accounts, transactions, categories, reports, transfers, exports, delete и leave family.

## Severity и release gates

| Severity | Релизное решение | Критерий |
| --- | --- | --- |
| P0 | Release blocker без обхода | Прямая утечка финансовых/персональных данных, обход auth/authz, хранение plaintext passwords/tokens/secrets, отсутствие restore capability, небезопасный backup, критичная CSRF/CORS ошибка для cookie auth, personal/shared transfer без утвержденной модели split visibility, report aggregation до access filter. |
| P1 | Release blocker до исправления или формально принятого release-blocker exception | Нет обязательного rate limit, неполные neutral errors, отсутствует доказательство session/token revocation, недостаточная log masking, отсутствие audit для security-sensitive событий, незакрытые критичные dependency/auth/crypto CVE, не подтверждены backups/restore/audit/secrets evidence. |
| P2 | Не блокирует закрытый MVP, но должен быть зафиксирован в backlog/risk register | Улучшения hardening без текущей эксплуатации риска: HSTS до публичного запуска, UI управления активными сессиями, расширенный monitoring/SIEM, 2FA/passkeys для public/SaaS, формальная retention policy. |

## P0 блокеры релиза

- [ ] Любой endpoint позволяет читать, изменять, экспортировать или агрегировать personal данные другого пользователя.
- [ ] Пользователь вне Household получает shared account, transaction, category, report, export, membership или invite context чужого Household.
- [ ] Invited или Former Member получает shared financial data до accept/activation или после `left`/`revoked`.
- [ ] Report API считает `SUM`, `COUNT`, balances, breakdown, trend, drill-down, export или cache materialization до фильтрации по visible accounts.
- [ ] Transfer API разрешает `personal -> shared`, `shared -> personal`, cross-user personal или cross-household shared transfer без отдельного утвержденного split-visibility/security решения.
- [ ] Passwords, reset tokens, invite tokens, session/refresh tokens, production secrets или bank/API/SMS/push credentials хранятся или логируются в plaintext.
- [ ] Logs, audit, telemetry, crash reports или debug output содержат суммы, остатки, описания операций, названия счетов/категорий, raw request/response bodies с финансовыми данными или токены.
- [ ] Cookie-based PWA state-changing endpoints работают без CSRF protection или CORS допускает wildcard origin с credentials.
- [ ] Logout, password reset, membership revoke/leave или suspected compromise не инвалидируют server-side session/refresh token/access cache.
- [ ] Production/staging с реальными данными доступны без HTTPS.
- [ ] Production database или backups не имеют encryption at rest.
- [ ] Restore не проходил успешно минимум один раз на отдельном окружении до релиза.
- [ ] В MVP появились endpoints, поля, настройки или хранилища для imports, bank API, broker API, SMS/push credentials, SMS/push/notification interception, raw SMS/push/notification body или raw bank statements. Capture drafts допускают только user-initiated OCR из выбранного скриншота, structured pending drafts и отсутствие raw body server-side.

## P1 блокеры релиза

- [ ] Нет rate limit/progressive delay для login, registration, password reset, resend email и invite flows.
- [ ] Login/register/password reset/invite responses раскрывают наличие email, invite token, reset token или inaccessible object.
- [ ] Missing id и inaccessible id дают различимую user-facing форму ответа для account, transaction, category, report, invite, export или referenced ids.
- [ ] Authz checks не доказаны для list/detail/search/autocomplete/report/export/debug на тех же predicates.
- [ ] Отсутствуют audit events для auth, failed login, password reset, invite accept/revoke, membership changes, account/transaction/category changes, report/export generation, access denied, backup/restore.
- [ ] Report cache/export/search/autocomplete/offline snapshots не инвалидируются при membership, invite, account/category/transaction или password/session changes.
- [ ] Transfer deny errors/logs раскрывают hidden side: owner, account name, balance, household, membership status или какая сторона недоступна.
- [ ] XSS payload в display name, account/category name или transaction description исполняется в PWA/Android UI.
- [ ] SQL/NoSQL injection payload в filters/search/reports меняет область доступа или ломает запрос с unsafe diagnostics.
- [ ] В репозитории, markdown, frontend/mobile bundles, Docker image layers, logs или issue artifacts найдены production secrets.
- [ ] Production secret manager / protected env var схема не утверждена для выбранного deployment.
- [ ] Backup storage доступен runtime-приложению на удаление или попадает в локальную разработку, public bucket, chat/issue attachments.
- [ ] Dependency scan показывает critical/high CVE в auth, crypto, session, parser, ORM или web framework без принятого remediation.

## P2 follow-up gates

- [ ] HSTS включен до публичного запуска.
- [ ] 2FA/passkeys decision оформлен до public/SaaS или хранения более чувствительных секретов.
- [ ] UI просмотра/отзыва активных сессий запланирован post-MVP.
- [ ] Formal data retention/account deletion policy согласована до публичного запуска.
- [ ] Monitoring/SIEM use cases для brute force, подозрительных authz denies и массового доступа запланированы.

## Mapping к API surfaces и QA scenarios

| Surface | API routes / scope | Security gates | QA scenarios / RG | Требуемые доказательства |
| --- | --- | --- | --- | --- |
| Auth registration/login | `POST /api/v1/users`, `POST /api/v1/sessions`, `GET /api/v1/users/me` | Password hashing Argon2id/bcrypt, neutral email behavior, no user enumeration, rate limit, session fixation defense | AS-REG-01..02, SEC-AUTH-01, SEC-RATE-01, RG-07, RG-10 | Automated auth tests, password storage review, response golden tests, rate-limit test output |
| Sessions | `GET/DELETE /api/v1/sessions/current`, `DELETE /api/v1/sessions`, token/cookie storage | HttpOnly/Secure/SameSite cookies or platform secure storage, logout/revocation, refresh rotation, password reset and membership invalidation | SEC-AUTH-02..03, PRIV-LEAVE-01, RG-05, RG-07 | Session revocation tests, cache invalidation tests, config evidence for cookie/token storage |
| Password reset | `POST /api/v1/password-resets`, `POST /api/v1/password-resets/confirmations` | One-time short-lived hashed token, neutral response, reset token invalidation, revoke old sessions, rate limit, no token logging | SEC-RESET-01..02, SEC-RATE-01, RG-07, RG-08, RG-10 | Token lifecycle tests, replay/expiry tests, log inspection, old refresh token rejection proof |
| Invites | `GET/POST /api/v1/households/{householdId}/invites`, `GET /api/v1/invites/{inviteId}`, `POST /api/v1/invites/{inviteId}/accept|decline|revoke|resend` | Active member management only, token-bound accept/decline, hashed one-time token, expiry/revoke/replay protection, no shared access before accept | AS-FAM-02, NEG-MEM-01, SEC-INV-01..02, SEC-RATE-01, RG-05, RG-07 | Invite lifecycle tests, resend no-token evidence, former/invited denial tests, log inspection |
| Membership/Household | `/api/v1/households*`, `/api/v1/memberships*`, `/api/v1/households/{householdId}/leave-requests` | Active membership required, former/invited deny, session/access/report/export cache invalidation on status changes | AS-FAM-01..03, NEG-MEM-01..02, PRIV-LEAVE-01..02, RG-05, RG-09 | Membership predicate tests, stale id/session tests, cache invalidation trace |
| Accounts | `/api/v1/accounts`, `/api/v1/accounts/{accountId}` and state endpoints | Personal owner only, shared active member only, neutral direct id errors, no hidden counts, immutable ownership in MVP | AS-ACC-01..04, NEG-IDOR-01..03, PRIV-VIS-01..02, RG-01, RG-02, RG-10 | API integration tests across A/B/C/Invited/Former, response snapshots |
| Transactions | `/api/v1/transactions`, `/api/v1/transactions/{transactionId}` and restore/delete/void | Inherit account scope, all referenced ids visible, manual source only, no partial write, soft delete/restore authz | AS-OPS-01..04, NEG-IDOR-04, NEG-CAT-01, RG-01, RG-02, RG-10 | Transaction authz tests, referenced-id neutral errors, no partial write evidence |
| Transfers | `transactionType = transfer` on `/api/v1/transactions*` | Only `personal_same_owner` and `household_same_household`, hidden-side neutrality, atomic balance effects, no personal/shared in MVP | NEG-TRN-01..04, RG-03, RG-04, RG-06, RG-08, RG-12 | TR-RG-01..10 evidence, golden errors, atomicity/concurrency tests, log inspection |
| Categories | `/api/v1/categories`, `/api/v1/categories/autocomplete` | Personal category owner only, household category active member only, usage does not leak hidden personal operations | AS-CAT-01..03, NEG-CAT-01, RG-01, RG-02, RG-10 | List/detail/autocomplete tests, category assignment denial tests |
| Reports | `/api/v1/reports/summary`, `/category-breakdown`, `/account-balances`, `/cash-flow`, `/transactions` | Authenticated only, canonical report modes, filter before aggregate, no hidden counts/facets, viewer-scoped cache keys | AS-REP-01..04, NEG-REP-01, RG-06, RG-08, RG-10 | Report pipeline review, visibleAccountIds tests, cache key/invalidation evidence, response snapshots |
| Export/delete/leave | `/api/v1/exports*`, `/api/v1/users/me/deletion-requests*`, `/api/v1/households/{householdId}/leave-requests` | Export visible data only, former member excludes former shared data, delete self only, leave revokes shared access | PRIV-EXP-01..02, PRIV-DEL-01, PRIV-LEAVE-01..02, RG-09 | Export fixture diff, deletion/leave tests, privacy review evidence |
| CSRF/CORS/cache | All state-changing routes and sensitive GETs | CSRF token or SameSite strategy for cookie auth, CORS allowlist-only, no wildcard credentials, private/no-store for sensitive responses | SEC-AUTH-*, RG-07, RG-10 | Security config dump, preflight tests, CSRF negative tests, cache header tests |
| Logs/audit/telemetry | All routes, background jobs, report/export/cache, backup/restore | Sanitized audit only, no financial values/tokens/secrets/raw bodies, access denied audited safely | SEC-LOG-01..02, RG-08 | Production-like log samples, grep/scan output, audit schema review |
| Secrets/config | Repo, env, bundles, images, secret manager, deployment config | No production secrets in repo/bundles/logs/images, separate dev/staging/prod, fail closed, rotation plan, least privilege | SEC-SECRET-01, RG-11 | Secret scan output, config review, deployment evidence, rotation/runbook evidence |
| Backups/restore | DB, audit logs, backup storage, migration process | Encrypted backups, isolated storage, RPO/RTO <= 24h for closed MVP, restore tested on separate env, tenant boundaries preserved | SEC-BACKUP-01, RG-07 | Backup job proof, encryption/access evidence, restore test report, migration rollback plan |

## Чеклист

### Аутентификация

- [ ] `user_id` is immutable and email/login is not used as a security boundary.
- [ ] Passwords are stored only as salted Argon2id or bcrypt hashes with approved cost parameters.
- [ ] Plaintext password storage, reversible password encryption and custom password hashing are absent.
- [ ] Password policy requires at least 12 characters and checks common/compromised passwords without relying only on character complexity.
- [ ] Registration/login/reset responses are account-neutral and do not reveal whether email exists.
- [ ] Email verification risk is explicitly accepted if closed MVP ships without verification for invite/reset flows.

### Сессии

- [ ] Cookie auth uses `HttpOnly`, `Secure`, `SameSite=Lax` or `Strict`; token auth uses platform secure storage.
- [ ] Frontend does not store session/refresh tokens in LocalStorage when secure cookies or platform storage are available.
- [ ] Access tokens are short-lived; refresh tokens are rotation-capable and revocable.
- [ ] Logout invalidates current server-side session or refresh token.
- [ ] Logout all invalidates all active server-side sessions or refresh tokens for the current user.
- [ ] Password reset, suspected compromise, account deletion/deactivation and membership `left`/`revoked` invalidate relevant sessions, access caches and refresh tokens.
- [ ] Session fixation is prevented by issuing a new session after login and password reset.
- [ ] Sensitive API responses use private/no-store cache behavior where applicable.

### Восстановление пароля

- [ ] Reset request endpoint is anonymous, rate limited and always returns neutral accepted semantics.
- [ ] Reset token is one-time, short-lived, generated with cryptographic randomness and stored only as a hash.
- [ ] Old reset tokens are invalidated when a new valid flow supersedes them or after password change.
- [ ] Used, expired, revoked and missing reset tokens cannot be distinguished beyond the approved neutral error policy.
- [ ] Password reset revokes old sessions/refresh tokens and prevents replay.
- [ ] Reset token never appears in logs, audit, telemetry, frontend bundle or API response after delivery.

### Приглашения

- [ ] Create/list/revoke/resend invite requires active membership in the target Household.
- [ ] Accept/decline requires current authenticated user plus verified invite token context.
- [ ] Invite token is one-time, short-lived/expiring, stored only as hash and not interchangeable with `inviteId`.
- [ ] Invite token replay after accept, decline, revoke or expiry is rejected.
- [ ] Resend does not return invite token in API response or logs.
- [ ] Invited Member has no shared financial access before membership becomes active.
- [ ] Former Member has no shared financial access after `left`/`revoked`, including with old ids, cursors, exports, snapshots or sessions.
- [ ] MVP member limit/two-participant assumption is enforced or explicitly accepted with Product/Security.

### Rate limits

- [ ] Login, registration, password reset, resend email and invite endpoints have configured rate limits.
- [ ] Rate limits are applied by account/email where safe, IP/source and device/session signals as appropriate.
- [ ] Rate-limit responses do not reveal account, membership, invite or reset-token existence.
- [ ] Progressive delay, temporary lockout or captcha escalation is defined for anomalous brute-force patterns.
- [ ] Backend/QA evidence includes successful `429` or equivalent deny behavior for repeated login/reset/invite attempts.

### CSRF, CORS и транспорт

- [ ] Cookie-based PWA state-changing routes require CSRF token or approved SameSite strategy.
- [ ] Cross-site simple requests cannot mutate account, transaction, category, report/export, invite, membership, session or password state.
- [ ] CORS uses explicit allowlist for known clients/domains.
- [ ] Wildcard CORS origin with credentials is disabled.
- [ ] Production/staging with real data uses HTTPS only.
- [ ] HSTS decision is recorded before public launch.

### Контроль доступа и нейтральные ошибки

- [ ] Backend applies deny-by-default to every endpoint, job, export, report, autocomplete, debug/support path and background recalculation.
- [ ] Server derives owner/scope from persisted data, not from client-supplied route/body ids.
- [ ] Personal account/category/transaction/report rows are visible only to `ownerUserId`.
- [ ] Shared account/category/transaction/report rows are visible only to active members of the same Household.
- [ ] List/detail/search/autocomplete/report/export/debug use equivalent predicates.
- [ ] Search/autocomplete cannot reveal hidden names, ids, amounts, dates, facets, counts or "partially hidden" messages.
- [ ] Missing and inaccessible objects use the same user-facing neutral response shape.
- [ ] Error `details` never include hidden object names, owner email, amounts, descriptions, tokens, stack traces, SQL text or environment ids.

### Отчеты и переводы

- [ ] Report API supports only `shared_family_report` and `combined_viewer_overview` unless new mode is escalated.
- [ ] `shared_family_report` includes only shared accounts/transactions/categories for requested Household after active membership check.
- [ ] `combined_viewer_overview` includes selected Household shared rows plus personal rows of `viewerUserId == currentUserId` only.
- [ ] Report filters validate supplied `accountIds` and `categoryIds` against visible sets before aggregation.
- [ ] Report cache keys include endpoint, mode, viewer, household, membership/access versions, filters and timezone.
- [ ] Report cache, cursors, exports and offline snapshots are invalidated on membership, invite, account/category/transaction and session-security changes.
- [ ] Transfers allow only same-owner personal-personal and same-household shared-shared.
- [ ] Transfers reject personal/shared, cross-user personal, cross-household shared, cross-currency and non-manual source types in MVP.
- [ ] Transfer create/update/delete/restore applies both sides atomically and never leaves one-sided row or balance/projection effect.

### Логи, аудит и телеметрия

- [ ] Audit events exist for login, failed login, logout, password reset, invite lifecycle, membership lifecycle, account/transaction/category changes, report/export generation, access denied, backup/restore and admin/manual production data access.
- [ ] Audit events contain only safe metadata: timestamp, actor/system id, action, target type/id when safe, scope type/id, result, request id, coarse IP/user-agent if allowed.
- [ ] Logs/audit/telemetry do not contain amounts, balances, report totals, descriptions, account/category names, plaintext email where avoidable, tokens, token hashes unless explicitly needed, passwords, secrets or raw request/response bodies.
- [ ] Denied access audit does not enrich caller-supplied hidden ids with hidden owner, name, balance, description or membership metadata.
- [ ] Production debug logs with request/response body are disabled for financial and auth endpoints.
- [ ] Stack traces, SQL errors and internal environment ids are not returned to users.

### Секреты и конфигурация

- [ ] Production secrets are absent from repository, markdown docs, frontend/mobile bundles, Docker image layers, logs and issue/chat artifacts.
- [ ] Secrets are provided through secret manager or protected platform environment variables with least privilege.
- [ ] Dev, staging and production use different secrets, databases and external endpoints.
- [ ] Application fails closed when required secret is missing or a dev secret is used in production.
- [ ] Secret generation, rotation and incident rotation procedures are documented.
- [ ] Access to production secrets is logged/audited.
- [ ] Production runtime DB credentials have minimum necessary privileges and are not administrative roles.
- [ ] Production dumps are not used in local development or QA without anonymization and explicit approval.

### Backups и восстановление

- [ ] Production database and audit logs have automatic encrypted backups.
- [ ] Backup storage is isolated from runtime app credentials; runtime app cannot delete backups.
- [ ] Closed MVP RPO is no more than 24 hours and RTO is no more than 24 hours, or a stricter accepted value is documented.
- [ ] Restore was tested successfully at least once on a separate environment before MVP release.
- [ ] Restore evidence proves tenant boundaries: personal ownership and Household separation are preserved.
- [ ] Backup and restore procedures are audited.
- [ ] Risky migrations touching financial tables require fresh backup and rollback/restore plan.
- [ ] Backups do not go to local development, public buckets, issue trackers, chat attachments or unprotected file shares.

### Контроль out-of-scope и safe capture

- [ ] MVP contains no `/api/v1/imports`, `/api/v1/import-jobs`, `/api/v1/files/imports`.
- [ ] MVP contains no `/api/v1/bank-connections`, `/api/v1/bank-accounts`, `/api/v1/bank-api/*`.
- [ ] MVP contains no full import endpoints such as `/api/v1/sms-imports`, `/api/v1/push-imports`, `/api/v1/notifications/push-tokens`; capture endpoints, if present, are limited to user-initiated screenshot OCR draft lifecycle.
- [ ] MVP contains no `/api/v1/broker-connections`, `/api/v1/external-credentials`.
- [ ] Transaction create/update flows create financial transactions only after manual entry or user-confirmed capture draft; raw `sms`/`push` source values cannot create transactions directly.
- [ ] Capture draft flow uses only user-initiated OCR from a selected screenshot, local/on-device before structured draft review; it does not intercept SMS, push notifications or Android notifications.
- [ ] Capture stores only structured capture draft, `idempotencyKey`/`evidenceHash`, confidence/metadata and status `pending`/`confirmed`/`discarded`.
- [ ] MVP has no fields, tables, settings, secrets, logs or backups intended to store bank passwords, bank/API/broker tokens, SMS codes, push secrets, raw SMS/push/notification body, card numbers, IBAN/account requisites or raw bank statements.

## Обязательные доказательства перед MVP release

- [ ] QA report showing RG-01..RG-12 pass, with failed/retried runs linked and final green run identified.
- [ ] Automated API/security test output for AS-*, NEG-*, SEC-* and PRIV-* scenarios using Owner A, Member B, Other C, Invited Member and Former Member fixtures.
- [ ] Auth/session evidence: password hash review, token/cookie config, logout/revocation tests, password-reset session invalidation tests.
- [ ] Rate-limit evidence for login, registration, password reset, resend and invite flows.
- [ ] CSRF/CORS evidence: negative CSRF tests for cookie auth and CORS preflight/config proving no wildcard credentials.
- [ ] Authz evidence mapping endpoints to predicates for accounts, transactions, categories, reports, transfers, exports, memberships and invites.
- [ ] Neutral-error golden tests comparing missing vs inaccessible ids and invalid vs inaccessible invite/reset/reference contexts.
- [ ] Report evidence: pipeline/code review proving visibleAccountIds before aggregation; tests for both report modes; no hidden counts/facets snapshots; cache key/invalidation proof.
- [ ] Transfer evidence: TR-RG-01..10, including hidden-side neutrality, atomicity, concurrency and log safety.
- [ ] Log/audit evidence: production-like log/audit samples or scan output proving no amounts, descriptions, account/category names, passwords, reset/invite/session/refresh tokens, secrets or raw financial payloads.
- [ ] Secret evidence: repo/bundle/image scan output, deployment secret-source review and rotation/runbook evidence.
- [ ] Backup/restore evidence: encrypted backup job proof, access control proof, restore test report on separate environment, RPO/RTO measurement and tenant-boundary verification.
- [ ] Dependency evidence: dependency scan/SBOM with no unaccepted critical/high CVEs in auth, crypto, session, parser, ORM or web framework components.
- [ ] Out-of-scope evidence: API route inventory, schema/config scan and sourceType tests proving imports/bank API/broker credentials, SMS/push/notification interception and raw SMS/push storage are absent/rejected; screenshot OCR capture draft lifecycle and dedup evidence are covered if enabled.
- [ ] Security sign-off note listing all P2 follow-ups, accepted residual risks and explicit owner/date for each.

## Триггеры эскалации

Escalate to Security Architect/Product/Legal/Operations before release if any trigger appears:

- A new required security decision is needed beyond accepted MVP docs.
- Product asks to show personal accounts, transactions, categories, reports, balances, aggregates or exports to another Household member.
- Product asks to allow personal/shared, cross-user personal or cross-household shared transfers.
- Family model expands beyond two active members or needs roles, children, delegated access or granular privacy.
- Former members must retain historical shared access after leaving or being revoked.
- Public launch, SaaS commitment, jurisdiction/compliance decision, formal retention/deletion SLA or 2FA/passkeys decision becomes part of MVP.
- Field-level encryption, client-side encryption, KMS/HSM, production secret manager or master-key storage decision is required and not already approved.
- Support/admin/debug tooling needs to read financial values or hidden user data.
- Report/export/debug cache cannot be scoped and invalidated by viewer, household, membership and access versions.
- Restore fails, backup is incomplete, backup access is too broad or there is any risk of financial data loss.
- Critical authz/privacy defect, financial data leak, secret leak or repeated failure of security acceptance checks is found.
- Imports, bank API, broker API, full SMS/push integrations, SMS/push/notification interception, external credentials, raw SMS/push/notification body storage or raw bank statements enter scope.

## Explicit out-of-scope для MVP

The following are out of scope and must not ship in MVP:

- File imports, import jobs, uploaded bank statements, CSV/Excel import parsing and import preview flows.
- Bank API, broker API, bank connections, broker connections, external payment integrations and automatic synchronization.
- Storage or processing of bank tokens, bank passwords, broker credentials, bank/API keys, SMS codes, push secrets, card numbers, IBAN/account requisites or raw bank statements.
- Full SMS import, push import, push token storage, SMS/push/notification interception and notification credential storage. The only allowed capture-draft flow is user-initiated OCR from a selected screenshot into pending drafts without raw body server-side storage.
- Any endpoint, table, config field, environment secret, mobile/frontend bundle value, audit field, backup content or hidden feature flag created for the above.

If any out-of-scope item appears in implementation, schema, API inventory, config, logs or backup, classify as P0 and escalate before further release work.

## Definition of done

- [ ] All P0 and P1 release blockers are closed.
- [ ] Checklist items for auth/session/password reset/invite/rate limit/CSRF/CORS/log masking/secrets/backups/restore are complete or explicitly classified with severity and owner.
- [ ] API surface mapping has evidence for each covered route group.
- [ ] QA/backend evidence is attached for RG-01..RG-12 and TR-RG-01..10 where transfer API is present.
- [ ] Logs, secrets, backups and restore gates have concrete scan/test/runbook evidence.
- [ ] Out-of-scope imports/bank API/SMS/push credentials, SMS/push/notification interception and raw SMS/push/notification server-side storage are absent and verified; screenshot OCR capture, if enabled, is draft-only and user-confirmed.
- [ ] Any remaining P2 risks are documented with owner and post-MVP target.
