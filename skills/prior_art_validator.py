"""Prior-art retrieval: Chroma store with optional Jina embeddings + rerank (hybrid)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from config import settings

logger = logging.getLogger("rcc.skills.prior_art")


class PriorArtValidator:
    def __init__(self, persist_directory: str = None, collection_name: str = "research_papers"):
        """Initializes the local ChromaDB client for semantic search."""
        self.client = None
        self.collection = None
        self._init_error: Optional[str] = None
        if persist_directory is None:
            persist_directory = settings.chroma_db_path
        try:
            import chromadb  # lazy: avoid import-time crash on incompatible runtimes
            self.client = chromadb.PersistentClient(path=persist_directory)
            self.collection = self.client.get_or_create_collection(name=collection_name)
            logger.info(
                "ChromaDB initialized at %s on collection '%s'",
                persist_directory,
                collection_name,
            )
        except Exception as e:
            self._init_error = str(e)
            logger.error("Failed to initialize ChromaDB: %s", e)

    def _backend(self) -> str:
        return (settings.retrieval_backend or "hybrid").lower()

    def query_prior_art(self, query_text: str, n_results: int = 3) -> Dict[str, Any]:
        """
        Executes a semantic search against the local vector database.
        hybrid/jina: embed query with Jina when key present; rerank candidates with Jina.
        """
        if self._init_error or self.collection is None:
            return {
                "status": "error",
                "message": self._init_error or "ChromaDB not initialized",
                "findings": [],
            }
        if not query_text or not str(query_text).strip():
            return {
                "status": "error",
                "message": "query_text is required",
                "findings": [],
            }
        q = query_text.strip()
        try:
            n = max(1, min(int(n_results), 5))
            fetch_n = min(10, max(n * 3, n))  # over-fetch for rerank
            backend = self._backend()

            query_kwargs: dict[str, Any] = {"n_results": fetch_n}
            used_jina_embed = False
            if backend in ("jina", "hybrid"):
                try:
                    from skills.retrieval.jina_client import JinaClient
                    jina = JinaClient()
                    if jina.available:
                        emb = jina.embed([q])
                        if emb.get("status") == "success" and emb.get("embeddings"):
                            query_kwargs["query_embeddings"] = emb["embeddings"]
                            used_jina_embed = True
                except Exception as exc:
                    logger.warning("Jina embed unavailable, falling back to Chroma texts: %s", exc)

            if "query_embeddings" not in query_kwargs:
                query_kwargs["query_texts"] = [q]

            results = self.collection.query(**query_kwargs)

            documents = results.get("documents", [[]])[0] if results.get("documents") else []
            metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            distances = results.get("distances", [[]])[0] if results.get("distances") else []

            formatted: list[dict] = []
            for doc, meta, dist in zip(documents, metadatas, distances):
                formatted.append({
                    "content": doc,
                    "source": meta.get("source", "Unknown") if meta else "Unknown",
                    "confidence_score": 1.0 - dist if dist is not None else None,
                })

            used_jina_rerank = False
            if backend in ("jina", "hybrid") and formatted:
                try:
                    from skills.retrieval.rerank import rerank_documents
                    rr = rerank_documents(q, [f["content"] for f in formatted], top_n=n)
                    if rr.get("status") == "success" and rr.get("findings"):
                        used_jina_rerank = True
                        reranked = []
                        for item in rr["findings"]:
                            idx = item.get("index", 0)
                            base = formatted[idx] if 0 <= idx < len(formatted) else {
                                "content": item.get("content"),
                                "source": "Unknown",
                            }
                            reranked.append({
                                "content": item.get("content") or base.get("content"),
                                "source": base.get("source", "Unknown"),
                                "confidence_score": item.get("relevance_score", base.get("confidence_score")),
                            })
                        formatted = reranked
                    else:
                        formatted = formatted[:n]
                except Exception as exc:
                    logger.warning("Jina rerank skipped: %s", exc)
                    formatted = formatted[:n]
            else:
                formatted = formatted[:n]

            return {
                "status": "success",
                "query": q,
                "findings": formatted,
                "retrieval": {
                    "backend": backend,
                    "used_jina_embed": used_jina_embed,
                    "used_jina_rerank": used_jina_rerank,
                },
            }

        except Exception as e:
            logger.error("Vector retrieval failed for query '%s': %s", query_text, e)
            return {
                "status": "error",
                "message": str(e),
                "findings": [],
            }
