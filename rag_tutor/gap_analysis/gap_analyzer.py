"""
Gap Analyzer
Compares student knowledge state against knowledge graph to identify gaps.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Set, Dict, Optional, Tuple
from datetime import datetime

import sys
sys.path.append('..')

from knowledge_graph import ConceptGraph, ConceptNode, PrerequisiteMapper
from student_model import KnowledgeState, MasteryLevel, StudentProfile


class GapType(Enum):
    """Types of knowledge gaps"""
    MISSING_PREREQUISITE = "missing_prerequisite"   # Prerequisite not learned
    WEAK_FOUNDATION = "weak_foundation"             # Prerequisite learned but not mastered
    SKILL_DECAY = "skill_decay"                     # Previously mastered but decayed
    COMPREHENSION_GAP = "comprehension_gap"         # Can't apply/transfer knowledge
    CONCEPTUAL_MISUNDERSTANDING = "conceptual_misunderstanding"  # Wrong mental model


@dataclass
class KnowledgeGap:
    """
    Represents an identified knowledge gap.
    """
    gap_type: GapType
    concept: ConceptNode
    severity: float  # 0-1, how critical this gap is
    
    # Context
    blocking_concepts: List[ConceptNode] = field(default_factory=list)  # What this gap prevents learning
    related_gaps: List['KnowledgeGap'] = field(default_factory=list)
    
    # Evidence
    current_mastery: float = 0.0
    required_mastery: float = 0.7
    attempts_count: int = 0
    last_interaction: Optional[datetime] = None
    
    # Recommendations
    recommended_action: str = ""
    estimated_remediation_time: int = 0  # minutes
    
    def __lt__(self, other):
        """For sorting by severity"""
        return self.severity > other.severity  # Higher severity first
    
    def to_dict(self) -> Dict:
        return {
            'gap_type': self.gap_type.value,
            'concept_id': self.concept.concept_id,
            'concept_name': self.concept.name,
            'severity': self.severity,
            'blocking_concepts': [c.name for c in self.blocking_concepts],
            'current_mastery': self.current_mastery,
            'required_mastery': self.required_mastery,
            'recommended_action': self.recommended_action,
            'estimated_remediation_time': self.estimated_remediation_time
        }


class GapAnalyzer:
    """
    Analyzes student knowledge state against domain knowledge graph.
    Identifies gaps and prioritizes them for remediation.
    """
    
    def __init__(self, knowledge_graph: ConceptGraph, 
                 prerequisite_mapper: PrerequisiteMapper):
        self.graph = knowledge_graph
        self.mapper = prerequisite_mapper
    
    def analyze_for_concept(self, target_concept_id: str,
                           student_knowledge: KnowledgeState,
                           student_profile: StudentProfile) -> List[KnowledgeGap]:
        """
        Identify all gaps preventing student from learning target concept.
        Returns gaps sorted by severity.
        """
        gaps = []
        
        # Get required prerequisites
        all_prereqs = self.graph.get_all_prerequisites(target_concept_id)
        
        # Get student's mastered concepts
        mastered_ids = {
            c.concept_id for c in student_knowledge.concepts.values()
            if c.mastery_level in [MasteryLevel.PROFICIENT, MasteryLevel.MASTERED]
        }
        
        # Check each prerequisite
        for prereq in all_prereqs:
            concept_mastery = student_knowledge.get_concept(prereq.concept_id)
            
            if concept_mastery is None:
                # Never encountered - missing prerequisite
                gap = self._create_missing_prerequisite_gap(prereq, target_concept_id)
                gaps.append(gap)
            
            elif concept_mastery.mastery_level in [MasteryLevel.NOT_STARTED, MasteryLevel.INTRODUCED]:
                # Seen but not learned
                gap = self._create_missing_prerequisite_gap(prereq, target_concept_id, concept_mastery)
                gaps.append(gap)
            
            elif concept_mastery.mastery_level in [MasteryLevel.DEVELOPING, MasteryLevel.APPROACHING]:
                # Partially learned - weak foundation
                gap = self._create_weak_foundation_gap(prereq, target_concept_id, concept_mastery)
                gaps.append(gap)
            
            elif concept_mastery.mastery_level in [MasteryLevel.PROFICIENT, MasteryLevel.MASTERED]:
                # Check for skill decay
                retrieval_strength = concept_mastery.get_retrieval_strength()
                if retrieval_strength < 0.7:
                    gap = self._create_skill_decay_gap(prereq, concept_mastery, retrieval_strength)
                    gaps.append(gap)
        
        # Check target concept itself if attempted
        target_mastery = student_knowledge.get_concept(target_concept_id)
        if target_mastery and target_mastery.attempts > 0:
            if target_mastery.recent_success_rate < 0.5:
                # Student is struggling despite having prerequisites
                # Might be comprehension or conceptual issue
                gap = self._create_comprehension_gap(
                    self.graph.get_concept(target_concept_id),
                    target_mastery
                )
                gaps.append(gap)
        
        # Calculate severity and sort
        self._calculate_severity(gaps, target_concept_id, student_profile)
        gaps.sort()
        
        return gaps
    
    def analyze_overall(self, student_knowledge: KnowledgeState,
                       student_profile: StudentProfile,
                       subject: Optional[str] = None) -> List[KnowledgeGap]:
        """
        Perform comprehensive gap analysis across all student knowledge.
        """
        gaps = []
        
        # Get all concepts student has attempted
        attempted_concepts = [
            c for c in student_knowledge.concepts.values()
            if c.attempts > 0
        ]
        
        for concept_mastery in attempted_concepts:
            concept = self.graph.get_concept(concept_mastery.concept_id)
            
            if not concept or (subject and concept.subject != subject):
                continue
            
            # Check if struggling with this concept
            if concept_mastery.mastery_level < MasteryLevel.PROFICIENT:
                # Find prerequisite gaps
                concept_gaps = self.analyze_for_concept(
                    concept.concept_id,
                    student_knowledge,
                    student_profile
                )
                gaps.extend(concept_gaps)
            
            # Check for decay
            elif concept_mastery.mastery_level >= MasteryLevel.PROFICIENT:
                retrieval_strength = concept_mastery.get_retrieval_strength()
                if retrieval_strength < 0.7:
                    gap = self._create_skill_decay_gap(concept, concept_mastery, retrieval_strength)
                    gaps.append(gap)
        
        # Deduplicate gaps (same concept might appear multiple times)
        unique_gaps = {}
        for gap in gaps:
            key = (gap.gap_type, gap.concept.concept_id)
            if key not in unique_gaps or gap.severity > unique_gaps[key].severity:
                unique_gaps[key] = gap
        
        result = list(unique_gaps.values())
        result.sort()
        
        return result
    
    def identify_bottleneck_concepts(self, student_knowledge: KnowledgeState) -> List[ConceptNode]:
        """
        Find concepts that are blocking progress on many other concepts.
        These are high-priority remediation targets.
        """
        mastered_ids = {
            c.concept_id for c in student_knowledge.concepts.values()
            if c.mastery_level >= MasteryLevel.PROFICIENT
        }
        
        # Count how many concepts each unmastered prerequisite is blocking
        blocking_counts = {}
        
        for concept in self.graph.concepts.values():
            prereqs = self.graph.get_prerequisites(concept.concept_id)
            
            for prereq in prereqs:
                if prereq.concept_id not in mastered_ids:
                    if prereq.concept_id not in blocking_counts:
                        blocking_counts[prereq.concept_id] = {
                            'concept': prereq,
                            'blocking_count': 0
                        }
                    blocking_counts[prereq.concept_id]['blocking_count'] += 1
        
        # Sort by blocking count
        bottlenecks = sorted(
            blocking_counts.values(),
            key=lambda x: x['blocking_count'],
            reverse=True
        )
        
        return [b['concept'] for b in bottlenecks[:5]]  # Top 5 bottlenecks
    
    def suggest_next_learning_target(self, student_knowledge: KnowledgeState,
                                    student_profile: StudentProfile,
                                    subject: Optional[str] = None) -> Optional[ConceptNode]:
        """
        Suggest the best concept to learn next based on readiness and gaps.
        """
        mastered_ids = {
            c.concept_id for c in student_knowledge.concepts.values()
            if c.mastery_level >= MasteryLevel.PROFICIENT
        }
        
        # Get concepts that are ready to learn
        ready_concepts = self.graph.get_next_concepts(mastered_ids, subject)
        
        if not ready_concepts:
            return None
        
        # Score each concept
        scored = []
        for concept in ready_concepts:
            # How many other concepts does this unlock?
            dependents = self.graph.get_dependents(concept.concept_id)
            unlock_score = len(dependents)
            
            # Difficulty match with student profile
            difficulty_match = self._get_difficulty_match_score(
                concept,
                student_profile
            )
            
            # Bloom level progression (prefer gradual increase)
            bloom_score = self._get_bloom_level_score(
                concept,
                student_knowledge,
                mastered_ids
            )
            
            total_score = (unlock_score * 0.4 + 
                          difficulty_match * 0.3 + 
                          bloom_score * 0.3)
            
            scored.append((concept, total_score))
        
        # Return highest scoring
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]
    
    def _create_missing_prerequisite_gap(self, concept: ConceptNode,
                                        target_id: str,
                                        mastery=None) -> KnowledgeGap:
        """Create gap for missing/unlearned prerequisite"""
        blocking = self.graph.get_dependents(concept.concept_id)
        
        return KnowledgeGap(
            gap_type=GapType.MISSING_PREREQUISITE,
            concept=concept,
            severity=0.9,  # Will be refined by severity calculator
            blocking_concepts=blocking,
            current_mastery=mastery.mastery_probability if mastery else 0.0,
            required_mastery=0.7,
            attempts_count=mastery.attempts if mastery else 0,
            recommended_action=f"Learn {concept.name} before attempting {self.graph.get_concept(target_id).name}",
            estimated_remediation_time=concept.typical_time_minutes
        )
    
    def _create_weak_foundation_gap(self, concept: ConceptNode,
                                   target_id: str,
                                   mastery) -> KnowledgeGap:
        """Create gap for weak foundational knowledge"""
        return KnowledgeGap(
            gap_type=GapType.WEAK_FOUNDATION,
            concept=concept,
            severity=0.7,
            current_mastery=mastery.mastery_probability,
            required_mastery=0.7,
            attempts_count=mastery.attempts,
            last_interaction=mastery.last_practiced,
            recommended_action=f"Review and practice {concept.name} with additional examples",
            estimated_remediation_time=concept.typical_time_minutes // 2
        )
    
    def _create_skill_decay_gap(self, concept: ConceptNode,
                               mastery,
                               retrieval_strength: float) -> KnowledgeGap:
        """Create gap for decayed knowledge"""
        return KnowledgeGap(
            gap_type=GapType.SKILL_DECAY,
            concept=concept,
            severity=0.5,
            current_mastery=retrieval_strength,
            required_mastery=0.7,
            attempts_count=mastery.attempts,
            last_interaction=mastery.last_practiced,
            recommended_action=f"Quick refresher on {concept.name}",
            estimated_remediation_time=15  # Quick review
        )
    
    def _create_comprehension_gap(self, concept: ConceptNode,
                                 mastery) -> KnowledgeGap:
        """Create gap for comprehension issues"""
        return KnowledgeGap(
            gap_type=GapType.COMPREHENSION_GAP,
            concept=concept,
            severity=0.8,
            current_mastery=mastery.mastery_probability,
            required_mastery=0.7,
            attempts_count=mastery.attempts,
            recommended_action=f"Try different explanation approach or additional examples for {concept.name}",
            estimated_remediation_time=concept.typical_time_minutes
        )
    
    def _calculate_severity(self, gaps: List[KnowledgeGap],
                          target_concept_id: str,
                          student_profile: StudentProfile):
        """
        Calculate severity scores for gaps based on multiple factors.
        Modifies gaps in place.
        """
        target = self.graph.get_concept(target_concept_id)
        
        for gap in gaps:
            base_severity = {
                GapType.MISSING_PREREQUISITE: 0.9,
                GapType.WEAK_FOUNDATION: 0.7,
                GapType.SKILL_DECAY: 0.5,
                GapType.COMPREHENSION_GAP: 0.8,
                GapType.CONCEPTUAL_MISUNDERSTANDING: 0.95
            }[gap.gap_type]
            
            # Adjust for how many concepts this blocks
            blocking_factor = min(1.0, len(gap.blocking_concepts) / 5)
            
            # Adjust for depth (foundational gaps are more severe)
            depth = self.graph.get_concept_depth(gap.concept.concept_id)
            depth_factor = 1.0 / (depth + 1)  # Shallower = more severe
            
            # Adjust for student's cognitive profile
            if gap.concept.difficulty == "hard" and student_profile.cognitive_profile.abstract_reasoning < 0.4:
                difficulty_factor = 1.2  # Extra severe if student struggles with difficulty
            else:
                difficulty_factor = 1.0
            
            # Combined severity
            gap.severity = min(1.0, base_severity * (0.5 + 0.3 * blocking_factor + 0.2 * depth_factor) * difficulty_factor)
    
    def _get_difficulty_match_score(self, concept: ConceptNode,
                                   student_profile: StudentProfile) -> float:
        """Score how well concept difficulty matches student level"""
        difficulty_map = {'easy': 0, 'medium': 1, 'hard': 2}
        
        # Estimate student's comfort level
        if student_profile.cognitive_profile.abstract_reasoning > 0.7:
            student_level = 2  # Can handle hard
        elif student_profile.cognitive_profile.abstract_reasoning > 0.4:
            student_level = 1  # Medium
        else:
            student_level = 0  # Stick to easy
        
        concept_level = difficulty_map[concept.difficulty]
        
        # Perfect match = 1.0, one off = 0.5, two off = 0.0
        diff = abs(student_level - concept_level)
        return max(0.0, 1.0 - diff * 0.5)
    
    def _get_bloom_level_score(self, concept: ConceptNode,
                              student_knowledge: KnowledgeState,
                              mastered_ids: Set[str]) -> float:
        """Score based on Bloom's taxonomy progression"""
        if not student_knowledge.concepts:
            return 1.0 if concept.bloom_level <= 2 else 0.0
        
        # Get max bloom level student has mastered
        mastered_concepts = [
            self.graph.get_concept(cid) for cid in mastered_ids
            if self.graph.get_concept(cid)
        ]
        
        if not mastered_concepts:
            max_bloom = 0
        else:
            max_bloom = max(c.bloom_level for c in mastered_concepts)
        
        # Prefer concepts at current level or one above
        if concept.bloom_level <= max_bloom + 1:
            return 1.0
        elif concept.bloom_level == max_bloom + 2:
            return 0.5
        else:
            return 0.0
