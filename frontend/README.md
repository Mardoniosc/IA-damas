# Frontend (Angular + TypeScript)

`frontend/damas-ui` is an Angular 21 workspace, scaffolded in G15 with the Angular CLI 21.0.2
already installed on the development machine (`ng new --skip-install`).

## Status

- Source written: board model (`src/app/board.ts`), API client (`api.service.ts`), workbench
  page (`app.ts` / `app.html` / `app.css`), unit tests for the board model (`app.spec.ts`), and
  a dev-server proxy (`proxy.conf.json`: `/api` → `http://127.0.0.1:8765`).
- Dependencies installed with the owner's approval (2026-11-21): `npm install` (470 packages,
  278 MB, `package-lock.json` committed). npm 11 blocked the install scripts of 4 packages
  (esbuild, lmdb, msgpackr-extract, @parcel/watcher). They were **not** approved, and the build and
  tests work without them.
- `ng build`: OK (193 kB initial, 54 kB transferred), no warnings. `ng test`: 3/3 board-model tests pass.
- Verified in the browser against the live backend (real engines + KB): Brazilian analysis
  (`22-17`, confidence low, single-source warning, move highlighted) and International analysis
  (`34-30`, confidence high, accepted by 3/3 engines, regret table). No server errors.
  **Not verified:** the layout at phone width (the browser pane was closed before that check).

- **Game review tab** (added 2026-11-21): load a PDN file (e.g. a PlayOK `.txt` export) or paste
  PDN text, pick a game, a judge engine and a depth, and step through the game with each move
  labelled (inaccuracy / mistake / blunder) and the engine's preferred move shown on the board.
  Components: `board-view.ts` (shared board), `game-review.ts/.html/.css`. Backend routes:
  `POST /games/parse`, `POST /games/analyze`. Verified in the browser with real PlayOK games.
- Shared form styles (`input`, `select`, `textarea`, `button`) live in `src/styles.css`.

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
