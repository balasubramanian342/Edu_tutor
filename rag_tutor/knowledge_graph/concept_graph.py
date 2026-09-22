"""
Concept Graph
Directed graph of domain concepts with typed relationships.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Optional, Tuple
import networkx as nx
from collections import deque


class RelationType(Enum):
    """Types of relationships between concepts"""
    PREREQUISITE = "prerequisite"      # A is prerequisite for B
    RELATED_TO = "related_to"         # A and B are related concepts
    PART_OF = "part_of"               # A is part of B (composition)
    EXAMPLE_OF = "example_of"         # A is an example of B
    CONTRASTS_WITH = "contrasts_with" # A contrasts with B (for compare/contrast)


@dataclass
class ConceptNode:
    """
    Single concept in the knowledge graph.
    """
    concept_id: str
    name: str
    subject: str
    unit: str
    
    # Taxonomy
    bloom_level: int = 2  # 1=Remember, 2=Understand, 3=Apply, 4=Analyze, 5=Evaluate, 6=Create
    difficulty: str = "medium"  # easy, medium, hard
    
    # Content
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    
    # Learning metadata
    typical_time_minutes: int = 30  # Estimated time to learn
    practice_questions_available: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'concept_id': self.concept_id,
            'name': self.name,
            'subject': self.subject,
            'unit': self.unit,
            'bloom_level': self.bloom_level,
            'difficulty': self.difficulty,
            'description': self.description,
            'keywords': self.keywords,
            'typical_time_minutes': self.typical_time_minutes,
            'practice_questions_available': self.practice_questions_available
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConceptNode':
        return cls(**data)


class ConceptGraph:
    """
    Knowledge graph for a domain.
    Stores concepts and their relationships using NetworkX.
    """
    
    def __init__(self):
        self.graph = nx.DiGraph()  # Directed graph for prerequisites
        self.concepts: Dict[str, ConceptNode] = {}
    
    def add_concept(self, concept: ConceptNode):
        """Add a concept to the graph"""
        self.concepts[concept.concept_id] = concept
        self.graph.add_node(concept.concept_id, data=concept)
    
    def add_relationship(self, source_id: str, target_id: str, 
                        relation_type: RelationType, strength: float = 1.0):
        """
        Add a relationship between concepts.
        
        For PREREQUISITE: source is prerequisite FOR target
        strength: how essential the prerequisite is (0-1)
        """
        if source_id not in self.concepts or target_id not in self.concepts:
            raise ValueError(f"Both concepts must exist in graph")
        
        self.graph.add_edge(source_id, target_id, 
                          relation_type=relation_type,
                          strength=strength)
    
    def get_concept(self, concept_id: str) -> Optional[ConceptNode]:
        """Retrieve a concept by ID"""
        return self.concepts.get(concept_id)
    
    def get_prerequisites(self, concept_id: str, 
                         min_strength: float = 0.5) -> List[ConceptNode]:
        """
        Get direct prerequisites for a concept.
        Only returns prerequisites with strength >= min_strength.
        """
        if concept_id not in self.graph:
            return []
        
        prereqs = []
        for pred_id in self.graph.predecessors(concept_id):
            edge_data = self.graph[pred_id][concept_id]
            if (edge_data.get('relation_type') == RelationType.PREREQUISITE and
                edge_data.get('strength', 1.0) >= min_strength):
                prereqs.append(self.concepts[pred_id])
        
        return prereqs
    
    def get_all_prerequisites(self, concept_id: str) -> List[ConceptNode]:
        """
        Get all prerequisites (transitive closure) for a concept.
        Returns in topological order (foundational concepts first).
        """
        if concept_id not in self.graph:
            return []
        
        # Find all ancestors in prerequisite chain
        prereq_ids = set()
        queue = deque([concept_id])
        
        while queue:
            current_id = queue.popleft()
            
            for pred_id in self.graph.predecessors(current_id):
                edge_data = self.graph[pred_id][current_id]
                if edge_data.get('relation_type') == RelationType.PREREQUISITE:
                    if pred_id not in prereq_ids:
                        prereq_ids.add(pred_id)
                        queue.append(pred_id)
        
        # Return in topological order
        if not prereq_ids:
            return []
        
        subgraph = self.graph.subgraph(prereq_ids)
        try:
            ordered_ids = list(nx.topological_sort(subgraph))
            return [self.concepts[cid] for cid in ordered_ids]
        except nx.NetworkXError:
            # Cycle detected, return unordered
            return [self.concepts[cid] for cid in prereq_ids]
    
    def get_dependents(self, concept_id: str) -> List[ConceptNode]:
        """
        Get concepts that depend on this concept (concepts this is a prerequisite for).
        """
        if concept_id not in self.graph:
            return []
        
        dependents = []
        for succ_id in self.graph.successors(concept_id):
            edge_data = self.graph[concept_id][succ_id]
            if edge_data.get('relation_type') == RelationType.PREREQUISITE:
                dependents.append(self.concepts[succ_id])
        
        return dependents
    
    def get_related_concepts(self, concept_id: str, 
                            relation_type: Optional[RelationType] = None) -> List[ConceptNode]:
        """
        Get concepts related to this one.
        If relation_type is None, returns all related concepts.
        """
        if concept_id not in self.graph:
            return []
        
        related = []
        
        # Check outgoing edges
        for succ_id in self.graph.successors(concept_id):
            edge_data = self.graph[concept_id][succ_id]
            if relation_type is None or edge_data.get('relation_type') == relation_type:
                related.append(self.concepts[succ_id])
        
        # Check incoming edges (for bidirectional relations)
        for pred_id in self.graph.predecessors(concept_id):
            edge_data = self.graph[pred_id][concept_id]
            if relation_type is None or edge_data.get('relation_type') == relation_type:
                if self.concepts[pred_id] not in related:
                    related.append(self.concepts[pred_id])
        
        return related
    
    def find_learning_path(self, target_concept_id: str, 
                          mastered_concepts: Set[str]) -> List[ConceptNode]:
        """
        Find optimal learning path to reach target concept.
        Returns ordered list of concepts to learn (excluding already mastered).
        """
        if target_concept_id not in self.graph:
            return []
        
        # Get all prerequisites
        all_prereqs = self.get_all_prerequisites(target_concept_id)
        
        # Filter out already mastered
        to_learn = [c for c in all_prereqs if c.concept_id not in mastered_concepts]
        
        # Add target if not mastered
        if target_concept_id not in mastered_concepts:
            to_learn.append(self.concepts[target_concept_id])
        
        return to_learn
    
    def get_next_concepts(self, mastered_concepts: Set[str], 
                         subject: Optional[str] = None) -> List[ConceptNode]:
        """
        Recommend next concepts to learn based on what's already mastered.
        Returns concepts where all prerequisites are mastered.
        """
        candidates = []
        
        for concept_id, concept in self.concepts.items():
            # Skip if already mastered
            if concept_id in mastered_concepts:
                continue
            
            # Filter by subject if specified
            if subject and concept.subject != subject:
                continue
            
            # Check if all prerequisites are mastered
            prereqs = self.get_prerequisites(concept_id)
            prereq_ids = {p.concept_id for p in prereqs}
            
            if prereq_ids.issubset(mastered_concepts):
                candidates.append(concept)
        
        # Sort by difficulty and bloom level
        candidates.sort(key=lambda c: (c.difficulty == "easy", c.bloom_level))
        
        return candidates
    
    def detect_cycles(self) -> List[List[str]]:
        """
        Detect cycles in prerequisite relationships (which shouldn't exist).
        Returns list of cycles.
        """
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except:
            return []
    
    def get_concept_depth(self, concept_id: str) -> int:
        """
        Get the depth of a concept in the prerequisite tree.
        Depth 0 = foundational (no prerequisites).
        """
        if concept_id not in self.graph:
            return 0
        
        prereqs = self.get_all_prerequisites(concept_id)
        return len(prereqs)
    
    def export_to_dict(self) -> Dict:
        """Export entire graph to dictionary for persistence"""
        nodes = {cid: concept.to_dict() for cid, concept in self.concepts.items()}
        
        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                'source': source,
                'target': target,
                'relation_type': data['relation_type'].value,
                'strength': data.get('strength', 1.0)
            })
        
        return {
            'nodes': nodes,
            'edges': edges
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConceptGraph':
        """Load graph from dictionary"""
        graph = cls()
        
        # Add nodes
        for node_data in data['nodes'].values():
            concept = ConceptNode.from_dict(node_data)
            graph.add_concept(concept)
        
        # Add edges
        for edge_data in data['edges']:
            graph.add_relationship(
                edge_data['source'],
                edge_data['target'],
                RelationType(edge_data['relation_type']),
                edge_data.get('strength', 1.0)
            )
        
        return graph
    
    def visualize(self, output_path: str = "knowledge_graph.png"):
        """
        Generate visualization of the knowledge graph.
        Requires matplotlib and graphviz.
        """
        try:
            import matplotlib.pyplot as plt
            from networkx.drawing.nx_agraph import graphviz_layout
            
            pos = graphviz_layout(self.graph, prog='dot')
            
            # Color nodes by subject
            subjects = list(set(c.subject for c in self.concepts.values()))
            color_map = {subj: i for i, subj in enumerate(subjects)}
            node_colors = [color_map[self.concepts[node].subject] 
                          for node in self.graph.nodes()]
            
            # Draw
            plt.figure(figsize=(16, 12))
            nx.draw(self.graph, pos, 
                   labels={n: self.concepts[n].name for n in self.graph.nodes()},
                   node_color=node_colors,
                   node_size=2000,
                   font_size=8,
                   font_weight='bold',
                   arrows=True,
                   edge_color='gray',
                   cmap=plt.cm.Set3)
            
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"Knowledge graph visualization saved to {output_path}")
        except ImportError:
            print("Visualization requires: pip install matplotlib pygraphviz")
