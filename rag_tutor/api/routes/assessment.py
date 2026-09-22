"""Assessment Routes — real adaptive test with IRT."""
import sys, uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from api.store import STUDENTS, KNOWLEDGE, GRAPH, IRT, LLM_CLIENT
from assessment.question_generator import QuestionGenerator
from assessment.grader import AutoGrader
from assessment.adaptive_test import AdaptiveTest

router = APIRouter()
qgen   = QuestionGenerator(llm_client=LLM_CLIENT)
grader = AutoGrader(llm_client=LLM_CLIENT)
engine = AdaptiveTest(qgen, grader, GRAPH)

# Active test sessions: session_id → TestSession
SESSIONS = {}


@router.post("/start")
async def start_test(student_id: str, subject: str = "Data Structures"):
    profile = STUDENTS.get(student_id)
    if not profile:
        raise HTTPException(404, "Student not found")
    knowledge = KNOWLEDGE.setdefault(student_id, __import__(
        'student_model.knowledge_state', fromlist=['KnowledgeState']
    ).KnowledgeState(student_id=student_id))

    session = engine.start_diagnostic_test(profile, subject=subject, max_questions=10)
    SESSIONS[session.session_id] = session

    first_q = engine.get_next_question(session, profile)
    return {
        "session_id": session.session_id,
        "question": _fmt_question(first_q) if first_q else None
    }


@router.post("/answer")
async def submit_answer(session_id: str, answer: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    profile = STUDENTS.get(session.student_id)
    knowledge = KNOWLEDGE.get(session.student_id)

    # Find the last unanswered question
    if not session.questions_asked or len(session.responses) >= len(session.questions_asked):
        raise HTTPException(400, "No pending question")

    current_q = session.questions_asked[len(session.responses)]
    result = engine.submit_answer(session, current_q, answer)

    # Next question
    next_q = engine.get_next_question(session, profile)

    if next_q is None or len(session.questions_asked) >= 8:
        # End test
        from student_model.knowledge_state import KnowledgeState
        ks = knowledge or KnowledgeState(student_id=session.student_id)
        final = engine.end_test(session, ks)
        SESSIONS.pop(session_id, None)
        return {
            "status": "completed",
            "grading": result.to_dict(),
            "final_result": final.to_dict()
        }

    return {
        "status": "continue",
        "grading": result.to_dict(),
        "next_question": _fmt_question(next_q),
        "ability_estimate": round(session.current_ability_estimate, 3),
        "questions_done": len(session.responses)
    }


@router.get("/question/{concept_id}")
async def get_practice_question(concept_id: str, bloom_level: int = 2):
    concept = GRAPH.get_concept(concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")
    q = qgen.generate_for_concept(concept, bloom_level=bloom_level)
    return _fmt_question(q)


def _fmt_question(q) -> dict:
    if q is None:
        return None
    return {
        "question_id": q.question_id,
        "type": q.question_type.value,
        "prompt": q.prompt,
        "options": q.options,
        "difficulty": q.difficulty,
        "bloom_level": q.bloom_level,
        "concept_name": q.concept_name,
        "concept_id": q.concept_id,
        "hints": q.hints,
        "points": q.points,
        "estimated_minutes": q.estimated_time_minutes
    }
