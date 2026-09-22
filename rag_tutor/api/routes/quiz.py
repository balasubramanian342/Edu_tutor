"""
api/routes/quiz.py

A straightforward, fixed-length quiz on one concept — distinct from the
adaptive diagnostic test in assessment.py (which runs an IRT-driven
placement test across a whole subject). This is the "take a quiz on
Recursion" flow: pick a concept, answer N questions of increasing
Bloom level, get real-time feedback and a mastery update after every
question (not just at the end), then a final score summary.

Each answer immediately updates BKT mastery via
MasteryTracker.update_from_assessment(...) and is persisted to the
database, so a quiz genuinely moves the needle on the student's
knowledge state — not just a disconnected scorecard.
"""
import sys
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.store import STUDENTS, KNOWLEDGE, GRAPH, TRACKER, LLM_CLIENT, persist_student, persist_interaction
from student_model.knowledge_state import KnowledgeState
from student_model.interaction_log import InteractionLog, InteractionType
from assessment.question_generator import QuestionGenerator, Question, QuestionType
from assessment.grader import AutoGrader

router = APIRouter()
qgen = QuestionGenerator(llm_client=LLM_CLIENT)
grader = AutoGrader(llm_client=LLM_CLIENT)


@dataclass
class QuizSession:
    quiz_id: str
    student_id: str
    concept_id: str
    questions: List[Question]
    index: int = 0
    correct_count: int = 0
    answers: List[dict] = field(default_factory=list)


QUIZZES = {}  # quiz_id -> QuizSession


class QuizStartRequest(BaseModel):
    student_id: str
    concept_id: str
    num_questions: int = 5


def _fmt_question(q: Question) -> dict:
    return {
        "question_id": q.question_id,
        "type": q.question_type.value,
        "prompt": q.prompt,
        "options": q.options,
        "difficulty": q.difficulty,
        "bloom_level": q.bloom_level,
        "hints": q.hints,
        "points": q.points,
    }


@router.post("/start")
async def start_quiz(req: QuizStartRequest):
    profile = STUDENTS.get(req.student_id)
    if not profile:
        raise HTTPException(404, "Student not found")
    concept = GRAPH.get_concept(req.concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")

    n = max(1, min(req.num_questions, 10))
    # Ramp Bloom level across the quiz: recall -> apply -> analyze, capped at 6
    bloom_levels = [min(concept.bloom_level + i // 2, 6) for i in range(n)]

    if LLM_CLIENT is None:
        # The template-based fallback (question_generator.py's
        # _generate_template_based) only ever fills in a real
        # correct_answer for MULTIPLE_CHOICE and TRUE_FALSE — every other
        # type (SHORT_ANSWER, PROBLEM_SOLVING, CODE_*) is left with
        # correct_answer=None, which the equally-template-based grader
        # can never score (it falls through to "requires manual
        # review" every time). Without an LLM key, force multiple-choice
        # so the quiz is actually completable; with a key, let the
        # natural Bloom-level ramp pick richer question types, since
        # both generation and grading go through the LLM then.
        questions = [
            qgen.generate_for_concept(concept, bloom_level=b, question_type=QuestionType.MULTIPLE_CHOICE)
            for b in bloom_levels
        ]
    else:
        questions = [qgen.generate_for_concept(concept, bloom_level=b) for b in bloom_levels]

    quiz_id = str(uuid.uuid4())
    QUIZZES[quiz_id] = QuizSession(
        quiz_id=quiz_id, student_id=req.student_id, concept_id=req.concept_id, questions=questions
    )

    return {
        "quiz_id": quiz_id,
        "concept_name": concept.name,
        "total_questions": n,
        "question_number": 1,
        "question": _fmt_question(questions[0]),
    }


class QuizAnswerRequest(BaseModel):
    quiz_id: str
    answer: str


@router.post("/answer")
async def answer_quiz_question(req: QuizAnswerRequest):
    quiz = QUIZZES.get(req.quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz session not found or already completed")
    if quiz.index >= len(quiz.questions):
        raise HTTPException(400, "This quiz has no more questions")

    profile = STUDENTS.get(quiz.student_id)
    knowledge = KNOWLEDGE.setdefault(quiz.student_id, KnowledgeState(student_id=quiz.student_id))
    current_q = quiz.questions[quiz.index]

    result = grader.grade(current_q, req.answer)
    update = TRACKER.update_from_assessment(
        knowledge, profile, result, quiz.concept_id, current_q.difficulty
    )

    quiz.answers.append({
        "question_id": current_q.question_id,
        "student_answer": req.answer,
        "is_correct": result.is_correct,
    })
    if result.is_correct:
        quiz.correct_count += 1
    quiz.index += 1

    profile.overall_mastery = knowledge.get_overall_mastery()
    persist_student(quiz.student_id)
    persist_interaction(InteractionLog(
        student_id=quiz.student_id,
        interaction_type=InteractionType.PRACTICE_ATTEMPTED,
        concept_id=quiz.concept_id,
        student_input=req.answer,
        system_response=result.feedback,
        was_correct=result.is_correct,
        difficulty=current_q.difficulty,
    ))

    base_response = {
        "is_correct": result.is_correct,
        "feedback": result.feedback,
        "correct_answer": result.correct_answer if hasattr(result, "correct_answer") else None,
        "mastery_after": round(update.new_mastery, 3),
        "mastery_level": update.new_level,
    }

    if quiz.index >= len(quiz.questions):
        QUIZZES.pop(req.quiz_id, None)
        return {
            **base_response,
            "status": "completed",
            "score": quiz.correct_count,
            "total": len(quiz.questions),
            "percentage": round(100 * quiz.correct_count / len(quiz.questions)),
        }

    return {
        **base_response,
        "status": "continue",
        "question_number": quiz.index + 1,
        "total_questions": len(quiz.questions),
        "question": _fmt_question(quiz.questions[quiz.index]),
    }
