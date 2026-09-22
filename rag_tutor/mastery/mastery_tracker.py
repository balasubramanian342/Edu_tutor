"""
Mastery Tracker
Coordinates mastery updates using BKT and IRT, tracks learning progress.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import math

import sys
sys.path.append('..')

from student_model import KnowledgeState, ConceptMastery, StudentProfile
from assessment import GradingResult


@dataclass
class MasteryUpdate:
    """Record of a mastery update event"""
    concept_id: str
    student_id: str
    
    # Before update
    previous_mastery: float
    previous_level: str
    
    # After update
    new_mastery: float
    new_level: str
    
    # Event details
    trigger_event: str  # "practice", "assessment", "teaching"
    was_correct: bool
    difficulty: str
    
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        return {
            'concept_id': self.concept_id,
            'student_id': self.student_id,
            'previous_mastery': self.previous_mastery,
            'previous_level': self.previous_level,
            'new_mastery': self.new_mastery,
            'new_level': self.new_level,
            'trigger_event': self.trigger_event,
            'was_correct': self.was_correct,
            'difficulty': self.difficulty,
            'timestamp': self.timestamp.isoformat()
        }


class MasteryTracker:
    """
    Tracks and updates mastery levels using Bayesian Knowledge Tracing
    and Item Response Theory.
    """
    
    def __init__(self, irt_engine=None):
        """
        Initialize mastery tracker.
        
        Args:
            irt_engine: Optional IRT engine for ability estimation
        """
        self.irt_engine = irt_engine
        self.update_history: List[MasteryUpdate] = []
    
    def update_from_assessment(self,
                              student_knowledge: KnowledgeState,
                              student_profile: StudentProfile,
                              grading_result: GradingResult,
                              concept_id: str,
                              difficulty: str) -> MasteryUpdate:
        """
        Update mastery based on assessment result.
        
        Args:
            student_knowledge: Student's knowledge state
            student_profile: Student profile
            grading_result: Result of grading
            concept_id: Concept being assessed
            difficulty: Question difficulty
        
        Returns:
            MasteryUpdate record
        """
        
        # Get or create concept mastery
        concept_mastery = student_knowledge.get_concept(concept_id)
        
        if not concept_mastery:
            # Create new concept mastery entry
            from knowledge_graph import ConceptNode
            concept_mastery = ConceptMastery(
                concept_id=concept_id,
                concept_name=f"Concept {concept_id}",
                subject="Unknown",
                unit="Unknown"
            )
            student_knowledge.add_concept(concept_mastery)
        
        # Record previous state
        prev_mastery = concept_mastery.mastery_probability
        prev_level = concept_mastery.mastery_level.name
        
        # Update using BKT
        was_correct = grading_result.is_correct
        concept_mastery.update_after_attempt(was_correct, difficulty)
        
        # If IRT engine available, also update ability estimate
        if self.irt_engine:
            self.irt_engine.update_ability(
                student_profile,
                concept_id,
                was_correct,
                difficulty
            )
        
        # Create update record
        update = MasteryUpdate(
            concept_id=concept_id,
            student_id=student_profile.student_id,
            previous_mastery=prev_mastery,
            previous_level=prev_level,
            new_mastery=concept_mastery.mastery_probability,
            new_level=concept_mastery.mastery_level.name,
            trigger_event="assessment",
            was_correct=was_correct,
            difficulty=difficulty
        )
        
        self.update_history.append(update)
        
        # Update student profile's overall mastery
        self._update_overall_mastery(student_profile, student_knowledge)
        
        return update
    
    def update_from_practice(self,
                           student_knowledge: KnowledgeState,
                           student_profile: StudentProfile,
                           concept_id: str,
                           was_successful: bool,
                           difficulty: str = "medium") -> MasteryUpdate:
        """
        Update mastery based on practice activity.
        
        Args:
            student_knowledge: Student's knowledge state
            student_profile: Student profile
            concept_id: Concept being practiced
            was_successful: Whether practice was successful
            difficulty: Practice difficulty
        
        Returns:
            MasteryUpdate record
        """
        
        concept_mastery = student_knowledge.get_concept(concept_id)
        
        if not concept_mastery:
            concept_mastery = ConceptMastery(
                concept_id=concept_id,
                concept_name=f"Concept {concept_id}",
                subject="Unknown",
                unit="Unknown"
            )
            student_knowledge.add_concept(concept_mastery)
        
        prev_mastery = concept_mastery.mastery_probability
        prev_level = concept_mastery.mastery_level.name
        
        # Update with slightly different parameters for practice
        # (practice might have more guessing)
        original_p_guess = concept_mastery.p_guess
        concept_mastery.p_guess = 0.3  # Higher guess rate for practice
        
        concept_mastery.update_after_attempt(was_successful, difficulty)
        
        concept_mastery.p_guess = original_p_guess  # Restore
        
        update = MasteryUpdate(
            concept_id=concept_id,
            student_id=student_profile.student_id,
            previous_mastery=prev_mastery,
            previous_level=prev_level,
            new_mastery=concept_mastery.mastery_probability,
            new_level=concept_mastery.mastery_level.name,
            trigger_event="practice",
            was_correct=was_successful,
            difficulty=difficulty
        )
        
        self.update_history.append(update)
        self._update_overall_mastery(student_profile, student_knowledge)
        
        return update
    
    def update_from_teaching(self,
                           student_knowledge: KnowledgeState,
                           student_profile: StudentProfile,
                           concept_id: str,
                           teaching_quality: float) -> MasteryUpdate:
        """
        Update mastery based on teaching interaction.
        
        Args:
            student_knowledge: Student's knowledge state
            student_profile: Student profile
            concept_id: Concept being taught
            teaching_quality: Quality of teaching (0-1, based on confidence, etc.)
        
        Returns:
            MasteryUpdate record
        """
        
        concept_mastery = student_knowledge.get_concept(concept_id)
        
        if not concept_mastery:
            concept_mastery = ConceptMastery(
                concept_id=concept_id,
                concept_name=f"Concept {concept_id}",
                subject="Unknown",
                unit="Unknown"
            )
            student_knowledge.add_concept(concept_mastery)
        
        prev_mastery = concept_mastery.mastery_probability
        prev_level = concept_mastery.mastery_level.name
        
        # Increase mastery based on teaching quality
        # Teaching provides learning opportunity without explicit testing
        learning_gain = concept_mastery.p_learn * teaching_quality
        concept_mastery.mastery_probability = min(1.0,
            concept_mastery.mastery_probability + learning_gain)
        
        # Update mastery level
        concept_mastery._update_mastery_level()
        
        # Mark as practiced
        concept_mastery.last_practiced = datetime.utcnow()
        
        update = MasteryUpdate(
            concept_id=concept_id,
            student_id=student_profile.student_id,
            previous_mastery=prev_mastery,
            previous_level=prev_level,
            new_mastery=concept_mastery.mastery_probability,
            new_level=concept_mastery.mastery_level.name,
            trigger_event="teaching",
            was_correct=True,  # Teaching is always "positive"
            difficulty="medium"
        )
        
        self.update_history.append(update)
        self._update_overall_mastery(student_profile, student_knowledge)
        
        return update
    
    def apply_decay(self,
                   student_knowledge: KnowledgeState,
                   student_profile: StudentProfile) -> List[MasteryUpdate]:
        """
        Apply temporal decay to concepts not recently practiced.
        Called periodically (e.g., daily).
        
        Args:
            student_knowledge: Student's knowledge state
            student_profile: Student profile
        
        Returns:
            List of concepts that decayed
        """
        
        updates = []
        
        for concept_mastery in student_knowledge.concepts.values():
            # Check how long since last practice
            hours_since = (datetime.utcnow() - concept_mastery.last_practiced).total_seconds() / 3600
            
            if hours_since > 168:  # More than 1 week
                prev_mastery = concept_mastery.mastery_probability
                prev_level = concept_mastery.mastery_level.name
                
                # Apply decay
                decay_rate = 0.01 * (hours_since / 168)  # 1% per week
                concept_mastery.mastery_probability *= (1 - decay_rate)
                concept_mastery._update_mastery_level()
                
                if prev_mastery != concept_mastery.mastery_probability:
                    update = MasteryUpdate(
                        concept_id=concept_mastery.concept_id,
                        student_id=student_profile.student_id,
                        previous_mastery=prev_mastery,
                        previous_level=prev_level,
                        new_mastery=concept_mastery.mastery_probability,
                        new_level=concept_mastery.mastery_level.name,
                        trigger_event="decay",
                        was_correct=False,
                        difficulty="medium"
                    )
                    updates.append(update)
        
        if updates:
            self._update_overall_mastery(student_profile, student_knowledge)
        
        return updates
    
    def get_mastery_trajectory(self,
                              student_id: str,
                              concept_id: str,
                              limit: int = 20) -> List[MasteryUpdate]:
        """
        Get mastery trajectory for a concept over time.
        
        Args:
            student_id: Student ID
            concept_id: Concept ID
            limit: Maximum number of updates to return
        
        Returns:
            List of mastery updates in chronological order
        """
        
        trajectory = [
            update for update in self.update_history
            if update.student_id == student_id and update.concept_id == concept_id
        ]
        
        trajectory.sort(key=lambda u: u.timestamp)
        
        return trajectory[-limit:]
    
    def get_recent_improvements(self,
                               student_id: str,
                               days: int = 7) -> List[Dict]:
        """
        Get concepts that improved in recent period.
        
        Args:
            student_id: Student ID
            days: Number of days to look back
        
        Returns:
            List of improved concepts with details
        """
        
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get recent updates
        recent_updates = [
            u for u in self.update_history
            if u.student_id == student_id and u.timestamp >= cutoff
        ]
        
        # Group by concept
        concept_improvements = {}
        
        for update in recent_updates:
            if update.concept_id not in concept_improvements:
                concept_improvements[update.concept_id] = {
                    'concept_id': update.concept_id,
                    'initial_mastery': update.previous_mastery,
                    'final_mastery': update.new_mastery,
                    'updates_count': 0
                }
            
            data = concept_improvements[update.concept_id]
            data['final_mastery'] = update.new_mastery
            data['updates_count'] += 1
        
        # Filter to actual improvements
        improvements = [
            data for data in concept_improvements.values()
            if data['final_mastery'] > data['initial_mastery']
        ]
        
        # Sort by improvement magnitude
        improvements.sort(
            key=lambda d: d['final_mastery'] - d['initial_mastery'],
            reverse=True
        )
        
        return improvements
    
    def predict_mastery(self,
                       student_knowledge: KnowledgeState,
                       concept_id: str,
                       future_attempts: int,
                       expected_success_rate: float) -> float:
        """
        Predict future mastery level given expected performance.
        
        Args:
            student_knowledge: Student's knowledge state
            concept_id: Concept to predict
            future_attempts: Number of future practice attempts
            expected_success_rate: Expected success rate on those attempts
        
        Returns:
            Predicted mastery probability
        """
        
        concept_mastery = student_knowledge.get_concept(concept_id)
        
        if not concept_mastery:
            return 0.0
        
        # Simulate future attempts
        predicted_mastery = concept_mastery.mastery_probability
        p_learn = concept_mastery.p_learn
        
        for _ in range(future_attempts):
            # Assume success with given probability
            if expected_success_rate > 0.5:  # More likely correct
                # Learning opportunity
                predicted_mastery = min(1.0,
                    predicted_mastery + (1 - predicted_mastery) * p_learn)
        
        return predicted_mastery
    
    def _update_overall_mastery(self,
                               student_profile: StudentProfile,
                               student_knowledge: KnowledgeState):
        """Update student profile's overall mastery statistics"""
        
        overall = student_knowledge.get_overall_mastery()
        student_profile.overall_mastery = overall
        
        # Count concepts at different levels
        from student_model import MasteryLevel
        
        mastered = sum(1 for c in student_knowledge.concepts.values()
                      if c.mastery_level == MasteryLevel.MASTERED)
        
        in_progress = sum(1 for c in student_knowledge.concepts.values()
                         if c.mastery_level in [MasteryLevel.DEVELOPING,
                                               MasteryLevel.APPROACHING,
                                               MasteryLevel.PROFICIENT])
        
        student_profile.concepts_mastered = mastered
        student_profile.concepts_in_progress = in_progress
        student_profile.updated_at = datetime.utcnow()
    
    def export_history(self, filepath: str):
        """Export update history to JSON file"""
        import json
        
        data = [update.to_dict() for update in self.update_history]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def load_history(self, filepath: str):
        """Load update history from JSON file"""
        import json
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.update_history = []
        for item in data:
            item['timestamp'] = datetime.fromisoformat(item['timestamp'])
            self.update_history.append(MasteryUpdate(**item))
