"""
api/routes/department.py

Department-wide analytics — the same kind of gap/mastery data the
teacher dashboard already shows for one class, aggregated up a level
for a department head or coordinator who needs to see how an entire
department (not just one class) is doing: which concepts are weakest
across the board, which cohorts are lagging, and overall engagement.

Departments are just a free-text field on StudentProfile
(student_model/student_profile.py) — there's no separate Department
model, since for a final-year project scope a department is really
just "a named group of students" and doesn't need its own lifecycle
(create/rename/archive) to be useful here. If you outgrow that, see
FEATURES_AND_ROADMAP.md for how to promote it to a real table.
"""
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException

from api.store import STUDENTS, KNOWLEDGE, GRAPH

router = APIRouter()


def _students_in(department: str):
    return [p for p in STUDENTS.values() if (p.department or "Unassigned") == department]


@router.get("/")
async def list_departments():
    """All departments with a headcount and their average mastery, for a top-level picker."""
    by_dept = defaultdict(list)
    for p in STUDENTS.values():
        by_dept[p.department or "Unassigned"].append(p)

    result = []
    for dept, profiles in sorted(by_dept.items()):
        avg_mastery = sum(p.overall_mastery for p in profiles) / len(profiles) if profiles else 0.0
        result.append({
            "department": dept,
            "student_count": len(profiles),
            "avg_mastery": round(avg_mastery * 100, 1),
        })
    return {"departments": result}


@router.get("/{department}/overview")
async def department_overview(department: str):
    """
    Headline stats for one department: enrollment, average mastery,
    engagement (sessions/interactions), and mastery distribution
    (how many students are struggling vs. proficient vs. mastered).
    """
    profiles = _students_in(department)
    if not profiles:
        raise HTTPException(404, f"No students found in department '{department}'")

    total_sessions = sum(p.total_sessions for p in profiles)
    avg_mastery = sum(p.overall_mastery for p in profiles) / len(profiles)

    distribution = {"struggling": 0, "developing": 0, "proficient": 0, "mastered": 0}
    for p in profiles:
        m = p.overall_mastery
        if m < 0.3:
            distribution["struggling"] += 1
        elif m < 0.6:
            distribution["developing"] += 1
        elif m < 0.85:
            distribution["proficient"] += 1
        else:
            distribution["mastered"] += 1

    return {
        "department": department,
        "student_count": len(profiles),
        "avg_mastery": round(avg_mastery * 100, 1),
        "total_sessions": total_sessions,
        "avg_sessions_per_student": round(total_sessions / len(profiles), 1),
        "mastery_distribution": distribution,
    }


@router.get("/{department}/concepts")
async def department_concept_breakdown(department: str):
    """
    Per-concept average mastery across every student in the department —
    this is the "which topics is the whole department weak on" view,
    the department-level analogue of the teacher dashboard's per-class
    concept breakdown, and directly useful for deciding what to re-teach
    or which course materials need improving.
    """
    profiles = _students_in(department)
    if not profiles:
        raise HTTPException(404, f"No students found in department '{department}'")

    concept_scores = defaultdict(list)
    for p in profiles:
        ks = KNOWLEDGE.get(p.student_id)
        if not ks:
            continue
        for cm in ks.concepts.values():
            concept_scores[cm.concept_id].append(cm.mastery_probability)

    breakdown = []
    for concept_id, scores in concept_scores.items():
        concept = GRAPH.get_concept(concept_id)
        breakdown.append({
            "concept_id": concept_id,
            "concept_name": concept.name if concept else concept_id,
            "subject": concept.subject if concept else None,
            "avg_mastery": round(sum(scores) / len(scores) * 100, 1),
            "students_attempted": len(scores),
        })
    breakdown.sort(key=lambda c: c["avg_mastery"])  # weakest first — the actionable view
    return {"department": department, "concepts": breakdown}


@router.get("/{department}/students")
async def department_students(department: str):
    """Roster with each student's mastery, for drilling from department -> individual."""
    profiles = _students_in(department)
    if not profiles:
        raise HTTPException(404, f"No students found in department '{department}'")

    return {
        "department": department,
        "students": [
            {
                "student_id": p.student_id,
                "name": p.name,
                "grade_level": p.grade_level,
                "overall_mastery": round(p.overall_mastery * 100, 1),
                "concepts_mastered": p.concepts_mastered,
                "total_sessions": p.total_sessions,
                "last_active": p.last_active.isoformat() if p.last_active else None,
            }
            for p in sorted(profiles, key=lambda p: p.overall_mastery)
        ]
    }
