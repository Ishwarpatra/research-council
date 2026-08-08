"""Jenni-inspired claim grounding: require evidence spans from methods/results only."""

from __future__ import annotations

import re
from typing import Any

from skills.base import SkillResult, ok


def _split_claims(claims: str, abstract: str) -> list[str]:
    raw = (claims or "").strip() or (abstract or "").strip()
    if not raw:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+|;\s+(?=[A-Z])", raw)
    out = []
    for p in parts:
        s = p.strip(" -\t•*")
        if len(s) >= 40:
            out.append(s)
    return out[:12]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _is_self_match(claim: str, span: str) -> bool:
    """Reject spans that are essentially the claim itself (echo / copy)."""
    c = _normalize(claim)
    s = _normalize(span)
    if not c or not s:
        return True
    # Claim extended with extra words beyond a shorter evidence span is OK (supported)
    if s in c and len(c) > len(s) * 1.15:
        return False
    if c in s or s in c:
        if len(s) > len(c) * 1.5:
            return False
        return True
    ct = set(re.findall(r"[a-z][a-z0-9\-]{3,}", c))
    st = set(re.findall(r"[a-z][a-z0-9\-]{3,}", s))
    if not ct:
        return False
    overlap = len(ct & st) / len(ct)
    return overlap >= 0.85 and abs(len(s) - len(c)) < max(40, len(c) * 0.3)


def _find_evidence_span(claim: str, corpus: str, window: int = 120) -> str | None:
    if not corpus:
        return None
    tokens = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z0-9\-]{4,}", claim)]
    if not tokens:
        return None
    corpus_l = corpus.lower()
    best_pos = -1
    best_tok = ""
    for tok in tokens:
        pos = corpus_l.find(tok)
        if pos != -1 and (best_pos == -1 or len(tok) > len(best_tok)):
            best_pos = pos
            best_tok = tok
    if best_pos < 0:
        return None
    start = max(0, best_pos - window // 2)
    end = min(len(corpus), best_pos + len(best_tok) + window // 2)
    span = corpus[start:end].strip()
    if _is_self_match(claim, span):
        return None
    return span


def run_claim_grounding(paper: Any, claim_text: str | None = None) -> SkillResult:
    """
    Score how many claims can be grounded in methods/results (not full_text).
    Optional claim_text: ground a single claim string instead of splitting paper claims.
    """
    if claim_text and str(claim_text).strip():
        claims = [str(claim_text).strip()]
    else:
        claims = _split_claims(
            getattr(paper, "claims", "") or "",
            getattr(paper, "abstract", "") or "",
        )

    # Evidence must come from methods/results only — never claims/full_text self-echo
    corpus = "\n".join([
        getattr(paper, "methods", "") or "",
        getattr(paper, "results", "") or "",
    ]).strip()

    if not claims:
        return ok(
            "review.claim_grounding",
            findings=[{"note": "No claim-like sentences found"}],
            score_hint=0.5,
            message="No claims to ground",
        )

    findings = []
    grounded = 0
    for claim in claims:
        span = _find_evidence_span(claim, corpus)
        if span:
            grounded += 1
            findings.append({
                "claim": claim[:400],
                "grounded": True,
                "evidence_span": span[:400],
                "confidence": "supported",
            })
        else:
            findings.append({
                "claim": claim[:400],
                "grounded": False,
                "evidence_span": None,
                "confidence": "ungrounded",
            })

    ratio = grounded / len(claims)
    return ok(
        "review.claim_grounding",
        findings=findings,
        evidence=[f for f in findings if f.get("grounded")],
        score_hint=round(ratio, 3),
        message=f"{grounded}/{len(claims)} claims grounded in methods/results",
    )
