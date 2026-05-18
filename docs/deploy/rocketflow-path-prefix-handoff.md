# RocketFlow path-prefix handoff

## Server state

- Finance is prepared beside RocketFlow on `45.10.110.42`.
- RocketFlow remains on `/` and `/api/`; do not move it to `/rocket/` or `/rocket-api/`.
- Finance nginx routes are already present:
  - `/finance/` serves `/var/www/finance/current/`.
  - `/finance-api/` proxies to `http://127.0.0.1:8081/`.
- Finance backend service is prepared as `finance-backend.service`, but it is not enabled or started until an artifact exists.
- Do not change RocketFlow service, dirs, DB, roles, `/`, `/api/`, or proxy `127.0.0.1:8080`.

## Required RocketFlow constraint

Any future RocketFlow work must preserve the current public contract:

- `/` continues serving RocketFlow frontend.
- `/api/` continues proxying RocketFlow backend on `127.0.0.1:8080`.
- Finance must remain isolated under `/finance/` and `/finance-api/`.

## Finance deployment follow-up

When Finance artifacts are ready:

1. Put backend files under `/opt/finance/current`.
2. Ensure the service command exists at `/opt/finance/current/bin/finance-backend` or update only `finance-backend.service` for the actual Finance command.
3. Keep backend binding to `127.0.0.1:8081` using `/etc/finance/backend.env` with `FINANCE_BACKEND_*` variables only.
4. Build frontend with `VITE_BASE_PATH=/finance/` and `VITE_API_BASE_URL=/finance-api`, then put frontend files under `/var/www/finance/current`.
5. Run `nginx -t` before any nginx reload.
6. Verify RocketFlow before and after:
   - `curl http://127.0.0.1/`
   - `curl http://127.0.0.1/api/`
7. Verify Finance:
   - `curl http://127.0.0.1/finance/`
   - `curl http://127.0.0.1/finance-api/`

Detailed Finance-only runbook: `docs/deploy/finance-production-install.md`.

No secrets are stored in this handoff file.
