"""Semantic embedding helpers for optional --semantic search.

Migrated from hub/storage/vector_store.py on 2026-08-31 when the hub package
was retired (first-principles: hub never ran in production; only this
embedding function is used by the search engine). Zero hub dependencies —
uses sentence-transformers only.
"""

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
