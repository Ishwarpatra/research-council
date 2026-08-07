# System Architecture Documentation

This document describes the stack components, database schemas, and data flow of the Research Consensus Council.

## High-Level Stack

```
   ┌────────────────────────────────────────────────────────┐
   │                  Web User Interface                    │
   │      (HTML5 / CSS / Vanilla JS dark-mode Dashboard)      │
   └───────────────────────────┬────────────────────────────┘
                               │ HTTP API
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │            ThreadingHTTPServer API Gateway             │
   │      - Non-blocking concurrent request routing         │
   │      - /api/papers, /api/reviews, /api/settings        │
   └───────────────────────────┬────────────────────────────┘
                               │ SQLite DB / File IO
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │           Deliberation Engine (SQLite DB)              │
   │      - 3-round multi-agent council processor           │
   │      - Dynamic environment settings & weight tuning    │
   └────────────────────────────────────────────────────────┘
```

- **Backend core:** Python 3.13 standard library.
- **Concurrency:** `ThreadingHTTPServer` prevents API calls (e.g. settings updates, deliberation queries) from blocking while long LLM processing tasks execute in separate threads.
- **Database:** SQLite 3. File-backed data repository with automatic table schema configuration and column migration.
- **Frontend Dashboard:** Dark-mode dashboard built with pure HTML, modern CSS variables (glassmorphism accents), and native JavaScript APIs. Fetches endpoints continuously.

## Database Model & Schema

```
                      ┌───────────────┐
                      │    papers     │
                      └───────┬───────┘
                              │ 1
                              ├───┐
                              │   │ N
                              ▼   ▼
                        ┌───────────────┐
                        │    reviews    │
                        └───────────────┘
```

### 1. `papers` Table
Stores extracted content and hashes:
- `id` (INTEGER PRIMARY KEY)
- `file_path` (TEXT UNIQUE)
- `content_hash` (TEXT)
- `abstract` (TEXT), `methods` (TEXT), `results` (TEXT), `claims` (TEXT)
- `full_text` (TEXT)
- `created_at` (REAL)

### 2. `reviews` Table
Stores reviews generated during round cycles:
- `id` (INTEGER PRIMARY KEY)
- `paper_id` (INTEGER FOREIGN KEY)
- `agent_name` (TEXT)
- `criterion` (TEXT)
- `score` (REAL)
- `justification` (TEXT)
- `evidence` (TEXT JSON list)
- `challenge_target` (TEXT)
- `round_num` (INTEGER)
- `created_at` (REAL)

### 3. `deliberations` Table
Stores final consensus runs:
- `id` (INTEGER PRIMARY KEY)
- `paper_id` (INTEGER FOREIGN KEY)
- `aggregate_score` (REAL)
- `verdict` (TEXT)
- `report_json` (TEXT)
- `created_at` (REAL)

### 4. `appeals` Table
Stores appeals history:
- `id` (INTEGER PRIMARY KEY)
- `paper_id` (INTEGER FOREIGN KEY)
- `author_rebuttal` (TEXT)
- `status` (TEXT DEFAULT 'pending')
- `new_verdict` (TEXT)
- `created_at` (REAL)

## Deliberation Flow & Protocol

1. **Extraction:** Segment paper PDF/Text to get section splits.
2. **Round 1 (Independent):** Each agent reviews the text and assigns an initial score.
3. **Round 2 (Debate):** Peer reviews from Round 1 are shared. Agents may issue challenges to targets using the `challenge_target` field.
4. **Round 3 (Consensus):** Agents look at Round 1 & Round 2 logs, finalize scores, and justify positions.
5. **Consensus Aggregation:** Run weighted calculation and determine final verdict.
