"""Audit skill: wrap monthly bias/drift stats into SkillResult."""

from __future__ import annotations

from typing import Any, Callable

from skills.base import SkillResult, errored, ok


def run_bias_drift(audit_fn: Callable[[], dict] | None = None) -> SkillResult:
    try:
        if audit_fn is None:
            import council
            data = council.run_monthly_audit()
        else:
            data = audit_fn()
    except Exception as exc:
        return errored("audit.bias_drift", str(exc))

    if data.get("status") == "no_data":
        return ok(
            "audit.bias_drift",
            findings=[data],
            score_hint=None,
            message=data.get("message", "no data"),
        )

    drift = data.get("agent_score_drift") or data.get("agent_drift") or data.get("drift") or {}
    # Flag agents with very tight or extreme ranges
    flags = []
    for key, stats in drift.items() if isinstance(drift, dict) else []:
        if not isinstance(stats, dict):
            continue
        spread = (stats.get("max", 0) or 0) - (stats.get("min", 0) or 0)
        mean = stats.get("mean", 0) or 0
        if stats.get("count", 0) >= 3 and spread < 0.3:
            flags.append({"agent_criterion": key, "issue": "low_variance", "stats": stats})
        if mean <= 2.0 or mean >= 4.7:
            flags.append({"agent_criterion": key, "issue": "extreme_mean", "stats": stats})

    return ok(
        "audit.bias_drift",
        findings={"drift": drift, "flags": flags, "raw": data},
        score_hint=None if not flags else max(0.0, 1.0 - 0.1 * len(flags)),
        message=f"{len(flags)} drift flags",
    )
