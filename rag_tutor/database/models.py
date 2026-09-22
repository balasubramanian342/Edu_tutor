"""
Database Models
SQLAlchemy ORM models for persistence.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class LearningStyleEnum(enum.Enum):
    VISUAL = "visual"
    AUDITORY = "auditory"
    READING_WRITING = "reading_writing"
    KINESTHETIC = "kinesthetic"


class PacePreferenceEnum(enum.Enum):
    SLOW = "slow"
    MODERATE = "moderate"
    FAST = "fast"


class MasteryLevelEnum(enum.Enum):
    NOT_STARTED = 0
    INTRODUCED = 1
    DEVELOPING = 2
    APPROACHING = 3
    PROFICIENT = 4
    MASTERED = 5


# Student Models
class Student(Base):
    __tablename__ = 'students'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    grade_level = Column(String(50))
    institution = Column(String(200))
    department = Column(String(100), index=True)
    class_name = Column(String(100), index=True)
    exam_marks = Column(Float, default=0.0)
    attendance_percentage = Column(Float, nullable=True)
    classification = Column(String(50), default='Unclassified')
    
    # Cognitive profile (JSON)
    cognitive_profile = Column(JSON)
    
    # Learning preferences
    primary_learning_style = Column(SQLEnum(LearningStyleEnum))
    secondary_learning_style = Column(SQLEnum(LearningStyleEnum), nullable=True)
    pace_preference = Column(SQLEnum(PacePreferenceEnum))
    
    # Preferences
    prefers_examples = Column(Boolean, default=True)
    prefers_step_by_step = Column(Boolean, default=True)
    prefers_practice = Column(Boolean, default=True)
    
    # Engagement metrics
    total_sessions = Column(Integer, default=0)
    total_time_minutes = Column(Integer, default=0)
    average_session_length = Column(Float, default=0.0)
    last_active = Column(DateTime, nullable=True)
    
    # Performance summary
    overall_mastery = Column(Float, default=0.0)
    concepts_mastered = Column(Integer, default=0)
    concepts_in_progress = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    concept_masteries = relationship("ConceptMasteryDB", back_populates="student", cascade="all, delete-orphan")
    interactions = relationship("InteractionLogDB", back_populates="student", cascade="all, delete-orphan")
    test_sessions = relationship("TestSessionDB", back_populates="student", cascade="all, delete-orphan")


class ConceptMasteryDB(Base):
    __tablename__ = 'concept_mastery'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(String(50), ForeignKey('students.id'), nullable=False)
    concept_id = Column(String(100), nullable=False)
    concept_name = Column(String(200))
    subject = Column(String(100))
    unit = Column(String(100))
    
    # Mastery tracking
    mastery_level = Column(SQLEnum(MasteryLevelEnum), default=MasteryLevelEnum.NOT_STARTED)
    mastery_probability = Column(Float, default=0.0)
    
    # Performance
    attempts = Column(Integer, default=0)
    correct_attempts = Column(Integer, default=0)
    recent_success_rate = Column(Float, default=0.0)
    
    # BKT parameters
    p_learn = Column(Float, default=0.3)
    p_slip = Column(Float, default=0.1)
    p_guess = Column(Float, default=0.2)
    
    # Temporal
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_practiced = Column(DateTime, default=datetime.utcnow)
    time_to_mastery_minutes = Column(Integer, nullable=True)
    
    # Spaced repetition
    repetition_number = Column(Integer, default=0)
    easiness_factor = Column(Float, default=2.5)
    next_review_date = Column(DateTime, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="concept_masteries")


class InteractionLogDB(Base):
    __tablename__ = 'interaction_logs'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(String(50), ForeignKey('students.id'), nullable=False)
    interaction_type = Column(String(50))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Context
    concept_id = Column(String(100), nullable=True)
    concept_name = Column(String(200), nullable=True)
    subject = Column(String(100), nullable=True)
    unit = Column(String(100), nullable=True)
    
    # Content
    student_input = Column(Text, nullable=True)
    system_response = Column(Text, nullable=True)
    
    # Metadata
    difficulty = Column(String(20), nullable=True)
    was_correct = Column(Boolean, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # Performance
    response_time_seconds = Column(Float, nullable=True)
    num_hints_used = Column(Integer, default=0)
    
    # RAG metadata (JSON)
    retrieval_metadata = Column(JSON, nullable=True)
    
    # Session
    session_id = Column(String(100), nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="interactions")


class TestSessionDB(Base):
    __tablename__ = 'test_sessions'
    
    id = Column(String(100), primary_key=True)
    student_id = Column(String(50), ForeignKey('students.id'), nullable=False)
    test_type = Column(String(50))
    
    # Adaptive tracking
    current_ability_estimate = Column(Float, default=0.5)
    confidence_in_estimate = Column(Float, default=0.0)
    
    # Results (JSON)
    concepts_tested = Column(JSON)
    questions_data = Column(JSON)
    responses_data = Column(JSON)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="test_sessions")


# Knowledge Graph Models
class ConceptDB(Base):
    __tablename__ = 'concepts'
    
    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    subject = Column(String(100))
    unit = Column(String(100))
    
    # Taxonomy
    bloom_level = Column(Integer, default=2)
    difficulty = Column(String(20), default="medium")
    
    # Content
    description = Column(Text)
    keywords = Column(JSON)
    
    # Learning metadata
    typical_time_minutes = Column(Integer, default=30)
    practice_questions_available = Column(Integer, default=0)


class ConceptRelationshipDB(Base):
    __tablename__ = 'concept_relationships'
    
    id = Column(Integer, primary_key=True)
    source_concept_id = Column(String(100), nullable=False)
    target_concept_id = Column(String(100), nullable=False)
    relation_type = Column(String(50))  # prerequisite, related_to, etc.
    strength = Column(Float, default=1.0)


# Question Bank
class QuestionDB(Base):
    __tablename__ = 'questions'
    
    id = Column(String(100), primary_key=True)
    concept_id = Column(String(100), nullable=False)
    question_type = Column(String(50))
    
    # Content
    prompt = Column(Text, nullable=False)
    difficulty = Column(String(20))
    bloom_level = Column(Integer)
    
    # Answers (JSON)
    correct_answer = Column(JSON, nullable=True)
    options = Column(JSON, nullable=True)
    rubric = Column(JSON, nullable=True)
    sample_answer = Column(Text, nullable=True)
    
    # Metadata
    estimated_time_minutes = Column(Integer, default=5)
    points = Column(Integer, default=1)
    hints = Column(JSON)
    tags = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# Mastery Updates History
class MasteryUpdateDB(Base):
    __tablename__ = 'mastery_updates'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(String(50), nullable=False)
    concept_id = Column(String(100), nullable=False)
    
    # Before/after
    previous_mastery = Column(Float)
    previous_level = Column(String(50))
    new_mastery = Column(Float)
    new_level = Column(String(50))
    
    # Event
    trigger_event = Column(String(50))
    was_correct = Column(Boolean)
    difficulty = Column(String(20))
    
    timestamp = Column(DateTime, default=datetime.utcnow)
