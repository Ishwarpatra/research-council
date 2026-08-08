# Deploying Research Consensus Council to Vercel

This guide outlines how to deploy the **Research Consensus Council** application to Vercel.

---

## Architecture Overview

The repository is configured as a Vercel Monorepo:
* **Frontend:** Built using Vite (`frontend/dist`), deployed automatically to Vercel's global CDN.
* **Backend:** FastAPI application served via Vercel Serverless Functions (`@vercel/python`) using the handler entrypoint at [`api/index.py`](file:///c:/Users/DELL/Desktop/codego/research-council/api/index.py).

---

## Quick Start: Deployment Options

### Option A: Deploy via Vercel CLI (Recommended)

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Deploy to Preview Environment:**
   Run `vercel` from the root directory:
   ```bash
   vercel
   ```

3. **Deploy to Production Environment:**
   ```bash
   vercel --prod
   ```

---

### Option B: Deploy via Vercel Dashboard (GitHub / GitLab / Bitbucket)

1. Push your repository to GitHub / GitLab / Bitbucket.
2. Go to [Vercel Dashboard](https://vercel.com/new) and click **Import Project**.
3. Select your `research-council` repository.
4. **Project Settings:**
   - **Framework Preset:** Vite
   - **Root Directory:** `./`
   - **Build Command:** `cd frontend && npm install && npm run build`
   - **Output Directory:** `frontend/dist`
5. Configure Environment Variables (see below).
6. Click **Deploy**.

---

## Environment Variables Configuration

Set these variables in the Vercel Dashboard (**Project Settings** -> **Environment Variables**):

| Variable | Recommended Value | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | `stub` or `openai` | Primary LLM provider (`stub`, `ollama`, or `openai`) |
| `FALLBACK_PROVIDER` | `stub` | Fallback LLM provider |
| `OPENAI_API_KEY` | `sk-...` | OpenAI API key (required if `LLM_PROVIDER=openai`) |
| `DB_PATH` | `/tmp/council.db` | Path to SQLite database (serverless function writable) |
| `RETRIEVAL_BACKEND` | `hybrid` | RAG mode (`hybrid` or `chroma`) |

---

## Important Serverless Function Notes

1. **REST APIs vs WebSockets (`ws://`):**
   Vercel Serverless Functions are stateless HTTP functions (AWS Lambda under the hood). While all standard REST endpoints (`/api/deliberate`, `/api/deliberation/status`, `/api/archive`, etc.) work natively, persistent WebSockets are not supported by serverless runtimes.
   
2. **Persistent Storage:**
   Vercel Serverless Functions provide a read-only filesystem with a temporary `/tmp` directory. For persistent database storage across cold restarts, set up a remote database (e.g. Turso, Postgres, or Supabase).

3. **Hybrid Deployment (Optional):**
   If long-lived WebSockets are required for live deliberation streaming, you can deploy the Python FastAPI backend to Render / Railway / Fly.io and set the frontend Vercel environment variables:
   ```env
   VITE_API_REST_URL=https://your-backend.onrender.com
   VITE_API_WSS_URL=wss://your-backend.onrender.com
   ```
