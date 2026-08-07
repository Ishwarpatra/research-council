import json
import sqlite3
import time
from contextlib import closing

import aiosqlite

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY,
    file_path TEXT UNIQUE,
    content_hash TEXT,
    abstract TEXT, methods TEXT, results TEXT, claims TEXT,
    full_text TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER,
    agent_name TEXT,
    criterion TEXT,
    score REAL,
    justification TEXT,
    evidence TEXT,  -- JSON array
    challenge_target TEXT DEFAULT '',
    round_num INTEGER,
    created_at REAL,
    FOREIGN KEY(paper_id) REFERENCES papers(id)
);

CREATE TABLE IF NOT EXISTS deliberations (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER,
    aggregate_score REAL,
    verdict TEXT,
    report_json TEXT,
    created_at REAL,
    FOREIGN KEY(paper_id) REFERENCES papers(id)
);

CREATE TABLE IF NOT EXISTS appeals (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER,
    author_rebuttal TEXT,
    status TEXT DEFAULT 'pending',  -- pending|re_deliberating|resolved
    new_verdict TEXT,
    created_at REAL,
    FOREIGN KEY(paper_id) REFERENCES papers(id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_paper ON reviews(paper_id);
CREATE INDEX IF NOT EXISTS idx_delib_paper ON deliberations(paper_id);
"""

# Dynamic database configuration path
DB_PATH = "council.db"

def configure_db_path(path: str) -> None:
    global DB_PATH
    DB_PATH = path

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Create schema tables if they do not exist. Called once at module startup."""
    with closing(_db()) as conn:
        conn.executescript(DB_SCHEMA)
        conn.commit()
        # Migration: add challenge_target column to existing databases that predate it
        try:
            conn.execute("ALTER TABLE reviews ADD COLUMN challenge_target TEXT DEFAULT ''")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists — safe to ignore

def save_paper(file_path: str, content_hash: str, abstract: str, methods: str,
               results: str, claims: str, full_text: str) -> int:
    """Upsert paper record preserving the original paper_id on re-runs."""
    with closing(_db()) as conn:
        conn.execute(
            """INSERT INTO papers
               (file_path, content_hash, abstract, methods, results, claims, full_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(file_path) DO UPDATE SET
                 content_hash=excluded.content_hash,
                 abstract=excluded.abstract,
                 methods=excluded.methods,
                 results=excluded.results,
                 claims=excluded.claims,
                 full_text=excluded.full_text""",
            (file_path, content_hash, abstract, methods, results, claims, full_text, time.time()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM papers WHERE file_path = ?", (file_path,)
        ).fetchone()
        return row["id"]

def load_paper(file_path: str) -> dict | None:
    with closing(_db()) as conn:
        row = conn.execute(
            "SELECT * FROM papers WHERE file_path = ?", (file_path,)
        ).fetchone()
        if row:
            return dict(row)
    return None

def save_review(paper_id: int, agent_name: str, criterion: str, score: float,
                justification: str, evidence: list, challenge_target: str, round_num: int) -> None:
    with closing(_db()) as conn:
        conn.execute(
            """INSERT INTO reviews
               (paper_id, agent_name, criterion, score, justification, evidence,
                challenge_target, round_num, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (paper_id, agent_name, criterion, score, justification, json.dumps(evidence),
             challenge_target, round_num, time.time()),
        )
        conn.commit()

def save_deliberation(paper_id: int, aggregate: float, verdict: str, report: dict) -> None:
    with closing(_db()) as conn:
        conn.execute(
            """INSERT INTO deliberations
               (paper_id, aggregate_score, verdict, report_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (paper_id, aggregate, verdict, json.dumps(report), time.time()),
        )
        conn.commit()

def list_all_papers() -> list:
    with closing(_db()) as conn:
        rows = conn.execute(
            "SELECT file_path, content_hash, created_at FROM papers ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

def get_paper_reviews(paper_id: int) -> list:
    with closing(_db()) as conn:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE paper_id = ? ORDER BY round_num, agent_name",
            (paper_id,),
        ).fetchall()
        return [dict(r) for r in rows]

def get_latest_deliberation(paper_id: int) -> dict | None:
    with closing(_db()) as conn:
        row = conn.execute(
            "SELECT * FROM deliberations WHERE paper_id = ? ORDER BY created_at DESC LIMIT 1",
            (paper_id,),
        ).fetchone()
        if row:
            return dict(row)
    return None

def get_paper_id_by_path(file_path: str) -> int | None:
    with closing(_db()) as conn:
        row = conn.execute(
            "SELECT id FROM papers WHERE file_path = ?", (file_path,)
        ).fetchone()
        return row["id"] if row else None

def get_audit_reviews_and_deliberations() -> tuple[list, int]:
    with closing(_db()) as conn:
        rows = conn.execute("""
            SELECT d.paper_id, d.verdict, d.aggregate_score,
                   r.agent_name, r.criterion, r.score, r.round_num
            FROM deliberations d
            JOIN reviews r ON d.paper_id = r.paper_id
            WHERE r.round_num = 3
            ORDER BY d.created_at DESC
            LIMIT 1000
        """).fetchall()
        distinct_count = conn.execute(
            "SELECT COUNT(DISTINCT paper_id) FROM deliberations"
        ).fetchone()[0]
        return [dict(r) for r in rows], distinct_count

def insert_appeal(paper_id: int, author_rebuttal: str) -> int:
    with closing(_db()) as conn:
        cur = conn.execute(
            "INSERT INTO appeals (paper_id, author_rebuttal, status, created_at) "
            "VALUES (?, ?, 'pending', ?)",
            (paper_id, author_rebuttal, time.time()),
        )
        appeal_id = cur.lastrowid
        conn.commit()
        return appeal_id

def update_appeal_verdict(appeal_id: int, verdict: str) -> None:
    with closing(_db()) as conn:
        conn.execute(
            "UPDATE appeals SET status = 'resolved', new_verdict = ? WHERE id = ?",
            (verdict, appeal_id),
        )
        conn.commit()


# ──────────────────────────────────────────────
# Async WebSockets State Storage (aiosqlite)
# ──────────────────────────────────────────────

async def init_db_async(db_path: str) -> aiosqlite.Connection:
    """Initialize schema and return a persistent, shared connection."""
    db = await aiosqlite.connect(db_path)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS websocket_frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER,
            seq_id INTEGER,
            payload TEXT,
            created_at REAL
        )
    """)
    await db.commit()
    return db

async def log_frame(db: aiosqlite.Connection, paper_id: int, seq_id: int, payload: str):
    import time
    await db.execute(
        "INSERT INTO websocket_frames (paper_id, seq_id, payload, created_at) VALUES (?, ?, ?, ?)",
        (paper_id, seq_id, payload, time.time())
    )
    await db.commit()

async def get_websocket_frames(db_path: str, paper_id: int, since_seq: int = 0) -> list:
    """Fetch websocket frames since a specific sequence ID for delta replay."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT payload FROM websocket_frames WHERE paper_id = ? AND seq_id > ? ORDER BY seq_id ASC",
            (paper_id, since_seq)
        ) as cursor:
            rows = await cursor.fetchall()
            return [json.loads(r[0]) for r in rows]
