"""
Graph Builder - Knowledge graph construction from skills
"""
from typing import Optional
from hub.storage.knowledge_graph import KnowledgeGraph
from hub.storage.vector_store import VectorStore


class GraphBuilder:
    """Builds and maintains knowledge graph from skill relationships"""

    def __init__(self, knowledge_graph: KnowledgeGraph,
                 vector_store: VectorStore):
        self.graph = knowledge_graph
        self.vector_store = vector_store

    def add_skill_to_graph(self, skill: dict) -> bool:
        """
        Add a skill node to the knowledge graph.
        Creates domain nodes as needed.
        """
        skill_id = skill.get("id")
        if not skill_id:
            return False

        # Add skill node
        metadata = {
            "name": skill.get("name"),
            "description": skill.get("description"),
            "confidence": skill.get("confidence", 0.5),
            "source": skill.get("source", "unknown"),
            "source_agent": skill.get("agent_id", "unknown"),
            "created_at": skill.get("created_at"),
            "last_used": skill.get("last_used")
        }
        self.graph.add_skill_node(skill_id, skill.get("name"), metadata)

        # Create or connect to domain node
        domain = skill.get("domain")
        if domain:
            domain_id = f"domain_{domain}"
            if domain_id not in self.graph.graph:
                self.graph.add_node(
                    domain_id,
                    type=self.graph.NODE_DOMAIN,
                    name=domain
                )
            # Connect skill to domain
            self.graph.add_edge(
                skill_id, domain_id,
                edge_type=self.graph.EDGE_IMPLIES
            )

        # Connect to agent node
        agent_id = skill.get("agent_id")
        if agent_id:
            if agent_id not in self.graph.graph:
                self.graph.add_agent_node(
                    agent_id, agent_id,
                    {"role": skill.get("agent_role", "unknown")}
                )
            self.graph.add_edge(
                agent_id, skill_id,
                edge_type=self.graph.EDGE_DEPENDS
            )

        self.graph.save()
        return True

    def link_similar_skills(self, skill1_id: str, skill2_id: str,
                            similarity: float) -> bool:
        """Create a SIMILAR edge between two skill nodes"""
        return self.graph.add_edge(
            skill1_id, skill2_id,
            edge_type=self.graph.EDGE_SIMILAR,
            weight=similarity
        )

    def build_from_manifest(self, manifest: dict) -> int:
        """
        Build graph from a skill manifest.

        Args:
            manifest: {
                "agent_id": str,
                "skills": [...],
                "knowledge": [...],
                "user_profile": {...}
            }

        Returns:
            Number of skills added
        """
        agent_id = manifest.get("agent_id")
        skills_added = 0

        # Ensure agent node exists
        if agent_id:
            self.graph.add_agent_node(
                agent_id, agent_id,
                {"role": manifest.get("agent_role", "unknown")}
            )

        # Add each skill
        for skill in manifest.get("skills", []):
            skill["agent_id"] = agent_id
            if self.add_skill_to_graph(skill):
                skills_added += 1

        return skills_added

    def find_skill_clusters(self) -> list[list[str]]:
        """
        Find clusters of related skills using graph analysis.
        Returns list of skill ID groups that are densely connected.
        """
        import networkx as nx

        # Get undirected view for clustering
        G_undirected = self.graph.graph.to_undirected()

        # Find connected components
        components = list(nx.connected_components(G_undirected))

        # Filter to only skill nodes
        skill_clusters = []
        for component in components:
            skills = [n for n in component
                     if self.graph.graph.nodes[n].get("type") == self.graph.NODE_SKILL]
            if len(skills) > 1:
                skill_clusters.append(skills)

        return skill_clusters

    def get_skill_evolution_path(self, skill_id: str) -> list[dict]:
        """
        Get the evolution path of a skill through graph traversal.
        """
        path = []
        visited = set()

        def dfs(node, depth=0):
            if node in visited or depth > 10:
                return
            visited.add(node)
            node_data = self.graph.graph.nodes[node]
            path.append({
                "id": node,
                "type": node_data.get("type"),
                "name": node_data.get("name"),
                "depth": depth
            })
            for successor in self.graph.graph.successors(node):
                dfs(successor, depth + 1)

        dfs(skill_id)
        return path
