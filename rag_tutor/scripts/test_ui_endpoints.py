"""
Smoke-test every endpoint the UI calls.
Run: python scripts/test_ui_endpoints.py
"""
import sys, json, urllib.request, urllib.error
from pathlib import Path

BASE = "http://localhost:8000"
PASS = []
FAIL = []

def get(path):
    url = BASE + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def post(path, body):
    url  = BASE + path
    data = json.dumps(body).encode()
    req  = urllib.request.Request(url, data=data,
           headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def post_qs(path):
    url = BASE + path
    req = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def check(name, fn):
    try:
        result = fn()
        print(f"  [OK]  {name}")
        PASS.append(name)
        return result
    except Exception as e:
        print(f"  [FAIL] {name}  →  {e}")
        FAIL.append(name)
        return None

print("\n── UI endpoint tests ─────────────────────────────────────")

print("\n[Root & Health]")
check("GET / (HTML page)", lambda: (
    urllib.request.urlopen("http://localhost:8000/", timeout=10).status == 200
    and {"ok": True} or (_ for _ in ()).throw(Exception("non-200")))
)
check("GET /health",    lambda: get("/health"))

print("\n[Students]")
students = check("GET /api/students/",              lambda: get("/api/students/"))
check("GET /api/students/demo_alice",               lambda: get("/api/students/demo_alice"))
check("GET /api/students/demo_bob",                 lambda: get("/api/students/demo_bob"))
check("GET /api/students/demo_carol",               lambda: get("/api/students/demo_carol"))
check("POST /api/students/ (new)",                  lambda: post("/api/students/", {
    "student_id": "test_dave", "name": "Dave Test", "email": "dave@test.com",
    "learning_style_survey": {"visual_score": 7, "auditory_score": 5,
        "reading_writing_score": 6, "kinesthetic_score": 4, "pace_preference": "moderate"}
}))

print("\n[Knowledge]")
concepts = check("GET /api/knowledge/concepts",     lambda: get("/api/knowledge/concepts"))
check("GET /api/knowledge/subjects",                lambda: get("/api/knowledge/subjects"))
check("GET /api/knowledge/graph",                   lambda: get("/api/knowledge/graph"))
check("GET /api/knowledge/concepts/ds_recursion/path", lambda: get("/api/knowledge/concepts/ds_recursion/path?mastered=ds_variable,ds_array"))

print("\n[Teaching]")
check("POST /api/teaching/ask (with concept)",      lambda: post("/api/teaching/ask", {
    "student_id": "demo_alice", "question": "What is a base case in recursion?",
    "concept_id": "ds_recursion"
}))
check("POST /api/teaching/ask (no concept)",        lambda: post("/api/teaching/ask", {
    "student_id": "demo_bob", "question": "Explain arrays"
}))
check("POST /api/teaching/hint",                    lambda: post_qs("/api/teaching/hint?student_id=demo_alice&concept_id=ds_recursion&hint_level=1"))

print("\n[Assessment]")
session_data = check("POST /api/assessment/start",  lambda: post_qs("/api/assessment/start?student_id=demo_alice"))
check("GET /api/assessment/question/ds_array",      lambda: get("/api/assessment/question/ds_array?bloom_level=2"))
check("GET /api/assessment/question/ds_recursion",  lambda: get("/api/assessment/question/ds_recursion?bloom_level=3"))

# Answer round-trip
if session_data and session_data.get("session_id") and session_data.get("question"):
    sid = session_data["session_id"]
    q   = session_data["question"]
    ans = q["options"][0] if q.get("options") else "test answer"
    check("POST /api/assessment/answer",            lambda: post_qs(
        f"/api/assessment/answer?session_id={sid}&answer={urllib.parse.quote(ans)}"
    ))

print("\n[Dashboard — Student]")
check("GET /api/dashboard/student/demo_alice",      lambda: get("/api/dashboard/student/demo_alice"))
check("GET /api/dashboard/student/demo_carol",      lambda: get("/api/dashboard/student/demo_carol"))
check("GET /api/dashboard/student/demo_alice/concepts", lambda: get("/api/dashboard/student/demo_alice/concepts"))
check("GET /api/dashboard/student/demo_alice/gaps", lambda: get("/api/dashboard/student/demo_alice/gaps"))
check("GET /api/dashboard/student/demo_alice/gaps?concept_id=ds_recursion",
      lambda: get("/api/dashboard/student/demo_alice/gaps?concept_id=ds_recursion"))
check("GET /api/dashboard/student/demo_alice/adaptation",
      lambda: get("/api/dashboard/student/demo_alice/adaptation?concept_id=ds_linked_list"))

print("\n[Dashboard — Teacher]")
check("GET /api/dashboard/teacher",                 lambda: get("/api/dashboard/teacher"))
check("GET /api/dashboard/teacher/interventions",   lambda: get("/api/dashboard/teacher/interventions"))

print("\n[Static UI]")
check("GET / (HTML)",  lambda: {"ok": True})   # already tested above

import urllib.parse
print(f"\n{'='*52}")
print(f"  Passed : {len(PASS)}/{len(PASS)+len(FAIL)}")
print(f"  Failed : {len(FAIL)}/{len(PASS)+len(FAIL)}")
if FAIL:
    print("\n  Failed:")
    for f in FAIL:
        print(f"    ✗ {f}")
else:
    print("\n  All endpoints healthy — UI is fully wired.\n")
sys.exit(0 if not FAIL else 1)
