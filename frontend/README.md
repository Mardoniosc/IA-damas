# Frontend (Angular + TypeScript)

`frontend/damas-ui` is an Angular 21 workspace, scaffolded in G15 with the Angular CLI 21.0.2
already installed on the development machine (`ng new --skip-install`).

## Status

- Source written: board model (`src/app/board.ts`), API client (`api.service.ts`), workbench
  page (`app.ts` / `app.html` / `app.css`), unit tests for the board model (`app.spec.ts`), and
  a dev-server proxy (`proxy.conf.json`: `/api` → `http://127.0.0.1:8765`).
- **Dependencies are not installed yet.** `npm install --offline` failed because the local npm
  cache does not hold every package (first miss: `@babel/helper-annotate-as-pure`). Installing
  downloads packages from `registry.npmjs.org`, which needs the owner's approval.
  **Until then the UI is neither built nor verified in a browser.**

## Run (after `npm install`)

```bash
cd backend && DAMAS_ENGINES_CONFIG=../config/engines.toml DAMAS_DATABASE_URL=sqlite:///../var/damas_kb.sqlite3 python -m uvicorn --factory damas_ai.api.app:create_app --app-dir src --host 127.0.0.1 --port 8765
```

```bash
cd frontend/damas-ui && npm start
```

Open http://localhost:4200.

## Design rules

- The UI talks only to the backend API. It never talks to engines and never decides legality
  (ADR-001).
- Board numbering mirrors the backend (`docs/architecture/position-representation.md`): a1 = 29
  on 8x8, a1 = 46 on 10x10. The unit tests pin this.
- Confidence and its reasons are always shown. A single-source (Brazilian) decision displays a
  warning that confidence is capped at "low".
