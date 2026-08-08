"""
Agent-kit tool registry (OpenAI function schemas + sync dispatcher).

RCC does not yet run a multi-turn LLM tool-calling loop; schemas are registered
here for API/tests/future loops. Agents consume results today via prompt injection.
"""

from __future__ import annotations

from typing import Any

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_claim_grounding",
            "description": (
                "Jenni-style claim confidence check: verify whether manuscript claims "
                "are supported by methods/results evidence spans, or flag them as ungrounded."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_text": {
                        "type": "string",
                        "description": (
                            "Optional single claim to verify. If omitted, all claims "
                            "from the current paper are checked."
                        ),
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_prior_art",
            "description": (
                "Searches the local vector database (Chroma, optionally Jina embed/rerank) "
                "for existing research related to a scientific claim."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_text": {
                        "type": "string",
                        "description": "Scientific claim or keyword phrase to verify.",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of top matches (1–5). Defaults to 3.",
                        "minimum": 1,
                        "maximum": 5,
                    },
                },
                "required": ["query_text"],
                "additionalProperties": False,
            },
        },
    },
]


def dispatch_tool(name: str, args: dict | None = None, paper: Any = None) -> dict[str, Any]:
    """Run a registered agent tool and return a plain dict result."""
    args = args or {}
    tool = (name or "").strip()

    if tool == "query_claim_grounding":
        from skills.review.claim_grounding import run_claim_grounding
        if paper is None:
            return {"status": "error", "message": "paper required for query_claim_grounding", "findings": []}
        result = run_claim_grounding(paper, claim_text=args.get("claim_text"))
        return result.to_dict()

    if tool == "query_prior_art":
        from skills.prior_art_validator import PriorArtValidator
        q = (args.get("query_text") or "").strip()
        if not q and paper is not None:
            q = (
                getattr(paper, "claims", "")
                or getattr(paper, "abstract", "")
                or ""
            ).strip()
        if not q:
            return {"status": "error", "message": "query_text required", "findings": []}
        n = args.get("n_results", 3)
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 3
        return PriorArtValidator().query_prior_art(q, n_results=n)

    return {"status": "error", "message": f"Unknown tool: {name}", "findings": []}


def list_tool_names() -> list[str]:
    return [t["function"]["name"] for t in TOOL_SCHEMAS]
