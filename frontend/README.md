# Frontend (Angular + TypeScript)

**Intentionally not scaffolded in G1.**

There is nothing for a UI to show until the Rules Core (G2) and at least one engine adapter
(G3/G4) exist. Generating an Angular workspace now would add a large `node_modules` tree and
framework versions that would be stale by the time a UI is needed.

Plan:

- Scaffold with the Angular CLI version that is current when the first UI-bearing gate starts
  (expected G6, multi-engine analysis view). Record the exact version in an ADR.
- The UI talks only to the FastAPI backend. It never talks to engines and never decides
  legality (ADR-001).
- Board rendering uses the canonical square indexing from
  `docs/architecture/position-representation.md`. Orientation and notation are presentation
  concerns.

Tooling observed on the development machine during G1 (2026-11-20): Node v26.13.1, npm 11.20.0.
