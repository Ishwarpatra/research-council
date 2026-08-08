"""Rerank helper over JinaClient with passthrough when Jina is unavailable."""

from __future__ import annotations

from typing import Any

from skills.retrieval.jina_client import JinaClient


def rerank_documents(
    query: str,
    documents: list[str],
    top_n: int = 3,
    client: JinaClient | None = None,
) -> dict[str, Any]:
    """
    Return ordered docs as {status, findings[{content, relevance_score, index}]}.
    On skip/error, returns original order truncated to top_n with score None.
    """
    jina = client or JinaClient()
    if not documents:
        return {"status": "error", "message": "documents required", "findings": []}

    res = jina.rerank(query, documents, top_n=top_n)
    if res.get("status") != "success":
        findings = [
            {"content": doc, "relevance_score": None, "index": i}
            for i, doc in enumerate(documents[:top_n])
        ]
        return {
            "status": res.get("status", "error"),
            "message": res.get("message", ""),
            "findings": findings,
        }

    findings = []
    for item in res.get("results", [])[:top_n]:
        idx = item.get("index", 0)
        doc_text = ""
        if isinstance(item.get("document"), dict):
            doc_text = item["document"].get("text", "")
        elif isinstance(item.get("document"), str):
            doc_text = item["document"]
        elif 0 <= idx < len(documents):
            doc_text = documents[idx]
        findings.append({
            "content": doc_text,
            "relevance_score": item.get("relevance_score"),
            "index": idx,
        })
    return {"status": "success", "findings": findings, "message": ""}
