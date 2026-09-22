"""
Student Profile Management
Captures student demographics, cognitive traits, and learning preferences.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import json


def classify_marks(marks: Optional[float]) -> str:
    """Classify a student using university exam marks."""
    if marks is None:
        return "Unclassified"
    if marks >= 85:
        return "Excellent"
    if marks >= 70:
        return "Good"
    if marks >= 50:
        return "Average"
    if marks >= 35:
        return "Needs Support"
    return "At Risk"


class LearningStyle(Enum):
    """VARK learning style preferences"""
    VISUAL = "visual"           # Charts, diagrams, spatial understanding
    AUDITORY = "auditory"       # Lectures, discussions, verbal explanations
    READING_WRITING = "reading_writing"  # Text-based, notes, written material
    KINESTHETIC = "kinesthetic" # Hands-on, practice, interactive


class PacePreference(Enum):
    """Learning pace preferences"""
    SLOW = "slow"         # More time, more examples
    MODERATE = "moderate" # Standard pace
    FAST = "fast"         # Quick progression, minimal repetition


@dataclass
class CognitiveProfile:
    """
    Models the student's cognitive characteristics.
    Based on educational psychology research (Bloom's taxonomy, cognitive load theory).
    """
    # Working memory capacity (normalized 0-1, affects chunk size)
    working_memory: float = 0.5
    
    # Processing speed (normalized 0-1, affects pace)
    processing_speed: float = 0.5
    
    # Abstract reasoning ability (0-1, affects when to introduce abstraction)
    abstract_reasoning: float = 0.5
    
    # Metacognitive awareness (0-1, self-regulated learning ability)
    metacognition: float = 0.5
    
    # Growth mindset score (0-1, resilience to difficulty)
    growth_mindset: float = 0.7
    
    def adjust_for_performance(self, success_rate: float, difficulty: str):
        """
        Update cognitive estimates based on observed performance.
        Conservative Bayesian-like update.
        """
        learning_rate = 0.1  # How quickly we update beliefs
        
        if difficulty == "hard" and success_rate > 0.7:
            self.abstract_reasoning += learning_rate * (1.0 - self.abstract_reasoning)
        elif difficulty == "easy" and success_rate < 0.5:
            self.abstract_reasoning -= learning_rate * self.abstract_reasoning
            self.working_memory = max(0.2, self.working_memory - 0.05)
    
    def to_dict(self) -> Dict:
        return {
            'working_memory': self.working_memory,
            'processing_speed': self.processing_speed,
            'abstract_reasoning': self.abstract_reasoning,
            'metacognition': self.metacognition,
            'growth_mindset': self.growth_mindset
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CognitiveProfile':
        return cls(**data)


@dataclass
class StudentProfile:
    """
    Complete student profile for personalized instruction.
    Persisted to database and updated throughout learning journey.
    """
    student_id: str
    name: str
    email: str
    
    # Demographics
    grade_level: Optional[str] = None
    institution: Optional[str] = None
    department: Optional[str] = None
    class_name: Optional[str] = None
    exam_marks: Optional[float] = None
    attendance_percentage: Optional[float] = None
    classification: str = "Unclassified"
    
    # Cognitive characteristics
    cognitive_profile: CognitiveProfile = field(default_factory=CognitiveProfile)
    
    # Learning preferences
    primary_learning_style: LearningStyle = LearningStyle.VISUAL
    secondary_learning_style: Optional[LearningStyle] = None
    pace_preference: PacePreference = PacePreference.MODERATE
    
    # Engagement metrics
    total_sessions: int = 0
    total_time_minutes: int = 0
    average_session_length: float = 0.0
    last_active: Optional[datetime] = None
    
    # Performance summary
    overall_mastery: float = 0.0  # Average across all concepts (0-1)
    concepts_mastered: int = 0
    concepts_in_progress: int = 0
    
    # Preferences
    prefers_examples: bool = True
    prefers_step_by_step: bool = True
    prefers_practice: bool = True
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.exam_marks is not None:
            self.classification = classify_marks(self.exam_marks)
        elif not self.classification or self.classification == "Unclassified":
            self.classification = "Unclassified"
        self.updated_at = datetime.utcnow()
    
    def update_engagement(self, session_duration_minutes: float):
        """Update engagement metrics after a session"""
        self.total_sessions += 1
        self.total_time_minutes += session_duration_minutes
        self.average_session_length = self.total_time_minutes / self.total_sessions
        self.last_active = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def get_recommended_chunk_size(self) -> int:
        """
        Recommend chunk size based on working memory.
        Higher working memory → larger chunks.
        """
        base_size = 300
        wm = self.cognitive_profile.working_memory
        return int(base_size * (0.5 + wm))  # 150-450 words
    
    def get_explanation_depth(self) -> str:
        """
        Determine explanation verbosity based on learning style and cognition.
        """
        if self.prefers_step_by_step or self.cognitive_profile.abstract_reasoning < 0.4:
            return "detailed"
        elif self.cognitive_profile.abstract_reasoning > 0.7:
            return "concise"
        return "moderate"
    
    def should_use_scaffolding(self) -> bool:
        """Determine if student needs extra scaffolding"""
        return (self.cognitive_profile.working_memory < 0.4 or 
                self.cognitive_profile.metacognition < 0.4)
    
    def to_dict(self) -> Dict:
        """Serialize for storage"""
        self.classification = classify_marks(self.exam_marks)
        return {
            'student_id': self.student_id,
            'name': self.name,
            'email': self.email,
            'grade_level': self.grade_level,
            'institution': self.institution,
            'department': self.department,
            'class_name': self.class_name,
            'exam_marks': self.exam_marks,
            'attendance_percentage': self.attendance_percentage,
            'classification': self.classification,
            'cognitive_profile': self.cognitive_profile.to_dict(),
            'primary_learning_style': self.primary_learning_style.value,
            'secondary_learning_style': self.secondary_learning_style.value if self.secondary_learning_style else None,
            'pace_preference': self.pace_preference.value,
            'total_sessions': self.total_sessions,
            'total_time_minutes': self.total_time_minutes,
            'average_session_length': self.average_session_length,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'overall_mastery': self.overall_mastery,
            'concepts_mastered': self.concepts_mastered,
            'concepts_in_progress': self.concepts_in_progress,
            'prefers_examples': self.prefers_examples,
            'prefers_step_by_step': self.prefers_step_by_step,
            'prefers_practice': self.prefers_practice,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StudentProfile':
        """Deserialize from storage"""
        data = data.copy()
        
        # Convert cognitive profile
        if 'cognitive_profile' in data:
            data['cognitive_profile'] = CognitiveProfile.from_dict(data['cognitive_profile'])
        
        # Convert enums
        if 'primary_learning_style' in data:
            data['primary_learning_style'] = LearningStyle(data['primary_learning_style'])
        if 'secondary_learning_style' in data and data['secondary_learning_style']:
            data['secondary_learning_style'] = LearningStyle(data['secondary_learning_style'])
        if 'pace_preference' in data:
            data['pace_preference'] = PacePreference(data['pace_preference'])

        if 'attendance_percentage' not in data:
            data['attendance_percentage'] = None
        if 'classification' not in data:
            data['classification'] = classify_marks(data.get('exam_marks'))
        elif not data['classification']:
            data['classification'] = classify_marks(data.get('exam_marks'))
        
        # Convert datetimes
        if 'last_active' in data and data['last_active']:
            data['last_active'] = datetime.fromisoformat(data['last_active'])
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        return cls(**data)


def create_initial_profile(student_id: str, name: str, email: str,
                          learning_style_survey: Optional[Dict] = None,
                          department: Optional[str] = None,
                          class_name: Optional[str] = None,
                          exam_marks: Optional[float] = None,
                          institution: Optional[str] = None) -> StudentProfile:
    """
    Create a new student profile with optional learning style survey results.
    
    learning_style_survey format:
    {
        'visual_score': 0-10,
        'auditory_score': 0-10,
        'reading_writing_score': 0-10,
        'kinesthetic_score': 0-10,
        'pace_preference': 'slow'|'moderate'|'fast'
    }
    """
    profile = StudentProfile(
        student_id=student_id,
        name=name,
        email=email,
        department=department,
        class_name=class_name,
        institution=institution,
        exam_marks=exam_marks,
    )
    profile.classification = classify_marks(exam_marks)
    
    if learning_style_survey:
        # Determine primary and secondary learning styles
        scores = {
            LearningStyle.VISUAL: learning_style_survey.get('visual_score', 5),
            LearningStyle.AUDITORY: learning_style_survey.get('auditory_score', 5),
            LearningStyle.READING_WRITING: learning_style_survey.get('reading_writing_score', 5),
            LearningStyle.KINESTHETIC: learning_style_survey.get('kinesthetic_score', 5)
        }
        
        sorted_styles = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        profile.primary_learning_style = sorted_styles[0][0]
        
        if sorted_styles[1][1] >= 7:  # Secondary style if score is high
            profile.secondary_learning_style = sorted_styles[1][0]
        
        # Set pace preference
        pace = learning_style_survey.get('pace_preference', 'moderate')
        profile.pace_preference = PacePreference(pace)
    
    return profile
