"""
database/repository.py

The DB schema (models.py) and engine (database.py) existed, but nothing
in the codebase ever read or wrote through them — api/store.py kept
everything in plain Python dicts that reset on every restart. This
module is the missing translation layer between the domain dataclasses
used everywhere else (StudentProfile, KnowledgeState, ConceptMastery,
InteractionLog) and the ORM rows that actually persist to disk.

Usage pattern (see api/store.py):
    with db.get_session() as session:
        save_student(session, profile)
        save_knowledge_state(session, knowledge)
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from .models import (
    Student, ConceptMasteryDB, InteractionLogDB,
    LearningStyleEnum, PacePreferenceEnum, MasteryLevelEnum,
)
from student_model.student_profile import (
    StudentProfile, CognitiveProfile, LearningStyle, PacePreference,
)
from student_model.knowledge_state import KnowledgeState, ConceptMastery, MasteryLevel
from student_model.interaction_log import InteractionLog


# ── Students ────────────────────────────────────────────────────

def save_student(session: Session, profile: StudentProfile) -> None:
    """Insert or update a student row from a StudentProfile."""
    row = session.get(Student, profile.student_id)
    if row is None:
        row = Student(id=profile.student_id)
        session.add(row)

    row.name = profile.name
    row.email = profile.email
    row.grade_level = profile.grade_level
    row.institution = profile.institution
    row.department = profile.department
    row.class_name = profile.class_name
    row.exam_marks = profile.exam_marks
    row.attendance_percentage = getattr(profile, 'attendance_percentage', None)
    row.classification = profile.classification or "Unclassified"
    row.cognitive_profile = profile.cognitive_profile.to_dict()
    row.primary_learning_style = LearningStyleEnum(profile.primary_learning_style.value)
    row.secondary_learning_style = (
        LearningStyleEnum(profile.secondary_learning_style.value)
        if profile.secondary_learning_style else None
    )
    row.pace_preference = PacePreferenceEnum(profile.pace_preference.value)
    row.prefers_examples = profile.prefers_examples
    row.prefers_step_by_step = profile.prefers_step_by_step
    row.prefers_practice = profile.prefers_practice
    row.total_sessions = profile.total_sessions
    row.total_time_minutes = int(profile.total_time_minutes)
    row.average_session_length = profile.average_session_length
    row.last_active = profile.last_active
    row.overall_mastery = profile.overall_mastery
    row.concepts_mastered = profile.concepts_mastered
    row.concepts_in_progress = profile.concepts_in_progress
    row.updated_at = datetime.utcnow()


def _profile_from_row(row: Student) -> StudentProfile:
    return StudentProfile(
        student_id=row.id,
        name=row.name,
        email=row.email,
        grade_level=row.grade_level,
        institution=row.institution,
        department=row.department,
        class_name=row.class_name,
        exam_marks=row.exam_marks,
        attendance_percentage=getattr(row, 'attendance_percentage', None),
        classification=row.classification or "Unclassified",
        cognitive_profile=CognitiveProfile.from_dict(row.cognitive_profile or {}),
        primary_learning_style=(
            LearningStyle(row.primary_learning_style.value)
            if row.primary_learning_style else LearningStyle.VISUAL
        ),
        secondary_learning_style=(
            LearningStyle(row.secondary_learning_style.value)
            if row.secondary_learning_style else None
        ),
        pace_preference=(
            PacePreference(row.pace_preference.value)
            if row.pace_preference else PacePreference.MODERATE
        ),
        total_sessions=row.total_sessions or 0,
        total_time_minutes=row.total_time_minutes or 0,
        average_session_length=row.average_session_length or 0.0,
        last_active=row.last_active,
        overall_mastery=row.overall_mastery or 0.0,
        concepts_mastered=row.concepts_mastered or 0,
        concepts_in_progress=row.concepts_in_progress or 0,
        prefers_examples=row.prefers_examples if row.prefers_examples is not None else True,
        prefers_step_by_step=row.prefers_step_by_step if row.prefers_step_by_step is not None else True,
        prefers_practice=row.prefers_practice if row.prefers_practice is not None else True,
        created_at=row.created_at or datetime.utcnow(),
        updated_at=row.updated_at or datetime.utcnow(),
    )


def load_student(session: Session, student_id: str) -> Optional[StudentProfile]:
    row = session.get(Student, student_id)
    return _profile_from_row(row) if row else None


def load_all_students(session: Session) -> List[StudentProfile]:
    return [_profile_from_row(r) for r in session.query(Student).all()]


def delete_student(session: Session, student_id: str) -> None:
    row = session.get(Student, student_id)
    if row:
        session.delete(row)  # cascades to concept_mastery / interactions / test_sessions


# ── Knowledge state (per-concept mastery) ──────────────────────

def save_knowledge_state(session: Session, knowledge: KnowledgeState) -> None:
    """Upserts every ConceptMastery in this KnowledgeState."""
    for cm in knowledge.concepts.values():
        row = (
            session.query(ConceptMasteryDB)
            .filter_by(student_id=knowledge.student_id, concept_id=cm.concept_id)
            .one_or_none()
        )
        if row is None:
            row = ConceptMasteryDB(student_id=knowledge.student_id, concept_id=cm.concept_id)
            session.add(row)

        row.concept_name = cm.concept_name
        row.subject = cm.subject
        row.unit = cm.unit
        row.mastery_level = MasteryLevelEnum(cm.mastery_level.value)
        row.mastery_probability = cm.mastery_probability
        row.attempts = cm.attempts
        row.correct_attempts = cm.correct_attempts
        row.recent_success_rate = cm.recent_success_rate
        row.p_learn = cm.p_learn
        row.p_slip = cm.p_slip
        row.p_guess = cm.p_guess
        row.first_seen = cm.first_seen
        row.last_practiced = cm.last_practiced
        row.time_to_mastery_minutes = cm.time_to_mastery_minutes
        row.repetition_number = cm.repetition_number
        row.easiness_factor = cm.easiness_factor
        row.next_review_date = cm.next_review_date


def load_knowledge_state(session: Session, student_id: str) -> KnowledgeState:
    state = KnowledgeState(student_id=student_id)
    rows = session.query(ConceptMasteryDB).filter_by(student_id=student_id).all()
    for row in rows:
        cm = ConceptMastery(
            concept_id=row.concept_id,
            concept_name=row.concept_name,
            subject=row.subject,
            unit=row.unit,
            mastery_level=MasteryLevel(row.mastery_level.value if row.mastery_level else 0),
            mastery_probability=row.mastery_probability or 0.0,
            attempts=row.attempts or 0,
            correct_attempts=row.correct_attempts or 0,
            recent_success_rate=row.recent_success_rate or 0.0,
            p_learn=row.p_learn if row.p_learn is not None else 0.3,
            p_slip=row.p_slip if row.p_slip is not None else 0.1,
            p_guess=row.p_guess if row.p_guess is not None else 0.2,
            first_seen=row.first_seen or datetime.utcnow(),
            last_practiced=row.last_practiced or datetime.utcnow(),
            time_to_mastery_minutes=row.time_to_mastery_minutes,
            repetition_number=row.repetition_number or 0,
            easiness_factor=row.easiness_factor or 2.5,
            next_review_date=row.next_review_date,
        )
        state.add_concept(cm)
    return state


# ── Interaction logs (analytics trail) ─────────────────────────

def log_interaction(session: Session, interaction: InteractionLog) -> None:
    row = InteractionLogDB(
        student_id=interaction.student_id,
        interaction_type=interaction.interaction_type.value,
        timestamp=interaction.timestamp,
        concept_id=interaction.concept_id,
        concept_name=interaction.concept_name,
        subject=interaction.subject,
        unit=interaction.unit,
        student_input=interaction.student_input,
        system_response=interaction.system_response,
        difficulty=interaction.difficulty,
        was_correct=interaction.was_correct,
        confidence_score=interaction.confidence_score,
        response_time_seconds=interaction.response_time_seconds,
        num_hints_used=interaction.num_hints_used,
        retrieval_metadata={
            "retrieved_chunks": interaction.retrieved_chunks,
            "retrieval_scores": interaction.retrieval_scores,
        } if (interaction.retrieved_chunks or interaction.retrieval_scores) else None,
        session_id=interaction.session_id,
    )
    session.add(row)


def load_recent_interactions(session: Session, student_id: str, limit: int = 50) -> List[InteractionLogDB]:
    return (
        session.query(InteractionLogDB)
        .filter_by(student_id=student_id)
        .order_by(InteractionLogDB.timestamp.desc())
        .limit(limit)
        .all()
    )
