"""Shared Jina AI HTTP client (embeddings, rerank, reader). Soft-fails without a key."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("rcc.skills.jina")

EMBED_URL = "https://api.jina.ai/v1/embeddings"
RERANK_URL = "https://api.jina.ai/v1/rerank"
READER_PREFIX = "https://r.jina.ai/"

DEFAULT_EMBED_MODEL = "jina-embeddings-v5-text-small"
DEFAULT_RERANK_MODEL = "jina-reranker-v3.5"


class JinaClient:
    def __init__(self, api_key: str | None = None, timeout: float = 60.0):
        self.api_key = (api_key if api_key is not None else settings.jina_api_key) or ""
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key.strip())

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def embed(self, texts: list[str], model: str = DEFAULT_EMBED_MODEL) -> dict[str, Any]:
        if not self.available:
            return {"status": "skipped", "message": "JINA_API_KEY not set", "embeddings": []}
        if not texts:
            return {"status": "error", "message": "texts required", "embeddings": []}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    EMBED_URL,
                    headers=self._headers(),
                    json={"model": model, "input": texts},
                )
                resp.raise_for_status()
                data = resp.json()
            vectors = [item.get("embedding", []) for item in data.get("data", [])]
            return {"status": "success", "embeddings": vectors, "model": model}
        except Exception as exc:
            logger.error("Jina embed failed: %s", exc)
            return {"status": "error", "message": str(exc), "embeddings": []}

    def rerank(
        self,
        query: str,
        documents: list[str],
        model: str = DEFAULT_RERANK_MODEL,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        if not self.available:
            return {"status": "skipped", "message": "JINA_API_KEY not set", "results": []}
        if not query.strip() or not documents:
            return {"status": "error", "message": "query and documents required", "results": []}
        payload: dict[str, Any] = {
            "model": model,
            "query": query,
            "documents": documents,
            "return_documents": True,
        }
        if top_n is not None:
            payload["top_n"] = top_n
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(RERANK_URL, headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
            results = data.get("results") or data.get("data") or []
            return {"status": "success", "results": results, "model": model}
        except Exception as exc:
            logger.error("Jina rerank failed: %s", exc)
            return {"status": "error", "message": str(exc), "results": []}

    def read_url(self, url: str) -> dict[str, Any]:
        """Fetch LLM-friendly markdown for a URL via r.jina.ai."""
        if not url or not str(url).strip():
            return {"status": "error", "message": "url required", "content": ""}
        target = str(url).strip()
        fetch_url = target if target.startswith(READER_PREFIX) else READER_PREFIX + target
        headers = {"Accept": "text/plain"}
        if self.available:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(fetch_url, headers=headers)
                resp.raise_for_status()
                return {"status": "success", "content": resp.text, "url": target}
        except Exception as exc:
            logger.error("Jina reader failed for %s: %s", target, exc)
            return {"status": "error", "message": str(exc), "content": ""}
