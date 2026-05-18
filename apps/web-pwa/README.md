# Web PWA Workspace

Ownership: PWA workers assigned by the orchestrator only.

Manual-first MVP skeleton for a Russian household finance PWA.

## Run

```powershell
npm.cmd install
npm.cmd run dev
```

## Verify

```powershell
npm.cmd run test
npm.cmd run build
```

## Production path prefix

Local development keeps the app at `/` and the API at `http://127.0.0.1:8000`.
For the shared production host, build Finance for `/finance/` and proxy API
requests through `/finance-api`:

```powershell
$env:VITE_BASE_PATH = "/finance/"
$env:VITE_API_BASE_URL = "/finance-api"
npm.cmd run build
Remove-Item Env:\VITE_BASE_PATH
Remove-Item Env:\VITE_API_BASE_URL
```

The generated manifest uses `start_url` and `scope` from the Vite base path, and
the service worker registers under that same scope instead of claiming `/`.

## Current scope

- React + TypeScript + Vite app shell.
- Web app manifest, SVG app icon, and production-only service worker registration.
- Sections: session, overview, accounts, categories, operations, transfers, reports.
- Report modes in user-facing Russian vocabulary:
  - `shared-family-report`: Общий семейный отчет.
  - `combined-viewer-overview`: Сводный обзор участника.
- Typed API abstraction in `src/api/client.ts` with mock data until generated OpenAPI client is ready.
- No bank import, SMS, push, or broker UI in the MVP skeleton.
