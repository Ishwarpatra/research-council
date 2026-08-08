# Documentation

This directory keeps project documentation separate from runtime code and deployment files.

## Current documentation

- [`architecture/ADK.md`](architecture/ADK.md) — Agent Development Kit, orchestration, tools, and contracts.
- [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md) — System architecture, data model, and deployment constraints.
- [`architecture/AGENTS_AND_SKILLS.md`](architecture/AGENTS_AND_SKILLS.md) — Agent and skill responsibilities.
- [`guides/SETUP.md`](guides/SETUP.md) — Local, Docker, and frontend setup instructions.
- [`guides/PRD.md`](guides/PRD.md) — Product requirements and roadmap.
- [`guides/VERCEL.md`](guides/VERCEL.md) — Vercel deployment notes.

## Archived documentation

[`archive/`](archive/) contains older plain-text documentation retained for historical reference. It is not required to run, test, or deploy the project.

## Repository conventions

- Runtime Python modules and deployment configuration remain at the repository root.
- Frontend source and configuration remain under [`frontend/`](../frontend/).
- Reusable scripts remain under [`scripts/`](../scripts/).
- Generated files, local databases, credentials, and build outputs are excluded through `.gitignore`.
