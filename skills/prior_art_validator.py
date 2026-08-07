import chromadb
import logging
from typing import Dict, Any

logger = logging.getLogger("rcc.skills.prior_art")

class PriorArtValidator:
    def __init__(self, persist_directory: str = "./chroma_db", collection_name: str = "research_papers"):
        """Initializes the local ChromaDB client for semantic search."""
        try:
            self.client = chromadb.PersistentClient(path=persist_directory)
            self.collection = self.client.get_or_create_collection(name=collection_name)
            logger.info(f"ChromaDB initialized at {persist_directory} on collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    def query_prior_art(self, query_text: str, n_results: int = 3) -> Dict[str, Any]:
        """
        Executes a semantic search against the local vector database.
        This is the functional endpoint exposed to the LLM agent.
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            # Flatten the nested lists returned by ChromaDB for the LLM context
            documents = results.get('documents', [[]])[0] if results.get('documents') else []
            metadatas = results.get('metadatas', [[]])[0] if results.get('metadatas') else []
            distances = results.get('distances', [[]])[0] if results.get('distances') else []
            
            formatted_results = []
            for doc, meta, dist in zip(documents, metadatas, distances):
                formatted_results.append({
                    "content": doc,
                    "source": meta.get("source", "Unknown") if meta else "Unknown",
                    "confidence_score": 1.0 - dist  # Assuming cosine distance
                })
                
            return {
                "status": "success",
                "query": query_text,
                "findings": formatted_results
            }
            
        except Exception as e:
            logger.error(f"Vector retrieval failed for query '{query_text}': {e}")
            return {
                "status": "error",
                "message": str(e),
                "findings": []
            }
