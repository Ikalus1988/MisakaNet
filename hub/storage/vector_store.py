"""
Vector Store - Chroma-backed skill vector storage
"""
import chromadb
from chromadb.config import Settings
from typing import Optional
import hashlib


class VectorStore:
    """Chroma-based vector store for skills and knowledge"""

    def __init__(self, persist_dir: str, collection_name: str = "skills"):
        self.client = chromadb.Client(Settings(
            persist_directory=persist_dir,
            anonymized_telemetry=False
        ))
        self.collection_name = collection_name
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if not exists"""
        try:
            self.collection = self.client.get_collection(self.collection_name)
        except Exception:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Skill embeddings for swarm memory"}
            )

    @staticmethod
    def _validate_skill_id(skill_id: str) -> bool:
        """Validate skill_id: alphanumeric, underscores, hyphens, dots, max 256 chars"""
        if not skill_id or len(skill_id) > 256:
            return False
        import re
        return bool(re.match(r'^[a-zA-Z0-9_\-.]+$', skill_id))

    @staticmethod
    def _validate_metadata(metadata: dict) -> dict:
        """Sanitize metadata: keep only string/int/float/bool values, max 10 keys"""
        if not isinstance(metadata, dict):
            return {}
        allowed_types = (str, int, float, bool)
        sanitized = {}
        for k, v in metadata.items():
            if len(sanitized) >= 10:
                break
            if isinstance(k, str) and len(k) <= 128 and isinstance(v, allowed_types):
                sanitized[k] = v
        return sanitized

    def add_skill(self, skill_id: str, embedding: list[float],
                  metadata: dict) -> bool:
        """Add a skill to the vector store"""
        if not self._validate_skill_id(skill_id):
            print(f"Error adding skill: invalid skill_id '{skill_id}'")
            return False
        try:
            self.collection.add(
                ids=[skill_id],
                embeddings=[embedding],
                metadatas=[self._validate_metadata(metadata)]
            )
            return True
        except Exception as e:
            print(f"Error adding skill {skill_id}: {e}")
            return False

    def search(self, query_embedding: list[float],
               n_results: int = 5) -> list[dict]:
        """Search for similar skills by embedding"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        return results

    def get_skill(self, skill_id: str) -> Optional[dict]:
        """Get a specific skill by ID"""
        if not self._validate_skill_id(skill_id):
            return None
        try:
            result = self.collection.get(ids=[skill_id])
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "embedding": result["embeddings"][0],
                    "metadata": result["metadatas"][0]
                }
            return None
        except Exception:
            return None

    def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill from the vector store"""
        if not self._validate_skill_id(skill_id):
            return False
        try:
            self.collection.delete(ids=[skill_id])
            return True
        except Exception as e:
            print(f"Error deleting skill {skill_id}: {e}")
            return False

    def count(self) -> int:
        """Get total number of skills"""
        return self.collection.count()

    def compute_similarity(self, emb1: list[float],
                           emb2: list[float]) -> float:
        """Compute cosine similarity between two embeddings"""
        import numpy as np
        e1 = np.array(emb1)
        e2 = np.array(emb2)
        dot_product = np.dot(e1, e2)
        norm1 = np.linalg.norm(e1)
        norm2 = np.linalg.norm(e2)
        # Guard against zero vectors
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return float(dot_product / (norm1 * norm2))


# Lazy-loaded embedding model (singleton)
_embedding_model = None
_embedding_model_name = None


def _get_embedding_model(model_name: str = "BAAI/bge-base-zh-v1.5"):
    """Get or create embedding model singleton."""
    global _embedding_model, _embedding_model_name
    if _embedding_model is not None and _embedding_model_name == model_name:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(model_name)
        _embedding_model_name = model_name
        print(f"[Embedding] Loaded model: {model_name}")
        return _embedding_model
    except ImportError:
        print("[Embedding] sentence-transformers not installed — semantic search unavailable")
        return None


# Dev-mode fallback flag: set to True to allow SHA256 pseudo-embeddings for testing
# In production, this MUST remain False so semantic search fails closed.
_ALLOW_HASH_FALLBACK = False


def _enable_hash_fallback():
    """Enable SHA256 pseudo-embedding fallback for development use only."""
    global _ALLOW_HASH_FALLBACK
    _ALLOW_HASH_FALLBACK = True


def generate_embedding(text: str, model: str = "BAAI/bge-base-zh-v1.5") -> list[float]:
    """
    Generate embedding for text using sentence-transformers.
    Default: fail-closed if model is unavailable (raises RuntimeError).
    Dev-only: call _enable_hash_fallback() to allow SHA256 pseudo-embedding.

    Args:
        text: Input text to embed
        model: Model name (default: BAAI/bge-base-zh-v1.5, Chinese optimized)

    Returns:
        Normalized embedding vector as list[float]

    Raises:
        RuntimeError: If embedding model is unavailable and hash fallback is not enabled
    """
    import numpy as np

    # Try real embedding first
    encoder = _get_embedding_model(model)
    if encoder is not None:
        try:
            # sentence-transformers returns numpy array
            emb = encoder.encode(text, normalize_embeddings=True)
            if isinstance(emb, np.ndarray):
                return emb.tolist()
            return emb
        except Exception as e:
            import logging
            logging.error(f"[Embedding] Model inference failed: {e}")

    # Fail-closed by default
    if not _ALLOW_HASH_FALLBACK:
        raise RuntimeError(
            "Semantic embedding unavailable (model failed to load or is not installed). "
            "For development, call _enable_hash_fallback() before generate_embedding()."
        )

    # Dev fallback: hash-based pseudo-embedding (meaningless similarity — for testing only)
    import logging as _log
    _log.warning("[Embedding] ⚠️ Using SHA256 hash pseudo-embedding (dev mode). Semantic search results are NOT meaningful.")
    import hashlib
    hash_bytes = hashlib.sha256(text.encode()).digest()
    arr = np.frombuffer(hash_bytes, dtype=np.float32)
    arr = arr / np.linalg.norm(arr)
    return arr.tolist()


def embedding_service_health() -> dict:
    """
    Return embedding service health status.
    Use this in /health endpoints to detect silent degradation.
    Returns:
        {"status": "ok"|"degraded"|"down", "model": str, "message": str}
    """
    global _embedding_model
    if _embedding_model is not None:
        return {
            "status": "ok",
            "model": _embedding_model_name or "unknown",
            "message": "Embedding model loaded and operational"
        }
    try:
        # Attempt to load
        test_model = _get_embedding_model()
        if test_model is not None:
            return {
                "status": "ok",
                "model": _embedding_model_name or "unknown",
                "message": "Embedding model loaded on demand"
            }
        return {
            "status": "degraded",
            "model": "N/A",
            "message": "Embedding model unavailable — all semantic operations will fail closed unless _enable_hash_fallback() is explicitly called."
        }
    except Exception as e:
        return {
            "status": "down",
            "model": "N/A",
            "message": f"Embedding model failed to load: {e}"
        }
