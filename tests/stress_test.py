#!/usr/bin/env python3
"""
RCC stub-mode stress suite: API load, API limits, hallucination/grounding, engine batch.

Usage:
  python tests/stress_test.py --base-url http://127.0.0.1:8090
  python tests/stress_test.py --api --limits --hallucination --engine --engine-n 10
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURE = ROOT / "tests" / "fixtures" / "test_paper.txt"
GROUNDED = ROOT / "tests" / "fixtures" / "paper_grounded.txt"
UNGROUNDED = ROOT / "tests" / "fixtures" / "paper_ungrounded.txt"


def _req(method: str, url: str, body: dict | None = None, timeout: float = 60.0) -> tuple[int, dict | str]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return s[idx]


def _pick_paper_path(base: str) -> str:
    code, data = _req("GET", f"{base}/api/papers")
    if code != 200 or not isinstance(data, list) or not data:
        # seed by running claim_grounding on fixture so paper may exist after council
        return str(FIXTURE.relative_to(ROOT)).replace("\\", "/")
    return data[0]["file_path"]


# ──────────────────────────────────────────────
# Phase A — API concurrent load
# ──────────────────────────────────────────────

def phase_api_load(base: str) -> dict:
    latencies: list[float] = []
    errors = 0
    total = 0
    lock = threading.Lock()

    endpoints = [
        "/api/papers",
        "/api/settings",
        "/api/active_deliberation",
        "/api/skills/tools",
    ]

    def hit(path: str):
        nonlocal errors, total
        t0 = time.perf_counter()
        code, _ = _req("GET", f"{base}{path}", timeout=30)
        dt = time.perf_counter() - t0
        with lock:
            total += 1
            latencies.append(dt)
            if code >= 400:
                errors += 1
        return code

    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = []
        for _ in range(10):
            for ep in endpoints:
                futs.append(ex.submit(hit, ep))
        for f in as_completed(futs):
            f.result()

    paper_path = _pick_paper_path(base)
    ep = urllib.parse.quote(paper_path, safe="")

    def hit_paper(kind: str):
        nonlocal errors, total
        url = f"{base}/api/{kind}?path={ep}"
        t0 = time.perf_counter()
        code, _ = _req("GET", url, timeout=30)
        dt = time.perf_counter() - t0
        with lock:
            total += 1
            latencies.append(dt)
            # deliberation may 404 if never run — count as soft miss not hard fail for load
            if code >= 500:
                errors += 1
        return code

    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = []
        for _ in range(5):
            for kind in ("paper", "reviews", "deliberation"):
                futs.append(ex.submit(hit_paper, kind))
        for f in as_completed(futs):
            f.result()

    # claim grounding storm
    cg_path = urllib.parse.quote(str(GROUNDED), safe="")
    def hit_cg():
        nonlocal errors, total
        t0 = time.perf_counter()
        code, _ = _req("POST", f"{base}/api/skills/claim_grounding?path={cg_path}", timeout=60)
        dt = time.perf_counter() - t0
        with lock:
            total += 1
            latencies.append(dt)
            if code >= 400:
                errors += 1
        return code

    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(hit_cg) for _ in range(15)]
        for f in as_completed(futs):
            f.result()

    # HITL serialize: 3 cycles
    hitl_ok = 0
    fixture_rel = str(FIXTURE)
    for i in range(3):
        if _run_hitl_cycle(base, fixture_rel):
            hitl_ok += 1

    err_rate = (errors / total) if total else 1.0
    passed = err_rate < 0.05 and hitl_ok == 3
    return {
        "phase": "api_load",
        "passed": passed,
        "total_requests": total,
        "errors": errors,
        "error_rate": round(err_rate, 4),
        "latency_p50_s": round(_percentile(latencies, 50), 4),
        "latency_p95_s": round(_percentile(latencies, 95), 4),
        "hitl_cycles_ok": hitl_ok,
        "hitl_cycles_total": 3,
    }


def _wait_status(base: str, want: set[str], timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        code, data = _req("GET", f"{base}/api/active_deliberation", timeout=10)
        if code == 200 and isinstance(data, dict):
            last = data
            if data.get("status") in want:
                return data
        time.sleep(0.4)
    return last


def _run_hitl_cycle(base: str, paper_path: str) -> bool:
    # wait until idle
    st = _wait_status(base, {"idle", "completed", "failed", "aborted"}, timeout=60)
    if st.get("status") in ("deliberating", "waiting_for_approval"):
        # try abort to clear
        _req("POST", f"{base}/api/abort_round")
        time.sleep(1)
        _wait_status(base, {"idle", "aborted", "failed", "completed"}, timeout=30)

    ep = urllib.parse.quote(paper_path, safe="")
    code, body = _req("POST", f"{base}/api/deliberate?path={ep}", timeout=30)
    if code != 200:
        return False
    for _ in range(2):
        st = _wait_status(base, {"waiting_for_approval", "completed", "failed", "aborted"}, timeout=90)
        if st.get("status") == "waiting_for_approval":
            ac, _ = _req("POST", f"{base}/api/approve_round")
            if ac != 200:
                return False
        elif st.get("status") == "completed":
            return True
        elif st.get("status") in ("failed", "aborted"):
            return False
    st = _wait_status(base, {"completed", "failed", "aborted", "idle"}, timeout=60)
    return st.get("status") == "completed"


# ──────────────────────────────────────────────
# Phase B — API limits
# ──────────────────────────────────────────────

def phase_api_limits(base: str) -> dict:
    results = []

    def check(name: str, ok: bool, detail: str = ""):
        results.append({"name": name, "passed": ok, "detail": detail})

    # Ensure idle
    st = _wait_status(base, {"idle", "completed", "failed", "aborted"}, timeout=30)
    if st.get("status") in ("deliberating", "waiting_for_approval"):
        _req("POST", f"{base}/api/abort_round")
        time.sleep(1)

    # Missing manuscript
    code, body = _req("POST", f"{base}/api/deliberate?path=missing_does_not_exist.pdf")
    check("missing_manuscript_404", code == 404, f"code={code} body={body}")

    # Empty prior art query
    code, body = _req("GET", f"{base}/api/prior_art?query=")
    check("empty_prior_art_400", code == 400, f"code={code}")

    # Bad weights
    bad = {
        "weights": {
            "Clarity & Presentation": 0.1,
            "Methodology Rigor": 0.1,
            "Novelty & Significance": 0.1,
            "Ethics & Integrity": 0.1,
            "Practical Impact": 0.1,
        }
    }
    code, body = _req("POST", f"{base}/api/settings", bad)
    check("bad_weights_400", code == 400, f"code={code}")

    # Approve when idle
    _wait_status(base, {"idle", "completed", "failed", "aborted"}, timeout=20)
    # force idle-ish: if completed, approve should fail
    code, body = _req("POST", f"{base}/api/approve_round")
    check("approve_when_idle_400", code == 400, f"code={code}")

    # Empty appeal rebuttal (need existing paper)
    paper_path = _pick_paper_path(base)
    ep = urllib.parse.quote(paper_path, safe="")
    code, body = _req("POST", f"{base}/api/appeal?path={ep}&rebuttal=")
    check("empty_rebuttal_400", code == 400, f"code={code} body={body}")

    # Single active deliberation + burst reads
    code, body = _req("POST", f"{base}/api/deliberate?path={urllib.parse.quote(str(FIXTURE), safe='')}")
    check("start_deliberation_200", code == 200, f"code={code}")
    st = _wait_status(base, {"waiting_for_approval", "failed"}, timeout=90)
    check("reached_hitl", st.get("status") == "waiting_for_approval", f"status={st.get('status')}")

    code2, body2 = _req("POST", f"{base}/api/deliberate?path={urllib.parse.quote(str(FIXTURE), safe='')}")
    check("second_deliberate_400", code2 == 400, f"code={code2} body={body2}")

    burst_ok = 0
    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = [ex.submit(_req, "GET", f"{base}/api/active_deliberation") for _ in range(20)]
        for f in as_completed(futs):
            c, d = f.result()
            if c == 200 and isinstance(d, dict) and d.get("status") == "waiting_for_approval":
                burst_ok += 1
    check("burst_reads_during_hitl", burst_ok == 20, f"ok={burst_ok}/20")

    # cleanup HITL
    while True:
        st = _wait_status(base, {"waiting_for_approval", "completed", "failed", "aborted", "idle"}, timeout=30)
        if st.get("status") == "waiting_for_approval":
            _req("POST", f"{base}/api/approve_round")
            time.sleep(0.5)
        else:
            break

    passed = all(r["passed"] for r in results)
    return {"phase": "api_limits", "passed": passed, "checks": results}


# ──────────────────────────────────────────────
# Phase C — Hallucination / grounding
# ──────────────────────────────────────────────

def phase_hallucination(base: str) -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = ""):
        checks.append({"name": name, "passed": ok, "detail": detail})

    # 1) Skill API ungrounded
    ug = urllib.parse.quote(str(UNGROUNDED), safe="")
    code, data = _req("POST", f"{base}/api/skills/claim_grounding?path={ug}", timeout=60)
    findings = data.get("findings", []) if isinstance(data, dict) else []
    ungrounded = [f for f in findings if isinstance(f, dict) and f.get("grounded") is False]
    check("api_ungrounded_flags", code == 200 and len(ungrounded) >= 1, f"ungrounded={len(ungrounded)}")

    # 1b) Skill API grounded
    g = urllib.parse.quote(str(GROUNDED), safe="")
    code, data = _req("POST", f"{base}/api/skills/claim_grounding?path={g}", timeout=60)
    findings = data.get("findings", []) if isinstance(data, dict) else []
    claim_findings = [f for f in findings if isinstance(f, dict) and "claim" in f]
    grounded_n = sum(1 for f in claim_findings if f.get("grounded"))
    check(
        "api_grounded_majority",
        code == 200 and claim_findings and grounded_n >= max(1, len(claim_findings) // 2),
        f"grounded={grounded_n}/{len(claim_findings)}",
    )

    # 2+4) Engine path on ungrounded + simulation_mode
    os.environ["RCC_NON_INTERACTIVE"] = "true"
    os.environ.setdefault("LLM_PROVIDER", "stub")
    import council
    # force stub-friendly
    report = council.run_council(str(UNGROUNDED))
    sf = (report.get("skill_findings") or {}).get("review") or {}
    skills = sf.get("skills") or []
    cg = next((s for s in skills if s.get("skill_id") == "review.claim_grounding"), None)
    eng_ungrounded = []
    if cg:
        eng_ungrounded = [f for f in (cg.get("findings") or []) if isinstance(f, dict) and f.get("grounded") is False]
    check("engine_ungrounded_in_skill_findings", len(eng_ungrounded) >= 1, f"n={len(eng_ungrounded)}")

    ctx = council._format_skill_context({"review": sf})
    check("skill_context_has_UNGROUNDED", "UNGROUNDED" in ctx, ctx[:120])

    sim = (report.get("executive_summary") or {}).get("simulation_mode")
    check("stub_simulation_mode_true", sim is True, f"simulation_mode={sim}")

    # 3) full_text self-echo must not ground
    from council import PaperContent
    from skills.review.claim_grounding import run_claim_grounding
    paper = PaperContent(
        file_path="echo.txt",
        content_hash="x",
        abstract="Short abstract placeholder text for parsing purposes here.",
        methods="Samples were refrigerated only.",
        results="Time was twelve minutes.",
        claims="Quantum teleportation of entire hospitals is achieved routinely in this work.",
        full_text="Quantum teleportation of entire hospitals is achieved routinely in this work.",
    )
    res = run_claim_grounding(paper)
    echo_flags = [f for f in res.findings if isinstance(f, dict) and f.get("claim")]
    check(
        "no_fulltext_self_hallucination",
        bool(echo_flags) and all(not f.get("grounded") for f in echo_flags),
        res.message,
    )

    passed = all(c["passed"] for c in checks)
    return {"phase": "hallucination", "passed": passed, "checks": checks}


# ──────────────────────────────────────────────
# Phase D — Engine batch
# ──────────────────────────────────────────────

def phase_engine_batch(n: int = 10) -> dict:
    os.environ["RCC_NON_INTERACTIVE"] = "true"
    os.environ.setdefault("LLM_PROVIDER", "stub")
    import council

    ok = 0
    errors = []
    times = []
    with tempfile.TemporaryDirectory() as td:
        src = FIXTURE.read_text(encoding="utf-8")
        for i in range(n):
            p = Path(td) / f"paper_{i}.txt"
            p.write_text(src, encoding="utf-8")
            t0 = time.perf_counter()
            try:
                report = council.run_council(str(p))
                dt = time.perf_counter() - t0
                times.append(dt)
                if report.get("skill_findings") and report.get("executive_summary"):
                    ok += 1
                else:
                    errors.append(f"missing fields run {i}")
            except Exception as exc:
                errors.append(f"run {i}: {exc}")

    passed = ok == n
    return {
        "phase": "engine_batch",
        "passed": passed,
        "ok": ok,
        "total": n,
        "errors": errors[:5],
        "avg_s": round(statistics.mean(times), 3) if times else None,
        "p95_s": round(_percentile(times, 95), 3) if times else None,
    }


def _ensure_server(base: str, start: bool) -> None:
    code, _ = _req("GET", f"{base}/api/health/circuit", timeout=3)
    if code == 200:
        return
    if not start:
        raise SystemExit(f"API not reachable at {base}. Start server or pass --start-server.")
    # parse port
    from urllib.parse import urlparse
    u = urlparse(base)
    port = u.port or 8090
    host = u.hostname or "127.0.0.1"

    def run():
        import api
        api.start_server(host, port)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    for _ in range(40):
        time.sleep(0.5)
        code, _ = _req("GET", f"{base}/api/health/circuit", timeout=2)
        if code == 200:
            return
    raise SystemExit(f"Failed to start API on {base}")


def main():
    parser = argparse.ArgumentParser(description="RCC stub-mode stress suite")
    parser.add_argument("--base-url", default="http://127.0.0.1:8090")
    parser.add_argument("--api", action="store_true", help="Run API load phase")
    parser.add_argument("--limits", action="store_true", help="Run API limit phase")
    parser.add_argument("--hallucination", action="store_true", help="Run hallucination phase")
    parser.add_argument("--engine", action="store_true", help="Run engine batch phase")
    parser.add_argument("--engine-n", type=int, default=10)
    parser.add_argument("--start-server", action="store_true")
    args = parser.parse_args()

    # default: all phases
    run_all = not any([args.api, args.limits, args.hallucination, args.engine])
    if run_all:
        args.api = args.limits = args.hallucination = args.engine = True

    os.chdir(ROOT)
    os.environ.setdefault("OPENAI_API_KEY", "dummy_openai_key")
    os.environ.setdefault("LLM_PROVIDER", "stub")
    os.environ["RCC_NON_INTERACTIVE"] = "true"

    need_api = args.api or args.limits or args.hallucination
    if need_api:
        try:
            _ensure_server(args.base_url.rstrip("/"), args.start_server)
        except SystemExit as e:
            # try start anyway on failure if flag set
            if args.start_server:
                raise
            print(json.dumps({"error": str(e)}))
            # still allow engine-only
            if not args.engine:
                sys.exit(1)
            need_api = False

    summary = {"base_url": args.base_url, "phases": []}
    base = args.base_url.rstrip("/")

    if args.api and need_api:
        print("Running Phase A: API load...", flush=True)
        summary["phases"].append(phase_api_load(base))
    if args.limits and need_api:
        print("Running Phase B: API limits...", flush=True)
        summary["phases"].append(phase_api_limits(base))
    if args.hallucination:
        print("Running Phase C: Hallucination...", flush=True)
        # hallucination uses API for skill checks when server up
        if need_api or args.start_server:
            try:
                _ensure_server(base, args.start_server)
                summary["phases"].append(phase_hallucination(base))
            except SystemExit:
                # engine-only subset without API skill checks — still run local checks
                summary["phases"].append(phase_hallucination_local_only())
        else:
            summary["phases"].append(phase_hallucination_local_only())
    if args.engine:
        print("Running Phase D: Engine batch...", flush=True)
        summary["phases"].append(phase_engine_batch(args.engine_n))

    summary["passed"] = all(p.get("passed") for p in summary["phases"]) if summary["phases"] else False
    print(json.dumps(summary, indent=2))
    sys.exit(0 if summary["passed"] else 1)


def phase_hallucination_local_only() -> dict:
    """Fallback without API: engine + claim_grounding only."""
    os.environ["RCC_NON_INTERACTIVE"] = "true"
    checks = []
    from council import PaperContent, _format_skill_context, run_council
    from skills.review.claim_grounding import run_claim_grounding

    report = run_council(str(UNGROUNDED))
    sf = (report.get("skill_findings") or {}).get("review") or {}
    cg = next((s for s in (sf.get("skills") or []) if s.get("skill_id") == "review.claim_grounding"), None)
    ung = [f for f in (cg or {}).get("findings", []) if isinstance(f, dict) and f.get("grounded") is False]
    checks.append({"name": "engine_ungrounded_in_skill_findings", "passed": len(ung) >= 1, "detail": f"n={len(ung)}"})
    ctx = _format_skill_context({"review": sf})
    checks.append({"name": "skill_context_has_UNGROUNDED", "passed": "UNGROUNDED" in ctx, "detail": ""})
    sim = (report.get("executive_summary") or {}).get("simulation_mode")
    checks.append({"name": "stub_simulation_mode_true", "passed": sim is True, "detail": f"{sim}"})
    paper = PaperContent(
        file_path="echo.txt", content_hash="x",
        abstract="Short abstract placeholder text for parsing purposes here.",
        methods="Samples were refrigerated only.", results="Time was twelve minutes.",
        claims="Quantum teleportation of entire hospitals is achieved routinely in this work.",
        full_text="Quantum teleportation of entire hospitals is achieved routinely in this work.",
    )
    res = run_claim_grounding(paper)
    echo_flags = [f for f in res.findings if isinstance(f, dict) and f.get("claim")]
    checks.append({
        "name": "no_fulltext_self_hallucination",
        "passed": bool(echo_flags) and all(not f.get("grounded") for f in echo_flags),
        "detail": res.message,
    })
    # mark API checks skipped as failed? Plan wants API checks — fail closed if no API
    checks.append({"name": "api_ungrounded_flags", "passed": False, "detail": "API unavailable"})
    checks.append({"name": "api_grounded_majority", "passed": False, "detail": "API unavailable"})
    return {"phase": "hallucination", "passed": all(c["passed"] for c in checks), "checks": checks}


if __name__ == "__main__":
    main()
