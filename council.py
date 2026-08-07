#!/usr/bin/env python3
"""
Research Consensus Council — Multi-agent deliberation with persistence & real LLM hooks.
5 agents, 3-round debate, weighted scoring, PDF input, SQLite audit log, HTTP API + dashboard.
"""

import json
import sys
import os
import sqlite3
import hashlib
import time
import re
import threading
import urllib.request          # Fix 12: moved from inside call_llm to module level
from pathlib import Path
from dataclasses import dataclass
from contextlib import closing

# PDF extraction
try:
    import pdfplumber  # type: ignore
except ImportError:
    pdfplumber = None
try:
    from pypdf import PdfReader  # type: ignore
except ImportError:
    PdfReader = None


# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

def load_config() -> dict:
    """Load config from environment variables + optional JSON file."""
    cfg = {
        "db_path":      os.getenv("RCC_DB",           "council.db"),
        "llm_provider": os.getenv("RCC_LLM_PROVIDER", "stub"),   # stub|ollama|openai
        "ollama_host":  os.getenv("OLLAMA_HOST",      "http://localhost:11434"),
        "openai_key":   os.getenv("OPENAI_API_KEY",   ""),
        "webhook_url":  os.getenv("RCC_WEBHOOK_URL",  ""),        # Fix 1: read webhook URL
        "openai_model_map": {
            # All five route to gpt-4o-mini on the OpenAI path (single-API convenience).
            # Agent names still encode the intended model persona.
            "Orca-2":     "gpt-4o-mini",
            "Phi-4":      "gpt-4o-mini",
            "Mistral-7B": "gpt-4o-mini",
            "Llama-3.2":  "gpt-4o-mini",
            "Phi-3":      "gpt-4o-mini",
        },
        "ollama_model_map": {
            # Real Ollama model tags — override via council_config.json if your local names differ.
            "Orca-2":     "orca2",
            "Phi-4":      "phi4",
            "Mistral-7B": "mistral",
            "Llama-3.2":  "llama3.2",
            "Phi-3":      "phi3",
        },
        "weights": {
            "Clarity & Presentation": 0.20,
            "Methodology Rigor":      0.25,
            "Novelty & Significance": 0.20,
            "Ethics & Integrity":     0.20,
            "Practical Impact":       0.15,
        },
    }
    cfg_path = Path("council_config.json")
    if cfg_path.exists():
        # Fix 5: guard against malformed JSON rather than hard-crashing
        try:
            cfg.update(json.loads(cfg_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            print(
                f"Warning: council_config.json is malformed ({exc}). Using defaults.",
                file=sys.stderr,
            )
    return cfg


CFG     = load_config()
WEIGHTS = CFG["weights"]


def _is_stub() -> bool:
    """
    Return True when no real LLM will be called (stub/fallback mode).
    Used to gate SIMULATED banners and add simulation_mode flags to reports.
    """
    p = CFG["llm_provider"]
    if p == "ollama":
        return False
    if p == "openai" and CFG.get("openai_key"):
        return False
    return True


# ──────────────────────────────────────────────
# Database (persistence + audit log)
# ──────────────────────────────────────────────

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
    evidence TEXT,
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
    status TEXT DEFAULT 'pending',
    new_verdict TEXT,
    created_at REAL,
    FOREIGN KEY(paper_id) REFERENCES papers(id)
);
CREATE INDEX IF NOT EXISTS idx_reviews_paper ON reviews(paper_id);
CREATE INDEX IF NOT EXISTS idx_delib_paper ON deliberations(paper_id);
"""


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(CFG["db_path"])
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


# Initialise exactly once at module load — never inside run_council/submit_appeal
init_db()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def save_paper(paper: "PaperContent") -> int:
    """
    Upsert paper record preserving the original paper_id on re-runs.
    INSERT OR REPLACE would delete-then-reinsert, generating a new rowid and
    orphaning every reviews/deliberations FK row linked to the old paper_id.
    ON CONFLICT DO UPDATE keeps the existing rowid intact.
    """
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
            (paper.file_path, paper.content_hash, paper.abstract, paper.methods,
             paper.results, paper.claims, paper.full_text, time.time()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM papers WHERE file_path = ?", (paper.file_path,)
        ).fetchone()
        return row["id"]


def load_paper(file_path: str) -> "PaperContent | None":
    with closing(_db()) as conn:
        row = conn.execute(
            "SELECT * FROM papers WHERE file_path = ?", (file_path,)
        ).fetchone()
        if row:
            return PaperContent(
                file_path=row["file_path"],
                content_hash=row["content_hash"],
                abstract=row["abstract"]  or "",
                methods=row["methods"]   or "",
                results=row["results"]   or "",
                claims=row["claims"]     or "",
                full_text=row["full_text"] or "",
            )
    return None


def save_review(paper_id: int, review: "AgentReview") -> None:
    with closing(_db()) as conn:
        conn.execute(
            """INSERT INTO reviews
               (paper_id, agent_name, criterion, score, justification, evidence,
                challenge_target, round_num, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (paper_id, review.agent_name, review.criterion, review.score,
             review.justification, json.dumps(review.evidence),
             review.challenge_target, review.round, time.time()),
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


# ──────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────

@dataclass
class PaperContent:
    file_path: str = ""
    content_hash: str = ""
    abstract: str = ""
    methods: str = ""
    results: str = ""
    claims: str = ""
    full_text: str = ""


@dataclass
class AgentReview:
    agent_name: str
    criterion: str
    score: float
    justification: str
    evidence: list
    round: int
    challenge_target: str = ""   # Round 2 only: name of challenged peer agent, or empty


# ──────────────────────────────────────────────
# Agent definitions
# ──────────────────────────────────────────────

AGENTS = [
    {"name": "Skeptical Reviewer", "model": "Orca-2", "criterion": "Clarity & Presentation", "weight": 0.20,
     "role": "Critical evaluator hunting for logical fallacies, overstatements, ambiguities",
     "responsibilities": "Question claims, find counter-examples, identify weaknesses in presentation"},
    # NOTE: Each agent owns exactly ONE criterion (single-authority model), an intentional
    # deviation from Architecture §3 which assigns all five criteria per agent.
    # This avoids inter-criterion averaging inconsistency and matches ScoreCalculator's interface.
    {"name": "Method Evaluator",     "model": "Phi-4",      "criterion": "Methodology Rigor",       "weight": 0.25,
     "role": "Detail-obsessed rigor specialist",
     "responsibilities": "Scrutinise experimental design, statistical validity, sample size, confounds"},
    {"name": "Domain Expert", "model": "Mistral-7B", "criterion": "Novelty & Significance", "weight": 0.20,
     "role": "Field knowledge authority",
     "responsibilities": "Assess novelty vs prior art, identify missing citations, evaluate academic impact"},
    {"name": "Ethics Officer", "model": "Llama-3.2", "criterion": "Ethics & Integrity", "weight": 0.20,
     "role": "Safeguard of academic and human integrity",
     "responsibilities": "IRB compliance, bias/fairness, conflicts of interest, privacy, societal harm"},
    {"name": "Industry Translator", "model": "Phi-3", "criterion": "Practical Impact", "weight": 0.15,
     "role": "Pragmatic, cost-conscious, implementation-focused",
     "responsibilities": "Real-world applicability, implementation barriers, commercial viability, scalability"},
]


# ──────────────────────────────────────────────
# Content extraction (tables + citations)
# ──────────────────────────────────────────────

def _format_table(table: list) -> str:
    """
    Fix 7: render a 2-D table as a column-aligned text block.
    Each column is padded to its maximum cell width (str.ljust) so LLMs receive
    valid, readable tabular context instead of naïve pipe-concatenated strings.
    """
    if not table:
        return ""
    max_cols = max(len(row) for row in table)
    norm = [
        [str(cell) if cell is not None else "" for cell in row]
        + [""] * (max_cols - len(row))
        for row in table
    ]
    col_w = [
        max(len(norm[r][c]) for r in range(len(norm)))
        for c in range(max_cols)
    ]
    col_w = [max(w, 3) for w in col_w]
    lines = []
    for i, row in enumerate(norm):
        lines.append(" | ".join(cell.ljust(col_w[c]) for c, cell in enumerate(row)))
        if i == 0:
            lines.append("-+-".join("-" * w for w in col_w))
    return "\n".join(lines)


def _find_abstract_in_text(text: str) -> str:
    """
    Fix 13: targeted abstract locator that avoids slicing raw front-matter
    (title page, author affiliations) which contaminates LLM context windows.
    """
    patterns = [
        r'(?im)^\s*abstract\s*\n+([\s\S]{100,2000}?)(?=\n\s*(?:1[.\s]?\s*introduction|keywords?|index\s+terms))',
        r'(?im)^\s*abstract[:\-\u2014]?\s*([\s\S]{100,1500}?)(?=\n\s*\n)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    idx = text.lower().find("abstract")
    if idx != -1:
        snippet = re.sub(r"^\W+", "", text[idx + 8: idx + 1600]).strip()
        if len(snippet) > 100:
            return snippet
    return ""


def _extract_citations(text: str) -> list:
    """
    Fix 6: extract all citation patterns — the hard [:50] cap has been removed
    so comprehensive literature reviews and meta-analyses keep every reference.
    """
    patterns = [
        r'\[\d+(?:,\s*\d+)*\]',
        r'\(\w+(?:,\s*\w+)*\s*,\s*\d{4}\)',
        r'\w+\s+et\s+al\.\s*\(\d{4}\)',
    ]
    citations: set = set()
    for pat in patterns:
        citations.update(re.findall(pat, text))
    return sorted(citations)   # no [:50] cap


def _split_sections(text: str) -> dict:
    """
    Fix 15: improved section splitter using exact/prefix keyword matching instead
    of naive substring 'in' check, preventing false triggers from in-paragraph
    words (e.g. 'experimental' incorrectly matching 'experiment').
    """
    sections: dict = {}
    current = "abstract"
    buf: list = []

    section_keywords: dict = {
        "abstract":     ["abstract"],
        "introduction": ["introduction", "1. introduction", "1 introduction", "background"],
        "methods":      ["method", "methods", "approach", "methodology",
                         "materials and methods", "experimental setup",
                         "2. method", "2. methods", "3. method", "3. methods"],
        "results":      ["results", "result", "findings", "evaluation",
                         "experiments and results",
                         "4. results", "4. result", "5. results", "5. result"],
        "discussion":   ["discussion", "analysis", "6. discussion"],
        "conclusion":   ["conclusion", "conclusions", "limitation", "limitations",
                         "future work", "summary"],
        "claims":       ["claims", "claim", "contributions", "contribution"],
    }

    for line in text.split("\n"):
        low = line.strip().lower()
        matched = None
        if len(low) < 80 and len(buf) > 50:
            for sec, kws in section_keywords.items():
                if any(
                    low == kw
                    or low.startswith(kw + " ")
                    or low.startswith(kw + ":")
                    or low.startswith(kw + "\t")
                    for kw in kws
                ):
                    matched = sec
                    break
        if matched and matched != current:
            sections[current] = "\n".join(buf).strip()
            current = matched
            buf = [line]
        else:
            buf.append(line)

    sections[current] = "\n".join(buf).strip()
    if not sections.get("claims"):
        sections["claims"] = (
            sections.get("discussion", "") + "\n" + sections.get("conclusion", "")
        ).strip()
    return sections


def extract_content(file_path: str) -> PaperContent:
    path   = Path(file_path)
    text   = ""
    tables: list = []

    if path.suffix.lower() == ".pdf":
        if pdfplumber:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
                    for tbl in page.extract_tables() or []:
                        fmt = _format_table(tbl)   # Fix 7: column-aligned
                        if fmt:
                            tables.append(fmt)
        elif PdfReader:
            reader = PdfReader(path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            raise RuntimeError("Install pdfplumber or pypdf for PDF support.")
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")

    sections  = _split_sections(text)
    citations = _extract_citations(text)
    full = (
        text
        + ("\n\n[TABLES]\n"    + "\n\n".join(tables)  if tables    else "")
        + ("\n\n[CITATIONS]\n" + "\n".join(citations) if citations else "")
    )
    h = content_hash(full)

    # Fix 13: prefer section-detected abstract, then targeted regex extraction,
    # then skip the first ~300 chars (title/author block) rather than blindly
    # taking text[:2000] which poisons the LLM with front-matter noise.
    abstract = sections.get("abstract") or sections.get("introduction")
    if not abstract:
        abstract = _find_abstract_in_text(text)
    if not abstract or len(abstract) < 50:
        abstract = text[300:2300].strip() if len(text) > 300 else text[:2000]

    return PaperContent(
        file_path=str(path),
        content_hash=h,
        abstract=abstract,
        methods=sections.get("methods", ""),
        results=sections.get("results", ""),
        claims=sections.get("claims", sections.get("conclusion", "")),
        full_text=full,
    )


# ──────────────────────────────────────────────
# LLM client (swappable provider)
# ──────────────────────────────────────────────

# Fix 8: module-level Event so backoff waits are interruptible from other threads.
_retry_event = threading.Event()


def call_llm(prompt: str, model: str) -> str:
    """Dispatch to the configured LLM provider (ollama / openai / stub)."""
    # Fix 12: urllib.request is already imported at module level — no redundant inner imports.
    provider = CFG["llm_provider"]

    if provider == "ollama":
        # Use the dedicated Ollama map — prevents asking Ollama for "gpt-4o-mini" which doesn't exist locally
        mapped = CFG["ollama_model_map"].get(model, model)
        req = urllib.request.Request(
            f"{CFG['ollama_host']}/api/generate",
            data=json.dumps({"model": mapped, "prompt": prompt,
                             "stream": False, "format": "json"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())["response"]

    if provider == "openai" and CFG["openai_key"]:
        mapped = CFG["openai_model_map"].get(model, "gpt-4o-mini")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps({
                "model":    mapped,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            }).encode(),
            headers={
                "Authorization": f"Bearer {CFG['openai_key']}",
                "Content-Type":  "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())["choices"][0]["message"]["content"]

    # Stub fallback — deterministic score derived from prompt hash
    seed = hashlib.md5(prompt.encode()).hexdigest()[:8]
    return json.dumps({
        "score":         round(3.0 + (int(seed, 16) % 20) / 10, 1),
        "justification": f"[{model}] Stub analysis. Score derived from content hash {seed}.",
        "evidence":      ["Extracted text segment 1", "Extracted text segment 2"],
    })


def call_llm_with_retry(prompt: str, model: str, max_retries: int = 3) -> str:
    """
    Fix 8: exponential backoff using threading.Event.wait() instead of time.sleep().
    Event.wait(timeout) suspends only the calling thread and can be cancelled
    externally without freezing other threads in a ThreadingHTTPServer context.
    """
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            return call_llm(prompt, model)
        except Exception as exc:
            last_err = exc
            if attempt < max_retries - 1:
                wait_sec = 2 ** attempt
                print(
                    f"   Retry {attempt + 1}/{max_retries - 1} for [{model}]"
                    f" in {wait_sec}s — {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                _retry_event.wait(timeout=wait_sec)  # non-blocking to other threads
    raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_err}") from last_err


# ──────────────────────────────────────────────
# Prompt building
# ──────────────────────────────────────────────

BASE_PROMPT = """# SYSTEM ROLE & CONTEXT
You are the {agent_name}, operating within the Research Consensus Council—an automated, multi-agent system designed to deliberate on and evaluate academic research papers. Your overarching goal is to critically assess the provided manuscript, engage in constructive debate with your peer agents, and arrive at a well-reasoned final score.

# YOUR SPECIFIC IDENTITY
* Role: {agent_role}
* Primary Focus: {agent_responsibilities}
* Scoring Assignment: You are the primary authority for the "{assigned_criterion}" metric, which carries a {criterion_weight} weight in the final consensus algorithm.
* Model Persona: You operate as a {underlying_model} model. Your tone must be strictly academic, objective, highly analytical, and tailored to your specialized domain.

# INPUT DATA
[ABSTRACT_START] {extracted_abstract} [ABSTRACT_END]
[METHODS_START] {extracted_methods} [METHODS_END]
[RESULTS_START] {extracted_results} [RESULTS_END]
[CLAIMS_START] {extracted_claims} [CLAIMS_END]

# DELIBERATION PROTOCOL
You are currently operating in: Round {current_round_number}

Follow the specific instructions for this round:
* ROUND 1 (Initial Review): Read the extracted content independently. Generate an initial assessment focusing strictly on your designated `{assigned_criterion}`. Provide a preliminary score (1.0 to 5.0) and write a justification citing specific evidence from the text.
* ROUND 2 (Respond to Critiques): You will be provided with the initial reviews of your 4 peer agents. Read them carefully. If you spot logical flaws, missed context, or disagree with their assessment—especially if it impacts your domain—you must issue a formal challenge. Defend your initial stance if challenged by others.
* ROUND 3 (Final Positions): Review the accumulated debate history. Finalize your score (1.0 to 5.0) for `{assigned_criterion}`. You may adjust your initial score based on valid points raised by peers, or maintain it. Provide a final, definitive justification for your score.

# CONSTRAINTS & RULES
1. Stay in your lane: While you may critique other agents in Round 2, your final output and score must revolve entirely around your `{assigned_criterion}`.
2. Grounded Evidence: You must not hallucinate external papers unless explicitly comparing novelty (Domain Expert only). All critiques must reference the provided extracted text.
3. No Sycophancy: Do not blindly agree with the council. If the paper has critical flaws in your domain, stand your ground even if other agents score the paper highly.
4. Formatting: Your output must strictly adhere to the requested JSON schema.

# OUTPUT SCHEMA
Rounds 1 & 3: {{"score": float, "justification": string, "evidence": [string]}}
Round 2 only: {{"score": float, "justification": string, "evidence": [string], "challenge_target": string_or_null}}
(challenge_target: exact name of the peer agent you formally challenge, or omit/null if no challenge)"""


def build_prompt(
    agent: dict,
    paper: PaperContent,
    round_num: int,
    peer_reviews: list | None = None,
) -> str:
    """
    Fix 11: peer reviews are grouped chronologically by their originating round
    so agents can distinguish initial positions from subsequent challenges.
    Each agent's own prior reviews are flagged so Round-3 agents can trace
    their full debate trajectory and make genuinely informed final decisions.
    """
    prompt = BASE_PROMPT.format(
        agent_name=agent["name"],
        agent_role=agent["role"],
        agent_responsibilities=agent["responsibilities"],
        assigned_criterion=agent["criterion"],
        criterion_weight=f"{agent['weight'] * 100:.0f}%",
        underlying_model=agent["model"],
        extracted_abstract=paper.abstract[:3000],
        extracted_methods=paper.methods[:3000],
        extracted_results=paper.results[:3000],
        extracted_claims=paper.claims[:3000],
        current_round_number=round_num,
    )
    if peer_reviews:
        # Round-accurate label so agents know exactly what debate context they hold
        if round_num == 2:
            label = "ROUND 1 PEER REVIEWS — Identify disagreements and prepare challenges"
        else:
            label = "ACCUMULATED DEBATE HISTORY (Rounds 1 & 2) — Use to finalise your position"
        prompt += f"\n# {label}\n"
        # Group by originating round for chronological clarity
        by_round: dict = {}
        for r in peer_reviews:
            by_round.setdefault(r.round, []).append(r)
        for rnd in sorted(by_round):
            prompt += f"\n## Round {rnd} Reviews\n"
            for r in by_round[rnd]:
                own = " <- YOUR OWN PRIOR REVIEW" if r.agent_name == agent["name"] else ""
                prompt += (
                    f"\n### {r.agent_name}{own} ({r.criterion}): {r.score}/5.0\n"
                    f"{r.justification}\n"
                )
    return prompt


# ──────────────────────────────────────────────
# ScoreCalculator (documented tool)
# ──────────────────────────────────────────────

class ScoreCalculator:
    """Deterministic weighted score computation (Tools Documentation §2)."""

    @staticmethod
    def compute(weights: dict[str, float], scores: dict[str, float]) -> float:
        total = sum(scores.get(c, 0) * w for c, w in weights.items())
        return round(total, 2)


# ──────────────────────────────────────────────
# Deliberation engine
# ──────────────────────────────────────────────

def run_round(
    paper: PaperContent,
    round_num: int,
    peer_reviews: list | None = None,
) -> list:
    """
    Fix 16: named exception types, stderr logging for all failure modes.
    A structured retry is attempted on JSON-parse failures before accepting
    the fallback score, preventing silent corruption of consensus data.
    """
    reviews = []
    for agent in AGENTS:
        prompt = build_prompt(agent, paper, round_num, peer_reviews)

        try:
            response = call_llm_with_retry(prompt, agent["model"])
        except RuntimeError as exc:
            print(
                f"Warning: [{agent['name']}] LLM exhausted retries in round {round_num}: {exc}",
                file=sys.stderr,
            )
            reviews.append(AgentReview(
                agent_name=agent["name"], criterion=agent["criterion"],
                score=3.0,
                justification=f"LLM unavailable after all retries: {exc}",
                evidence=[], round=round_num,
            ))
            continue

        data: dict = {}
        score: float = 3.0
        try:
            data  = json.loads(response)
            score = max(1.0, min(5.0, float(data.get("score", 3.0))))
        except (json.JSONDecodeError, ValueError, TypeError) as parse_err:
            print(
                f"Warning: [{agent['name']}] JSON parse error round {round_num}: {parse_err}. Retrying...",
                file=sys.stderr,
            )
            retry_prompt = prompt + (
                "\n\nCRITICAL: Your previous response could not be parsed. "
                "Output ONLY valid JSON matching the schema — no extra text, no markdown."
            )
            try:
                data  = json.loads(call_llm_with_retry(retry_prompt, agent["model"]))
                score = max(1.0, min(5.0, float(data.get("score", 3.0))))
            except (json.JSONDecodeError, ValueError, TypeError) as exc2:
                print(
                    f"Warning: [{agent['name']}] JSON parse failed after retry in round {round_num}: {exc2}",
                    file=sys.stderr,
                )
                data = {"justification": f"JSON parse failed after retry: {exc2}", "evidence": []}
            except RuntimeError as exc3:
                print(
                    f"Warning: [{agent['name']}] Retry LLM call failed in round {round_num}: {exc3}",
                    file=sys.stderr,
                )
                data = {"justification": f"LLM retry call failed: {exc3}", "evidence": []}
        except Exception as exc:
            print(
                f"Warning: [{agent['name']}] Unexpected error in round {round_num}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            data = {"justification": f"Unexpected error: {type(exc).__name__}: {exc}", "evidence": []}

        reviews.append(AgentReview(
            agent_name=agent["name"],
            criterion=agent["criterion"],
            score=score,
            justification=data.get("justification", ""),
            evidence=data.get("evidence", []),
            round=round_num,
            challenge_target=data.get("challenge_target", "") if round_num == 2 else "",
        ))
    return reviews


def _run_council_on_paper(paper: PaperContent, paper_id: int | None = None) -> dict:
    """
    Fix 17: core deliberation engine decoupled from file-path concerns.
    Accepts a pre-built PaperContent so appeal re-deliberations can inject
    rebuttal context without overwriting the canonical DB record.
    If paper_id is supplied the paper record is NOT re-saved.

    Round flow (Fix 11):
      Round 1 — agents review independently
      Round 2 — agents receive Round 1 history         (peer_reviews = r1)
      Round 3 — agents receive full accumulated history (peer_reviews = r1 + r2)
    """
    if paper_id is None:
        paper_id = save_paper(paper)

    if _is_stub():
        print(
            "\n" + "=" * 60 +
            "\n  SIMULATED — no LLM model was called" +
            "\n  Scores are hash-derived and carry no analytical meaning." +
            "\n  Set RCC_LLM_PROVIDER=ollama or RCC_LLM_PROVIDER=openai" +
            "\n  (with OPENAI_API_KEY) to run against a real model." +
            "\n" + "=" * 60,
            file=sys.stderr,
        )

    print("Deliberating: Round 1 - Initial reviews...")
    r1 = run_round(paper, 1)
    for r in r1:
        save_review(paper_id, r)

    print("Deliberating: Round 2 - Peer debate...")
    r2 = run_round(paper, 2, r1)          # agents see Round 1 history
    for r in r2:
        save_review(paper_id, r)

    print("Deliberating: Round 3 - Final positions...")
    r3 = run_round(paper, 3, r1 + r2)    # agents see full accumulated history
    for r in r3:
        save_review(paper_id, r)

    all_reviews  = r1 + r2 + r3
    final_scores = {r.criterion: r.score for r in r3}
    aggregate    = ScoreCalculator.compute(WEIGHTS, final_scores)
    verdict      = determine_verdict(aggregate)

    print(f"Verdict: {verdict} ({aggregate}/5.0)")

    report = generate_report(paper, all_reviews, aggregate, verdict)
    save_deliberation(paper_id, aggregate, verdict, report)
    notify(verdict, aggregate, paper.file_path)
    return report


def run_council(paper_path: str) -> dict:
    """CLI entry: extract paper -> 3-round deliberation -> save & return report."""
    print(f"Extracting: {paper_path}")
    paper = extract_content(paper_path)

    # Cache check: compare hashes derived from the same extraction pipeline
    cached = load_paper(paper_path)
    if cached and cached.content_hash == paper.content_hash:
        print("Content unchanged - using cached section splits")
        paper = cached

    return _run_council_on_paper(paper)   # Fix 10: init_db() NOT called here


def determine_verdict(score: float) -> str:
    """
    Fix 14: round to 2 decimal places before threshold comparison to prevent
    IEEE-754 floating-point boundary artefacts (e.g. 3.4999999 mapping to
    'Major Revisions' instead of the correct 'Minor Revisions').
    """
    s = round(score, 2)
    if s >= 4.5:
        return "Accept"
    if s >= 3.5:
        return "Minor Revisions"
    if s >= 2.5:
        return "Major Revisions"
    return "Reject"


# ──────────────────────────────────────────────
# Report generation
# ──────────────────────────────────────────────

def generate_report(paper: PaperContent, reviews: list[AgentReview], aggregate: float, verdict: str) -> dict:
    final_reviews = [r for r in reviews if r.round == 3]

    scores = {r.criterion: r.score for r in final_reviews}
    agreements = []
    disagreements = []
    for c, s in scores.items():
        if s >= 4.0:
            agreements.append(f"{c}: strong ({s}/5)")
        elif s <= 2.5:
            disagreements.append(f"{c}: weak ({s}/5)")

    return {
        "executive_summary": {
            "verdict": verdict,
            "aggregate_score": aggregate,
            "simulation_mode": _is_stub(),
            "key_strengths": agreements[:3],
            "major_concerns": disagreements[:3],
        },
        "individual_reviews": [
            {"agent": r.agent_name, "criterion": r.criterion, "score": r.score,
             "justification": r.justification, "evidence": r.evidence,
             "challenge_target": r.challenge_target}
            for r in final_reviews
        ],
        "consensus_dissent": {"agreements": agreements, "disagreements": disagreements},
        "actionable_feedback": {
            "prioritized_revisions": [f"Improve {r.criterion} (score: {r.score}/5)" for r in final_reviews if r.score < 3.5],
            "rebuttal_template": "Authors may respond to each criterion above with evidence.",
            "decision_path": f"Current: {verdict} ({aggregate}/5). Address major concerns to improve.",
        },
    }


# ──────────────────────────────────────────────
# Notifications
# ──────────────────────────────────────────────

def notify(verdict: str, score: float, paper_path: str) -> None:
    """
    Fix 1: dispatch notification via three channels in priority order:
      1. Console  (always)
      2. Append-only log file  (council_notifications.log)
      3. HTTP webhook POST to RCC_WEBHOOK_URL (if configured)
    """
    name = Path(paper_path).name
    msg  = f"Research Consensus Council: {name} -> {verdict} ({score}/5.0)"
    ts   = time.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Console
    print(f"Notification: {msg}")

    # 2. Append-only log file
    try:
        with open("council_notifications.log", "a", encoding="utf-8") as lf:
            lf.write(f"[{ts}] {msg}\n")
    except OSError as exc:
        print(f"Warning: Could not write notification log: {exc}", file=sys.stderr)

    # 3. Webhook POST
    webhook_url = CFG.get("webhook_url", "")
    if webhook_url:
        payload = json.dumps({
            "verdict":   verdict,
            "score":     score,
            "paper":     paper_path,
            "message":   msg,
            "timestamp": ts,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10):
                pass
            print(f"Webhook delivered to {webhook_url}")
        except Exception as exc:
            print(f"Warning: Webhook delivery failed: {exc}", file=sys.stderr)


# ──────────────────────────────────────────────
# Appeal Processor (FR5)
# ──────────────────────────────────────────────

def submit_appeal(paper_path: str, author_rebuttal: str) -> dict:
    """
    Fix 4: record the author rebuttal in the appeals table, build an in-memory
    augmented PaperContent (rebuttal appended), and re-deliberate WITHOUT
    overwriting the original paper record in the database.
    The appeal verdict is written back to the appeals table, preserving a
    versioned history of every deliberation cycle.
    """
    paper = load_paper(paper_path)
    if not paper:
        return {"error": "Paper not found. Run council first."}

    # Persist the appeal and retrieve the existing paper_id
    with closing(_db()) as conn:
        pid_row = conn.execute(
            "SELECT id FROM papers WHERE file_path = ?", (paper_path,)
        ).fetchone()
        if not pid_row:
            return {"error": "Paper ID not found in database."}
        paper_id = pid_row["id"]
        cur = conn.execute(
            "INSERT INTO appeals (paper_id, author_rebuttal, status, created_at) "
            "VALUES (?, ?, 'pending', ?)",
            (paper_id, author_rebuttal, time.time()),
        )
        appeal_id = cur.lastrowid
        conn.commit()

    # In-memory augmented copy — the DB paper record is NOT mutated
    appeal_paper = PaperContent(
        file_path=paper.file_path,
        content_hash=paper.content_hash,
        abstract=paper.abstract,
        methods=paper.methods,
        results=paper.results,
        claims=paper.claims + f"\n\n[AUTHOR REBUTTAL]\n{author_rebuttal}",
        full_text=paper.full_text + f"\n\n[AUTHOR REBUTTAL]\n{author_rebuttal}",
    )

    print("Appeal submitted. Re-deliberating with rebuttal context...")
    # Pass existing paper_id: reviews link to the same paper but claims field preserved
    report = _run_council_on_paper(appeal_paper, paper_id=paper_id)  # Fix 10: no init_db()

    # Record the appeal verdict
    new_verdict = report.get("executive_summary", {}).get("verdict", "Unknown")
    with closing(_db()) as conn:
        conn.execute(
            "UPDATE appeals SET status = 'resolved', new_verdict = ? WHERE id = ?",
            (new_verdict, appeal_id),
        )
        conn.commit()

    return report


# ──────────────────────────────────────────────
# HTML Dashboard (self-contained, no CDN dependencies)
# ──────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Research Consensus Council - Dashboard</title>
<meta name="description" content="Multi-agent paper review dashboard: verdict badge, score breakdown by criterion, and full review-chain timeline.">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d0f1a;--surface:#151826;--s2:#1e2235;--card:#242840;
  --accent:#7c6ff7;--text:#e4e8f1;--muted:#7a86a1;--border:#2b3050;
  --acc:#22c55e;--acc-bg:rgba(34,197,94,.13);
  --min:#f59e0b;--min-bg:rgba(245,158,11,.13);
  --maj:#f97316;--maj-bg:rgba(249,115,22,.13);
  --rej:#ef4444;--rej-bg:rgba(239,68,68,.13);
  --font:'Segoe UI',system-ui,-apple-system,sans-serif;
  --r:10px;--rl:16px;--sh:0 8px 32px rgba(0,0,0,.35)
}
body{font-family:var(--font);background:var(--bg);color:var(--text);display:flex;flex-direction:column;min-height:100vh}
header{background:linear-gradient(135deg,#1a1d35,#0d0f1a);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;gap:14px}
header h1{font-size:1.05rem;font-weight:600;letter-spacing:-.01em}
.hbadge{background:var(--accent);color:#fff;border-radius:20px;padding:2px 9px;font-size:.68rem;font-weight:700;letter-spacing:.07em}
.hsub{color:var(--muted);font-size:.76rem;margin-left:auto}
.layout{display:flex;flex:1;overflow:hidden;height:calc(100vh - 53px)}
.sidebar{width:265px;min-width:210px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.sbhdr{padding:13px;border-bottom:1px solid var(--border)}
.sbhdr h2{font-size:.69rem;text-transform:uppercase;letter-spacing:.11em;color:var(--muted);margin-bottom:8px}
.srch{background:var(--s2);border:1px solid var(--border);border-radius:var(--r);padding:7px 10px;color:var(--text);font-size:.81rem;width:100%;outline:none;transition:border-color .2s}
.srch:focus{border-color:var(--accent)}
.plist{flex:1;overflow-y:auto;padding:6px}
.pitem{padding:9px 11px;border-radius:var(--r);cursor:pointer;transition:background .14s;margin-bottom:3px;border:1px solid transparent}
.pitem:hover{background:var(--s2)}
.pitem.active{background:var(--s2);border-color:var(--accent)}
.pname{font-size:.81rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pdate{font-size:.69rem;color:var(--muted);margin-top:2px}
.main{flex:1;overflow-y:auto;padding:22px 26px;background:var(--bg)}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:58vh;color:var(--muted);gap:10px;text-align:center}
.empty .ico{font-size:2.8rem;opacity:.22}
.empty code{background:var(--s2);padding:2px 7px;border-radius:5px;font-size:.74rem;color:#aab}
.vc{background:linear-gradient(135deg,var(--surface),var(--s2));border:1px solid var(--border);border-radius:var(--rl);padding:20px 22px;display:flex;align-items:center;gap:20px;margin-bottom:16px;box-shadow:var(--sh)}
.sring{width:78px;height:78px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column;border:4px solid var(--border);flex-shrink:0}
.sval{font-size:1.35rem;font-weight:700;line-height:1}
.smax{font-size:.65rem;color:var(--muted)}
.vinfo h2{font-size:1.28rem;font-weight:700;margin-bottom:4px}
.vbadge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:.73rem;font-weight:600;letter-spacing:.04em}
.va{background:var(--acc-bg);color:var(--acc)}.vm{background:var(--min-bg);color:var(--min)}.vmj{background:var(--maj-bg);color:var(--maj)}.vr{background:var(--rej-bg);color:var(--rej)}
.stitle{font-size:.69rem;text-transform:uppercase;letter-spacing:.11em;color:var(--muted);margin-bottom:9px;padding-bottom:7px;border-bottom:1px solid var(--border)}
.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:9px;margin-bottom:20px}
.scard{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:12px 14px;transition:transform .14s,box-shadow .14s;cursor:default}
.scard:hover{transform:translateY(-2px);box-shadow:var(--sh)}
.scn{font-size:.72rem;color:var(--muted);margin-bottom:5px}
.scv{font-size:1.12rem;font-weight:700;margin-bottom:6px}
.sbbg{background:var(--s2);border-radius:4px;height:5px;overflow:hidden}
.sbf{height:100%;border-radius:4px;transition:width .65s ease}
.scag{font-size:.66rem;color:var(--muted);margin-top:5px}
.rnd{margin-bottom:17px}
.rlbl{font-size:.71rem;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;display:flex;align-items:center;gap:7px}
.rlbl::after{content:'';flex:1;height:1px;background:var(--border)}
.rcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(205px,1fr));gap:8px}
.rc{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:10px 12px}
.rct{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px}
.rag{font-size:.76rem;font-weight:600}
.rcrn{font-size:.66rem;color:var(--muted);margin-bottom:3px}
.rpill{font-size:.72rem;font-weight:700;padding:2px 7px;border-radius:11px;background:var(--s2);flex-shrink:0}
.rjust{font-size:.7rem;color:var(--muted);line-height:1.5;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.sp{display:inline-block;width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:var(--surface)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
</style>
</head>
<body>
<header>
  <span style="font-size:1.25rem">⚖️</span>
  <h1>Research Consensus Council</h1>
  <span class="hbadge">LIVE</span>
  <span class="hsub" id="ref">Loading...</span>
</header>
<div class="layout">
  <aside class="sidebar">
    <div class="sbhdr">
      <h2>Processed Papers</h2>
      <input class="srch" id="srch" type="text" placeholder="Search..." oninput="filter()">
    </div>
    <div class="plist" id="plist">
      <div style="text-align:center;padding:18px"><span class="sp"></span></div>
    </div>
  </aside>
  <main class="main" id="main">
    <div class="empty">
      <div class="ico">📋</div>
      <p>Select a paper to view its deliberation results.</p>
      <p style="font-size:.74rem">Process a paper with <code>python council.py &lt;paper&gt;</code></p>
    </div>
  </main>
</div>
<script>
var papers=[],sel=null;
function scoreColor(s){return s>=4?'#22c55e':s>=3?'#f59e0b':s>=2?'#f97316':'#ef4444';}
function verdictCls(v){if(!v)return'';var l=v.toLowerCase();if(l==='accept')return'va';if(l.includes('minor'))return'vm';if(l.includes('major'))return'vmj';return'vr';}
function fmtDate(ts){if(!ts)return'';return new Date(ts*1000).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});}
function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function basename(p){return(p||'').split(/[\\/]/).pop();}
async function loadPapers(){
  try{
    var r=await fetch('/api/papers');papers=await r.json();
    renderList(papers);
    document.getElementById('ref').textContent='Refreshed '+new Date().toLocaleTimeString();
  }catch(e){
    document.getElementById('plist').innerHTML='<p style="color:#ef4444;padding:14px;font-size:.76rem">Failed to load papers</p>';
  }
}
function renderList(list){
  var el=document.getElementById('plist');
  if(!list.length){el.innerHTML='<p style="color:#7a86a1;padding:14px;font-size:.76rem;text-align:center">No papers yet.</p>';return;}
  el.innerHTML=list.map(function(p){
    var n=basename(p.file_path);
    var ac=p.file_path===sel?' active':'';
    return '<div class="pitem'+ac+'" onclick="pick('+JSON.stringify(p.file_path)+')" title="'+esc(p.file_path)+'">'
      +'<div class="pname">'+esc(n)+'</div>'
      +'<div class="pdate">'+fmtDate(p.created_at)+'</div></div>';
  }).join('');
}
function filter(){var q=document.getElementById('srch').value.toLowerCase();renderList(papers.filter(function(p){return p.file_path.toLowerCase().includes(q);}));}
async function pick(path){
  sel=path;renderList(papers);
  var m=document.getElementById('main');
  m.innerHTML='<div style="text-align:center;padding:40px"><span class="sp" style="width:30px;height:30px;border-width:3px"></span></div>';
  try{
    var ep=encodeURIComponent(path);
    var res=await Promise.all([fetch('/api/deliberation?path='+ep),fetch('/api/reviews?path='+ep)]);
    var d=await res[0].json(),rv=await res[1].json();
    renderDetail(path,d,rv);
  }catch(e){m.innerHTML='<p style="color:#ef4444;padding:22px">Failed to load data.</p>';}
}
function renderDetail(path,d,rv){
  var m=document.getElementById('main');
  var report=d.report_json?JSON.parse(d.report_json):{};
  var verdict=d.verdict||'Unknown',score=parseFloat(d.aggregate_score)||0;
  var fname=esc(basename(path));
  var col=scoreColor(score);
  var ir=report.individual_reviews||[];
  var scards=ir.map(function(r){
    var pct=Math.max(0,Math.min(100,((r.score-1)/4*100))).toFixed(0);
    var c=scoreColor(r.score);
    return '<div class="scard"><div class="scn">'+esc(r.criterion)+'</div>'
      +'<div class="scv" style="color:'+c+'">'+r.score.toFixed(1)
      +'<span style="font-size:.66rem;color:#7a86a1;font-weight:400">/5.0</span></div>'
      +'<div class="sbbg"><div class="sbf" style="width:'+pct+'%;background:'+c+'"></div></div>'
      +'<div class="scag">'+esc(r.agent)+'</div></div>';
  }).join('');
  var br=rv.rounds||{};
  var rl={'1':'Round 1 - Initial Assessment','2':'Round 2 - Peer Debate','3':'Round 3 - Final Positions'};
  var timeline=Object.keys(br).sort(function(a,b){return a-b;}).map(function(rn){
    var cards=br[rn].map(function(r){
      var rs=parseFloat(r.score);
      return '<div class="rc"><div class="rct"><div><div class="rag">'+esc(r.agent_name)+'</div>'
        +'<div class="rcrn">'+esc(r.criterion)+'</div></div>'
        +'<span class="rpill" style="color:'+scoreColor(rs)+'">'+rs.toFixed(1)+'</span></div>'
        +'<div class="rjust">'+(esc(r.justification)||'&mdash;')+'</div></div>';
    }).join('');
    return '<div class="rnd"><div class="rlbl">'+(rl[rn]||'Round '+rn)+'</div>'
      +'<div class="rcards">'+cards+'</div></div>';
  }).join('');
  m.innerHTML=
    '<div class="vc">'
      +'<div class="sring" style="border-color:'+col+'">'
        +'<span class="sval" style="color:'+col+'">'+score.toFixed(2)+'</span>'
        +'<span class="smax">/5.0</span>'
      +'</div>'
      +'<div class="vinfo">'
        +'<div style="font-size:.72rem;color:#7a86a1;margin-bottom:3px">'+fname+'</div>'
        +'<h2>'+esc(verdict)+'</h2>'
        +'<span class="vbadge '+verdictCls(verdict)+'">'+esc(verdict)+'</span>'
      +'</div>'
    +'</div>'
    +'<div class="stitle">Score Breakdown by Criterion</div>'
    +'<div class="sgrid">'+(scards||'<p style="color:#7a86a1;font-size:.8rem">No scores available.</p>')+'</div>'
    +'<div class="stitle">Review Chain</div>'
    +'<div>'+(timeline||'<p style="color:#7a86a1;font-size:.8rem">No reviews found.</p>')+'</div>';
}
loadPapers();setInterval(loadPapers,30000);
</script>
</body>
</html>"""


# ──────────────────────────────────────────────
# HTTP API Server (Fix 2: ThreadingHTTPServer, Fix 3: HTML dashboard)
# ──────────────────────────────────────────────

def start_api_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """
    Fix 2: ThreadingHTTPServer — each request runs in its own thread so
    long-running LLM deliberations never freeze the server or lock out endpoints.
    Fix 3: HTML dashboard served at / and /dashboard.
    """
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs

    class APIHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # suppress default per-request stdout noise

        def do_GET(self):
            parsed = urlparse(self.path)
            pth    = parsed.path
            params = parse_qs(parsed.query)

            if pth in ("/", "/dashboard"):
                self._html(DASHBOARD_HTML)
            elif pth == "/api/papers":
                self._json(_list_papers())
            elif pth == "/api/paper" and "path" in params:
                self._json(_get_paper_detail(params["path"][0]))
            elif pth == "/api/reviews" and "path" in params:
                self._json(_get_reviews(params["path"][0]))
            elif pth == "/api/deliberation" and "path" in params:
                self._json(_get_deliberation(params["path"][0]))
            elif pth == "/api/settings":
                # Get current config with key redacted for safety
                c = dict(CFG)
                if "openai_key" in c:
                    c["openai_key"] = "[REDACTED]" if c["openai_key"] else ""
                self._json(c)
            elif pth == "/api/audit":
                self._json(run_monthly_audit())
            else:
                self._404()

        def do_POST(self):
            global WEIGHTS
            parsed = urlparse(self.path)
            pth    = parsed.path

            if pth == "/api/settings":
                content_len = int(self.headers.get("Content-Length", 0))
                try:
                    body = self.rfile.read(content_len)
                    data = json.loads(body.decode("utf-8"))
                except Exception as exc:
                    self._error(400, f"Malformed JSON: {exc}")
                    return

                new_weights = data.get("weights")
                if not new_weights:
                    self._error(400, "Missing 'weights' key in request payload.")
                    return

                # Validate criteria keys match exactly
                req_keys = set(WEIGHTS.keys())
                got_keys = set(new_weights.keys())
                if req_keys != got_keys:
                    self._error(400, f"Invalid weights criteria keys. Expected: {list(req_keys)}")
                    return

                # Validate types and sum
                try:
                    parsed_weights = {k: float(v) for k, v in new_weights.items()}
                except (ValueError, TypeError):
                    self._error(400, "All weight values must be numbers.")
                    return

                w_sum = sum(parsed_weights.values())
                if not (0.999 <= w_sum <= 1.001):
                    self._error(400, f"Weights must sum to 1.0 (got {w_sum:.4f})")
                    return

                # Schema validation passed. Persist config file
                cfg_path = Path("council_config.json")
                try:
                    persisted = {}
                    if cfg_path.exists():
                        persisted = json.loads(cfg_path.read_text(encoding="utf-8"))
                    persisted["weights"] = parsed_weights
                    cfg_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")
                    
                    # Update local state live
                    CFG["weights"] = parsed_weights
                    WEIGHTS = parsed_weights
                except Exception as exc:
                    self._error(500, f"Could not write configuration file: {exc}")
                    return

                c = dict(CFG)
                if "openai_key" in c:
                    c["openai_key"] = "[REDACTED]" if c["openai_key"] else ""
                self._json(c)
            else:
                self._404()

        def _html(self, body: str):
            b = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b)

        def _json(self, data):
            b = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b)

        def _error(self, code: int, msg: str):
            b = json.dumps({"error": msg}, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _404(self):
            self.send_response(404)
            self.end_headers()

    def _list_papers() -> list:
        with closing(_db()) as conn:
            rows = conn.execute(
                "SELECT file_path, content_hash, created_at FROM papers ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def _get_paper_detail(fp: str) -> dict:
        paper = load_paper(fp)
        if not paper:
            return {"error": "not found"}
        return {
            "file_path": paper.file_path,
            "abstract":  paper.abstract[:600],
            "methods":   paper.methods[:600],
            "results":   paper.results[:600],
            "claims":    paper.claims[:600],
        }

    def _get_reviews(fp: str) -> dict:
        with closing(_db()) as conn:
            pid = conn.execute(
                "SELECT id FROM papers WHERE file_path = ?", (fp,)
            ).fetchone()
            if not pid:
                return {"error": "not found"}
            rows = conn.execute(
                "SELECT * FROM reviews WHERE paper_id = ? ORDER BY round_num, agent_name",
                (pid["id"],),
            ).fetchall()
        by_round: dict = {}
        for r in rows:
            review_dict = dict(r)
            # Parse evidence JSON array to avoid double-encoding issues
            if isinstance(review_dict.get("evidence"), str):
                try:
                    review_dict["evidence"] = json.loads(review_dict["evidence"])
                except Exception:
                    review_dict["evidence"] = []
            by_round.setdefault(r["round_num"], []).append(review_dict)
        return {"rounds": by_round}

    def _get_deliberation(fp: str) -> dict:
        with closing(_db()) as conn:
            pid = conn.execute(
                "SELECT id FROM papers WHERE file_path = ?", (fp,)
            ).fetchone()
            if not pid:
                return {"error": "not found"}
            row = conn.execute(
                "SELECT * FROM deliberations WHERE paper_id = ? ORDER BY created_at DESC LIMIT 1",
                (pid["id"],),
            ).fetchone()
        if not row:
            return {"error": "no deliberation found"}
        
        delib_dict = dict(row)
        # Parse report_json structure to avoid double-encoding inside returned JSON payload
        if isinstance(delib_dict.get("report_json"), str):
            try:
                delib_dict["report_json"] = json.loads(delib_dict["report_json"])
            except Exception:
                pass
        return delib_dict

    server = ThreadingHTTPServer((host, port), APIHandler)
    print(f"Dashboard  -> http://{host}:{port}/")
    print(f"API papers -> http://{host}:{port}/api/papers")
    print(f"API audit  -> http://{host}:{port}/api/audit")
    server.serve_forever()


def run_api_server() -> None:
    """CLI entry: python council.py --api"""
    # threading already imported at module level (Fix 12)
    t = threading.Thread(target=start_api_server, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nAPI server stopped")


# ──────────────────────────────────────────────
# Quality Control / Bias Detection (Tools Doc §4)
# ──────────────────────────────────────────────

def run_monthly_audit() -> dict:
    """QATool: compare agent scoring patterns across deliberations for drift/bias detection."""
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
        
        # Get count of unique papers processed from deliberations
        distinct_count = conn.execute(
            "SELECT COUNT(DISTINCT paper_id) FROM deliberations"
        ).fetchone()[0]

    if not rows:
        return {"status": "no_data", "message": "No completed deliberations to audit."}

    agent_stats = {}
    for r in rows:
        key = (r["agent_name"], r["criterion"])
        agent_stats.setdefault(key, []).append(r["score"])

    drift = {}
    for (agent, criterion), scores in agent_stats.items():
        drift[f"{agent}/{criterion}"] = {
            "mean": round(sum(scores) / len(scores), 2),
            "count": len(scores),
            "min": min(scores),
            "max": max(scores),
        }

    res = {
        "status": "completed",
        "papers_audited": distinct_count,
        "agent_drift": drift,
        "note": "Compare agent means to human benchmarks. Flag if |diff| > 0.5 consistently.",
    }
    if _is_stub():
        res["disclaimer"] = "Scores in stub mode are hash-derived and unsuitable for human-benchmark comparison."
    return res


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage:")
        print("  python council.py <paper.pdf>           # Run full council")
        print("  python council.py --appeal <paper.pdf> \"rebuttal text\"  # Submit appeal")
        print("  python council.py --audit               # Run monthly bias audit")
        print("  python council.py --history <paper.pdf> # Show review history")
        print("  python council.py --api                 # Start REST API server")
        return

    cmd = sys.argv[1]

    if cmd == "--appeal":
        if len(sys.argv) < 4:
            print("Usage: python council.py --appeal <paper.pdf> \"rebuttal text\"")
            sys.exit(1)
        report = submit_appeal(sys.argv[2], sys.argv[3])
        print(json.dumps(report, indent=2))

    elif cmd == "--audit":
        result = run_monthly_audit()
        print(json.dumps(result, indent=2))

    elif cmd == "--history":
        if len(sys.argv) < 3:
            print("Usage: python council.py --history <paper>")
            sys.exit(1)
        with closing(_db()) as conn:
            rows = conn.execute(
                "SELECT * FROM reviews "
                "WHERE paper_id = (SELECT id FROM papers WHERE file_path = ?)",
                (sys.argv[2],),
            ).fetchall()
        if not rows:
            print("No review history found for that paper.")
            sys.exit(1)
        for r in rows:
            print(f"  Round {r['round_num']} | {r['agent_name']} ({r['criterion']}): {r['score']}/5")

    elif cmd == "--api":
        run_api_server()

    else:
        try:
            report = run_council(sys.argv[1])
        except FileNotFoundError as exc:
            print(f"Error: File not found: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"Error executing council: {exc}", file=sys.stderr)
            sys.exit(1)

        out_path = Path(sys.argv[1]).with_suffix(".report.json")
        out_path.write_text(json.dumps(report, indent=2))
        print(f"Report saved: {out_path}")


if __name__ == "__main__":
    main()