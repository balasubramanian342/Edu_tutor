"""Student Management Routes — backed by real in-memory store."""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
import io
import re
import pandas as pd

from student_model.student_profile import create_initial_profile, classify_marks, LearningStyle, PacePreference
from student_model.knowledge_state import KnowledgeState
from api.store import STUDENTS, KNOWLEDGE, persist_student

router = APIRouter()


class StudentCreate(BaseModel):
    student_id: str
    name: str
    email: str
    grade_level: Optional[str] = None
    institution: Optional[str] = None
    department: Optional[str] = None
    class_name: Optional[str] = None
    exam_marks: Optional[float] = None
    attendance_percentage: Optional[float] = None
    learning_style_survey: Optional[Dict] = None


class ClassRosterImport(BaseModel):
    institution: Optional[str] = None
    department: Optional[str] = None
    class_name: Optional[str] = None
    students: list[StudentCreate]


@router.post("/")
async def create_student(data: StudentCreate):
    if data.student_id in STUDENTS:
        raise HTTPException(400, "Student already exists")
    profile = create_initial_profile(
        student_id=data.student_id,
        name=data.name,
        email=data.email,
        learning_style_survey=data.learning_style_survey,
        department=data.department,
        class_name=data.class_name,
        institution=data.institution,
        exam_marks=data.exam_marks
    )
    if data.grade_level:
        profile.grade_level = data.grade_level
    if data.class_name:
        profile.class_name = data.class_name
    if data.exam_marks is not None:
        profile.exam_marks = data.exam_marks
    if data.attendance_percentage is not None:
        profile.attendance_percentage = data.attendance_percentage
    profile.classification = classify_marks(profile.exam_marks)
    STUDENTS[data.student_id] = profile
    KNOWLEDGE[data.student_id] = KnowledgeState(student_id=data.student_id)
    persist_student(data.student_id)
    return {
        "student_id": data.student_id,
        "name": data.name,
        "message": "Student created",
        "created_at": datetime.utcnow().isoformat(),
        "class_name": profile.class_name,
        "exam_marks": profile.exam_marks,
        "classification": profile.classification,
    }


@router.post("/class-roster")
async def import_class_roster(data: ClassRosterImport):
    created = []
    for item in data.students:
        if item.student_id in STUDENTS:
            continue
        profile = create_initial_profile(
            student_id=item.student_id,
            name=item.name,
            email=item.email,
            learning_style_survey=item.learning_style_survey,
            department=data.department or item.department,
            class_name=data.class_name or item.class_name,
            exam_marks=item.exam_marks,
            institution=item.institution,
        )
        if item.grade_level:
            profile.grade_level = item.grade_level
        if item.class_name:
            profile.class_name = item.class_name
        if item.exam_marks is not None:
            profile.exam_marks = item.exam_marks
        if item.attendance_percentage is not None:
            profile.attendance_percentage = item.attendance_percentage
        profile.classification = classify_marks(profile.exam_marks)
        STUDENTS[item.student_id] = profile
        KNOWLEDGE[item.student_id] = KnowledgeState(student_id=item.student_id)
        persist_student(item.student_id)
        created.append({
            "student_id": item.student_id,
            "name": item.name,
            "class_name": profile.class_name,
            "exam_marks": profile.exam_marks,
            "classification": profile.classification,
        })
    return {"class_name": data.class_name, "created": created}


@router.get("/")
async def list_students():
    return [
        {
            "student_id": p.student_id,
            "name": p.name,
            "email": p.email,
            "institution": getattr(p, "institution", None),
            "department": p.department,
            "class_name": p.class_name,
            "exam_marks": p.exam_marks,
            "attendance_percentage": getattr(p, "attendance_percentage", None),
            "classification": p.classification,
            "overall_mastery": round(p.overall_mastery * 100),
            "concepts_mastered": p.concepts_mastered,
            "last_active": p.last_active.isoformat() if p.last_active else None
        }
        for p in STUDENTS.values()
    ]


@router.get("/{student_id}")
async def get_student(student_id: str):
    profile = STUDENTS.get(student_id)
    if not profile:
        raise HTTPException(404, "Student not found")
    knowledge = KNOWLEDGE.get(student_id, KnowledgeState(student_id=student_id))
    return {
        "student_id": profile.student_id,
        "name": profile.name,
        "email": profile.email,
        "institution": getattr(profile, "institution", None),
        "grade_level": profile.grade_level,
        "department": profile.department,
        "class_name": getattr(profile, 'class_name', None),
        "exam_marks": getattr(profile, 'exam_marks', None),
        "attendance_percentage": getattr(profile, "attendance_percentage", None),
        "classification": getattr(profile, 'classification', classify_marks(profile.exam_marks)),
        "learning_style": profile.primary_learning_style.value,
        "pace": profile.pace_preference.value,
        "overall_mastery": round(profile.overall_mastery * 100, 1),
        "concepts_mastered": profile.concepts_mastered,
        "concepts_in_progress": profile.concepts_in_progress,
        "total_sessions": profile.total_sessions,
        "total_time_minutes": profile.total_time_minutes,
        "cognitive_profile": profile.cognitive_profile.to_dict(),
        "last_active": profile.last_active.isoformat() if profile.last_active else None
    }


