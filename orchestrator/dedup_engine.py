"""
Dedup Engine - Semantic deduplication for skills

⚠️  DEAD CODE — 语义去重已在 SkillIndexer.register_skill() 内建实现。
保留作为设计参考。
"""
from typing import Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from storage.vector_store import VectorStore


class DedupAction(Enum):
    MERGE = "merge"      # similarity > 0.92, merge content
    LINK = "link"        # 0.75 < similarity <= 0.92, create edge
    ADD = "add"          # similarity <= 0.75, new skill


@dataclass
class DedupResult:
    action: DedupAction
    target_id: Optional[str] = None
    similarity: float = 0.0
    merged_sources: list = None

    def __post_init__(self):
        if self.merged_sources is None:
            self.merged_sources = []


class DedupEngine:
    """
    Semantic deduplication engine for skill merging.
    Implements cosine similarity threshold-based decisions.
    """

    # Similarity thresholds
    THRESHOLD_MERGE = 0.92
    THRESHOLD_LINK = 0.75

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def analyze(self, new_skill: dict, existing_skills: list[dict]) -> DedupResult:
        """
        Analyze a new skill against existing ones.

        Args:
            new_skill: {
                "id": str,
                "name": str,
                "description": str,
                "embedding": list[float],
                "source": str,
                "metadata": dict
            }
            existing_skills: List of similar structure

        Returns:
            DedupResult with action and details
        """
        best_match_id = None
        best_similarity = 0.0

        for existing in existing_skills:
            similarity = self.vector_store.compute_similarity(
                new_skill.get("embedding", []),
                existing.get("embedding", [])
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_match_id = existing.get("id")

        if best_similarity > self.THRESHOLD_MERGE:
            return DedupResult(
                action=DedupAction.MERGE,
                target_id=best_match_id,
                similarity=best_similarity,
                merged_sources=[new_skill.get("source"), best_match_id]
            )
        elif best_similarity > self.THRESHOLD_LINK:
            return DedupResult(
                action=DedupAction.LINK,
                target_id=best_match_id,
                similarity=best_similarity,
                merged_sources=[new_skill.get("source")]
            )
        else:
            return DedupResult(
                action=DedupAction.ADD,
                similarity=best_similarity
            )

    def merge_skills(self, skill1: dict, skill2: dict) -> dict:
        """
        Merge two skills into one.
        Takes union of metadata, marks sources.
        """
        merged = {
            "id": skill1.get("id"),
            "name": skill1.get("name"),
            "description": skill1.get("description"),
            "confidence": max(
                skill1.get("confidence", 0),
                skill2.get("confidence", 0)
            ),
            "sources": [
                skill1.get("source", "unknown"),
                skill2.get("source", "unknown")
            ],
            "metadata": {
                **skill1.get("metadata", {}),
                **skill2.get("metadata", {})
            }
        }
        return merged

    def resolve_conflict(self, skills: list[dict], strategy: str = "latest") -> dict:
        """
        Resolve conflict when multiple versions of same skill exist.

        Args:
            skills: List of skill versions
            strategy: "latest" | "source_priority" | "highest_confidence"
        """
        if not skills:
            return None

        if strategy == "latest":
            return max(skills, key=lambda s: s.get("updated_at", ""))
        elif strategy == "source_priority":
            # Keep the one from preferred source
            preferred_source = "hermes-hub"  # Hub has priority
            for skill in skills:
                if skill.get("source") == preferred_source:
                    return skill
            return skills[0]
        elif strategy == "highest_confidence":
            return max(skills, key=lambda s: s.get("confidence", 0))
        else:
            return skills[0]
