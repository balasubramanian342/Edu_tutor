"""
End-to-end smoke test.
Exercises every major module without needing any data files or an LLM.
Run from rag_tutor/ directory:  python scripts/smoke_test.py
"""

import sys
import os
import traceback

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = []
FAIL = []

def section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")

def ok(msg):
    print(f"  [OK]  {msg}")
    PASS.append(msg)

def fail(msg, exc=None):
    print(f"  [FAIL] {msg}")
    if exc:
        print(f"         {exc}")
    FAIL.append(msg)

# ── 1. Student Modeling ─────────────────────────────────────
section("1. Student Modeling")
try:
    from student_model.student_profile import (
        create_initial_profile, LearningStyle, PacePreference
    )
    profile = create_initial_profile(
        student_id="s001", name="Alice", email="alice@test.com",
        learning_style_survey={
            "visual_score": 8, "auditory_score": 5,
            "reading_writing_score": 6, "kinesthetic_score": 4,
            "pace_preference": "moderate"
        }
    )
    assert profile.student_id == "s001"
    assert profile.primary_learning_style == LearningStyle.VISUAL
    ok("StudentProfile created with learning style survey")
except Exception as e:
    fail("StudentProfile", e)

try:
    from student_model.knowledge_state import KnowledgeState, ConceptMastery, MasteryLevel
    ks = KnowledgeState(student_id="s001")
    cm = ConceptMastery(concept_id="ds_array", concept_name="Arrays",
                        subject="Data Structures", unit="Unit 1")
    ks.add_concept(cm)

    # Simulate 3 correct, 1 wrong
    for correct in [True, True, True, False]:
        ks.update_concept("ds_array", correct, "medium")

    updated = ks.get_concept("ds_array")
    assert updated.attempts == 4
    assert updated.correct_attempts == 3
    assert updated.mastery_probability > 0
    ok(f"KnowledgeState BKT update OK (mastery={updated.mastery_probability:.3f})")
except Exception as e:
    fail("KnowledgeState BKT", e)

try:
    from student_model.interaction_log import InteractionLog, InteractionType
    log = InteractionLog(
        student_id="s001",
        interaction_type=InteractionType.QUESTION_ASKED,
        concept_id="ds_array",
        student_input="What is an array?",
        was_correct=True
    )
    d = log.to_dict()
    assert d["interaction_type"] == "question_asked"
    ok("InteractionLog serialization OK")
except Exception as e:
    fail("InteractionLog", e)

# ── 2. Knowledge Graph ──────────────────────────────────────
section("2. Knowledge Graph")
try:
    from knowledge_graph.domain_loader import DomainLoader
    graph = DomainLoader.create_sample_cs_graph()
    assert len(graph.concepts) == 9
    ok(f"Sample CS graph loaded ({len(graph.concepts)} concepts)")
except Exception as e:
    fail("DomainLoader.create_sample_cs_graph", e)
    graph = None

try:
    prereqs = graph.get_all_prerequisites("ds_recursion")
    names = [c.name for c in prereqs]
    assert any("Stack" in n for n in names), f"Expected Stack in prereqs, got {names}"
    ok(f"Prerequisite traversal OK (ds_recursion ← {names})")
except Exception as e:
    fail("Prerequisite traversal", e)

try:
    from knowledge_graph.prerequisite_mapper import PrerequisiteMapper
    mapper = PrerequisiteMapper(graph)
    mastered = {"ds_variable", "ds_array", "ds_complexity"}
    path = mapper.find_path_to_concept("ds_tree", mastered)
    assert path.target_concept.concept_id == "ds_tree"
    assert len(path.missing_prerequisites) > 0
    ok(f"Learning path to ds_tree: {len(path.missing_prerequisites)} steps, "
       f"~{path.estimated_time_minutes} min")
except Exception as e:
    fail("PrerequisiteMapper", e)

try:
    issues = DomainLoader.validate_graph(graph)
    assert issues["cycles"] == [], f"Unexpected cycles: {issues['cycles']}"
    ok("Graph validation passed (no cycles)")
except Exception as e:
    fail("Graph validation", e)

