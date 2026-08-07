#!/usr/bin/env python3
"""
Research Consensus Council - Minimal Implementation with Persistence & Real LLM Hook
5 agents, 3-round debate, weighted scoring, PDF input, SQLite audit log, HTTP API.
"""

import json
import sys
import os
import sqlite3
import hashlib
import time
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any
from contextlib import closing

# PDF extraction
try:
    import pdfplumber
except ImportError:
    pdfplumber = None
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


# ──────────────────────────────────────────────
# Config (stdlib only)
# ──────────────────────────────────────────────

def load_config() -> dict:
    """Load config from env + optional JSON file."""
    cfg = {
        "db_path": os.getenv("RCC_DB", "council.db"),
        "llm_provider": os.getenv("RCC_LLM_PROVIDER", "stub"),  # stub|ollama|openai
        "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_model_map": {
            "Orca-2": "gpt-4o-mini",
            "Phi-4": "gpt-4o-mini",
            "Mistral-7B": "gpt-4o-mini",
            "Llama-3.2": "gpt-4o-mini",
            "Phi-3": "gpt-4o-mini",
        },
        "weights": {
            "Clarity & Presentation": 0.20,
            "Methodology Rigor": 0.25,
            "Novelty & Significance": 0.20,
            "Ethics & Integrity": 0.20,
            "Practical Impact": 0.15,
        },
    }
    cfg_path = Path("council_config.json")
    if cfg_path.exists():
        cfg.update(json.loads(cfg_path.read_text()))
    return cfg


