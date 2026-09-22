"""
Remediation Planner
Creates personalized learning plans to address knowledge gaps.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta

import sys
sys.path.append('..')

from knowledge_graph import ConceptNode, ConceptGraph, PrerequisiteMapper
from student_model import StudentProfile, KnowledgeState
from .gap_analyzer import KnowledgeGap, GapType


@dataclass
class RemediationStep:
    """Single step in a remediation plan"""
    concept: ConceptNode
    action_type: str  # "learn", "review", "practice", "assess"
    estimated_duration_minutes: int
    resources: List[str] = field(default_factory=list)
    
    # Sequencing
    step_number: int = 0
    depends_on_steps: List[int] = field(default_factory=list)
    
    # Pedagogical guidance
    teaching_approach: str = ""  # "visual", "step-by-step", "example-driven"
    difficulty_level: str = "medium"
    
    def to_dict(self) -> Dict:
        return {
            'step_number': self.step_number,
            'concept_name': self.concept.name,
            'concept_id': self.concept.concept_id,
            'action_type': self.action_type,
            'estimated_duration_minutes': self.estimated_duration_minutes,
            'teaching_approach': self.teaching_approach,
            'difficulty_level': self.difficulty_level,
            'depends_on_steps': self.depends_on_steps
        }


@dataclass
class RemediationPlan:
    """
    Complete remediation plan for addressing knowledge gaps.
    """
    student_id: str
    target_concept: ConceptNode
    identified_gaps: List[KnowledgeGap]
    steps: List[RemediationStep]
    
    # Summary
    total_duration_minutes: int
    priority: str  # "critical", "high", "medium", "low"
    
    # Scheduling
    created_at: datetime = field(default_factory=datetime.utcnow)
    suggested_completion_date: Optional[datetime] = None
    
    def get_next_step(self) -> Optional[RemediationStep]:
        """Get the next uncompleted step"""
        if self.steps:
            return self.steps[0]
        return None
    
    def to_dict(self) -> Dict:
        return {
            'student_id': self.student_id,
            'target_concept': self.target_concept.name,
            'target_concept_id': self.target_concept.concept_id,
            'gaps_count': len(self.identified_gaps),
            'gaps': [g.to_dict() for g in self.identified_gaps],
            'steps': [s.to_dict() for s in self.steps],
            'total_duration_minutes': self.total_duration_minutes,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'suggested_completion_date': self.suggested_completion_date.isoformat() if self.suggested_completion_date else None
        }


class RemediationPlanner:
    """
    Creates personalized remediation plans based on gap analysis.
    """
    
    def __init__(self, knowledge_graph: ConceptGraph,
                 prerequisite_mapper: PrerequisiteMapper):
        self.graph = knowledge_graph
        self.mapper = prerequisite_mapper
    
    def create_plan(self, target_concept_id: str,
                   gaps: List[KnowledgeGap],
                   student_profile: StudentProfile,
                   student_knowledge: KnowledgeState) -> RemediationPlan:
        """
        Create a remediation plan to address identified gaps.
        """
        target = self.graph.get_concept(target_concept_id)
        
        # Prioritize gaps
        prioritized_gaps = self._prioritize_gaps(gaps, target_concept_id)
        
        # Generate remediation steps
        steps = self._generate_steps(prioritized_gaps, student_profile, student_knowledge)
        
        # Calculate total duration
        total_duration = sum(s.estimated_duration_minutes for s in steps)
        
        # Determine priority
        priority = self._determine_priority(gaps, target)
        
        # Suggest completion date based on student's pace
        completion_date = self._suggest_completion_date(
            total_duration,
            student_profile
        )
        
        return RemediationPlan(
            student_id=student_profile.student_id,
            target_concept=target,
            identified_gaps=prioritized_gaps,
            steps=steps,
            total_duration_minutes=total_duration,
            priority=priority,
            suggested_completion_date=completion_date
        )
    
    def create_quick_review_plan(self, decayed_concepts: List[ConceptNode],
                                student_profile: StudentProfile) -> RemediationPlan:
        """
        Create a quick review plan for decayed knowledge.
        Optimized for spaced repetition review.
        """
        # Create lightweight gaps
        gaps = [
            KnowledgeGap(
                gap_type=GapType.SKILL_DECAY,
                concept=c,
                severity=0.5,
                recommended_action=f"Quick review of {c.name}"
            )
            for c in decayed_concepts
        ]
        
        # Generate review steps (shorter than full learning)
        steps = []
        for i, concept in enumerate(decayed_concepts):
            step = RemediationStep(
                concept=concept,
                action_type="review",
                estimated_duration_minutes=10,
                step_number=i + 1,
                teaching_approach=self._get_teaching_approach(student_profile),
                difficulty_level=concept.difficulty
            )
            steps.append(step)
        
        total_duration = sum(s.estimated_duration_minutes for s in steps)
        
        return RemediationPlan(
            student_id=student_profile.student_id,
            target_concept=decayed_concepts[0] if decayed_concepts else None,
            identified_gaps=gaps,
            steps=steps,
            total_duration_minutes=total_duration,
            priority="medium",
            suggested_completion_date=datetime.utcnow() + timedelta(days=1)
        )
    
    def create_unit_completion_plan(self, subject: str, unit: str,
                                   student_profile: StudentProfile,
                                   student_knowledge: KnowledgeState) -> RemediationPlan:
        """
        Create a plan to complete an entire unit.
        """
        # Get all concepts in the unit
        unit_concepts = [
            c for c in self.graph.concepts.values()
            if c.subject == subject and c.unit == unit
        ]
        
        # Get learning sequence
        mastered_ids = {
            c.concept_id for c in student_knowledge.concepts.values()
            if c.mastery_level.value >= 4
        }
        
        sequence = self.mapper.build_unit_learning_sequence(subject, unit, mastered_ids)
        
        # Generate steps for each concept
        steps = []
        for i, concept in enumerate(sequence):
            # Determine if this is new learning or reinforcement
            concept_mastery = student_knowledge.get_concept(concept.concept_id)
            
            if concept_mastery and concept_mastery.mastery_level.value >= 3:
                action = "practice"
                duration = concept.typical_time_minutes // 2
            else:
                action = "learn"
                duration = concept.typical_time_minutes
            
            step = RemediationStep(
                concept=concept,
                action_type=action,
                estimated_duration_minutes=duration,
                step_number=i + 1,
                teaching_approach=self._get_teaching_approach(student_profile),
                difficulty_level=concept.difficulty
            )
            steps.append(step)
            
            # Add practice step after every 2-3 concepts
            if (i + 1) % 3 == 0:
                practice_step = RemediationStep(
                    concept=concept,
                    action_type="assess",
                    estimated_duration_minutes=15,
                    step_number=len(steps) + 1,
                    teaching_approach="practice",
                    difficulty_level="medium"
                )
                steps.append(practice_step)
        
        total_duration = sum(s.estimated_duration_minutes for s in steps)
        
        return RemediationPlan(
            student_id=student_profile.student_id,
            target_concept=sequence[-1] if sequence else None,
            identified_gaps=[],
            steps=steps,
            total_duration_minutes=total_duration,
            priority="medium",
            suggested_completion_date=self._suggest_completion_date(total_duration, student_profile)
        )
    
    def _prioritize_gaps(self, gaps: List[KnowledgeGap],
                        target_concept_id: str) -> List[KnowledgeGap]:
        """
        Prioritize gaps for remediation order.
        Returns gaps in learning order (foundational first).
        """
        # Separate by type
        missing = [g for g in gaps if g.gap_type == GapType.MISSING_PREREQUISITE]
        weak = [g for g in gaps if g.gap_type == GapType.WEAK_FOUNDATION]
        decay = [g for g in gaps if g.gap_type == GapType.SKILL_DECAY]
        comprehension = [g for g in gaps if g.gap_type == GapType.COMPREHENSION_GAP]
        
        # Sort each category by concept depth (foundational first)
        missing.sort(key=lambda g: self.graph.get_concept_depth(g.concept.concept_id))
        weak.sort(key=lambda g: self.graph.get_concept_depth(g.concept.concept_id))
        
        # Combine: missing first, then weak, then decay, then comprehension
        return missing + weak + decay + comprehension
    
    def _generate_steps(self, gaps: List[KnowledgeGap],
                       student_profile: StudentProfile,
                       student_knowledge: KnowledgeState) -> List[RemediationStep]:
        """
        Generate concrete remediation steps from gaps.
        """
        steps = []
        step_number = 1
        
        teaching_approach = self._get_teaching_approach(student_profile)
        
        for gap in gaps:
            # Determine action based on gap type
            if gap.gap_type == GapType.MISSING_PREREQUISITE:
                action = "learn"
                duration = gap.concept.typical_time_minutes
            elif gap.gap_type == GapType.WEAK_FOUNDATION:
                action = "review"
                duration = gap.concept.typical_time_minutes // 2
            elif gap.gap_type == GapType.SKILL_DECAY:
                action = "review"
                duration = 15
            else:  # COMPREHENSION_GAP
                action = "practice"
                duration = gap.concept.typical_time_minutes
            
            # Create learning step
            learn_step = RemediationStep(
                concept=gap.concept,
                action_type=action,
                estimated_duration_minutes=duration,
                step_number=step_number,
                teaching_approach=teaching_approach,
                difficulty_level=gap.concept.difficulty
            )
            steps.append(learn_step)
            step_number += 1
            
            # Add practice step for critical gaps
            if gap.severity > 0.7 and action in ["learn", "review"]:
                practice_step = RemediationStep(
                    concept=gap.concept,
                    action_type="practice",
                    estimated_duration_minutes=15,
                    step_number=step_number,
                    depends_on_steps=[step_number - 1],
                    teaching_approach="interactive",
                    difficulty_level=gap.concept.difficulty
                )
                steps.append(practice_step)
                step_number += 1
        
        return steps
    
    def _get_teaching_approach(self, student_profile: StudentProfile) -> str:
        """Determine teaching approach based on student profile"""
        primary_style = student_profile.primary_learning_style.value
        
        approach_map = {
            'visual': 'visual',
            'auditory': 'verbal',
            'reading_writing': 'textual',
            'kinesthetic': 'interactive'
        }
        
        approach = approach_map.get(primary_style, 'balanced')
        
        # Add step-by-step if student needs scaffolding
        if student_profile.should_use_scaffolding():
            approach = "step-by-step"
        
        return approach
    
    def _determine_priority(self, gaps: List[KnowledgeGap],
                          target_concept: ConceptNode) -> str:
        """Determine overall priority of remediation"""
        if not gaps:
            return "low"
        
        avg_severity = sum(g.severity for g in gaps) / len(gaps)
        critical_gaps = sum(1 for g in gaps if g.severity > 0.8)
        
        if critical_gaps > 2 or avg_severity > 0.8:
            return "critical"
        elif critical_gaps > 0 or avg_severity > 0.6:
            return "high"
        elif avg_severity > 0.4:
            return "medium"
        else:
            return "low"
    
    def _suggest_completion_date(self, total_minutes: int,
                                student_profile: StudentProfile) -> datetime:
        """Suggest realistic completion date based on student pace"""
        # Estimate daily learning time based on past behavior
        if student_profile.average_session_length > 0:
            daily_minutes = student_profile.average_session_length
        else:
            daily_minutes = 30  # Default
        
        # Adjust for pace preference
        if student_profile.pace_preference.value == "fast":
            daily_minutes *= 1.5
        elif student_profile.pace_preference.value == "slow":
            daily_minutes *= 0.7
        
        # Calculate days needed
        days_needed = max(1, int(total_minutes / daily_minutes))
        
        # Add buffer (20%)
        days_with_buffer = int(days_needed * 1.2)
        
        return datetime.utcnow() + timedelta(days=days_with_buffer)
