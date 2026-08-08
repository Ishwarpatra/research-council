"""Optional: embed texts with Jina and upsert into Chroma for hybrid retrieval."""

from __future__ import annotations

import logging
from typing import Any

from config import settings
from skills.retrieval.jina_client import JinaClient

logger = logging.getLogger("rcc.skills.embed_store")


class EmbedStore:
    def __init__(self, collection_name: str = "research_papers"):
        self.jina = JinaClient()
        self.collection = None
        self._init_error: str | None = None
        try:
            import chromadb
            client = chromadb.PersistentClient(path=settings.chroma_db_path)
            self.collection = client.get_or_create_collection(name=collection_name)
        except Exception as exc:
            self._init_error = str(exc)
            logger.error("EmbedStore Chroma init failed: %s", exc)

    def upsert_texts(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict] | None = None,
    ) -> dict[str, Any]:
        if self._init_error or self.collection is None:
            return {"status": "error", "message": self._init_error or "Chroma unavailable"}
        if not texts:
            return {"status": "error", "message": "texts required"}

        embeddings = None
        backend = (settings.retrieval_backend or "hybrid").lower()
        if backend in ("jina", "hybrid") and self.jina.available:
            emb = self.jina.embed(texts)
            if emb.get("status") == "success" and emb.get("embeddings"):
                embeddings = emb["embeddings"]

        try:
            kwargs: dict[str, Any] = {
                "ids": ids,
                "documents": texts,
                "metadatas": metadatas or [{"source": "upsert"} for _ in texts],
            }
            if embeddings:
                kwargs["embeddings"] = embeddings
            self.collection.upsert(**kwargs)
            return {
                "status": "success",
                "count": len(texts),
                "used_jina_embeddings": bool(embeddings),
            }
        except Exception as exc:
            logger.error("EmbedStore upsert failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def query(self, query_text: str, n_results: int = 5) -> dict[str, Any]:
        if self._init_error or self.collection is None:
            return {"status": "error", "message": self._init_error or "Chroma unavailable", "documents": []}
        try:
            backend = (settings.retrieval_backend or "hybrid").lower()
            kwargs: dict[str, Any] = {"n_results": n_results}
            if backend in ("jina", "hybrid") and self.jina.available:
                emb = self.jina.embed([query_text])
                if emb.get("status") == "success" and emb.get("embeddings"):
                    kwargs["query_embeddings"] = emb["embeddings"]
                else:
                    kwargs["query_texts"] = [query_text]
            else:
                kwargs["query_texts"] = [query_text]

            results = self.collection.query(**kwargs)
            docs = results.get("documents", [[]])[0] if results.get("documents") else []
            metas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            dists = results.get("distances", [[]])[0] if results.get("distances") else []
            return {
                "status": "success",
                "documents": docs,
                "metadatas": metas,
                "distances": dists,
            }
        except Exception as exc:
            logger.error("EmbedStore query failed: %s", exc)
            return {"status": "error", "message": str(exc), "documents": []}
