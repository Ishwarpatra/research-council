"""Audit skill: R1→R3 score volatility and challenge sanity."""

from __future__ import annotations

from typing import Any

from skills.base import SkillResult, ok


def run_score_consistency(reviews: list[dict[str, Any]] | None = None) -> SkillResult:
    """
    reviews: list of dicts with agent_name, criterion, score, round_num, challenge_target.
    """
    rows = reviews or []
    if not rows:
        return ok(
            "audit.score_consistency",
            findings=[{"note": "No reviews supplied"}],
            message="no reviews",
        )

    by_agent: dict[str, dict[int, float]] = {}
    challenges = []
    for r in rows:
        name = r.get("agent_name") or r.get("agent") or ""
        rnd = int(r.get("round_num") or r.get("round") or 0)
        score = float(r.get("score") or 0)
        by_agent.setdefault(name, {})[rnd] = score
        ct = (r.get("challenge_target") or "").strip()
        if rnd == 2 and ct:
            challenges.append({"from": name, "target": ct, "score": score})

    volatility = []
    for name, rounds in by_agent.items():
        if 1 in rounds and 3 in rounds:
            delta = abs(rounds[3] - rounds[1])
            if delta >= 1.5:
                volatility.append({
                    "agent": name,
                    "r1": rounds[1],
                    "r3": rounds[3],
                    "delta": round(delta, 2),
                    "issue": "high_r1_r3_swing",
                })

    known = set(by_agent.keys())
    bad_challenges = [c for c in challenges if c["target"] not in known]

    findings = {
        "volatility": volatility,
        "challenges": challenges,
        "invalid_challenge_targets": bad_challenges,
    }
    score_hint = max(0.0, 1.0 - 0.15 * len(volatility) - 0.1 * len(bad_challenges))
    return ok(
        "audit.score_consistency",
        findings=findings,
        score_hint=round(score_hint, 3),
        message=f"{len(volatility)} volatility flags; {len(challenges)} challenges",
    )
