# Release git worker report

Date: 2026-05-18
Worker: RELEASE-GIT-WORKER
Scope: local git/release preparation and GitHub publication attempt for project folder `Финансы`.

## Summary

Status: local release preparation completed; GitHub publication blocked by missing GitHub CLI.

Initial state:
- `C:\Users\style\Documents\Codex\Финансы` was not a git repository.
- `git` was available: `git version 2.54.0.windows.1`.
- `gh` was not available in PATH; no token was requested or printed.

Repository action:
- Initialized a local git repository in `C:\Users\style\Documents\Codex\Финансы`.
- Used allowlist staging only. No blind `git add -A` was used.
- Intended release tag: `v0.1.0-mvp`.

## Included Policy

Included:
- Source and project docs under explicit roots: `api`, `apps`, `db`, `docs`, `ops`, `packages`, `qa`, `security`.
- Root release/project metadata: `.gitignore`, `README.md`, `AGENTS.md`, `Ru_OrchestratorRules.md`, `Ru_SubagentFirstFinishNew.md`.
- Curated MVP evidence markdown: `MVP_EVIDENCE/*.md`, `MVP_EVIDENCE/reports/**`, and markdown-only summaries under `MVP_EVIDENCE/test-runs/*.md`.

Excluded / left local:
- `.env`, `.env.*` except `.env.example`.
- `node_modules`, Python virtualenvs, Python caches, build/dist folders, Android `.gradle`, APK/AAB/build outputs, `local.properties`.
- Runtime logs, temp DB files, SQLite/DB dumps/backups, token/session/key/keystore-like files.
- Raw evidence: `MVP_EVIDENCE/screenshots/**`, raw `MVP_EVIDENCE/test-runs/**` such as `.txt`, `.json`, `.xml`, `.log`, browser profiles, cookie jars, DOM dumps and runner scripts.
- Generated scanner/evidence outputs: `artifacts/evidence/**`, `security/scans/**`, `qa/traces/**`.

## Gitignore Audit

`.gitignore` was updated to strengthen release exclusions:
- Added keystore/certificate/container formats: `*.jks`, `*.keystore`, `*.p12`, `*.pfx`.
- Added token/session-like local files: `*.token`, `*.session`.
- Added generic cache/temp/database/dump/backup ignores.
- Added npm/yarn debug logs.
- Added explicit raw MVP evidence exclusions while allowing curated markdown reports.
- Re-closed `security/scans/**` after README allow rules.

## Secret Scan Evidence

Checks performed against the staged set:
- Path scan for generated/cache/secret-bearing names.
- Content scan for bearer/session/access/refresh token terms.
- Narrow scan for real-looking bearer tokens, JWTs, GitHub tokens, AWS key IDs and private key headers.
- URL scan for credential-bearing URLs.
- `.env` handling check.

Findings:
- No real bearer/session/access/refresh token values found in staged files.
- No GitHub token-like values found.
- No private key blocks found.
- No non-redacted credential-bearing URL found.
- `apps/backend/.env.example` is staged intentionally and contains only local placeholders/comments.
- Known benign values remain staged as dev/test-only evidence or fixtures:
  - `demo-password-only` is a documented dev/demo password only.
  - `correct horse battery staple` is used in backend tests.
  - `raw-token-must-not-echo` is a negative redaction test fixture.
  - `<generated-password-redacted>` appears only as an already redacted placeholder in evidence.

## GitHub Publication

Publication was not attempted because `gh` is not installed or not available in PATH.

Blocker:
- GitHub CLI unavailable, so authentication and `gh repo create`/push cannot be performed safely without requesting or exposing credentials.

Safe next command after installing/authenticating `gh` outside chat:

```powershell
gh auth status
gh repo create "Финансы" --private --source . --remote origin --push
git push origin v0.1.0-mvp
```

If GitHub rejects the Cyrillic repository name `Финансы`, stop and request an explicit naming decision. Do not silently transliterate.

## Handoff

Local repo is prepared for initial commit/tag when the staged set remains unchanged and scans stay clean.
Final commit hash, tag status, and final `git status` are reported in the parent handoff response.
