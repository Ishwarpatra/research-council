"""
RCC skill tree registry.

Modes:
  review — pre-council manuscript checks
  audit  — post-council / DB quality checks
  full   — review only at this layer (council wires audit separately)
"""

from __future__ import annotations

import logging
from typing import Any

from skills.base import SkillResult
from skills.review.claim_grounding import run_claim_grounding
from skills.review.citation_hygiene import run_citation_hygiene
from skills.review.section_coherence import run_section_coherence

logger = logging.getLogger("rcc.skills")


def run_review_tree(paper: Any) -> list[dict]:
    results: list[SkillResult] = []
    for fn in (run_claim_grounding, run_citation_hygiene, run_section_coherence):
        try:
            results.append(fn(paper))
        except Exception as exc:
            logger.exception("Review skill failed: %s", fn.__name__)
            from skills.base import errored
            results.append(errored(fn.__name__, str(exc)))
    return [r.to_dict() for r in results]


def run_audit_tree(
    reviews: list[dict] | None = None,
    query_text: str = "",
    paper: Any = None,
) -> list[dict]:
    from skills.audit.bias_drift import run_bias_drift
    from skills.audit.score_consistency import run_score_consistency
    from skills.audit.prior_art import run_prior_art_audit

    results: list[SkillResult] = []
    try:
        results.append(run_bias_drift())
    except Exception as exc:
        from skills.base import errored
        results.append(errored("audit.bias_drift", str(exc)))

    try:
        results.append(run_score_consistency(reviews))
    except Exception as exc:
        from skills.base import errored
        results.append(errored("audit.score_consistency", str(exc)))

    try:
        results.append(run_prior_art_audit(query_text=query_text, paper=paper))
    except Exception as exc:
        from skills.base import errored
        results.append(errored("audit.prior_art", str(exc)))

    return [r.to_dict() for r in results]


def run_skill_tree(
    mode: str,
    paper: Any = None,
    context: dict | None = None,
) -> dict[str, Any]:
    """
    Run a skill-tree mode and return {mode, skills: [...], summary}.
    """
    ctx = context or {}
    mode_l = (mode or "review").lower().strip()
    if mode_l in ("review", "full"):
        skills = run_review_tree(paper)
        if mode_l == "full":
            # full = review now; caller/council may append audit after deliberation
            pass
    elif mode_l == "audit":
        skills = run_audit_tree(
            reviews=ctx.get("reviews"),
            query_text=ctx.get("query_text", ""),
            paper=paper,
        )
    else:
        return {"mode": mode_l, "skills": [], "error": f"Unknown skill mode: {mode}"}

    ok_n = sum(1 for s in skills if s.get("status") == "success")
    return {
        "mode": mode_l,
        "skills": skills,
        "summary": {
            "total": len(skills),
            "success": ok_n,
            "errors": sum(1 for s in skills if s.get("status") == "error"),
            "skipped": sum(1 for s in skills if s.get("status") == "skipped"),
        },
    }
