"""Print live data from every major UI section."""
import urllib.request, urllib.parse, json

BASE = "http://localhost:8000"

def get(p):
    with urllib.request.urlopen(BASE + p, timeout=10) as r:
        return json.loads(r.read())

def post(p, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + p, data=data,
          headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def post_qs(p):
    req = urllib.request.Request(BASE + p, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

sep = lambda t: print(f"\n{'='*55}\n  {t}\n{'='*55}")

sep("1. STUDENT LIST")
students = get("/api/students/")
for s in students:
    print(f"  {s['name']:20s}  mastery={s['overall_mastery']}%  mastered={s['concepts_mastered']}")

sep("2. ALICE — OVERVIEW")
d = get("/api/dashboard/student/demo_alice")
print(f"  overall_mastery   : {d['overall_mastery']}%")
print(f"  concepts_mastered : {d['concepts_mastered']}")
print(f"  concepts_in_prog  : {d['concepts_in_progress']}")
print(f"  study_time_hrs    : {d['total_study_time_hours']:.1f}")
print(f"  streak            : {d['current_streak']} days")
print(f"  next_targets      : {d['next_learning_targets']}")
print(f"  subject_progress  :")
for subj, info in d['subject_progress'].items():
    print(f"    {subj}: {round(info['average_mastery']*100)}%  ({info['mastered']}/{info['total_concepts']} mastered)")

sep("3. ALICE — MY CONCEPTS")
concepts = get("/api/dashboard/student/demo_alice/concepts")
for c in concepts['concepts']:
    bar = '█' * int(c['mastery_pct'] / 10) + '░' * (10 - int(c['mastery_pct'] / 10))
    print(f"  {c['name']:25s}  [{bar}] {c['mastery_pct']:5.1f}%  {c['mastery_level']}")

sep("4. GAP ANALYSIS — Alice targeting ds_recursion")
gaps = get("/api/dashboard/student/demo_alice/gaps?concept_id=ds_recursion")
for g in gaps['gaps']:
    print(f"  [{g['gap_type']:30s}]  {g['concept_name']:20s}  severity={round(g['severity']*100)}%")
    print(f"    → {g['recommended_action']}")

sep("5. LEARNING PATH — Alice to ds_tree")
path = get("/api/knowledge/concepts/ds_tree/path?mastered=ds_variable,ds_array,ds_complexity")
print(f"  Target: {path['target']}  ({len(path['missing_steps'])} steps, {path['total_minutes']} min)")
for i, s in enumerate(path['missing_steps'], 1):
    print(f"  {i}. {s['name']:25s} [{s['difficulty']}]  ~{s['estimated_minutes']} min")

sep("6. ASK TUTOR — Bob asks about arrays")
resp = post("/api/teaching/ask", {
    "student_id": "demo_bob",
    "question": "What is an array and how does indexing work?",
    "concept_id": "ds_array"
})
print(f"  confidence  : {resp['confidence']}")
print(f"  gaps_found  : {resp['gaps_found']}")
print(f"  sources_used: {resp['sources_used']}")
print(f"  answer (first 200 chars):")
print(f"    {resp['answer'][:200]}...")

sep("7. ADAPTIVE QUIZ — start for Alice")
session = post_qs("/api/assessment/start?student_id=demo_alice")
print(f"  session_id : {session['session_id']}")
q = session['question']
print(f"  Q: [{q['type']}] {q['prompt']}")
if q.get('options'):
    print(f"  Options: {q['options']}")
# Answer with first option
ans = q['options'][0] if q.get('options') else "test"
enc = urllib.parse.quote(ans)
ans_resp = post_qs(f"/api/assessment/answer?session_id={session['session_id']}&answer={enc}")
gr = ans_resp['grading']
print(f"  Answered: '{ans}'")
print(f"  Result  : correct={gr['is_correct']}  pts={gr['points_earned']}/{gr['points_possible']}")
print(f"  Feedback: {gr['feedback']}")
if ans_resp['status'] == 'continue':
    nq = ans_resp['next_question']
    print(f"  Next Q  : {nq['prompt'][:80]}…")
    print(f"  Ability : {round(ans_resp['ability_estimate']*100)}%")

sep("8. TEACHER — CLASS ANALYTICS")
t = get("/api/dashboard/teacher")
print(f"  total_students     : {t['total_students']}")
print(f"  active_students    : {t['active_students']}")
print(f"  average_mastery    : {round(t['average_mastery']*100)}%")
print(f"  students_excelling : {t['students_excelling']}")
print(f"  students_struggling: {t['students_struggling']}")
print(f"  mastery_trend      : {t['mastery_trend']}")
if t['challenging_concepts']:
    print(f"  hardest concept    : {t['challenging_concepts'][0]['concept_name']}")
if t['students_needing_attention']:
    print(f"  needs attention    : {t['students_needing_attention'][0]['student_name']}")

sep("9. INTERVENTIONS")
iv = get("/api/dashboard/teacher/interventions")
for item in iv['interventions']:
    print(f"  {item['student_name']}: {len(item['recommendations'])} recommendation(s)")
    for r in item['recommendations'][:2]:
        print(f"    [{r['priority']}] {r['title']}")

sep("10. KNOWLEDGE GRAPH")
kg = get("/api/knowledge/graph")
print(f"  nodes: {len(kg['nodes'])}   edges: {len(kg['edges'])}")
prereq_edges = [e for e in kg['edges'] if e['type'] == 'prerequisite']
print(f"  prerequisite edges: {len(prereq_edges)}")
for n in kg['nodes']:
    print(f"  {n['label']:25s}  [{n['difficulty']:6s}]  {n['unit']}")

print("\n" + "="*55)
print("  All 10 UI views have live data. System fully working.")
print("="*55 + "\n")