# ── 3. Gap Analysis ─────────────────────────────────────────
section("3. Gap Analysis")
try:
    from gap_analysis.gap_analyzer import GapAnalyzer
    from student_model.knowledge_state import KnowledgeState, ConceptMastery, MasteryLevel

    ks2 = KnowledgeState(student_id="s001")
    # Student only knows variables
    known = ConceptMastery(concept_id="ds_variable", concept_name="Variables",
                           subject="Data Structures", unit="Unit 1")
    for _ in range(5):
        known.update_after_attempt(True, "easy")
    ks2.add_concept(known)

    analyzer = GapAnalyzer(graph, mapper)
    gaps = analyzer.analyze_for_concept("ds_recursion", ks2, profile)
    assert len(gaps) > 0
    ok(f"Gap analysis found {len(gaps)} gaps for ds_recursion")
    ok(f"  Top gap: [{gaps[0].gap_type.value}] {gaps[0].concept.name} "
       f"(severity={gaps[0].severity:.2f})")
except Exception as e:
    fail("GapAnalyzer", e)
    traceback.print_exc()

try:
    from gap_analysis.remediation_planner import RemediationPlanner
    planner = RemediationPlanner(graph, mapper)
    plan = planner.create_plan("ds_recursion", gaps, profile, ks2)
    assert len(plan.steps) > 0
    ok(f"Remediation plan: {len(plan.steps)} steps, "
       f"{plan.total_duration_minutes} min, priority={plan.priority}")
except Exception as e:
    fail("RemediationPlanner", e)

# ── 4. Assessment ───────────────────────────────────────────
section("4. Assessment")
try:
    from assessment.question_generator import QuestionGenerator, QuestionType
    qgen = QuestionGenerator()
    concept_node = graph.get_concept("ds_array")
    q = qgen.generate_for_concept(concept_node, bloom_level=2,
                                  question_type=QuestionType.MULTIPLE_CHOICE)
    assert q.prompt
    assert q.options is not None
    ok(f"QuestionGenerator: '{q.prompt[:60]}...'")
except Exception as e:
    fail("QuestionGenerator", e)

try:
    from assessment.grader import AutoGrader
    grader = AutoGrader()

    # Grade a MC question
    result = grader.grade(q, q.correct_answer)
    assert result.is_correct
    ok(f"AutoGrader correct answer: {result.points_earned}/{result.points_possible} pts")

    result_wrong = grader.grade(q, "definitely wrong answer xyz")
    assert not result_wrong.is_correct
    ok(f"AutoGrader wrong answer: {result_wrong.points_earned}/{result_wrong.points_possible} pts")
except Exception as e:
    fail("AutoGrader", e)

try:
    from assessment.adaptive_test import AdaptiveTest, TestSession
    test = AdaptiveTest(qgen, grader, graph)
    session = test.start_diagnostic_test(profile, subject="Data Structures", max_questions=5)
    assert session.student_id == "s001"

    # Run 3 question cycles
    for i in range(3):
        next_q = test.get_next_question(session, profile)
        if next_q:
            test.submit_answer(session, next_q, next_q.correct_answer)

    ks_fresh = KnowledgeState(student_id="s001")
    result = test.end_test(session, ks_fresh)
    ok(f"AdaptiveTest: {result.total_questions} Qs, "
       f"{result.correct_answers} correct, "
       f"score={result.score_percentage:.0f}%, "
       f"ability={result.ability_estimate:.2f}")
except Exception as e:
    fail("AdaptiveTest", e)
    traceback.print_exc()

# ── 5. Mastery Tracking ─────────────────────────────────────
section("5. Mastery Tracking")
try:
    from mastery.irt_engine import IRTEngine, ItemParameters
    irt = IRTEngine()
    params = ItemParameters.from_difficulty_level("medium")
    prob = irt.calculate_probability(0.5, params)
    assert 0 < prob < 1
    ok(f"IRT 3PL: ability=0.5, difficulty=medium → P(correct)={prob:.3f}")

    ability = irt.update_ability(profile, "ds_array", was_correct=True, difficulty="medium")
    ok(f"Ability update after correct answer: theta={ability:.3f}")
except Exception as e:
    fail("IRTEngine", e)

