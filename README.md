# Research Consensus Council (RCC)

Multi-agent deliberation consensus system with persistence, real LLM hooks, appeals processing, skill-tree audit/review, and a React portal (landing + workspace).

## Documentation

- **[SETUP.md](SETUP.md)** — Install, ports (8090 local / 8080 Docker), frontend + portal UX
- **[ADK.md](ADK.md)** — Agent Development Kit (agent catalog, skill tree, tools, orchestration, contracts, HITL)
- [ARCHITECTURE.md](ARCHITECTURE.md) — Stack, database schema, UI shell, deployment constraints
- [AGENTS.md](AGENTS.md) — Agent personas, skills, and tool schemas
- [PRD.md](PRD.md) — Product requirements and roadmap

## Setup & Ingestion

Full steps: **[SETUP.md](SETUP.md)**. Short version:

1. `pip install -r requirements.txt` then copy `.env.example` → `.env`.
2. Start API on **8090** locally (recommended on Windows):
   ```bash
   python -c "import api; api.start_server('127.0.0.1', 8090)"
   ```
   `python council.py --api` still defaults to **8080**.
3. Frontend: `cd frontend && npm install && npm run dev` (defaults to API `http://127.0.0.1:8090`).

Environment knobs (see `.env.example`):

- `LLM_PROVIDER` / `FALLBACK_PROVIDER`: `stub` (default), `ollama`, or `openai`
- `OLLAMA_HOST`, `OPENAI_API_KEY`, `WEBHOOK_URL`
- `JINA_API_KEY`, `RETRIEVAL_BACKEND` (`chroma` | `jina` | `hybrid`)
- Optional `council_config.json` for custom weights

## Usage

- **Run Consensus Deliberation:**
  ```bash
  python council.py <paper.pdf>
  ```
- **Review skill tree only (claim grounding, citations, coherence):**
  ```bash
  python council.py --review <paper.pdf>
  ```
- **Submit Appeal:**
  ```bash
  python council.py --appeal <paper.pdf> "rebuttal text here"
  ```
- **Run Quality Audit (monthly drift + audit skill tree):**
  ```bash
  python council.py --audit
  ```
- **Stress suite (stub API load + limits + hallucination + engine batch):**
  ```bash
  python tests/stress_test.py --base-url http://127.0.0.1:8090 --start-server
  ```
  Use port **8090** if 8080 is taken (e.g. Oracle TNSLSNR on Windows).
- **Review Paper Deliberation History:**
  ```bash
  python council.py --history <paper.pdf>
  ```
- **Start HTTP API Server:**
  ```bash
  python council.py --api
  ```
  Default bind: `http://127.0.0.1:8080/`. For local UI pairing, prefer **8090** (see [SETUP.md](SETUP.md)).

### Portal (React)

1. Open the Vite app → **landing page**.
2. **Access Portal** / **Start Validation** → workspace (`AppShell`).
3. **SideNav** switches Research / Council / Archive / Audit / Lab / Docs; **TopNav** is brand + notifications + Settings only.
4. Browser **Back** or **Leave portal** returns to the landing page.

### Jenni.ai note

Jenni has no public developer API. RCC mirrors claim-confidence review locally (`skills/review/claim_grounding.py`). You may manually import a saved `*.report.json` into Jenni’s Library for human verification.

## REST API Endpoints

- `GET /api/papers`: Returns all processed papers.
- `GET /api/reviews?path=<path>`: Returns all 3 rounds of review history for a paper.
- `GET /api/deliberation?path=<path>`: Returns final verdict, aggregate scores, and parsed report.
- `GET /api/settings`: Read current server configurations.
- `POST /api/settings`: Modify criterion weights live (JSON: `{"weights": {...}}`). Weights must sum to 1.0.
- `POST /api/upload`: Upload a manuscript file; returns a server path for deliberation.
- `POST /api/deliberate?path=<path>`: Start deliberation (path must be a file, not a directory).
- `POST /api/approve_round` / `POST /api/abort_round`: HITL gates.
- `GET /api/audit`: Monthly drift + audit skill tree.
- `POST /api/skills/review?path=<path>`: Run review skill tree on a manuscript.
- `POST /api/skills/claim_grounding?path=<path>`: Jenni-style claim grounding (optional `claim_text`).
- `GET /api/skills/tools`: Registered agent-kit tool schemas.
- `GET /api/skills/audit?path=<path>`: Run audit skill tree (optional paper path for consistency checks).
- `WS /api/ws/{paper_id}`: Live deliberation events.

## Data Connections & Volume Persistence

To prevent data loss and ensure that indexed vector search embeddings persist across container lifecycles, deployments must configure persistent volume mounts:

1. **SQLite Database Path:**
   - Mount a persistent directory to the SQLite file path defined by `DB_PATH` (e.g. `/app/data/`).
2. **ChromaDB Vector Store Path:**
   - Mount a persistent volume at the path configured by `CHROMA_DB_PATH` (defaults to `/app/data/chroma_db`).
   - This ensures the `PriorArtValidator` semantic index is not wiped when the container spins down.
   - The local `chroma_db/` folder is excluded from version control in `.gitignore` to prevent committing binary artifacts to repository branches.
