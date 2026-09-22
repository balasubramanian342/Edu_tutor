"""
Shared state for API routes, now backed by a real SQLite database.

Previously STUDENTS/KNOWLEDGE were plain Python dicts that reset on
every server restart, even though database/models.py + database.py
defined a full SQLAlchemy schema that nothing ever used. This version
keeps the same in-memory dicts as a fast per-request cache (so route
code barely changes) but loads them from the database at startup and
persists every write through database/repository.py, so data survives
restarts.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from student_model.student_profile import create_initial_profile
from student_model.knowledge_state import KnowledgeState, ConceptMastery
from student_model.interaction_log import InteractionLog
from knowledge_graph.domain_loader import DomainLoader
from knowledge_graph.prerequisite_mapper import PrerequisiteMapper
from gap_analysis.gap_analyzer import GapAnalyzer
from mastery.irt_engine import IRTEngine
from mastery.mastery_tracker import MasteryTracker
from mastery.adaptation_engine import AdaptationEngine
from llm.client import build_llm_client
from database import Database
from database.repository import (
    save_student, load_all_students, save_knowledge_state, load_knowledge_state,
    log_interaction as _log_interaction_row,
)

# ── LLM client (shared) ────────────────────────────────────────
# Real Gemini-backed client if GEMINI_API_KEY is set, else None —
# every consumer (ExplanationGenerator, QuestionGenerator, AutoGrader)
# already falls back to template-based generation when this is None,
# so the system works either way.
LLM_CLIENT = build_llm_client()

# ── Knowledge graph (singleton) ───────────────────────────────
GRAPH = DomainLoader.create_sample_cs_graph()
MAPPER = PrerequisiteMapper(GRAPH)
IRT = IRTEngine()
TRACKER = MasteryTracker(irt_engine=IRT)
ANALYZER = GapAnalyzer(GRAPH, MAPPER)
ADAPTATION = AdaptationEngine(TRACKER)

# ── Database ────────────────────────────────────────────────
DB = Database(f"sqlite:///{ROOT / 'rag_tutor.db'}")
DB.create_tables()

# ── Student store: student_id → StudentProfile (in-memory cache) ──
STUDENTS = {}
# ── Knowledge store: student_id → KnowledgeState (in-memory cache) ─
KNOWLEDGE = {}


def persist_student(student_id: str) -> None:
    """
    Call this after mutating STUDENTS[student_id] and/or
    KNOWLEDGE[student_id] in a route handler, so the change survives a
    restart. Cheap enough (SQLite, small tables) to call after every
    interaction rather than batching.
    """
    profile = STUDENTS.get(student_id)
    knowledge = KNOWLEDGE.get(student_id)
    if not profile:
        return
    with DB.get_session() as session:
        save_student(session, profile)
        if knowledge:
            save_knowledge_state(session, knowledge)


def persist_interaction(interaction: InteractionLog) -> None:
    """Append one row to the interaction_logs table (analytics trail)."""
    with DB.get_session() as session:
        _log_interaction_row(session, interaction)


def _load_from_db() -> bool:
    """Returns True if any students were found and loaded from the DB."""
    with DB.get_session() as session:
        profiles = load_all_students(session)
        if not profiles:
            return False
        for profile in profiles:
            STUDENTS[profile.student_id] = profile
            KNOWLEDGE[profile.student_id] = load_knowledge_state(session, profile.student_id)
    return True


def _seed():
    demos = [
        ("demo_alice", "Alice Chen",   "alice@demo.com",  "Year 2", 7, 5, 4, 6, "moderate", "Computer Science"),
        ("demo_bob",   "Bob Martinez", "bob@demo.com",    "Year 1", 4, 7, 6, 5, "fast",     "Computer Science"),
        ("demo_carol", "Carol Smith",  "carol@demo.com",  "Year 3", 8, 6, 8, 7, "slow",     "Computer Science"),
        ("demo_dan",   "Dan Okafor",   "dan@demo.com",    "Year 1", 5, 5, 6, 6, "moderate", "Electronics & Comm."),
        ("demo_eve",   "Eve Larsson",  "eve@demo.com",    "Year 2", 6, 6, 5, 5, "moderate", "Electronics & Comm."),
    ]
    for sid, name, email, grade, vis, aud, rw, kin, pace, dept in demos:
        profile = create_initial_profile(
            student_id=sid, name=name, email=email,
            learning_style_survey={
                "visual_score": vis, "auditory_score": aud,
                "reading_writing_score": rw, "kinesthetic_score": kin,
                "pace_preference": pace
            },
            department=dept
        )
        profile.grade_level = grade
        STUDENTS[sid] = profile
        ks = KnowledgeState(student_id=sid)
        KNOWLEDGE[sid] = ks

    # Give Alice some practice history on a few concepts
    _simulate_practice("demo_alice", {
        "ds_variable": [True, True, True, True, True],
        "ds_array":    [True, True, True, False, True],
        "ds_complexity":[True, False, True, True],
        "ds_linked_list":[True, False, False, True],
        "ds_stack":    [True, True, False],
    })
    # Bob knows basics only
    _simulate_practice("demo_bob", {
        "ds_variable": [True, True, False, True],
        "ds_array":    [False, True, False],
    })
    # Carol is advanced
    _simulate_practice("demo_carol", {
        "ds_variable":   [True]*6,
        "ds_array":      [True]*5,
        "ds_complexity": [True]*4,
        "ds_linked_list":[True]*5,
        "ds_stack":      [True]*4,
        "ds_queue":      [True]*4,
        "ds_recursion":  [True, True, False, True, True],
        "ds_sorting":    [True, True, False, True],
    })
    # Dan (Electronics dept) — light engagement, still building basics
    _simulate_practice("demo_dan", {
        "ds_variable": [True, False, True],
        "ds_array":    [False, True],
    })
    # Eve (Electronics dept) — moderate engagement
    _simulate_practice("demo_eve", {
        "ds_variable": [True, True, True],
        "ds_array":    [True, False, True],
        "ds_complexity": [True, True],
    })

    # Refresh overall mastery on profiles
    for sid, profile in STUDENTS.items():
        ks = KNOWLEDGE[sid]
        profile.overall_mastery = ks.get_overall_mastery()
        profile.concepts_mastered = len(ks.get_mastered_concepts())
        profile.concepts_in_progress = len([
            c for c in ks.concepts.values() if 0 < c.mastery_probability < 0.85
        ])

    # Persist the freshly seeded demo data so it survives a restart too
    with DB.get_session() as session:
        for sid in STUDENTS:
            save_student(session, STUDENTS[sid])
            save_knowledge_state(session, KNOWLEDGE[sid])


def _simulate_practice(student_id: str, concept_results: dict):
    ks = KNOWLEDGE[student_id]
    graph = GRAPH
    for concept_id, results in concept_results.items():
        concept = graph.get_concept(concept_id)
        if not concept:
            continue
        cm = ConceptMastery(
            concept_id=concept_id,
            concept_name=concept.name,
            subject=concept.subject,
            unit=concept.unit
        )
        ks.add_concept(cm)
        for correct in results:
            ks.update_concept(concept_id, correct, concept.difficulty)


# Load existing data if the DB already has students (e.g. a previous run
# or students created through the API); otherwise seed demo data once.
if not _load_from_db():
    _seed()
