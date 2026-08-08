"""Audit-tree prior-art skill: hybrid Chroma + Jina embed/rerank."""

from __future__ import annotations

from typing import Any

from skills.base import SkillResult, errored, ok, skipped
from skills.prior_art_validator import PriorArtValidator


def run_prior_art_audit(query_text: str, n_results: int = 3, paper: Any = None) -> SkillResult:
    q = (query_text or "").strip()
    if not q and paper is not None:
        q = (
            getattr(paper, "claims", "")
            or getattr(paper, "abstract", "")
            or (getattr(paper, "full_text", "") or "")[:500]
        )
        q = (q or "").strip()
    if not q:
        return skipped("audit.prior_art", "No query_text or paper claims available")

    try:
        validator = PriorArtValidator()
        res = validator.query_prior_art(q, n_results=n_results)
    except Exception as exc:
        return errored("audit.prior_art", str(exc))

    status = res.get("status", "error")
    if status == "skipped":
        return skipped("audit.prior_art", res.get("message", "skipped"))
    if status != "success":
        msg = res.get("message", "prior art query failed")
        # Soft-degrade when Chroma/runtime is unavailable (e.g. Python 3.14 + chromadb)
        low = msg.lower()
        if "chromadb" in low or "not initialized" in low or "unable to infer" in low:
            return skipped("audit.prior_art", msg)
        return errored("audit.prior_art", msg)

    return ok(
        "audit.prior_art",
        findings=res.get("findings", []),
        evidence=res.get("findings", []),
        message=f"{len(res.get('findings', []))} prior-art hits",
    )
