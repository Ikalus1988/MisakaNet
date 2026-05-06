"""
Skill Indexer - Skill registry and indexing with semantic deduplication
"""
from typing import Optional, List
import json
import os
from datetime import datetime

# BGE-m3 for semantic embedding
import torch
from transformers import AutoModel, AutoTokenizer


class SkillIndexer:
    """
    Maintains a registry of all skills across the swarm.
    Provides indexing, searching, and version tracking with semantic dedup.
    Auto-maintains KnowledgeGraph on skill changes.
    """

    _embedding_model = None
    _embedding_tokenizer = None
    _embedding_model_name = "BAAI/bge-m3"
    _graph = None

    def __init__(self, index_path: str = "./storage/skill_index.json",
                 graph_path: str = "./storage/knowledge_graph/graph.gpickle",
                 model_path: str = None):
        self.index_path = index_path
        self.graph_path = graph_path
        # 模型路径可配置：优先构造函数参数 → 环境变量 → 模型名（auto-download）
        self._embedding_model_path = (model_path
                                      or os.environ.get("EMBEDDING_MODEL_PATH")
                                      or self._embedding_model_name)
        self.index = self._load_index()
        self._init_embedding_model()
        self._init_graph()

    def _init_embedding_model(self):
        """Lazy load BGE-m3 embedding model with fallback"""
        if SkillIndexer._embedding_model is not None:
            return
        print(f"[Embedding] Loading model: {self._embedding_model_path}")
        model_path = self._embedding_model_path
        is_local = os.path.isdir(model_path) or os.path.isfile(model_path + "/config.json")
        try:
            kwargs = {"local_files_only": True} if is_local else {}
            SkillIndexer._embedding_tokenizer = AutoTokenizer.from_pretrained(
                model_path, **kwargs
            )
            SkillIndexer._embedding_model = AutoModel.from_pretrained(
                model_path, **kwargs
            )
            SkillIndexer._embedding_model.eval()
            source = "local" if is_local else "hub (auto-download)"
            print(f"[Embedding] BGE-m3 loaded from {source}!")
        except Exception as e:
            print(f"[Embedding] 加载失败: {e}")
            print("[Embedding] 降级运行 — 语义去重和搜索将不可用")
            SkillIndexer._embedding_model = None
            SkillIndexer._embedding_tokenizer = None

    def _init_graph(self):
        """Lazy load knowledge graph"""
        if SkillIndexer._graph is None:
            from storage.knowledge_graph import KnowledgeGraph
            SkillIndexer._graph = KnowledgeGraph(persist_path=self.graph_path)

    def _update_graph(self, skill: dict, action: str, target_id: str = None):
        """Update knowledge graph when skills change"""
        if SkillIndexer._graph is None:
            return

        sid = skill.get('id')
        name = skill.get('name', sid)
        domain = skill.get('domain', 'unknown')
        source = skill.get('source', 'unknown')

        if action == "added":
            # Add domain node
            if not SkillIndexer._graph.graph.has_node(domain):
                SkillIndexer._graph.graph.add_node(domain, type='domain', name=domain)
            # Add agent node
            if not SkillIndexer._graph.graph.has_node(source):
                SkillIndexer._graph.graph.add_node(source, type='agent', name=source)
            # Add skill node
            if not SkillIndexer._graph.graph.has_node(sid):
                SkillIndexer._graph.graph.add_node(sid, type='skill', name=name,
                                                   domain=domain, source=source)
                # Edges
                SkillIndexer._graph.graph.add_edge(sid, domain, type='belongs_to', weight=1.0)
                SkillIndexer._graph.graph.add_edge(source, sid, type='owns', weight=1.0)
                # Same-domain edges
                for node in SkillIndexer._graph.graph.nodes:
                    if (SkillIndexer._graph.graph.nodes[node].get('type') == 'skill'
                            and node != sid
                            and SkillIndexer._graph.graph.nodes[node].get('domain') == domain):
                        if not SkillIndexer._graph.graph.has_edge(sid, node):
                            SkillIndexer._graph.graph.add_edge(sid, node, type='same_domain', weight=0.5)

        elif action == "merged":
            if target_id and SkillIndexer._graph.graph.has_node(sid):
                SkillIndexer._graph.graph.add_edge(sid, target_id, type='merged_to', weight=1.0)

        SkillIndexer._graph.save()

    def _generate_embedding(self, texts: List[str]) -> List[List[float]]:
        """Generate BGE-m3 embeddings for texts. Returns empty list if model unavailable."""
        if SkillIndexer._embedding_model is None:
            return []
        with torch.no_grad():
            inputs = SkillIndexer._embedding_tokenizer(
                texts, return_tensors='pt', padding=True, truncation=True, max_length=512
            )
            outputs = SkillIndexer._embedding_model(**inputs)
            embeddings = outputs.last_hidden_state.mean(dim=1)
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            return embeddings.numpy().tolist()

    def _compute_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Compute cosine similarity between two embeddings"""
        import numpy as np
        e1 = np.array(emb1)
        e2 = np.array(emb2)
        return float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2)))

    def _load_index(self) -> dict:
        """Load index from disk, migrate old formats"""
        try:
            with open(self.index_path, 'r') as f:
                idx = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            idx = {}

        idx.setdefault("skills", {})
        idx.setdefault("tools", {})
        idx.setdefault("users", {})
        idx.setdefault("version", "0")
        idx.setdefault("last_updated", None)
        idx.setdefault("sync_version", 0)
        return idx

    def _save_index(self):
        """Persist index to disk"""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2, default=str)

    def _get_skill_text_for_embedding(self, skill: dict) -> str:
        """Combine skill fields for embedding text"""
        parts = [
            skill.get("name", ""),
            skill.get("description", ""),
            skill.get("domain", ""),
        ]
        if "sources" in skill:
            parts.append(", ".join(skill["sources"]))
        return " | ".join(filter(None, parts))

    def register_skill(self, skill: dict) -> dict:
        """
        Register a new skill with semantic dedup.
        Returns: {"action": "added"|"merged"|"linked", "skill_id": str, "target_id": str|None}
        """
        skill_id = skill.get("id")
        if not skill_id:
            return {"action": "error", "reason": "no skill id"}

        # Generate embedding for dedup
        text = self._get_skill_text_for_embedding(skill)
        embeddings = self._generate_embedding([text])
        embedding = embeddings[0] if embeddings else None

        existing_skills = list(self.index["skills"].values())
        result = {"action": "added", "skill_id": skill_id, "target_id": None}

        # 如果模型不可用，跳过语义去重直接添加
        if embedding is not None:
            for existing in existing_skills:
                existing_emb = existing.get("embedding")
                if existing_emb:
                    sim = self._compute_similarity(embedding, existing_emb)
                    if sim > 0.92:
                        # MERGE: update existing with new source
                        existing.setdefault("sources", [])
                        skill_source = skill.get("source")
                        if skill_source not in existing["sources"]:
                            existing["sources"].append(skill_source)
                        existing["updated_at"] = datetime.now().isoformat()
                        self.index["skills"][existing["id"]] = existing
                        self.index["last_updated"] = datetime.now().isoformat()
                        self._save_index()
                        self._update_graph(skill, "merged", target_id=existing["id"])
                        return {"action": "merged", "skill_id": skill_id, "target_id": existing["id"], "similarity": sim}
                    elif sim > 0.75:
                        # LINK: mark relationship
                        existing.setdefault("linked_skills", [])
                        if skill_id not in existing["linked_skills"]:
                            existing["linked_skills"].append(skill_id)
                        self.index["last_updated"] = datetime.now().isoformat()
                        self._save_index()
                        return {"action": "linked", "skill_id": skill_id, "target_id": existing["id"], "similarity": sim}

        # ADD: new skill
        skill["embedding"] = embedding
        skill["indexed_at"] = datetime.now().isoformat()
        skill["updated_at"] = datetime.now().isoformat()
        self.index["skills"][skill_id] = skill
        self.index["last_updated"] = datetime.now().isoformat()
        self._save_index()
        self._update_graph(skill, "added")
        return result

    def register_tools(self, tools: List[dict], source: str) -> int:
        """Register tools from a node"""
        count = 0
        for tool in tools:
            tool_id = tool.get("id") or tool.get("name")
            if not tool_id:
                continue
            tool_key = f"{source}/{tool_id}"
            self.index["tools"][tool_key] = {
                **tool,
                "source": source,
                "indexed_at": datetime.now().isoformat()
            }
            count += 1
        if count > 0:
            self.index["last_updated"] = datetime.now().isoformat()
            self._save_index()
        return count

    def register_user(self, user: dict, source: str) -> bool:
        """Register user profile from a node"""
        user_id = user.get("id")
        if not user_id:
            return False
        existing = self.index["users"].get(user_id)
        if existing:
            existing_time = existing.get("indexed_at", "")
            new_time = datetime.now().isoformat()
            if existing_time and existing_time > new_time:
                return False
        self.index["users"][user_id] = {
            **user,
            "source": source,
            "indexed_at": datetime.now().isoformat()
        }
        self.index["last_updated"] = datetime.now().isoformat()
        self._save_index()
        return True

    def unregister_skill(self, skill_id: str) -> bool:
        """Remove a skill from the registry"""
        if skill_id in self.index["skills"]:
            del self.index["skills"][skill_id]
            self.index["last_updated"] = datetime.now().isoformat()
            self._save_index()
            return True
        return False

    def get_skill(self, skill_id: str) -> Optional[dict]:
        """Get a specific skill by ID"""
        return self.index["skills"].get(skill_id)

    def get_all_skills(self) -> list[dict]:
        """Get all registered skills"""
        return list(self.index["skills"].values())

    def get_all_tools(self) -> list[dict]:
        """Get all registered tools"""
        return list(self.index["tools"].values())

    def get_all_users(self) -> list[dict]:
        """Get all registered users"""
        return list(self.index["users"].values())

    def search_skills(self, query: str, filters: Optional[dict] = None) -> list[dict]:
        """Search skills by semantic similarity"""
        results = []
        query_embs = self._generate_embedding([query])
        query_emb = query_embs[0] if query_embs else None

        for skill in self.index["skills"].values():
            skill_emb = skill.get("embedding")
            if query_emb is not None and skill_emb:
                sim = self._compute_similarity(query_emb, skill_emb)
                skill["_search_score"] = sim
                results.append(skill)
            elif (query.lower() in skill.get("name", "").lower() or
                  query.lower() in skill.get("description", "").lower()):
                results.append(skill)

        results.sort(key=lambda s: s.get("_search_score", 0), reverse=True)

        if filters:
            results = [s for s in results if all(
                s.get(k) == v for k, v in filters.items()
            )]

        return results

    def get_skills_by_agent(self, agent_id: str) -> list[dict]:
        """Get all skills owned by an agent"""
        return [
            skill for skill in self.index["skills"].values()
            if skill.get("source") == agent_id
        ]

    def get_skills_by_domain(self, domain: str) -> list[dict]:
        """Get all skills in a domain"""
        return [
            skill for skill in self.index["skills"].values()
            if skill.get("domain") == domain
        ]

    def increment_sync_version(self) -> int:
        """Increment sync version and return new value"""
        self.index["sync_version"] += 1
        self.index["last_updated"] = datetime.now().isoformat()
        self._save_index()
        return self.index["sync_version"]

    def get_delta_since(self, sync_version: int) -> list[dict]:
        """Get all skills changed since given sync version"""
        return list(self.index["skills"].values())

    def stats(self) -> dict:
        """Get index statistics"""
        skills = self.index["skills"].values()
        graph_stats = SkillIndexer._graph.stats() if SkillIndexer._graph else {}
        return {
            "total_skills": len(skills),
            "total_tools": len(self.index["tools"]),
            "total_users": len(self.index["users"]),
            "graph_nodes": graph_stats.get("nodes", 0),
            "graph_edges": graph_stats.get("edges", 0),
            "by_agent": self._count_by_field("source"),
            "by_domain": self._count_by_field("domain"),
            "sync_version": self.index.get("sync_version", 0),
            "last_updated": self.index.get("last_updated")
        }

    def graph_stats(self) -> dict:
        """Get graph statistics"""
        if SkillIndexer._graph:
            return SkillIndexer._graph.stats()
        return {"nodes": 0, "edges": 0, "skills": 0, "agents": 0}

    def get_skill_related(self, skill_id: str, depth: int = 2) -> list[dict]:
        """Get skills related to given skill via graph"""
        if SkillIndexer._graph:
            return SkillIndexer._graph.get_skill_related(skill_id, depth=depth)
        return []

    def _count_by_field(self, field: str) -> dict:
        """Count skills grouped by a field"""
        counts = {}
        for skill in self.index["skills"].values():
            value = skill.get(field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts
