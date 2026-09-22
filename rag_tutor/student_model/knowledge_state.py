"""
Knowledge State Tracking
Maintains fine-grained mastery levels for every concept the student encounters.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Dict, List, Optional
import math


class MasteryLevel(IntEnum):
    """Granular mastery levels for concepts"""
    NOT_STARTED = 0      # Never encountered
    INTRODUCED = 1       # Seen but not practiced
    DEVELOPING = 2       # Practicing, <50% success
    APPROACHING = 3      # 50-70% success
    PROFICIENT = 4       # 70-85% success
    MASTERED = 5         # 85%+ success, can teach others


@dataclass
class ConceptMastery:
    """
    Tracks mastery for a single concept/topic.
    Uses Bayesian Knowledge Tracing principles.
    """
    concept_id: str
    concept_name: str
    subject: str
    unit: str
    
    # Current state
    mastery_level: MasteryLevel = MasteryLevel.NOT_STARTED
    mastery_probability: float = 0.0  # P(mastered) from BKT, 0-1
    
    # Performance tracking
    attempts: int = 0
    correct_attempts: int = 0
    recent_success_rate: float = 0.0  # Last 5 attempts
    
    # Bayesian Knowledge Tracing parameters
    p_learn: float = 0.3    # Probability of learning on each opportunity
    p_slip: float = 0.1     # Probability of making a mistake despite knowing
    p_guess: float = 0.2    # Probability of guessing correctly without knowing
    
    # Temporal
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_practiced: datetime = field(default_factory=datetime.utcnow)
    time_to_mastery_minutes: Optional[int] = None
    
    # Spaced repetition (SM-2 algorithm parameters)
    repetition_number: int = 0
    easiness_factor: float = 2.5  # 1.3 to 2.5+
    next_review_date: Optional[datetime] = None
    
    def update_after_attempt(self, was_correct: bool, difficulty: str = "medium"):
        """
        Update mastery using Bayesian Knowledge Tracing.
        Called after each practice question or assessment.
        """
        self.attempts += 1
        if was_correct:
            self.correct_attempts += 1
        
        self.last_practiced = datetime.utcnow()
        
        # Bayesian update
        p_known_prior = self.mastery_probability
        
        if was_correct:
            # P(known | correct) using Bayes' theorem
            p_correct_if_known = 1 - self.p_slip
            p_correct_if_unknown = self.p_guess
            
            numerator = p_known_prior * p_correct_if_known
            denominator = (p_known_prior * p_correct_if_known + 
                          (1 - p_known_prior) * p_correct_if_unknown)
            
            if denominator > 0:
                p_known_posterior = numerator / denominator
            else:
                p_known_posterior = p_known_prior
        else:
            # P(known | incorrect)
            p_incorrect_if_known = self.p_slip
            p_incorrect_if_unknown = 1 - self.p_guess
            
            numerator = p_known_prior * p_incorrect_if_known
            denominator = (p_known_prior * p_incorrect_if_known + 
                          (1 - p_known_prior) * p_incorrect_if_unknown)
            
            if denominator > 0:
                p_known_posterior = numerator / denominator
            else:
                p_known_posterior = p_known_prior
        
        # Add learning opportunity
        self.mastery_probability = min(1.0, p_known_posterior + 
                                      (1 - p_known_posterior) * self.p_learn)
        
        # Update recent success rate (last 5 attempts)
        if self.attempts >= 5:
            # Approximate from total stats
            self.recent_success_rate = self.correct_attempts / self.attempts
        else:
            self.recent_success_rate = self.correct_attempts / self.attempts if self.attempts > 0 else 0
        
        # Update mastery level
        self._update_mastery_level()
        
        # Update spaced repetition parameters
        self._update_spaced_repetition(was_correct, difficulty)
    
    def _update_mastery_level(self):
        """Discretize mastery probability into level"""
        p = self.mastery_probability
        
        if p >= 0.85:
            new_level = MasteryLevel.MASTERED
        elif p >= 0.70:
            new_level = MasteryLevel.PROFICIENT
        elif p >= 0.50:
            new_level = MasteryLevel.APPROACHING
        elif p >= 0.25:
            new_level = MasteryLevel.DEVELOPING
        elif self.attempts > 0:
            new_level = MasteryLevel.INTRODUCED
        else:
            new_level = MasteryLevel.NOT_STARTED
        
        # Track time to mastery
        if self.mastery_level != MasteryLevel.MASTERED and new_level == MasteryLevel.MASTERED:
            delta = datetime.utcnow() - self.first_seen
            self.time_to_mastery_minutes = int(delta.total_seconds() / 60)
        
        self.mastery_level = new_level
    
    def _update_spaced_repetition(self, was_correct: bool, difficulty: str):
        """
        Update spaced repetition schedule using SM-2 algorithm.
        Determines when student should review this concept next.
        """
        difficulty_map = {"easy": 5, "medium": 3, "hard": 1}
        quality = difficulty_map.get(difficulty, 3) if was_correct else 0
        
        if quality >= 3:  # Correct answer
            if self.repetition_number == 0:
                interval_days = 1
            elif self.repetition_number == 1:
                interval_days = 6
            else:
                interval_days = int(self.repetition_number * self.easiness_factor)
            
            self.repetition_number += 1
        else:  # Incorrect answer
            self.repetition_number = 0
            interval_days = 1
        
        # Update easiness factor
        self.easiness_factor = max(1.3, self.easiness_factor + 
                                   (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        
        # Set next review date
        from datetime import timedelta
        self.next_review_date = datetime.utcnow() + timedelta(days=interval_days)
    
    def needs_review(self) -> bool:
        """Check if concept is due for review (spaced repetition)"""
        if self.next_review_date is None:
            return False
        return datetime.utcnow() >= self.next_review_date
    
    def get_retrieval_strength(self) -> float:
        """
        Calculate current retrieval strength (memory retention).
        Decays over time since last practice.
        """
        if self.attempts == 0:
            return 0.0
        
        # Time decay
        hours_since_practice = (datetime.utcnow() - self.last_practiced).total_seconds() / 3600
        decay_rate = 0.05  # Decay per day
        days_since = hours_since_practice / 24
        
        decay_factor = math.exp(-decay_rate * days_since)
        
        return self.mastery_probability * decay_factor
    
    def to_dict(self) -> Dict:
        return {
            'concept_id': self.concept_id,
            'concept_name': self.concept_name,
            'subject': self.subject,
            'unit': self.unit,
            'mastery_level': self.mastery_level.value,
            'mastery_probability': self.mastery_probability,
            'attempts': self.attempts,
            'correct_attempts': self.correct_attempts,
            'recent_success_rate': self.recent_success_rate,
            'p_learn': self.p_learn,
            'p_slip': self.p_slip,
            'p_guess': self.p_guess,
            'first_seen': self.first_seen.isoformat(),
            'last_practiced': self.last_practiced.isoformat(),
            'time_to_mastery_minutes': self.time_to_mastery_minutes,
            'repetition_number': self.repetition_number,
            'easiness_factor': self.easiness_factor,
            'next_review_date': self.next_review_date.isoformat() if self.next_review_date else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConceptMastery':
        data = data.copy()
        data['mastery_level'] = MasteryLevel(data['mastery_level'])
        data['first_seen'] = datetime.fromisoformat(data['first_seen'])
        data['last_practiced'] = datetime.fromisoformat(data['last_practiced'])
        if data['next_review_date']:
            data['next_review_date'] = datetime.fromisoformat(data['next_review_date'])
        return cls(**data)


@dataclass
class KnowledgeState:
    """
    Complete knowledge state for a student across all concepts.
    Provides aggregate views and gap identification.
    """
    student_id: str
    concepts: Dict[str, ConceptMastery] = field(default_factory=dict)
    
    def add_concept(self, concept: ConceptMastery):
        """Add or update a concept"""
        self.concepts[concept.concept_id] = concept
    
    def get_concept(self, concept_id: str) -> Optional[ConceptMastery]:
        """Retrieve concept mastery"""
        return self.concepts.get(concept_id)
    
    def update_concept(self, concept_id: str, was_correct: bool, difficulty: str = "medium"):
        """Update a concept after practice"""
        if concept_id in self.concepts:
            self.concepts[concept_id].update_after_attempt(was_correct, difficulty)
    
    def get_mastered_concepts(self) -> List[ConceptMastery]:
        """Get all mastered concepts"""
        return [c for c in self.concepts.values() 
                if c.mastery_level == MasteryLevel.MASTERED]
    
    def get_weak_concepts(self, threshold: float = 0.5) -> List[ConceptMastery]:
        """Get concepts below mastery threshold"""
        return [c for c in self.concepts.values() 
                if c.mastery_probability < threshold and c.attempts > 0]
    
    def get_concepts_for_review(self) -> List[ConceptMastery]:
        """Get concepts due for spaced repetition review"""
        return [c for c in self.concepts.values() if c.needs_review()]
    
    def get_overall_mastery(self) -> float:
        """Calculate overall mastery across all concepts"""
        if not self.concepts:
            return 0.0
        return sum(c.mastery_probability for c in self.concepts.values()) / len(self.concepts)
    
    def get_subject_mastery(self, subject: str) -> float:
        """Calculate mastery for a specific subject"""
        subject_concepts = [c for c in self.concepts.values() if c.subject == subject]
        if not subject_concepts:
            return 0.0
        return sum(c.mastery_probability for c in subject_concepts) / len(subject_concepts)
    
    def get_unit_mastery(self, subject: str, unit: str) -> float:
        """Calculate mastery for a specific unit"""
        unit_concepts = [c for c in self.concepts.values() 
                        if c.subject == subject and c.unit == unit]
        if not unit_concepts:
            return 0.0
        return sum(c.mastery_probability for c in unit_concepts) / len(unit_concepts)
    
    def to_dict(self) -> Dict:
        return {
            'student_id': self.student_id,
            'concepts': {k: v.to_dict() for k, v in self.concepts.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'KnowledgeState':
        state = cls(student_id=data['student_id'])
        for concept_data in data['concepts'].values():
            concept = ConceptMastery.from_dict(concept_data)
            state.add_concept(concept)
        return state
