"""Dashboard Routes — real student + teacher analytics."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from api.store import STUDENTS, KNOWLEDGE, GRAPH, ANALYZER, TRACKER, ADAPTATION
from dashboard.student_dashboard import StudentDashboard
from dashboard.teacher_dashboard import TeacherDashboard
from student_model.knowledge_state import KnowledgeState

router = APIRouter()
student_dash = StudentDashboard(GRAPH, ANALYZER, TRACKER)
teacher_dash = TeacherDashboard(GRAPH)


@router.get("/student/{student_id}")
async def get_student_dashboard(student_id: str):
    profile = STUDENTS.get(student_id)
    if not profile:
        raise HTTPException(404, "Student not found")
    knowledge = KNOWLEDGE.get(student_id, KnowledgeState(student_id=student_id))
    report = student_dash.generate_report(profile, knowledge)
    return report.to_dict()


@router.get("/student/{student_id}/concepts")
async def get_student_concepts(student_id: str):
    knowledge = KNOWLEDGE.get(student_id, KnowledgeState(student_id=student_id))
    concepts_out = []
    for cid, cm in knowledge.concepts.items():
        concept = GRAPH.get_concept(cid)
        concepts_out.append({
            "concept_id": cid,
            "name": cm.concept_name,
            "unit": cm.unit,
            "mastery_level": cm.mastery_level.name,
            "mastery_pct": round(cm.mastery_probability * 100, 1),
            "attempts": cm.attempts,
            "success_rate": round(cm.recent_success_rate * 100, 1),
            "needs_review": cm.needs_review(),
            "difficulty": concept.difficulty if concept else "medium"
        })
    concepts_out.sort(key=lambda x: x["mastery_pct"], reverse=True)
    return {"concepts": concepts_out}


@router.get("/student/{student_id}/gaps")
async def get_student_gaps(student_id: str, concept_id: str = None):
    profile = STUDENTS.get(student_id)
    if not profile:
        raise HTTPException(404, "Student not found")
    knowledge = KNOWLEDGE.get(student_id, KnowledgeState(student_id=student_id))

    if concept_id:
        gaps = ANALYZER.analyze_for_concept(concept_id, knowledge, profile)
    else:
        gaps = ANALYZER.analyze_overall(knowledge, profile)

    return {"gaps": [g.to_dict() for g in gaps[:8]]}


@router.get("/student/{student_id}/adaptation")
async def get_adaptation(student_id: str, concept_id: str = None):
    profile = STUDENTS.get(student_id)
    if not profile:
        raise HTTPException(404, "Student not found")
    knowledge = KNOWLEDGE.get(student_id, KnowledgeState(student_id=student_id))
    decision = ADAPTATION.evaluate_and_adapt(profile, knowledge, concept_id)
    return decision.to_dict()


@router.get("/teacher")
async def get_teacher_dashboard():
    profiles = list(STUDENTS.values())
    if not profiles:
        return {"message": "No students enrolled yet"}
    analytics = teacher_dash.generate_class_analytics(
        class_id="CS101",
        class_name="Data Structures 101",
        student_profiles=profiles,
        student_knowledge_states=KNOWLEDGE
    )
    return analytics.to_dict()


@router.get("/teacher/interventions")
async def get_interventions():
    interventions = []
    for sid, profile in STUDENTS.items():
        knowledge = KNOWLEDGE.get(sid, KnowledgeState(student_id=sid))
        recs = teacher_dash.get_intervention_recommendations(profile, knowledge)
        if recs:
            interventions.append({
                "student_id": sid,
                "student_name": profile.name,
                "recommendations": recs
            })
    return {"interventions": interventions}
