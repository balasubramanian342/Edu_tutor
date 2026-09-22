"""
Adaptation Engine
Dynamically adjusts difficulty, pace, and content modality based on performance.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import sys
sys.path.append('..')

from student_model import StudentProfile, KnowledgeState, MasteryLevel
from .mastery_tracker import MasteryTracker


class AdaptationTrigger(Enum):
    """Events that trigger adaptation"""
    PERFORMANCE_DECLINE = "performance_decline"
    PERFORMANCE_EXCELLENCE = "performance_excellence"
    ENGAGEMENT_DROP = "engagement_drop"
    FRUSTRATION_DETECTED = "frustration_detected"
    MASTERY_ACHIEVED = "mastery_achieved"
    TIME_LIMIT_APPROACHING = "time_limit_approaching"
    SCHEDULED_CHECK = "scheduled_check"


@dataclass
class AdaptationDecision:
    """
    Decision about how to adapt instruction.
    """
    trigger: AdaptationTrigger
    
    # Adjustments
    adjust_difficulty: Optional[str] = None  # "increase", "decrease", "maintain"
    adjust_pace: Optional[str] = None  # "faster", "slower", "maintain"
    adjust_modality: Optional[str] = None  # "more_visual", "more_textual", "more_interactive"
    adjust_scaffolding: Optional[str] = None  # "increase", "decrease", "maintain"
    
    # Content changes
    provide_remediation: bool = False
    provide_enrichment: bool = False
    suggest_break: bool = False
    
    # Recommendations
    reasoning: str = ""
    recommended_actions: List[str] = None
    
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.recommended_actions is None:
            self.recommended_actions = []
    
    def to_dict(self) -> Dict:
        return {
            'trigger': self.trigger.value,
            'adjust_difficulty': self.adjust_difficulty,
            'adjust_pace': self.adjust_pace,
            'adjust_modality': self.adjust_modality,
            'adjust_scaffolding': self.adjust_scaffolding,
            'provide_remediation': self.provide_remediation,
            'provide_enrichment': self.provide_enrichment,
            'suggest_break': self.suggest_break,
            'reasoning': self.reasoning,
            'recommended_actions': self.recommended_actions,
            'timestamp': self.timestamp.isoformat()
        }


class AdaptationEngine:
    """
    Monitors student performance and adapts instruction in real-time.
    """
    
    def __init__(self, mastery_tracker: MasteryTracker):
        self.mastery_tracker = mastery_tracker
        self.adaptation_history: List[AdaptationDecision] = []
        
        # Thresholds for triggering adaptations
        self.performance_decline_threshold = 0.5  # Success rate below this
        self.performance_excellence_threshold = 0.9  # Success rate above this
        self.engagement_time_threshold = 30  # Minutes without activity
    
    def evaluate_and_adapt(self,
                          student_profile: StudentProfile,
                          student_knowledge: KnowledgeState,
                          current_concept_id: Optional[str] = None,
                          recent_session_data: Optional[Dict] = None) -> AdaptationDecision:
        """
        Evaluate current student state and decide on adaptations.
        
        Args:
            student_profile: Student profile
            student_knowledge: Knowledge state
            current_concept_id: Currently learning concept
            recent_session_data: Recent interaction data
        
        Returns:
            AdaptationDecision with recommended changes
        """
        
        # Analyze recent performance
        performance_trigger = self._check_performance(
            student_knowledge,
            current_concept_id
        )
        
        if performance_trigger:
            return self._adapt_to_performance(
                performance_trigger,
                student_profile,
                student_knowledge,
                current_concept_id
            )
        
        # Check engagement
        engagement_trigger = self._check_engagement(student_profile, recent_session_data)
        
        if engagement_trigger:
            return self._adapt_to_engagement(
                engagement_trigger,
                student_profile,
                recent_session_data
            )
        
        # Check for mastery achievement
        if current_concept_id:
            concept_mastery = student_knowledge.get_concept(current_concept_id)
            if concept_mastery and concept_mastery.mastery_level == MasteryLevel.MASTERED:
                return self._adapt_to_mastery(student_profile, current_concept_id)
        
        # No adaptation needed
        return AdaptationDecision(
            trigger=AdaptationTrigger.SCHEDULED_CHECK,
            adjust_difficulty="maintain",
            adjust_pace="maintain",
            reasoning="Student is progressing well, no changes needed."
        )
    
    def adapt_difficulty(self,
                        student_profile: StudentProfile,
                        student_knowledge: KnowledgeState,
                        concept_id: str,
                        recent_success_rate: float) -> str:
        """
        Determine appropriate difficulty level.
        
        Args:
            student_profile: Student profile
            student_knowledge: Knowledge state
            concept_id: Target concept
            recent_success_rate: Recent performance (0-1)
        
        Returns:
            Difficulty level: "easy", "medium", or "hard"
        """
        
        concept_mastery = student_knowledge.get_concept(concept_id)
        
        if not concept_mastery:
            return "easy"  # Start easy for new concepts
        
        mastery = concept_mastery.mastery_probability
        
        # Zone of Proximal Development principle
        # Aim for 70-80% success rate for optimal learning
        
        if recent_success_rate < 0.5:
            # Struggling - decrease difficulty
            return "easy"
        
        elif recent_success_rate > 0.9:
            # Too easy - increase difficulty
            if mastery > 0.7:
                return "hard"
            else:
                return "medium"
        
        else:
            # In good range - maintain or slightly adjust
            if mastery < 0.4:
                return "easy"
            elif mastery > 0.7:
                return "hard"
            else:
                return "medium"
    
    def adapt_pace(self,
                  student_profile: StudentProfile,
                  recent_performance: float,
                  time_on_concept: int) -> str:
        """
        Determine appropriate learning pace.
        
        Args:
            student_profile: Student profile
            recent_performance: Recent success rate
            time_on_concept: Minutes spent on current concept
        
        Returns:
            Pace adjustment: "faster", "slower", or "maintain"
        """
        
        # Check student's pace preference
        preferred_pace = student_profile.pace_preference.value
        
        # Check if student is spending too much/little time
        typical_time = 45  # Typical time for a concept
        
        if time_on_concept > typical_time * 1.5:
            # Taking too long
            if recent_performance < 0.6:
                return "slower"  # Need more time, but also struggling
            else:
                return "maintain"  # Just methodical
        
        elif time_on_concept < typical_time * 0.5:
            # Moving very quickly
            if recent_performance > 0.8:
                return "faster"  # Mastering quickly, can accelerate
            else:
                return "slower"  # Moving too fast, not absorbing
        
        # Check cognitive load
        if student_profile.cognitive_profile.processing_speed < 0.4:
            return "slower"
        elif student_profile.cognitive_profile.processing_speed > 0.7 and recent_performance > 0.75:
            return "faster"
        
        return "maintain"
    
    def adapt_modality(self,
                      student_profile: StudentProfile,
                      recent_engagement: float,
                      current_modality: str) -> str:
        """
        Adapt content presentation modality.
        
        Args:
            student_profile: Student profile
            recent_engagement: Engagement score (0-1)
            current_modality: Current presentation mode
        
        Returns:
            Modality recommendation
        """
        
        primary_style = student_profile.primary_learning_style.value
        
        # If engagement is low, try preferred style
        if recent_engagement < 0.5:
            style_map = {
                'visual': 'more_visual',
                'auditory': 'more_verbal',
                'reading_writing': 'more_textual',
                'kinesthetic': 'more_interactive'
            }
            return style_map.get(primary_style, 'more_interactive')
        
        # If doing well, maintain current
        return "maintain"
    
    def adapt_scaffolding(self,
                         student_profile: StudentProfile,
                         student_knowledge: KnowledgeState,
                         concept_id: str,
                         recent_errors: List[str]) -> str:
        """
        Adapt level of scaffolding/support.
        
        Args:
            student_profile: Student profile
            student_knowledge: Knowledge state
            concept_id: Current concept
            recent_errors: Recent error patterns
        
        Returns:
            Scaffolding adjustment: "increase", "decrease", "maintain"
        """
        
        concept_mastery = student_knowledge.get_concept(concept_id)
        
        if not concept_mastery:
            return "increase"  # New concept needs scaffolding
        
        # Check if student is struggling with same errors
        if len(recent_errors) > 3:
            return "increase"
        
        # Check mastery progress
        if concept_mastery.mastery_level in [MasteryLevel.PROFICIENT, MasteryLevel.MASTERED]:
            return "decrease"  # Fade scaffolding for mastered concepts
        
        # Check metacognition
        if student_profile.cognitive_profile.metacognition < 0.4:
            return "increase"  # Low self-monitoring needs more support
        
        return "maintain"
    
    def _check_performance(self,
                          student_knowledge: KnowledgeState,
                          concept_id: Optional[str]) -> Optional[AdaptationTrigger]:
        """Check for performance-based triggers"""
        
        if not concept_id:
            return None
        
        concept_mastery = student_knowledge.get_concept(concept_id)
        
        if not concept_mastery or concept_mastery.attempts < 3:
            return None  # Not enough data
        
        recent_rate = concept_mastery.recent_success_rate
        
        if recent_rate < self.performance_decline_threshold:
            return AdaptationTrigger.PERFORMANCE_DECLINE
        
        elif recent_rate > self.performance_excellence_threshold:
            return AdaptationTrigger.PERFORMANCE_EXCELLENCE
        
        return None
    
    def _check_engagement(self,
                         student_profile: StudentProfile,
                         session_data: Optional[Dict]) -> Optional[AdaptationTrigger]:
        """Check for engagement-based triggers"""
        
        if not session_data:
            return None
        
        # Check time since last activity
        last_active = student_profile.last_active
        if last_active:
            minutes_inactive = (datetime.utcnow() - last_active).total_seconds() / 60
            
            if minutes_inactive > self.engagement_time_threshold:
                return AdaptationTrigger.ENGAGEMENT_DROP
        
        # Check for frustration indicators (rapid incorrect attempts)
        if session_data.get('rapid_failures', 0) > 3:
            return AdaptationTrigger.FRUSTRATION_DETECTED
        
        return None
    
    def _adapt_to_performance(self,
                             trigger: AdaptationTrigger,
                             student_profile: StudentProfile,
                             student_knowledge: KnowledgeState,
                             concept_id: str) -> AdaptationDecision:
        """Create adaptation for performance triggers"""
        
        if trigger == AdaptationTrigger.PERFORMANCE_DECLINE:
            return AdaptationDecision(
                trigger=trigger,
                adjust_difficulty="decrease",
                adjust_pace="slower",
                adjust_scaffolding="increase",
                provide_remediation=True,
                reasoning="Student is struggling with current material. "
                         "Reducing difficulty and providing additional support.",
                recommended_actions=[
                    "Review prerequisite concepts",
                    "Provide worked examples",
                    "Increase practice opportunities",
                    "Use step-by-step guidance"
                ]
            )
        
        else:  # PERFORMANCE_EXCELLENCE
            return AdaptationDecision(
                trigger=trigger,
                adjust_difficulty="increase",
                adjust_pace="faster",
                adjust_scaffolding="decrease",
                provide_enrichment=True,
                reasoning="Student is excelling. Increasing challenge to maintain engagement.",
                recommended_actions=[
                    "Introduce more complex problems",
                    "Encourage independent exploration",
                    "Provide advanced topics",
                    "Reduce explicit guidance"
                ]
            )
    
    def _adapt_to_engagement(self,
                            trigger: AdaptationTrigger,
                            student_profile: StudentProfile,
                            session_data: Dict) -> AdaptationDecision:
        """Create adaptation for engagement triggers"""
        
        if trigger == AdaptationTrigger.ENGAGEMENT_DROP:
            return AdaptationDecision(
                trigger=trigger,
                adjust_modality="more_interactive",
                suggest_break=True,
                reasoning="Low engagement detected. Suggesting break and more interactive content.",
                recommended_actions=[
                    "Take a 5-10 minute break",
                    "Try interactive practice problems",
                    "Switch to a different learning modality",
                    "Review progress to regain motivation"
                ]
            )
        
        else:  # FRUSTRATION_DETECTED
            return AdaptationDecision(
                trigger=trigger,
                adjust_difficulty="decrease",
                adjust_scaffolding="increase",
                provide_remediation=True,
                suggest_break=True,
                reasoning="Signs of frustration detected. Providing easier material and support.",
                recommended_actions=[
                    "Take a short break",
                    "Review easier concepts first",
                    "Use guided practice with hints",
                    "Focus on building confidence"
                ]
            )
    
    def _adapt_to_mastery(self,
                         student_profile: StudentProfile,
                         concept_id: str) -> AdaptationDecision:
        """Create adaptation for mastery achievement"""
        
        return AdaptationDecision(
            trigger=AdaptationTrigger.MASTERY_ACHIEVED,
            adjust_difficulty="maintain",
            provide_enrichment=True,
            reasoning=f"Mastery achieved! Ready for next concept or advanced applications.",
            recommended_actions=[
                "Celebrate this achievement",
                "Move to next concept in learning path",
                "Try advanced applications",
                "Help teach others to reinforce mastery"
            ]
        )
    
    def get_adaptation_history(self,
                              student_id: str,
                              limit: int = 10) -> List[AdaptationDecision]:
        """Get recent adaptation decisions for a student"""
        
        # Filter would go here in production
        return self.adaptation_history[-limit:]
    
    def export_history(self, filepath: str):
        """Export adaptation history"""
        import json
        
        data = [decision.to_dict() for decision in self.adaptation_history]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
