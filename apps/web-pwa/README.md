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

## Current scope

- React + TypeScript + Vite app shell.
- Web app manifest, SVG app icon, and production-only service worker registration.
- Sections: session, overview, accounts, categories, operations, transfers, reports.
- Report modes in user-facing Russian vocabulary:
  - `shared-family-report`: Общий семейный отчет.
  - `combined-viewer-overview`: Сводный обзор участника.
- Typed API abstraction in `src/api/client.ts` with mock data until generated OpenAPI client is ready.
- No bank import, SMS, push, or broker UI in the MVP skeleton.
