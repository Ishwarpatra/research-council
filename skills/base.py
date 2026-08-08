"""Common skill result envelope for the RCC skill tree."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SkillResult:
    status: str  # success | error | skipped
    skill_id: str
    findings: list[Any] = field(default_factory=list)
    evidence: list[Any] = field(default_factory=list)
    score_hint: float | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def skipped(skill_id: str, message: str) -> SkillResult:
    return SkillResult(status="skipped", skill_id=skill_id, message=message)


def errored(skill_id: str, message: str) -> SkillResult:
    return SkillResult(status="error", skill_id=skill_id, message=message)


def ok(
    skill_id: str,
    findings: list | None = None,
    evidence: list | None = None,
    score_hint: float | None = None,
    message: str = "",
) -> SkillResult:
    return SkillResult(
        status="success",
        skill_id=skill_id,
        findings=findings or [],
        evidence=evidence or [],
        score_hint=score_hint,
        message=message,
    )
