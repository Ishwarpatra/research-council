# Product Requirements Document (PRD)

## 1. Product Overview
The Research Consensus Council is an agentic tool built to automate academic research review. The tool extracts relevant parts of uploaded papers, deliberates on them via a council of 5 specialized agents, and produces a final score and revision feedback report. It provides an appeal interface for authors and quality audits for administrators.

## 2. User Stories

### Story 1: Paper Reviewer / Editor
- **As a** journal editor,
- **I want to** submit a research manuscript file,
- **So that** I get an automated consensus verdict, aggregate scores, and detailed peer reviews grouped by round.

### Story 2: Manuscript Author (Appeal Process)
- **As a** submitting author whose paper was rejected or given major revisions,
- **I want to** submit a text rebuttal against specific critiques,
- **So that** the council re-evaluates the paper incorporating my feedback, updates the appeal status, and records any changed verdict.

### Story 3: System Administrator / Quality Auditor
- **As a** quality assurance manager,
- **I want to** inspect the statistical drift and mean scores of each agent against a human baseline,
- **So that** I can identify bias or score stagnation across deliberations.

### Story 4: Frontend Operator
- **As a** conference organizer,
- **I want to** enter a portal from a landing page, navigate Research/Council/Archive/Audit/Lab/Docs from a single SideNav, watch live deliberation (WebSocket), adjust weights in Settings, and use browser Back or Leave portal to return to landing,
- **So that** I can operate reviews without duplicated top-bar navigation or losing the marketing entry point.

### Story 5: Local Stub Developer
- **As a** developer on Windows,
- **I want to** run the stub API on port **8090** (when 8080 is occupied) with the Vite app pointed at that base URL,
- **So that** I can exercise upload, deliberation, and HITL without Docker.

## 3. Task Breakdown & Timeline (12-Week Roadmap)

### Phase 1: Foundation & Ingestion (Weeks 1-3)
- Initialize environment, dependencies, and DB schema.
- Develop extraction skills (`pdfplumber` tables, citation regex).
- Implement basic unit test framework.

### Phase 2: Agent Council & Engine (Weeks 4-6)
- Setup agent definitions (roles, criteria, weights).
- Program the multi-round deliberation logic (R1 Initial -> R2 Debate -> R3 Consensus).
- Address prompt injection hazards by implementing justification limits.

### Phase 3: Appeals & Audit Features (Weeks 7-9)
- Write non-destructive appeal re-deliberation code using in-memory mock copies.
- Implement quality control audits (`run_monthly_audit`).
- Add interactive Human-in-the-Loop approval sequences.

### Phase 4: API, Interface & QA (Weeks 10-12)
- Host FastAPI (`api.py`) with REST + WebSocket + HITL approve/abort.
- Ship React portal: landing gate, AppShell (TopNav chrome + SideNav views), Docs/Audit/Lab.
- Wire History API for portal enter/leave; GitHub Actions CI (ruff, pytest, Vitest).
- Document local **8090** vs Docker **8080** in SETUP.md.
