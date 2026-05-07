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
        self.client = chromadb.PersistentClient(
            persist_directory=persist_dir,
            anonymized_telemetry=False
        )
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

    def add_skill(self, skill_id: str, embedding: list[float],
                  metadata: dict) -> bool:
        """Add a skill to the vector store"""
        try:
            self.collection.add(
                ids=[skill_id],
                embeddings=[embedding],
                metadatas=[metadata]
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
        print("[Embedding] sentence-transformers not installed, falling back to hash-based embedding")
        return None


def generate_embedding(text: str, model: str = "BAAI/bge-base-zh-v1.5") -> list[float]:
    """
    Generate embedding for text using sentence-transformers.
    Falls back to hash-based pseudo-embedding if model not available.

    Args:
        text: Input text to embed
        model: Model name (default: BAAI/bge-base-zh-v1.5, Chinese optimized)

    Returns:
        Normalized embedding vector as list[float]
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
            print(f"[Embedding] Model inference failed: {e}, falling back to hash")

    # Fallback: hash-based pseudo-embedding (for development only)
    # WARNING: This produces meaningless similarity scores — upgrade to real embedding ASAP
    import hashlib
    hash_bytes = hashlib.sha256(text.encode()).digest()
    arr = np.frombuffer(hash_bytes, dtype=np.float32)
    arr = arr / np.linalg.norm(arr)
    return arr.tolist()