# ── Bulk institution dataset import ───────────────────────────
def _normalise_column(name: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower())
    return name.strip("_")


def _first_value(row, *names):
    for name in names:
        if name in row.index:
            value = row[name]
            if pd.notna(value) and str(value).strip():
                return value
    return None


def _to_float(value):
    if value is None:
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


@router.post("/import-dataset")
async def import_student_dataset(
    file: UploadFile = File(...),
    institution: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    class_name: Optional[str] = Form(None),
):
    """
    Import a college/institution student dataset.

    Supported formats: CSV and XLSX/XLS.
    Required columns (case-insensitive): student_id, name, email.
    Common optional columns: grade_level, department, class_name,
    institution, exam_marks/marks/average_marks, attendance_percentage/
    attendance/attendance_percent.
    """
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(
            400,
            "Unsupported dataset. Please upload CSV, XLSX or XLS."
        )

    raw = await file.read()
    try:
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(raw))
        else:
            df = pd.read_excel(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(400, f"Could not read dataset: {exc}") from exc

    if df.empty:
        raise HTTPException(400, "The uploaded dataset is empty.")

    df.columns = [_normalise_column(c) for c in df.columns]

    # Friendly aliases used by common college exports.
    aliases = {
        "studentid": "student_id",
        "student_no": "student_id",
        "roll_no": "student_id",
        "roll_number": "student_id",
        "register_no": "student_id",
        "registration_number": "student_id",
        "full_name": "name",
        "student_name": "name",
        "email_id": "email",
        "mail": "email",
        "marks": "exam_marks",
        "average_marks": "exam_marks",
        "overall_marks": "exam_marks",
        "attendance": "attendance_percentage",
        "attendance_percent": "attendance_percentage",
        "attendance_pct": "attendance_percentage",
        "year": "grade_level",
        "course": "department",
        "section": "class_name",
        "college": "institution",
        "college_name": "institution",
    }
    df = df.rename(columns={c: aliases.get(c, c) for c in df.columns})

    required = {"student_id", "name", "email"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise HTTPException(
            400,
            "Missing required columns: " + ", ".join(missing) +
            ". Required: student_id, name, email."
        )

    created, skipped, errors = [], [], []

    for idx, row in df.iterrows():
        sid = str(row["student_id"]).strip()
        name = str(row["name"]).strip()
        email = str(row["email"]).strip()

        if not sid or sid.lower() == "nan" or not name or name.lower() == "nan":
            errors.append({"row": int(idx) + 2, "error": "student_id and name are required"})
            continue
        if sid in STUDENTS:
            skipped.append({"student_id": sid, "reason": "already exists"})
            continue

        row_department = _first_value(row, "department") or department
        row_class = _first_value(row, "class_name") or class_name
        row_institution = _first_value(row, "institution") or institution
        marks = _to_float(_first_value(row, "exam_marks"))
        attendance = _to_float(_first_value(row, "attendance_percentage"))

        # Convert an attendance fraction such as 0.82 to 82 only when it
        # clearly looks like a fraction.
        if attendance is not None and 0 <= attendance <= 1:
            attendance *= 100

        survey = {
            "visual_score": _to_float(_first_value(row, "visual_score")) or 5,
            "auditory_score": _to_float(_first_value(row, "auditory_score")) or 5,
            "reading_writing_score": _to_float(_first_value(row, "reading_writing_score")) or 5,
            "kinesthetic_score": _to_float(_first_value(row, "kinesthetic_score")) or 5,
            "pace_preference": str(_first_value(row, "pace_preference") or "moderate").lower(),
        }

        try:
            profile = create_initial_profile(
                student_id=sid,
                name=name,
                email=email,
                learning_style_survey=survey,
                department=row_department,
                class_name=row_class,
                exam_marks=marks,
                institution=row_institution,
            )
            grade = _first_value(row, "grade_level")
            if grade is not None:
                profile.grade_level = str(grade)
            if attendance is not None:
                profile.attendance_percentage = max(0.0, min(100.0, attendance))

            profile.classification = classify_marks(profile.exam_marks)
            STUDENTS[sid] = profile
            KNOWLEDGE[sid] = KnowledgeState(student_id=sid)
            persist_student(sid)

            created.append({
                "student_id": sid,
                "name": name,
                "classification": profile.classification,
                "exam_marks": marks,
                "attendance_percentage": getattr(profile, "attendance_percentage", None),
            })
        except Exception as exc:
            errors.append({"row": int(idx) + 2, "student_id": sid, "error": str(exc)})

    return {
        "message": "Institution dataset processed",
        "filename": filename,
        "rows_received": len(df),
        "created_count": len(created),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "created": created,
        "skipped": skipped[:50],
        "errors": errors[:50],
    }
