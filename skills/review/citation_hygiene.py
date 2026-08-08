"""Citation presence and format hygiene checks."""

from __future__ import annotations

import re
from typing import Any

from skills.base import SkillResult, ok

_CITATION_PATTERNS = [
    re.compile(r"\[\d+\]"),
    re.compile(r"\([A-Z][A-Za-z\-]+(?:\s+(?:et\s+al\.)?)?,?\s*\d{4}[a-z]?\)"),
    re.compile(r"[A-Z][A-Za-z\-]+\s+et\s+al\.\s*\(\d{4}\)"),
]


def _extract_citations(text: str) -> list[str]:
    found: list[str] = []
    for pat in _CITATION_PATTERNS:
        found.extend(pat.findall(text or ""))
    seen: set[str] = set()
    out: list[str] = []
    for c in found:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def run_citation_hygiene(paper: Any) -> SkillResult:
    full = getattr(paper, "full_text", "") or ""
    claims = getattr(paper, "claims", "") or ""
    abstract = getattr(paper, "abstract", "") or ""
    citations = _extract_citations(full)
    claim_cites = _extract_citations(claims + "\n" + abstract)

    findings: list[dict] = []
    if not citations:
        findings.append({
            "issue": "no_citations_detected",
            "severity": "high",
            "detail": "No bracket or author-year citations found in full text.",
        })
    else:
        findings.append({
            "issue": "citations_present",
            "severity": "info",
            "detail": f"Found {len(citations)} unique citation markers.",
            "samples": citations[:8],
        })

    if (claims or abstract) and not claim_cites and len(claims) > 80:
        findings.append({
            "issue": "claims_lack_citations",
            "severity": "medium",
            "detail": "Claims/abstract sections lack inline citation markers.",
        })

    nums = re.findall(r"\[(\d+)\]", full)
    if nums:
        max_n = max(int(n) for n in nums)
        if max_n > len(set(nums)) * 2 and "reference" not in full.lower() and "bibliography" not in full.lower():
            findings.append({
                "issue": "possible_missing_reference_list",
                "severity": "low",
                "detail": f"Highest citation index [{max_n}] but no References/Bibliography heading detected.",
            })

    high = sum(1 for f in findings if f.get("severity") == "high")
    score_hint = 1.0 if not findings or (len(citations) > 0 and high == 0) else max(0.2, 1.0 - 0.25 * high)
    return ok(
        "review.citation_hygiene",
        findings=findings,
        evidence=[{"citation_count": len(citations), "samples": citations[:5]}],
        score_hint=round(score_hint, 3),
        message=f"{len(citations)} citations; {len(findings)} hygiene notes",
    )
