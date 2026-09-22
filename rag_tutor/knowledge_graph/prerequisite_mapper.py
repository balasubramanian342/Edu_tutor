"""
Prerequisite Mapper
Analyzes prerequisite chains and finds optimal learning sequences.
"""

from dataclasses import dataclass
from typing import List, Set, Dict, Optional
from .concept_graph import ConceptGraph, ConceptNode


@dataclass
class PrerequisitePath:
    """
    Represents a learning path through prerequisites.
    """
    target_concept: ConceptNode
    prerequisites: List[ConceptNode]  # Ordered from foundational to target
    missing_prerequisites: List[ConceptNode]  # Not yet mastered
    estimated_time_minutes: int
    difficulty_progression: List[str]  # easy -> medium -> hard
    
    def get_next_step(self) -> Optional[ConceptNode]:
        """Get the next concept to learn in this path"""
        if not self.missing_prerequisites:
            return None
        return self.missing_prerequisites[0]
    
    def is_ready(self) -> bool:
        """Check if student is ready for target (all prerequisites mastered)"""
        return len(self.missing_prerequisites) == 0


class PrerequisiteMapper:
    """
    Analyzes prerequisite relationships and generates learning paths.
    """
    
    def __init__(self, knowledge_graph: ConceptGraph):
        self.graph = knowledge_graph
    
    def find_path_to_concept(self, target_concept_id: str, 
                            mastered_concepts: Set[str]) -> PrerequisitePath:
        """
        Find the learning path from current knowledge to target concept.
        """
        target = self.graph.get_concept(target_concept_id)
        if not target:
            raise ValueError(f"Concept {target_concept_id} not found")
        
        # Get all prerequisites in order
        all_prereqs = self.graph.get_all_prerequisites(target_concept_id)
        
        # Identify missing prerequisites
        missing = [c for c in all_prereqs if c.concept_id not in mastered_concepts]
        
        # Calculate estimated time
        total_time = sum(c.typical_time_minutes for c in missing)
        if target_concept_id not in mastered_concepts:
            total_time += target.typical_time_minutes
            missing.append(target)
        
        # Get difficulty progression
        difficulty_prog = [c.difficulty for c in missing]
        
        return PrerequisitePath(
            target_concept=target,
            prerequisites=all_prereqs,
            missing_prerequisites=missing,
            estimated_time_minutes=total_time,
            difficulty_progression=difficulty_prog
        )
    
    def identify_gaps(self, target_concept_id: str, 
                     mastered_concepts: Set[str]) -> List[ConceptNode]:
        """
        Identify knowledge gaps preventing learning of target concept.
        Returns missing prerequisites sorted by importance.
        """
        path = self.find_path_to_concept(target_concept_id, mastered_concepts)
        
        # Sort by prerequisite depth (foundational first)
        gaps = sorted(path.missing_prerequisites, 
                     key=lambda c: self.graph.get_concept_depth(c.concept_id))
        
        return gaps
    
    def find_critical_prerequisites(self, target_concept_id: str) -> List[ConceptNode]:
        """
        Find prerequisites that are critical for the target concept.
        Critical = high relationship strength and direct prerequisite.
        """
        direct_prereqs = self.graph.get_prerequisites(target_concept_id, min_strength=0.7)
        return direct_prereqs
    
    def suggest_remediation_path(self, weak_concept_id: str,
                                mastered_concepts: Set[str]) -> List[ConceptNode]:
        """
        When a student struggles with a concept, suggest which prerequisites to review.
        """
        # Get direct prerequisites
        direct_prereqs = self.graph.get_prerequisites(weak_concept_id)
        
        # Find which ones might not be truly mastered
        candidates_for_review = []
        
        for prereq in direct_prereqs:
            # If marked as mastered but is a direct prerequisite of weak concept,
            # it might need review
            if prereq.concept_id in mastered_concepts:
                candidates_for_review.append(prereq)
        
        return candidates_for_review
    
    def build_unit_learning_sequence(self, subject: str, unit: str,
                                    mastered_concepts: Set[str]) -> List[ConceptNode]:
        """
        Generate optimal learning sequence for an entire unit.
        """
        # Get all concepts in the unit
        unit_concepts = [c for c in self.graph.concepts.values()
                        if c.subject == subject and c.unit == unit]
        
        # Build dependency graph for just this unit
        sequence = []
        remaining = {c.concept_id for c in unit_concepts if c.concept_id not in mastered_concepts}
        current_mastered = mastered_concepts.copy()
        
        while remaining:
            # Find concepts that are ready to learn
            ready = []
            for cid in remaining:
                prereqs = self.graph.get_prerequisites(cid)
                prereq_ids = {p.concept_id for p in prereqs}
                
                # Ready if all prerequisites are mastered
                if prereq_ids.issubset(current_mastered):
                    ready.append(self.graph.get_concept(cid))
            
            if not ready:
                # Deadlock - might have external prerequisites or cycles
                # Add remaining in arbitrary order
                for cid in remaining:
                    sequence.append(self.graph.get_concept(cid))
                break
            
            # Sort ready concepts by difficulty and bloom level
            ready.sort(key=lambda c: (
                {'easy': 0, 'medium': 1, 'hard': 2}[c.difficulty],
                c.bloom_level
            ))
            
            # Add first ready concept to sequence
            next_concept = ready[0]
            sequence.append(next_concept)
            current_mastered.add(next_concept.concept_id)
            remaining.remove(next_concept.concept_id)
        
        return sequence
    
    def get_prerequisite_tree(self, concept_id: str) -> Dict:
        """
        Get hierarchical prerequisite structure for visualization.
        Returns nested dict suitable for tree rendering.
        """
        concept = self.graph.get_concept(concept_id)
        if not concept:
            return {}
        
        def build_tree(cid: str, visited: Set[str]) -> Dict:
            if cid in visited:
                return {'concept_id': cid, 'name': '(cycle)', 'children': []}
            
            visited.add(cid)
            c = self.graph.get_concept(cid)
            prereqs = self.graph.get_prerequisites(cid)
            
            return {
                'concept_id': cid,
                'name': c.name,
                'difficulty': c.difficulty,
                'children': [build_tree(p.concept_id, visited.copy()) for p in prereqs]
            }
        
        return build_tree(concept_id, set())
    
    def calculate_learning_order_score(self, concept_id: str,
                                      mastered_concepts: Set[str]) -> float:
        """
        Score how appropriate it is to learn this concept now (0-1).
        Higher score = better to learn now.
        
        Factors:
        - All prerequisites mastered: high score
        - Some prerequisites missing: low score
        - Difficulty matches current level: bonus
        """
        prereqs = self.graph.get_prerequisites(concept_id)
        prereq_ids = {p.concept_id for p in prereqs}
        
        if not prereq_ids:
            # No prerequisites, foundational concept
            return 1.0
        
        # Calculate prerequisite mastery ratio
        mastered_prereq_count = len(prereq_ids.intersection(mastered_concepts))
        prereq_mastery_ratio = mastered_prereq_count / len(prereq_ids)
        
        # Penalty for missing prerequisites
        if prereq_mastery_ratio < 1.0:
            score = prereq_mastery_ratio * 0.5  # Max 0.5 if incomplete
        else:
            score = 1.0  # Full score if all prerequisites met
        
        return score
    
    def find_alternative_prerequisites(self, target_concept_id: str,
                                      blocked_concept_ids: Set[str]) -> List[ConceptNode]:
        """
        Find alternative concepts that could substitute for blocked prerequisites.
        Useful if certain materials are unavailable.
        """
        # Get direct prerequisites
        prereqs = self.graph.get_prerequisites(target_concept_id)
        
        alternatives = []
        for prereq in prereqs:
            if prereq.concept_id in blocked_concept_ids:
                # Find related concepts at similar depth
                related = self.graph.get_related_concepts(prereq.concept_id)
                
                # Filter to similar difficulty/level
                similar = [c for c in related 
                          if c.difficulty == prereq.difficulty and
                          c.concept_id not in blocked_concept_ids]
                
                alternatives.extend(similar)
        
        return alternatives
