# Setup

Local development and container setup for Research Consensus Council (RCC).

## Prerequisites

- Python 3.11+ (CI uses 3.13)
- Node.js 20+ (frontend Vite app)
- Optional: Docker / Docker Compose

## 1. Backend

From the repo root (`research-council-main/`):

```bash
pip install -r requirements.txt
# or: pip install .
cp .env.example .env
```

Edit `.env` as needed. Defaults:

| Variable | Typical local value |
|---|---|
| `LLM_PROVIDER` | `stub` |
| `FALLBACK_PROVIDER` | `stub` |
| `OPENAI_API_KEY` | dummy string if using stub |
| `WEBHOOK_URL` | `http://127.0.0.1:8090/dummy-webhook` |
| `DB_PATH` | `council.db` |

### API port

| Context | Port | How to start |
|---|---|---|
| Docker / `python council.py --api` | **8080** | Default |
| Local Windows (recommended) | **8090** | Avoids clashes with Oracle TNSLSNR on 8080 |

Start on 8090 (matches frontend defaults):

```bash
python -c "import api; api.start_server('127.0.0.1', 8090)"
```

Or:

```bash
python council.py --api
```

then point the frontend at 8080 via `frontend/.env` (see below).

Health check: `GET http://127.0.0.1:8090/api/settings`

## 2. Frontend

```bash
cd frontend
cp .env.example .env   # defaults to http://127.0.0.1:8090
npm install
npm run dev
```

Open `http://localhost:3000/` (or the port Vite prints).

### Portal UX

1. **Landing** — marketing page (`LandingView`). **Access Portal** / **Start Validation** enter the workspace.
2. **Portal** — `AppShell`: **TopNav** (brand + notifications + Settings only) and **SideNav** (Research / Council / Archive / Audit / Lab / Docs).
3. **Browser Back** / **Leave portal** return to the landing page (history `pushState` / `popstate`; session flag `rcc_portal`).

Workspace navigation lives only in the SideNav (TopNav does not duplicate view links).

### Env overrides

`frontend/.env`:

```
VITE_API_REST_URL=http://127.0.0.1:8090
VITE_API_WSS_URL=ws://127.0.0.1:8090
```

## 3. Tests

```bash
# Python
pytest tests/test_units.py tests/test_e2e.py

# Stub stress suite (starts or uses API on 8090)
python tests/stress_test.py --base-url http://127.0.0.1:8090 --start-server

# Frontend
cd frontend && npm test
```

## 4. Docker Compose

```bash
docker compose up --build
```

- API: `http://localhost:8080`
- SPA (nginx): `http://localhost:3000` → API URLs use host `8080`

Compose pins **8080** inside the container network; local Windows stub work should prefer **8090**.

## 5. Persistence

Mount durable storage for:

- `DB_PATH` (SQLite)
- `CHROMA_DB_PATH` (vector index; default `/app/data/chroma_db` in Docker)

See [ARCHITECTURE.md](ARCHITECTURE.md) and [README.md](README.md).