CFG = load_config()
WEIGHTS = CFG["weights"]


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


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(CFG["db_path"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(db()) as conn:
        conn.executescript(DB_SCHEMA)
        conn.commit()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def save_paper(paper: "PaperContent") -> int:
    with closing(db()) as conn:
        cur = conn.execute(
            """INSERT OR REPLACE INTO papers (file_path, content_hash, abstract, methods, results, claims, full_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (paper.file_path, paper.content_hash, paper.abstract, paper.methods,
             paper.results, paper.claims, paper.full_text, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def load_paper(file_path: str) -> "PaperContent | None":
    with closing(db()) as conn:
        row = conn.execute("SELECT * FROM papers WHERE file_path=?", (file_path,)).fetchone()
        if row:
            return PaperContent(
                file_path=row["file_path"],
                content_hash=row["content_hash"],
                abstract=row["abstract"],
                methods=row["methods"],
                results=row["results"],
                claims=row["claims"],
                full_text=row["full_text"],
            )
    return None


def save_review(paper_id: int, review: "AgentReview"):
    with closing(db()) as conn:
        conn.execute(
            """INSERT INTO reviews (paper_id, agent_name, criterion, score, justification, evidence, round_num, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (paper_id, review.agent_name, review.criterion, review.score,
             review.justification, json.dumps(review.evidence), review.round, time.time()),
        )
        conn.commit()


def save_deliberation(paper_id: int, aggregate: float, verdict: str, report: dict):
    with closing(db()) as conn:
        conn.execute(
            """INSERT INTO deliberations (paper_id, aggregate_score, verdict, report_json, created_at)
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
    evidence: list[str]
    round: int


# ──────────────────────────────────────────────
# Agent definitions
# ──────────────────────────────────────────────

AGENTS = [
    {"name": "Skeptical Reviewer", "model": "Orca-2", "criterion": "Clarity & Presentation", "weight": 0.20,
     "role": "Critical evaluator hunting for logical fallacies, overstatements, ambiguities",
     "responsibilities": "Question claims, find counter-examples, identify weaknesses in presentation"},
    {"name": "Methodologist", "model": "Phi-4", "criterion": "Methodology Rigor", "weight": 0.25,
     "role": "Detail-obsessed rigor specialist",
     "responsibilities": "Scrutinize experimental design, statistical validity, sample size, confounds"},
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
# Content extraction (with tables + citations)
# ──────────────────────────────────────────────

def extract_content(file_path: str) -> PaperContent:
    path = Path(file_path)
    text = ""
    tables = []

    if path.suffix.lower() == ".pdf":
        if pdfplumber:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
                    for table in page.extract_tables() or []:
                        tables.append("\n".join(" | ".join(str(c or "") for c in row) for row in table))
        elif PdfReader:
            reader = PdfReader(path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            raise RuntimeError("Install pdfplumber or pypdf for PDF support")
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")

    sections = _split_sections(text)
    citations = _extract_citations(text)
    full = text + ("\n\n[TABLES]\n" + "\n\n".join(tables) if tables else "") + ("\n\n[CITATIONS]\n" + "\n".join(citations) if citations else "")
    h = content_hash(full)

    abstract = sections.get("abstract") or sections.get("introduction") or text[:2000]

    return PaperContent(
        file_path=str(path),
        content_hash=h,
        abstract=abstract,
        methods=sections.get("methods", ""),
        results=sections.get("results", ""),
        claims=sections.get("claims", sections.get("conclusion", "")),
        full_text=full,
    )


def _extract_citations(text: str) -> list[str]:
    """Extract citation patterns from text (basic regex for [1], (Author, 2023), etc.)."""
    patterns = [
        r'\[\d+(?:,\s*\d+)*\]',
        r'\(\w+(?:,\s*\w+)*\s*,\s*\d{4}\)',
        r'\w+\s+et\s+al\.\s*\(\d{4}\)',
    ]
    citations = set()
    for pat in patterns:
        citations.update(re.findall(pat, text))
    return sorted(citations)[:50]


def _split_sections(text: str) -> dict[str, str]:
    """Improved heuristic: case-insensitive, handles numbered sections, common variants."""
    sections = {}
    current = "abstract"
    buf = []
    lines = text.split("\n")

    section_keywords = {
        "abstract": ["abstract"],
        "introduction": ["introduction", "1. introduction", "1 introduction"],
        "methods": ["method", "approach", "experiment", "methodology", "2. method", "3. method"],
        "results": ["result", "finding", "evaluation", "experiment", "4. result", "5. result"],
        "discussion": ["discussion", "analysis"],
        "conclusion": ["conclusion", "limitation", "future work"],
        "claims": ["claim", "contribution"],
    }

    for line in lines:
        low = line.strip().lower()
        matched = None
        for sec, kws in section_keywords.items():
            if any(kw in low for kw in kws) and len(low) < 80 and len(buf) > 50:
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
        sections["claims"] = sections.get("discussion", "") + "\n" + sections.get("conclusion", "")
    return sections


# ──────────────────────────────────────────────
# LLM client (swappable provider)
# ──────────────────────────────────────────────

def call_llm(prompt: str, model: str) -> str:
    provider = CFG["llm_provider"]

    if provider == "ollama":
        import urllib.request
        mapped = CFG["openai_model_map"].get(model, model)
        req = urllib.request.Request(
            f"{CFG['ollama_host']}/api/generate",
            data=json.dumps({"model": mapped, "prompt": prompt, "stream": False, "format": "json"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())["response"]

    if provider == "openai" and CFG["openai_key"]:
        import urllib.request
        mapped = CFG["openai_model_map"].get(model, "gpt-4o-mini")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps({
                "model": mapped,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            }).encode(),
            headers={"Authorization": f"Bearer {CFG['openai_key']}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())["choices"][0]["message"]["content"]

    # Stub fallback (deterministic by content hash)
    seed = hashlib.md5(prompt.encode()).hexdigest()[:8]
    return json.dumps({
        "score": round(3.0 + (int(seed, 16) % 20) / 10, 1),
        "justification": f"[{model}] Analysis complete. Score derived from content hash {seed}.",
        "evidence": ["Extracted text segment 1", "Extracted text segment 2"],
    })


def call_llm_with_retry(prompt: str, model: str, max_retries: int = 3) -> str:
    last_err = None
    for attempt in range(max_retries):
        try:
            return call_llm(prompt, model)
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_err}")


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
{{\"score\": float, \"justification\": string, \"evidence\": [string]}}"""


def build_prompt(agent: dict, paper: PaperContent, round_num: int, peer_reviews: list[AgentReview] | None = None) -> str:
    prompt = BASE_PROMPT.format(
        agent_name=agent["name"],
        agent_role=agent["role"],
        agent_responsibilities=agent["responsibilities"],
        assigned_criterion=agent["criterion"],
        criterion_weight=f"{agent['weight']*100:.0f}%",
        underlying_model=agent["model"],
        extracted_abstract=paper.abstract[:3000],
        extracted_methods=paper.methods[:3000],
        extracted_results=paper.results[:3000],
        extracted_claims=paper.claims[:3000],
        current_round_number=round_num,
    )
    if peer_reviews:
        prompt += "\n# PEER REVIEWS (Rounds 1-2)\n"
        for r in peer_reviews:
            prompt += f"\n## {r.agent_name} ({r.criterion}): {r.score}/5.0\n{r.justification}\n"
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

def run_round(paper: PaperContent, round_num: int, peer_reviews: list[AgentReview] | None = None) -> list[AgentReview]:
    reviews = []
    for agent in AGENTS:
        prompt = build_prompt(agent, paper, round_num, peer_reviews)
        response = call_llm_with_retry(prompt, agent["model"])
        try:
            data = json.loads(response)
            score = max(1.0, min(5.0, float(data.get("score", 3.0))))
        except json.JSONDecodeError:
            retry_prompt = prompt + "\n\nCRITICAL: Output ONLY valid JSON. No extra text."
            response = call_llm_with_retry(retry_prompt, agent["model"])
            try:
                data = json.loads(response)
                score = max(1.0, min(5.0, float(data.get("score", 3.0))))
            except json.JSONDecodeError:
                score = 3.0
                data = {"justification": "JSON parse failed after retry", "evidence": []}
        except Exception as e:
            score = 3.0
            data = {"justification": f"Error: {e}", "evidence": []}

        reviews.append(AgentReview(
            agent_name=agent["name"],
            criterion=agent["criterion"],
            score=score,
            justification=data.get("justification", ""),
            evidence=data.get("evidence", []),
            round=round_num,
        ))
    return reviews


def run_council(paper_path: str) -> dict:
    init_db()
    print(f"📄 Extracting: {paper_path}")

    cached = load_paper(paper_path)
    if cached and cached.content_hash == content_hash(Path(paper_path).read_bytes() if Path(paper_path).suffix == ".pdf" else Path(paper_path).read_text()):
        print("📦 Loaded from cache")
        paper = cached
    else:
        paper = extract_content(paper_path)

    paper_id = save_paper(paper)

    print("🗣️  Round 1: Initial reviews...")
    r1 = run_round(paper, 1)
    for r in r1:
        save_review(paper_id, r)

    print("🗣️  Round 2: Debate...")
    r2 = run_round(paper, 2, r1)
    for r in r2:
        save_review(paper_id, r)

    print("🗣️  Round 3: Final positions...")
    r3 = run_round(paper, 3, r1 + r2)
    for r in r3:
        save_review(paper_id, r)

    all_reviews = r1 + r2 + r3

    final_scores = {r.criterion: r.score for r in r3}
    aggregate = ScoreCalculator.compute(WEIGHTS, final_scores)
    verdict = determine_verdict(aggregate)

    print(f"✅ Verdict: {verdict} ({aggregate}/5.0)")

    report = generate_report(paper, all_reviews, aggregate, verdict)
    save_deliberation(paper_id, aggregate, verdict, report)
    notify(verdict, aggregate, paper_path)
    return report


def determine_verdict(score: float) -> str:
    if score >= 4.5:
        return "Accept"
    if score >= 3.5:
        return "Minor Revisions"
    if score >= 2.5:
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
            "key_strengths": agreements[:3],
            "major_concerns": disagreements[:3],
        },
        "individual_reviews": [
            {"agent": r.agent_name, "criterion": r.criterion, "score": r.score,
             "justification": r.justification, "evidence": r.evidence}
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

def notify(verdict: str, score: float, paper_path: str):
    msg = f"📢 Research Consensus Council: {Path(paper_path).name} → {verdict} ({score}/5.0)"
    print(msg)


# ──────────────────────────────────────────────
# Appeal Processor (FR5)
# ──────────────────────────────────────────────

def submit_appeal(paper_path: str, author_rebuttal: str) -> dict:
    init_db()
    paper = load_paper(paper_path)
    if not paper:
        return {"error": "Paper not found. Run council first."}

    paper_id = save_paper(paper)

    with closing(db()) as conn:
        conn.execute(
            "INSERT INTO appeals (paper_id, author_rebuttal, status, created_at) VALUES (?, ?, 'pending', ?)",
            (paper_id, author_rebuttal, time.time()),
        )
        conn.commit()

    paper.claims += f"\n\n[AUTHOR REBUTTAL]\n{author_rebuttal}"
    save_paper(paper)

    print("⚖️  Appeal submitted. Re-deliberating...")
    return run_council(paper_path)


# ──────────────────────────────────────────────
# HTTP API Server (stdlib) — for frontend/data panels
# ──────────────────────────────────────────────

def start_api_server(host: str = "127.0.0.1", port: int = 8080):
    """Minimal REST API for review chain visibility & vote breakdown."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs

    class APIHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            if path == "/api/papers":
                self._json(list_papers())
            elif path == "/api/paper" and "path" in params:
                self._json(get_paper_detail(params["path"][0]))
            elif path == "/api/reviews" and "path" in params:
                self._json(get_reviews(params["path"][0]))
            elif path == "/api/deliberation" and "path" in params:
                self._json(get_deliberation(params["path"][0]))
            elif path == "/api/audit":
                self._json(run_monthly_audit())
            else:
                self._404()

        def _json(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())

        def _404(self):
            self.send_response(404)
            self.end_headers()

    def list_papers() -> list[dict]:
        with closing(db()) as conn:
            rows = conn.execute("SELECT file_path, content_hash, created_at FROM papers ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get_paper_detail(file_path: str) -> dict:
        paper = load_paper(file_path)
        if not paper:
            return {"error": "not found"}
        return {"file_path": paper.file_path, "abstract": paper.abstract[:500], "methods": paper.methods[:500], "results": paper.results[:500], "claims": paper.claims[:500]}

    def get_reviews(file_path: str) -> dict:
        paper = load_paper(file_path)
        if not paper:
            return {"error": "not found"}
        with closing(db()) as conn:
            pid_row = conn.execute("SELECT id FROM papers WHERE file_path=?", (file_path,)).fetchone()
            if not pid_row:
                return {"error": "not found"}
            rows = conn.execute("SELECT * FROM reviews WHERE paper_id=? ORDER BY round_num, agent_name", (pid_row["id"],)).fetchall()
            by_round = {}
            for r in rows:
                by_round.setdefault(r["round_num"], []).append(dict(r))
            return {"rounds": by_round}

    def get_deliberation(file_path: str) -> dict:
        paper = load_paper(file_path)
        if not paper:
            return {"error": "not found"}
        with closing(db()) as conn:
            pid_row = conn.execute("SELECT id FROM papers WHERE file_path=?", (file_path,)).fetchone()
            if not pid_row:
                return {"error": "not found"}
            row = conn.execute("SELECT * FROM deliberations WHERE paper_id=? ORDER BY created_at DESC LIMIT 1", (pid_row["id"],)).fetchone()
            if not row:
                return {"error": "no deliberation"}
            return dict(row)

    server = HTTPServer((host, port), APIHandler)
    print(f"🌐 API server running at http://{host}:{port}")
    print("   GET /api/papers           — list all papers")
    print("   GET /api/paper?path=...   — paper detail")
    print("   GET /api/reviews?path=... — full review chain")
    print("   GET /api/deliberation?path=... — verdict & aggregate")
    print("   GET /api/audit            — bias audit")
    server.serve_forever()


def run_api_server():
    """CLI entry: python council.py --api"""
    import threading
    t = threading.Thread(target=start_api_server, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 API server stopped")


# ──────────────────────────────────────────────
# Quality Control / Bias Detection (Tools Doc §4)
# ──────────────────────────────────────────────

def run_monthly_audit() -> dict:
    """Compare agent consensus vs historical human decisions (stub for QATool)."""
    with closing(db()) as conn:
        rows = conn.execute("""
            SELECT d.paper_id, d.verdict, d.aggregate_score, r.agent_name, r.criterion, r.score, r.round_num
            FROM deliberations d
            JOIN reviews r ON d.paper_id = r.paper_id
            WHERE r.round_num = 3
            ORDER BY d.created_at DESC
            LIMIT 1000
        """).fetchall()

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

    return {
        "status": "completed",
        "papers_audited": len(set(r["paper_id"] for r in rows)),
        "agent_drift": drift,
        "note": "Compare agent means to human benchmarks. Flag if |diff| > 0.5 consistently.",
    }


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
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
            return
        report = submit_appeal(sys.argv[2], sys.argv[3])
        print(json.dumps(report, indent=2))

    elif cmd == "--audit":
        result = run_monthly_audit()
        print(json.dumps(result, indent=2))

    elif cmd == "--history":
        paper = load_paper(sys.argv[2])
        if not paper:
            print("Paper not found")
            return
        with closing(db()) as conn:
            rows = conn.execute("SELECT * FROM reviews WHERE paper_id=(SELECT id FROM papers WHERE file_path=?)", (sys.argv[2],)).fetchall()
            for r in rows:
                print(f"  Round {r['round_num']} | {r['agent_name']} ({r['criterion']}): {r['score']}/5")

    elif cmd == "--api":
        run_api_server()

    else:
        report = run_council(sys.argv[1])
        out_path = Path(sys.argv[1]).with_suffix(".report.json")
        out_path.write_text(json.dumps(report, indent=2))
        print(f"📝 Report saved: {out_path}")


if __name__ == "__main__":
    main()