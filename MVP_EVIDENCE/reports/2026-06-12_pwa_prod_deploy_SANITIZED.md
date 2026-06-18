# PWA production deploy, sanitized report

Дата: 2026-06-12
Роль: ограниченный DevOps/release worker
Проект: Finance
Workspace: `C:\Users\style\Documents\Codex\Финансы`

## Статус

PASS. PWA production build задеплоен на существующий production host по approved flow.

## Approved flow

Источник процесса:

- `apps/web-pwa/README.md`
- `docs/deploy/finance-production-install.md`
- `docs/deploy/rocketflow-path-prefix-handoff.md`

Зафиксированный процесс:

- PWA workspace: `apps/web-pwa`.
- Локальные gates: `npm.cmd run test`, затем production build.
- Production build env: `VITE_BASE_PATH=/finance/`, `VITE_API_BASE_URL=/finance-api`.
- Deployment target: статические файлы из `apps/web-pwa/dist` под `/var/www/finance/current`.
- Public frontend path: `http://45.10.110.42/finance/`.
- Public backend proxy health: `http://45.10.110.42/finance-api/health`.

## Build identity

- Git commit: `26b487d61b7d2d6de704f0a632bcb08ff7f240f7`.
- PWA release id: `20260612T091555Z-26b487d61b7d`.
- Previous release target: `/var/www/finance/releases/20260608T002838Z-6ce31f5`.
- Current release target: `/var/www/finance/releases/20260612T091555Z-26b487d61b7d`.
- Public JS asset version: `/finance/assets/index-BxFzW0Su.js`.
- Public CSS asset version: `/finance/assets/index-BGpCKtps.css`.

## Commands, sanitized

Discovery:

```powershell
Get-Content .\AGENTS.md
Get-Content .\Ru_OrchestratorRules.md
Get-Content .\Ru_SubagentFirstFinishNew.md
rg -n "(pwa|deploy|production|prod|...)" .\README.md .\docs .\ops .\apps\web-pwa ...
Get-Content .\apps\web-pwa\README.md
Get-Content .\apps\web-pwa\package.json
Get-Content .\docs\deploy\finance-production-install.md
Get-Content .\docs\deploy\rocketflow-path-prefix-handoff.md
```

Local gates:

```powershell
cd apps\web-pwa
npm.cmd run test
$env:VITE_BASE_PATH="/finance/"
$env:VITE_API_BASE_URL="/finance-api"
npm.cmd run build
Remove-Item Env:\VITE_BASE_PATH
Remove-Item Env:\VITE_API_BASE_URL
```

Deploy:

```powershell
tar -czf <temp>\finance-pwa-20260612T091555Z-26b487d61b7d.tar.gz -C .\apps\web-pwa\dist .
scp <archive> root@45.10.110.42:/tmp/finance-pwa-20260612T091555Z-26b487d61b7d.tar.gz
ssh root@45.10.110.42 <remote deploy script>
```

Remote deploy script actions, summarized:

```bash
mkdir -p /var/www/finance/releases/20260612T091555Z-26b487d61b7d
tar -xzf /tmp/finance-pwa-20260612T091555Z-26b487d61b7d.tar.gz -C /var/www/finance/releases/20260612T091555Z-26b487d61b7d
chown -R finance:finance /var/www/finance/releases/20260612T091555Z-26b487d61b7d
chmod directories 755
chmod files 644
ln -sfn /var/www/finance/releases/20260612T091555Z-26b487d61b7d /var/www/finance/current.next
mv -Tf /var/www/finance/current.next /var/www/finance/current
rm -f /tmp/finance-pwa-20260612T091555Z-26b487d61b7d.tar.gz
```

Verification:

```powershell
ssh root@45.10.110.42 "nginx -t; readlink -f /var/www/finance/current"
curl.exe http://45.10.110.42/finance/
curl.exe http://45.10.110.42/finance/manifest.webmanifest
curl.exe -I http://45.10.110.42/finance/assets/index-BxFzW0Su.js
curl.exe http://45.10.110.42/finance-api/health
curl.exe http://45.10.110.42/finance/sw.js
```

## Results

Local gate:

- `npm.cmd run test`: PASS, 4 test files passed, 43 tests passed.
- `npm.cmd run build`: PASS, Vite production build completed.

Build artifact inspection:

- `dist/index.html`: PASS, references `/finance/manifest.webmanifest`, `/finance/pwa-icon.svg`, `/finance/assets/index-BxFzW0Su.js`, `/finance/assets/index-BGpCKtps.css`.
- `dist/manifest.webmanifest`: PASS, `start_url` and `scope` are `/finance/`.
- `dist/sw.js`: PASS, service worker scope-safe behavior preserved; API prefixes are excluded from shell cache.

Remote deploy:

- SSH access: PASS via existing configured `root@45.10.110.42` key.
- Release switch: PASS, `current` symlink now resolves to `/var/www/finance/releases/20260612T091555Z-26b487d61b7d`.
- Remote SHA256 for deployed files matched local SHA256:
  - `index.html`: `5d2fc62fb3d159be7d647bab52a60593352633d2cbf6420ef8a98b3b0f818123`
  - `manifest.webmanifest`: `23ae090c2961076254e9015bab16dbba3fa10a6d7a05d06eaea590acd2182ad8`
  - `sw.js`: `0aaedaf8d30b892b4cd7faa192b473d2803a285e5753bf87935db0e6ab99498f`
  - `assets/index-BxFzW0Su.js`: `952270a476dd77f2c0c650b7a401422709b7cf4ac5a3b60cf3fbe690f4515cb2`
  - `assets/index-BGpCKtps.css`: `b4ee917c80ccad5e2a337da34b34a06b4acdbbbc995e98ec52e7af34db2ee190`

Public smoke:

- `http://45.10.110.42/finance/`: PASS, HTTP 200, HTML references `/finance/assets/index-BxFzW0Su.js`.
- `http://45.10.110.42/finance/manifest.webmanifest`: PASS, HTTP 200, `start_url=/finance/`, `scope=/finance/`.
- `http://45.10.110.42/finance/assets/index-BxFzW0Su.js`: PASS, HTTP 200.
- `http://45.10.110.42/finance-api/health`: PASS, HTTP 200, body `{"status":"ok"}`.
- `nginx -t`: PASS.

UI/API authenticated smoke:

- Not run. No QA credentials were provided in scope, and no secrets/tokens/cookies were printed, requested, or stored.

## Rollback

Rollback target discovered:

```bash
/var/www/finance/releases/20260608T002838Z-6ce31f5
```

Rollback command pattern, sanitized:

```bash
ln -sfn /var/www/finance/releases/20260608T002838Z-6ce31f5 /var/www/finance/current.next
mv -Tf /var/www/finance/current.next /var/www/finance/current
nginx -t
```

No nginx reload is required for the static symlink switch unless operational policy requires it.

## Secret scan

PASS. This report and companion `secret_scan_summary.json` contain no secrets, tokens, cookies, passwords, private keys, production env dumps, raw financial data, or credential material.

Companion file:

- `MVP_EVIDENCE/reports/secret_scan_summary.json`

## Notes and residual risk

- The production host is currently accessed as plain HTTP IP `http://45.10.110.42/finance/`; service worker registration is intentionally skipped on non-secure non-localhost origins by the PWA code.
- Existing unrelated Android and evidence changes were present in the workspace before this report and were not modified.
