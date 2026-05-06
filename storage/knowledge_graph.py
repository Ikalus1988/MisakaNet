"""
Knowledge Graph - NetworkX-based knowledge graph
"""
import networkx as nx
from typing import Optional
import pickle
from datetime import datetime


class KnowledgeGraph:
    """NetworkX-based knowledge graph for skill relationships"""

    # Node types
    NODE_SKILL = "skill"
    NODE_KNOWLEDGE = "knowledge"
    NODE_DOMAIN = "domain"
    NODE_AGENT = "agent"
    NODE_USER = "user"

    # Edge types
    EDGE_IMPLIES = "implies"
    EDGE_RELATED = "related"
    EDGE_DEPENDS = "depends"
    EDGE_EVOLVES = "evolves"
    EDGE_SIMILAR = "similar"

    def __init__(self, persist_path: Optional[str] = None):
        self.graph = nx.DiGraph()
        self.persist_path = persist_path
        if persist_path:
            self._load()

    def _load(self):
        """Load graph from disk"""
        try:
            with open(self.persist_path, 'rb') as f:
                self.graph = pickle.load(f)
            print(f"Loaded graph with {len(self.graph.nodes)} nodes")
        except FileNotFoundError:
            print("Starting with empty graph")

    def save(self):
        """Persist graph to disk"""
        if self.persist_path:
            import os
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            with open(self.persist_path, 'wb') as f:
                pickle.dump(self.graph, f)

    def add_skill_node(self, skill_id: str, name: str,
                       metadata: dict) -> bool:
        """Add a skill node to the graph"""
        try:
            self.graph.add_node(
                skill_id,
                type=self.NODE_SKILL,
                name=name,
                **metadata
            )
            return True
        except Exception as e:
            print(f"Error adding skill node: {e}")
            return False

    def add_agent_node(self, agent_id: str, name: str,
                       metadata: dict) -> bool:
        """Add an agent node"""
        try:
            self.graph.add_node(
                agent_id,
                type=self.NODE_AGENT,
                name=name,
                **metadata
            )
            return True
        except Exception as e:
            print(f"Error adding agent node: {e}")
            return False

    def add_edge(self, source_id: str, target_id: str,
                 edge_type: str, weight: float = 1.0,
                 metadata: Optional[dict] = None) -> bool:
        """Add an edge between nodes"""
        try:
            edge_data = {
                "type": edge_type,
                "weight": weight,
                "created_at": datetime.now().isoformat()
            }
            if metadata:
                edge_data.update(metadata)
            self.graph.add_edge(source_id, target_id, **edge_data)
            return True
        except Exception as e:
            print(f"Error adding edge: {e}")
            return False

    def get_skill_related(self, skill_id: str,
                           depth: int = 1) -> list[dict]:
        """Get all skills related to this skill"""
        related = []
        try:
            for neighbor in nx.ego_graph(self.graph, skill_id, radius=depth):
                node_data = self.graph.nodes[neighbor]
                if node_data.get("type") == self.NODE_SKILL:
                    related.append({
                        "id": neighbor,
                        "name": node_data.get("name"),
                        "type": node_data.get("type")
                    })
        except Exception as e:
            print(f"Error getting related skills: {e}")
        return related

    def find_path(self, source_id: str, target_id: str) -> list:
        """Find shortest path between two nodes"""
        try:
            return nx.shortest_path(self.graph, source_id, target_id)
        except nx.NetworkXNoPath:
            return []
        except Exception:
            return []

    def get_all_skills(self) -> list[dict]:
        """Get all skill nodes"""
        skills = []
        for node in self.graph.nodes:
            data = self.graph.nodes[node]
            if data.get("type") == self.NODE_SKILL:
                skills.append({"id": node, **data})
        return skills

    def get_agent_skills(self, agent_id: str) -> list[str]:
        """Get all skills owned by an agent"""
        skills = []
        for skill_id in self.graph.nodes:
            if self.graph.nodes[skill_id].get("type") == self.NODE_SKILL:
                if self.graph.nodes[skill_id].get("source_agent") == agent_id:
                    skills.append(skill_id)
        return skills

    def merge_skill_nodes(self, source_id: str, target_id: str,
                          merged_metadata: dict) -> bool:
        """
        Merge two skill nodes into one.
        Keeps target, removes source, creates edges to merged node.
        """
        try:
            # Update target with merged metadata
            for key, value in merged_metadata.items():
                self.graph.nodes[target_id][key] = value

            # Reconnect edges from source to target
            for predecessor in self.graph.predecessors(source_id):
                edge_data = self.graph.edges[predecessor, source_id]
                self.graph.add_edge(predecessor, target_id, **edge_data)

            for successor in self.graph.successors(source_id):
                edge_data = self.graph.edges[source_id, successor]
                self.graph.add_edge(target_id, successor, **edge_data)

            # Remove source node
            self.graph.remove_node(source_id)
            return True
        except Exception as e:
            print(f"Error merging skill nodes: {e}")
            return False

    def stats(self) -> dict:
        """Get graph statistics"""
        return {
            "nodes": len(self.graph.nodes),
            "edges": len(self.graph.edges),
            "skills": len([n for n in self.graph.nodes
                          if self.graph.nodes[n].get("type") == self.NODE_SKILL]),
            "agents": len([n for n in self.graph.nodes
                          if self.graph.nodes[n].get("type") == self.NODE_AGENT]),
        }


# ⚠️  DEAD CODE — 无调用者，shadows nx.ego_graph。移除以保持清晰。
