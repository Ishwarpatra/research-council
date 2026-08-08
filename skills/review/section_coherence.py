"""Lightweight section coherence checks (abstract vs methods/results)."""

from __future__ import annotations

import re
from typing import Any

from skills.base import SkillResult, ok


def _keywords(text: str, n: int = 12) -> set[str]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "were", "was", "are",
        "our", "into", "using", "based", "have", "has", "been", "which", "their",
    }
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", (text or "").lower())
    freq: dict[str, int] = {}
    for t in tokens:
        if t in stop:
            continue
        freq[t] = freq.get(t, 0) + 1
    return {w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:n]}


def run_section_coherence(paper: Any) -> SkillResult:
    abstract = getattr(paper, "abstract", "") or ""
    methods = getattr(paper, "methods", "") or ""
    results = getattr(paper, "results", "") or ""

    findings: list[dict] = []
    if not abstract.strip():
        findings.append({"issue": "missing_abstract", "severity": "high"})
    if not methods.strip():
        findings.append({"issue": "missing_methods", "severity": "medium"})
    if not results.strip():
        findings.append({"issue": "missing_results", "severity": "medium"})

    ak = _keywords(abstract)
    mk = _keywords(methods)
    rk = _keywords(results)
    if ak and mk:
        overlap_m = len(ak & mk) / max(len(ak), 1)
        if overlap_m < 0.15:
            findings.append({
                "issue": "abstract_methods_drift",
                "severity": "medium",
                "detail": f"Keyword overlap abstract∩methods={overlap_m:.2f}",
            })
    if ak and rk:
        overlap_r = len(ak & rk) / max(len(ak), 1)
        if overlap_r < 0.1:
            findings.append({
                "issue": "abstract_results_drift",
                "severity": "medium",
                "detail": f"Keyword overlap abstract∩results={overlap_r:.2f}",
            })

    high = sum(1 for f in findings if f.get("severity") == "high")
    med = sum(1 for f in findings if f.get("severity") == "medium")
    score_hint = max(0.0, 1.0 - 0.3 * high - 0.15 * med)
    return ok(
        "review.section_coherence",
        findings=findings or [{"issue": "sections_ok", "severity": "info"}],
        score_hint=round(score_hint, 3),
        message=f"{len(findings)} coherence issues" if findings else "Sections look coherent",
    )