try:
    from mastery.mastery_tracker import MasteryTracker
    from assessment.grader import GradingResult

    tracker = MasteryTracker(irt_engine=irt)
    ks3 = KnowledgeState(student_id="s001")
    cm3 = ConceptMastery(concept_id="ds_array", concept_name="Arrays",
                         subject="Data Structures", unit="Unit 1")
    ks3.add_concept(cm3)

    gr = GradingResult(question_id="Q001", is_correct=True,
                       points_earned=1, points_possible=1, feedback="Correct!")
    update = tracker.update_from_assessment(ks3, profile, gr, "ds_array", "medium")
    assert update.new_mastery > update.previous_mastery
    ok(f"MasteryTracker: {update.previous_mastery:.3f} → {update.new_mastery:.3f}")
except Exception as e:
    fail("MasteryTracker", e)

try:
    from mastery.adaptation_engine import AdaptationEngine
    engine = AdaptationEngine(tracker)
    ks3.update_concept("ds_array", False, "medium")
    ks3.update_concept("ds_array", False, "medium")
    ks3.update_concept("ds_array", False, "medium")

    decision = engine.evaluate_and_adapt(profile, ks3, "ds_array")
    ok(f"AdaptationEngine trigger: {decision.trigger.value}, "
       f"difficulty={decision.adjust_difficulty}")
except Exception as e:
    fail("AdaptationEngine", e)

# ── 6. Dashboard ────────────────────────────────────────────
section("6. Dashboard")
try:
    from dashboard.student_dashboard import StudentDashboard
    student_dash = StudentDashboard(graph, analyzer, tracker)
    report = student_dash.generate_report(profile, ks3)
    assert report.student_id == "s001"
    ok(f"StudentDashboard report: mastery={report.overall_mastery:.2f}, "
       f"sessions_this_week={report.sessions_this_week}")
except Exception as e:
    fail("StudentDashboard", e)

try:
    from dashboard.teacher_dashboard import TeacherDashboard
    teacher_dash = TeacherDashboard(graph)
    analytics = teacher_dash.generate_class_analytics(
        class_id="CS101", class_name="Data Structures 101",
        student_profiles=[profile],
        student_knowledge_states={"s001": ks3}
    )
    assert analytics.total_students == 1
    ok(f"TeacherDashboard: {analytics.total_students} student, "
       f"avg_mastery={analytics.average_mastery:.2f}, "
       f"trend={analytics.mastery_trend}")
except Exception as e:
    fail("TeacherDashboard", e)

try:
    from dashboard.visualizations import ProgressVisualizer
    pie = ProgressVisualizer.generate_progress_pie(ks3)
    assert pie["type"] == "pie_chart"
    chartjs = ProgressVisualizer.export_for_charting_library(pie, "chartjs")
    assert chartjs["type"] == "pie"
    ok("ProgressVisualizer: pie chart + Chart.js export OK")
except Exception as e:
    fail("ProgressVisualizer", e)

# ── 7. Database ─────────────────────────────────────────────
section("7. Database (SQLite in-memory)")
try:
    from database.database import Database
    db = Database("sqlite:///:memory:")
    db.create_tables()
    ok("Database tables created in-memory")

    from database.models import Student, LearningStyleEnum, PacePreferenceEnum
    with db.get_session() as session:
        student_row = Student(
            id="s001", name="Alice", email="alice@test.com",
            primary_learning_style=LearningStyleEnum.VISUAL,
            pace_preference=PacePreferenceEnum.MODERATE,
            cognitive_profile={"working_memory": 0.7, "abstract_reasoning": 0.6,
                               "processing_speed": 0.5, "metacognition": 0.5,
                               "growth_mindset": 0.8}
        )
        session.add(student_row)

    with db.get_session() as session:
        fetched = session.get(Student, "s001")
        assert fetched.name == "Alice"
    ok("Student row insert + fetch OK")
except Exception as e:
    fail("Database ORM", e)
    traceback.print_exc()

# ── Summary ─────────────────────────────────────────────────
section("SUMMARY")
total = len(PASS) + len(FAIL)
print(f"\n  Passed : {len(PASS)}/{total}")
print(f"  Failed : {len(FAIL)}/{total}")
if FAIL:
    print("\n  Failed tests:")
    for f in FAIL:
        print(f"    - {f}")
    print()
    sys.exit(1)
else:
    print("\n  All tests passed. System is working correctly.\n")
